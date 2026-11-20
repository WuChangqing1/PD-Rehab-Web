"""Offline backup tests use only synthetic SQLite databases and temp files."""
import importlib.util
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'backup_business_data.py'


def utility():
    spec = importlib.util.spec_from_file_location('backup_business_data', MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path):
    path = tmp_path/'source.sqlite3'
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.executescript('''CREATE TABLE patients(id TEXT PRIMARY KEY,is_deleted INTEGER NOT NULL);
    CREATE TABLE media_files(id TEXT PRIMARY KEY,patient_id TEXT,assessment_session_id TEXT,stored_path TEXT,sha256 TEXT,type TEXT);
    CREATE TABLE face_recordings(id TEXT PRIMARY KEY,patient_id TEXT,status TEXT,created_at TEXT,updated_at TEXT,data_json TEXT);
    CREATE TABLE mobile_face_jobs(id TEXT PRIMARY KEY,patient_id TEXT,assessment_session_id TEXT,stored_path TEXT,status TEXT,created_at TEXT);
    CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES('synthetic-head');
    CREATE TABLE staff_users(id TEXT,password_hash TEXT);
    INSERT INTO patients VALUES('p',0); INSERT INTO patients VALUES('deleted',1);
    INSERT INTO staff_users VALUES('staff','SYNTHETIC-HASH');''')
    connection.commit()
    uploads=tmp_path/'uploads';uploads.mkdir()
    outputs=tmp_path/'outputs';outputs.mkdir()
    yield path, connection, uploads, outputs
    connection.close()


