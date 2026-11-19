#!/usr/bin/env python3
"""Offline SQLite + authorized-file backup verification. Standard library only.

Run only with an operator-selected database and controlled encrypted storage.
This is a full sensitive backup, never a public business export or web API.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import getpass
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import UUID

MEDIA_SUFFIXES = {'.mp4','.webm','.mov','.avi','.mkv','.wav','.png','.jpg','.jpeg','.webp','.pdf'}
TERMINAL = {'SUCCESS','PARTIAL_SUCCESS','NO_VALID_SEGMENTS','FAILED','CANCELLED','DELETED'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024), b''):result.update(block)
    return result.hexdigest()


@contextmanager
def readonly(path):
    path=Path(path).resolve(strict=True)
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        yield db
    finally:
        db.close()


def private_dir(path):
    path=Path(path)
    # A new destination is mandatory. Never overwrite a database or backup.
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(path,0o700)
    return path.resolve()


def private_write(path,content):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'wb') as target:
        target.write(content);target.flush();os.fsync(target.fileno())
    os.chmod(path,0o600)


def safe_path(root,relative):
    relative=str(relative).replace('\\','/')
    parts=PurePosixPath(relative).parts
    if not relative or PurePosixPath(relative).is_absolute() or ':' in relative or any(p in ('..','.env') or p.startswith('.env.') for p in parts):
        raise ValueError('Unsafe attachment path')
    root=Path(root).resolve(strict=True)
    candidate=root.joinpath(*parts)
    # Reject symlinks even when their target happens to remain inside the root.
    current=root
    for part in parts:
        current=current/part
        if current.is_symlink():raise ValueError('Symlink attachment excluded')
    resolved=candidate.resolve()
    if not resolved.is_relative_to(root):raise ValueError('Attachment escapes root')
    return resolved


def db_metadata(db):
    if [row[0] for row in db.execute('PRAGMA integrity_check')] != ['ok']:
        raise ValueError('SQLite integrity check failed')
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise ValueError('SQLite foreign-key check failed')
    schema=[tuple(row) for row in db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
    names=[row[1] for row in schema if row[0]=='table']
    counts={}
    columns={}
    for name in names:
        quoted='"'+name.replace('"','""')+'"'
        counts[name]=db.execute('SELECT count(*) FROM '+quoted).fetchone()[0]
        columns[name]=[{'name':r[1],'type':r[2],'notnull':r[3],'pk':r[5]} for r in db.execute('PRAGMA table_info('+quoted+')')]
    versions=[r[0] for r in db.execute('SELECT version_num FROM alembic_version ORDER BY version_num')] if 'alembic_version' in names else []
    return {'schema_sha256':hashlib.sha256(canonical(schema)).hexdigest(),'columns':columns,'counts':counts,'migration_versions':versions}


def table_rows(db,name,tables):
    return [dict(row) for row in db.execute('SELECT * FROM "'+name+'"')] if name in tables else []


def stamp(raw):
    value=datetime.fromisoformat(raw.replace('Z','+00:00'))
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def select_attachments(db,roots,now):
    """Explicit DB references only: no recursive upload/config/secret scanning."""
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'patients' not in tables:raise ValueError('Not a supported patient database')
    alive={p['id'] for p in table_rows(db,'patients',tables) if not p.get('is_deleted')}
    jobs=table_rows(db,'mobile_face_jobs',tables)
    recordings=table_rows(db,'face_recordings',tables)
    blocked_ids=set();blocked_jobs=set();excluded=[];candidates=[]
    def exclude(kind,identifier,reason):excluded.append({'kind':kind,'id':identifier,'reason':reason})
    for row in recordings:
        data=json.loads(row['data_json'])
        expiry=min(stamp(row['created_at'])+timedelta(days=7),stamp(row['updated_at'])+timedelta(hours=24)) if row['status'] in TERMINAL else stamp(row['created_at'])+timedelta(hours=24 if row['status']=='UPLOADING' else 168)
        if row['patient_id'] not in alive or row['status'] in ('CANCELLED','DELETED') or data.get('media_deleted') or now>=expiry or not data.get('upload_complete'):
            blocked_ids.add(row['id']);blocked_jobs.update(s.get('job_id') for s in data.get('segments',[]) if isinstance(s,dict))
            exclude('training_video',row['id'],'deleted, expired, inactive patient or incomplete')
            continue
        for file in data.get('manifest',{}).get('files',[]):
            recording_id,file_id=str(UUID(row['id'])),str(UUID(file['file_id']))
            candidates.append(('training_video',recording_id+':'+file_id,'uploads',f'training-face/{recording_id}/{file_id}/video.mp4',file.get('sha256')))
    blocked_sessions={j['assessment_session_id'] for j in jobs if j['id'] in blocked_jobs and j.get('assessment_session_id')}
    for row in table_rows(db,'media_files',tables):
        if row['patient_id'] not in alive or row.get('assessment_session_id') in blocked_sessions:
            exclude('media_file',row['id'],'inactive patient or deleted training media');continue
        candidates.append(('media_file',row['id'],'uploads',row['stored_path'],row.get('sha256')))
    for row in jobs:
        raw=row.get('stored_path');parts=Path(raw).parts if raw else ()
        expired=row['status'] in ('REVIEW_REQUIRED','PENDING') and stamp(row['created_at'])<now-timedelta(hours=24)
        blocked=len(parts)>1 and parts[0]=='training-face' and parts[1] in blocked_ids
        if row['patient_id'] not in alive or row['id'] in blocked_jobs or blocked or expired or row['status'] in ('DELETED','CANCELLED'):
            exclude('mobile_face_job',row['id'],'inactive, deleted or expired');continue
        if raw:candidates.append(('mobile_face_job',row['id'],'uploads',raw,None))
    assessments={r['id'] for r in table_rows(db,'assessment_sessions',tables) if r['patient_id'] in alive}
    for row in table_rows(db,'finger_tapping_results',tables):
        if row['assessment_session_id'] in assessments and row.get('raw_timeseries_path'):
            raw=Path(row['raw_timeseries_path'])
            if raw.is_absolute():
                try:raw=raw.relative_to(roots['outputs'])
                except ValueError:exclude('tapping_timeseries',row['id'],'outside controlled root');continue
            candidates.append(('tapping_timeseries',row['id'],'outputs',raw.as_posix(),None))
    # Private UUID job snapshots are the only allowed JSON files.
    job_root=roots.get('outputs')
    if job_root and (job_root/'jobs').is_dir() and not (job_root/'jobs').is_symlink():
        for path in (job_root/'jobs').glob('*.json'):
            try:
                identifier=str(UUID(path.stem))
                safe=safe_path(job_root,'jobs/'+path.name)
                data=json.loads(safe.read_text(encoding='utf-8'))
                if path.stem==identifier and data.get('job_id')==identifier and data.get('patient_id') in alive:
                    candidates.append(('job_metadata',identifier,'outputs','jobs/'+path.name,None))
            except (ValueError,OSError,TypeError):continue
    attachments=[];seen=set()
    for kind,identifier,root_name,relative,expected in candidates:
        if root_name not in roots:raise ValueError('An attachment root is required: '+root_name)
        try:
            path=safe_path(roots[root_name],relative)
            suffixes={'.json'} if kind=='job_metadata' else {'.npz'} if kind=='tapping_timeseries' else MEDIA_SUFFIXES
            if path.suffix.lower() not in suffixes:raise ValueError('Not an approved attachment type')
        except ValueError:
            exclude(kind,identifier,'unsafe path or unsupported type');continue
        if not path.is_file():raise ValueError('Referenced active attachment is missing: '+identifier)
        key=(root_name,path.relative_to(roots[root_name]).as_posix())
        actual=digest(path)
        if expected and actual!=expected:raise ValueError('Attachment source hash mismatch: '+identifier)
        if key not in seen:
            attachments.append({'kind':kind,'id':identifier,'root':key[0],'relative_path':key[1],'sha256':actual,'size_bytes':path.stat().st_size})
            seen.add(key)
    return attachments,excluded


def copy_verified(source,target,expected):
    target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    checksum=hashlib.sha256()
    descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with Path(source).open('rb') as incoming,os.fdopen(descriptor,'wb') as outgoing:
        for block in iter(lambda:incoming.read(1024*1024),b''):
            checksum.update(block);outgoing.write(block)
        outgoing.flush();os.fsync(outgoing.fileno())
    if checksum.hexdigest()!=expected:raise ValueError('File changed during copy')
    os.chmod(target,0o600)


def create_backup(source,destination,*,upload_root=None,output_root=None,copy_files=False,encrypted_storage_ack=False):
    if not encrypted_storage_ack:raise ValueError('Confirm controlled encrypted storage before creating a sensitive backup')
    source=Path(source).resolve(strict=True)
    destination=private_dir(destination)
    database=destination/'database.sqlite3'
    # A read-only source connection still observes committed WAL data. Never copy just the main file.
    with readonly(source) as incoming,closing(sqlite3.connect(database)) as outgoing:
        incoming.backup(outgoing)
    os.chmod(database,0o600)
    roots={key:Path(value).resolve(strict=True) for key,value in (('uploads',upload_root),('outputs',output_root)) if value is not None}
    with readonly(database) as snapshot:
        metadata=db_metadata(snapshot)
        attachments,excluded=select_attachments(snapshot,roots,datetime.now(timezone.utc).replace(tzinfo=None))
    if copy_files:
        for item in attachments:
            copy_verified(safe_path(roots[item['root']],item['relative_path']),destination/'files'/item['root']/item['relative_path'],item['sha256'])
    result={'format_version':1,'created_at':datetime.now(timezone.utc).isoformat(),'operator':getpass.getuser(),'sensitive_full_database':True,
            'external_encrypted_storage_acknowledged':True,'files_copied':copy_files,
            'database':{'file':'database.sqlite3','sha256':digest(database),**metadata},'attachments':attachments,'excluded':excluded}
    # Publish completion manifest last; failed/partial directories remain clearly incomplete.
    payload=canonical(result)
    private_write(destination/'manifest.json',payload)
    private_write(destination/'manifest.sha256',(hashlib.sha256(payload).hexdigest()+'\n').encode())
    verify_backup(destination,require_files=copy_files)
    return result


def verify_backup(bundle,*,require_files=False):
    bundle=Path(bundle).resolve(strict=True)
    manifest=safe_path(bundle,'manifest.json');payload=manifest.read_bytes()
    expected=safe_path(bundle,'manifest.sha256').read_text().strip()
    if hashlib.sha256(payload).hexdigest()!=expected:raise ValueError('Manifest checksum mismatch')
    report=json.loads(payload)
    if report.get('format_version')!=1 or report.get('database',{}).get('file')!='database.sqlite3':raise ValueError('Unsupported backup format')
    if require_files and not report.get('files_copied'):raise ValueError('A manifest-only backup cannot restore patient attachments')
    database=safe_path(bundle,'database.sqlite3')
    if digest(database)!=report['database']['sha256']:raise ValueError('Database checksum mismatch')
    with readonly(database) as db:
        actual=db_metadata(db)
    if any(actual[key]!=report['database'].get(key) for key in actual):raise ValueError('Database schema, migration or row count mismatch')
    for item in report['attachments']:
        if item['root'] not in ('uploads','outputs'):raise ValueError('Unknown attachment root')
        file=safe_path(bundle,'files/'+item['root']+'/'+item['relative_path'])
        if report['files_copied'] and (not file.is_file() or file.stat().st_size!=item['size_bytes'] or digest(file)!=item['sha256']):
            raise ValueError('Backup attachment verification failed')
    return report


def restore_backup(bundle,destination,*,encrypted_storage_ack=False):
    if not encrypted_storage_ack:raise ValueError('Confirm controlled encrypted restore storage')
    report=verify_backup(bundle,require_files=True)
    destination=private_dir(destination)
    # Recreate only into the NEW sandbox directory, never apply to a configured service database.
    target=destination/'database.sqlite3'
    with readonly(Path(bundle)/'database.sqlite3') as incoming,closing(sqlite3.connect(target)) as outgoing:incoming.backup(outgoing)
    os.chmod(target,0o600)
    with readonly(target) as restored:
        metadata=db_metadata(restored)
    if any(metadata[key]!=report['database'][key] for key in metadata):raise ValueError('Restored database differs from backup')
    for item in report['attachments']:
        relative='files/'+item['root']+'/'+item['relative_path']
        copy_verified(safe_path(bundle,relative),destination/relative,item['sha256'])
    private_write(destination/'restore-verification.json',canonical({'verified_at':datetime.now(timezone.utc).isoformat(),'operator':getpass.getuser(),'source_manifest_sha256':digest(Path(bundle)/'manifest.json'),'restored_database_sha256':digest(target),'database':metadata,'attachments_verified':len(report['attachments'])}))
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    backup=commands.add_parser('backup');backup.add_argument('--database',type=Path,required=True);backup.add_argument('--destination',type=Path,required=True)
    backup.add_argument('--upload-root',type=Path);backup.add_argument('--output-root',type=Path);backup.add_argument('--copy-files',action='store_true')
    verify=commands.add_parser('verify');verify.add_argument('--bundle',type=Path,required=True);verify.add_argument('--require-files',action='store_true')
    restore=commands.add_parser('restore');restore.add_argument('--bundle',type=Path,required=True);restore.add_argument('--destination',type=Path,required=True)
    for command in (backup,restore):command.add_argument('--acknowledge-sensitive-encrypted-storage',dest='encrypted_storage_ack',action='store_true')
    args=vars(parser.parse_args());command=args.pop('command')
    try:
        if command=='backup':
            args['source']=args.pop('database');result=create_backup(**args);print('Backup verified. Tables:',len(result['database']['counts']),'attachments:',len(result['attachments']))
        elif command=='verify':result=verify_backup(**args);print('Verified. Tables:',len(result['database']['counts']),'attachments:',len(result['attachments']))
        else:restore_backup(**args);print('Isolated restore verified.')
    except (ValueError,OSError,sqlite3.Error) as error:parser.exit(1,'Backup operation failed: '+str(error)+'\n')


if __name__=='__main__':main()