def test_online_backup_includes_committed_wal_and_restore_checks(source,tmp_path):
    module=utility();path,connection,uploads,outputs=source
    connection.execute("INSERT INTO patients VALUES('in-wal',0)");connection.commit()
    assert Path(str(path)+'-wal').is_file()
    (uploads/'live.mp4').write_bytes(b'synthetic-video')
    connection.execute("INSERT INTO media_files VALUES('m','p',NULL,'live.mp4',NULL,'POSE_VIDEO')");connection.commit()
    bundle=tmp_path/'bundle'
    report=module.create_backup(path,bundle,upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert report['database']['counts']['patients'] == 3
    assert report['database']['migration_versions'] == ['synthetic-head']
    assert len(report['attachments']) == 1
    assert 'SYNTHETIC-HASH' not in (bundle/'manifest.json').read_text()
    module.verify_backup(bundle,require_files=True)
    restored=tmp_path/'restored'
    module.restore_backup(bundle,restored,encrypted_storage_ack=True)
    with sqlite3.connect(restored/'database.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM patients').fetchone()[0] == 3
    assert (restored/'files'/'uploads'/'live.mp4').read_bytes() == b'synthetic-video'
    with pytest.raises(FileExistsError):module.restore_backup(bundle,restored,encrypted_storage_ack=True)
    with pytest.raises(FileExistsError):module.create_backup(path,bundle,encrypted_storage_ack=True)


def test_sensitive_ack_required_and_manifest_only_has_explicit_boundary(source,tmp_path):
    module=utility();path,_,uploads,outputs=source
    with pytest.raises(ValueError):module.create_backup(path,tmp_path/'refused')
    report=module.create_backup(path,tmp_path/'bundle',upload_root=uploads,output_root=outputs,encrypted_storage_ack=True)
    assert report['files_copied'] is False
    with pytest.raises(ValueError):module.restore_backup(tmp_path/'bundle',tmp_path/'restore',encrypted_storage_ack=True)


def test_deleted_expired_traversal_symlinks_and_private_extensions_excluded(source,tmp_path):
    module=utility();path,db,uploads,outputs=source
    outside=tmp_path/'outside.mp4';outside.write_bytes(b'do-not-copy')
    for identifier,patient,relative in [('deleted','deleted','deleted.mp4'),('escape','p','../outside.mp4'),('secret','p','.env'),('config','p','private.json')]:
        if '/' not in relative:(uploads/relative).write_bytes(b'do-not-copy')
        db.execute('INSERT INTO media_files VALUES(?,?,NULL,?,NULL,?)',(identifier,patient,relative,'POSE_VIDEO'))
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    for status,age,erased in [('SUCCESS',0,False),('DELETED',0,False),('SUCCESS',8,False),('SUCCESS',0,True)]:
        ident,file_id=str(uuid4()),str(uuid4())
        data={'manifest':{'files':[{'file_id':file_id}]},'segments':[],'upload_complete':True,'media_deleted':erased}
        stamp=(now-timedelta(days=age)).isoformat()
        db.execute('INSERT INTO face_recordings VALUES(?,?,?,?,?,?)',(ident,'p',status,stamp,stamp,json.dumps(data)))
        directory=uploads/'training-face'/ident/file_id;directory.mkdir(parents=True)
        (directory/'video.mp4').write_bytes(b'test')
    db.commit()
    report=module.create_backup(path,tmp_path/'bundle',upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert len(report['attachments']) == 1
    assert report['attachments'][0]['kind'] == 'training_video'
    assert len(report['excluded']) >= 7


def test_tamper_database_attachment_and_manifest_path_fail_closed(source,tmp_path):
    module=utility();path,db,uploads,outputs=source
    (uploads/'live.mp4').write_bytes(b'original')
    db.execute("INSERT INTO media_files VALUES('m','p',NULL,'live.mp4',NULL,'POSE_VIDEO')");db.commit()
    bundle=tmp_path/'bundle';module.create_backup(path,bundle,upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    file=bundle/'files'/'uploads'/'live.mp4';file.write_bytes(b'tampered')
    with pytest.raises(ValueError):module.verify_backup(bundle,require_files=True)
    file.write_bytes(b'original')
    manifest=json.loads((bundle/'manifest.json').read_text());manifest['attachments'][0]['relative_path']='../../outside.mp4'
    (bundle/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):module.verify_backup(bundle,require_files=True)
    with pytest.raises(ValueError):module.restore_backup(bundle,tmp_path/'not-created',encrypted_storage_ack=True)
    assert not (tmp_path/'not-created').exists()


def test_source_hash_mismatch_and_missing_files_prevent_verified_backup(source,tmp_path):
    module=utility();path,db,uploads,outputs=source
    (uploads/'bad.mp4').write_bytes(b'changed')
    db.execute("INSERT INTO media_files VALUES('bad','p',NULL,'bad.mp4',?,'POSE_VIDEO')",('0'*64,));db.commit()
    with pytest.raises(ValueError):module.create_backup(path,tmp_path/'bad-bundle',upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert not (tmp_path/'bad-bundle'/'manifest.json').exists()


def test_database_bytes_and_metadata_tamper_are_detected(source,tmp_path):
    module=utility();path,_,uploads,outputs=source
    bundle=tmp_path/'bundle';module.create_backup(path,bundle,upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    database=bundle/'database.sqlite3';before=database.read_bytes();database.write_bytes(before+b'changed')
    with pytest.raises(ValueError):module.verify_backup(bundle)
    database.write_bytes(before)
    manifest=json.loads((bundle/'manifest.json').read_text());manifest['database']['counts']['patients']=999
    payload=module.canonical(manifest);(bundle/'manifest.json').write_bytes(payload)
    (bundle/'manifest.sha256').write_text(__import__('hashlib').sha256(payload).hexdigest())
    with pytest.raises(ValueError):module.verify_backup(bundle)


def test_manifest_traversal_rejected_even_with_matching_checksum(source,tmp_path):
    module=utility();path,db,uploads,outputs=source
    (uploads/'live.mp4').write_bytes(b'original');db.execute("INSERT INTO media_files VALUES('m','p',NULL,'live.mp4',NULL,'POSE_VIDEO')");db.commit()
    bundle=tmp_path/'bundle';module.create_backup(path,bundle,upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    report=json.loads((bundle/'manifest.json').read_text());report['attachments'][0]['relative_path']='../../../../outside.mp4'
    payload=module.canonical(report);(bundle/'manifest.json').write_bytes(payload);(bundle/'manifest.sha256').write_text(__import__('hashlib').sha256(payload).hexdigest())
    with pytest.raises(ValueError):module.verify_backup(bundle,require_files=True)


def test_live_source_change_and_missing_attachment_never_claim_complete(source,tmp_path,monkeypatch):
    module=utility();path,db,uploads,outputs=source
    (uploads/'live.mp4').write_bytes(b'original');db.execute("INSERT INTO media_files VALUES('m','p',NULL,'live.mp4',NULL,'POSE_VIDEO')");db.commit()
    original=module.copy_verified
    def changed(source,target,expected):
        Path(source).write_bytes(b'changed-during-backup')
        original(source,target,expected)
    monkeypatch.setattr(module,'copy_verified',changed)
    with pytest.raises(ValueError):module.create_backup(path,tmp_path/'racing',upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert not (tmp_path/'racing'/'manifest.json').exists()
    (uploads/'live.mp4').unlink()
    with pytest.raises(ValueError):module.create_backup(path,tmp_path/'missing',upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert not (tmp_path/'missing'/'manifest.json').exists()


def test_symlink_reference_never_copied(source,tmp_path):
    module=utility();path,db,uploads,outputs=source
    outside=tmp_path/'outside.mp4';outside.write_bytes(b'outside')
    try:(uploads/'link.mp4').symlink_to(outside)
    except OSError:pytest.skip('Windows account cannot create symlinks')
    db.execute("INSERT INTO media_files VALUES('m','p',NULL,'link.mp4',NULL,'POSE_VIDEO')");db.commit()
    report=module.create_backup(path,tmp_path/'bundle',upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert not report['attachments']
    assert report['excluded'][0]['reason'] == 'unsafe path or unsupported type'


def test_full_application_model_schema_synthetic_restore(engine,db,staff_user,tmp_path):
    from app.db.base import Base
    from app.db.models import Patient, StaffUser, MobileAccount, TrainingPlan, PianoSession, PianoEvent, ExternalPracticeRecord, AssessmentSession, FingerTappingResult, MediaFile
    module=utility()
    person=Patient(hospital_number='SYNTHETIC-BACKUP',name='Synthetic backup fixture')
    account=StaffUser(username='synthetic-backup-patient',display_name='Synthetic',password_hash='SYNTHETIC-ONLY-HASH',role='PATIENT',is_active=True)
    db.add_all([person,account]);db.flush()
    db.add(MobileAccount(user_id=account.id,patient_id=person.id,recovery_hash='SYNTHETIC-ONLY-RECOVERY',sync_consent_version='test'))
    plan=TrainingPlan(patient_id=person.id,name='Synthetic plan')
    piano=PianoSession(patient_id=person.id,mode='SINGLE_KEY_RHYTHM')
    assessment=AssessmentSession(patient_id=person.id,status='COMPLETED')
    db.add_all([plan,piano,assessment]);db.flush()
    db.add_all([PianoEvent(session_id=piano.id,event_index=1),FingerTappingResult(assessment_session_id=assessment.id,hand='LEFT'),ExternalPracticeRecord(patient_id=person.id,operator_id=staff_user.id,device_id='synthetic',source_record_id='1',record_type='training_plan_snapshot',schema_version='test',payload_sha256='0'*64,payload_json='{"daily_progress":[1]}')])
    uploads=tmp_path/'uploads';uploads.mkdir();outputs=tmp_path/'outputs';outputs.mkdir()
    (uploads/'synthetic.mp4').write_bytes(b'synthetic-data')
    db.add(MediaFile(patient_id=person.id,type='POSE_VIDEO',stored_path='synthetic.mp4'));db.commit()
    source=tmp_path/'full.sqlite3'
    raw=engine.raw_connection()
    try:
        with sqlite3.connect(source) as target:raw.driver_connection.backup(target)
    finally:raw.close()
    report=module.create_backup(source,tmp_path/'bundle',upload_root=uploads,output_root=outputs,copy_files=True,encrypted_storage_ack=True)
    assert len(report['database']['counts']) == len(Base.metadata.tables)
    for name in ('patients','mobile_accounts','training_plans','piano_sessions','piano_events','external_practice_records','assessment_sessions','finger_tapping_results','media_files'):
        assert report['database']['counts'][name] == 1
    module.restore_backup(tmp_path/'bundle',tmp_path/'restored',encrypted_storage_ack=True)
    with module.readonly(tmp_path/'restored'/'database.sqlite3') as restored:
        assert module.db_metadata(restored)['counts'] == report['database']['counts']
    print('Synthetic full-model restore: tables=%d, patients=1, staff_users=2, training_plans=1, piano_sessions=1, piano_events=1, external_practice_records=1, assessment_sessions=1, finger_tapping_results=1, media_files=1, attachments=1' % len(Base.metadata.tables))


def test_cli_backup_verify_restore_cohort(source,tmp_path):
    import subprocess
    import sys
    path,_,uploads,outputs=source
    bundle=tmp_path/'cli-bundle';restored=tmp_path/'cli-restored'
    commands=[['backup','--database',str(path),'--destination',str(bundle),'--upload-root',str(uploads),'--output-root',str(outputs),'--copy-files','--acknowledge-sensitive-encrypted-storage'],['verify','--bundle',str(bundle),'--require-files'],['restore','--bundle',str(bundle),'--destination',str(restored),'--acknowledge-sensitive-encrypted-storage']]
    for args in commands:
        process=subprocess.run([sys.executable,str(MODULE_PATH),*args],capture_output=True,text=True,check=False)
        assert process.returncode == 0,process.stderr
    assert (restored/'restore-verification.json').is_file()
