"""Explicitly published documentation, not a filesystem browser or patient store."""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path
from threading import RLock
from app.core.config import PROJECT_ROOT

ACCESS={'PUBLIC':0,'PATIENT':0,'NURSE':1,'DOCTOR':1,'STAFF':1,'ADMIN':2}
def tokens(text):
    text=text.casefold()
    return re.findall(r'[a-z0-9_]{2,}',text)+[s[i:i+2] for s in re.findall(r'[\u4e00-\u9fff]+',text) for i in range(len(s)-1)]

class DocumentLibrary:
    def __init__(self, root:Path, manifest:list[dict], manifest_path:Path|None=None):
        self.root=root.resolve();self.manifest={};self.cache={};self.lock=RLock()
        self.manifest_path=manifest_path;self.manifest_hash=None
        for entry in manifest:
            if not re.fullmatch(r'[a-z][a-z0-9-]{0,79}',entry['id']) or entry['id'] in self.manifest:
                raise ValueError('Invalid or duplicate document ID')
            self.path(entry['path'])
            if entry['access'] not in ('PUBLIC','STAFF','ADMIN'):raise ValueError('Invalid document permission')
            for asset in entry.get('assets',[]):self.path(asset)
            self.manifest[entry['id']]=dict(entry)

    def path(self, relative):
        p=(self.root/relative).resolve()
        if not p.is_relative_to(self.root) or any(x in str(relative).split('/') for x in ('..','.env')):
            raise ValueError('Document path escapes approved root')
        return p

    def refresh(self):
        if self.manifest_path is None:return
        try:content=self.manifest_path.read_bytes()
        except FileNotFoundError:content=b'[]'
        digest=hashlib.sha256(content).hexdigest()
        if digest==self.manifest_hash:return
        with self.lock:
            try:
                candidate=DocumentLibrary(self.root,json.loads(content))
            except Exception:
                self.manifest={};self.cache.clear();self.manifest_hash=None
                raise
            self.manifest=candidate.manifest
            self.cache={k:v for k,v in self.cache.items() if k in self.manifest}
            self.manifest_hash=digest

    def entry(self, document_id,role):
        self.refresh()
        entry=self.manifest.get(document_id)
        if not entry or entry.get('enabled') is False:raise KeyError(document_id)
        if ACCESS.get(role,-1)<ACCESS[entry['access']]:raise PermissionError(document_id)
        return entry

    def read(self,document_id,role):
        entry=self.entry(document_id,role);p=self.path(entry['path'])
        if not p.is_file():raise KeyError(document_id)
        content=p.read_bytes();sha=hashlib.sha256(content).hexdigest()
        with self.lock:
            cached=self.cache.get(document_id)
            if cached and cached['sha256']==sha:return {**cached,**entry}
            suffix=p.suffix.lower()
            if suffix not in ('.md','.pdf'):raise ValueError('Unsupported document format')
            result={**entry,'sha256':sha,'format':suffix[1:],'url':'/pd-rehab/docs/'+document_id,
                    'content':content.decode('utf-8') if suffix=='.md' else None}
            self.cache[document_id]=result
            return dict(result)

    def list(self,role):
        self.refresh()
        result=[]
        for key in tuple(self.manifest):
            try:entry=self.read(key,role)
            except (KeyError,PermissionError):
                with self.lock:self.cache.pop(key,None)
                continue
            result.append({k:v for k,v in entry.items() if k not in ('content','assets')})
        return result

    def asset(self,document_id,name,role):
        entry=self.entry(document_id,role)
        # Only declared relative resources, never arbitrary files or remote fetches.
        if name not in entry.get('assets',[]):raise KeyError(name)
        p=self.path(name)
        if not p.is_file() or p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.pdf'):raise KeyError(name)
        return p

    def search(self,query,role,limit=6):
        aliases=[(r'\b(?:register|registration|signup)\b','注册'),
                 (r'\b(?:login|signin)\b','登录'),(r'\b(?:password|reset)\b','密码 找回'),
                 (r'\b(?:report|pdf|export)\b','报告 导出 PDF'),
                 (r'\b(?:download|apk)\b','下载 安装'),(r'\b(?:piano|rhythm|hands)\b','钢琴 节奏 双手'),
                 (r'\b(?:face|video|camera)\b','面部 录像 摄像头'),(r'\b(?:dance|ballet)\b','舞蹈 芭蕾'),
                 (r'\b(?:plan|schedule|progress)\b','训练 计划 进度'),
                 (r'\b(?:sync|synchronize|offline|history)\b','同步 离线 历史'),
                 (r'\b(?:metrics|assessment|evaluation)\b','指标 评估')]
        expanded=query[:3000]+' '+ ' '.join(text for pattern,text in aliases if re.search(pattern,query,re.I))
        q=set(tokens(expanded))-{'这个','什么','怎么','如何','可以','是否','查询','问题','的是','相关'};chunks=[];seen=set()
        for meta in self.list(role):
            try:d=self.read(meta['id'],role)
            except (KeyError,PermissionError):continue
            if not d['content']:continue
            section='';part=0
            for block in re.split(r'\n(?=#{1,3} )',d['content']):
                match=re.match(r'#{1,3} (.+)',block)
                if match:section=match[1].strip()
                # Bounded evidence chunks; changes/removals are reflected on each search.
                for start in range(0,len(block),900):
                    text=block[start:start+1100];digest=hashlib.sha256(text.encode()).hexdigest()
                    if digest in seen:continue
                    seen.add(digest);ts=tokens(meta['title']+' '+section+' '+text)
                    counts={t:ts.count(t) for t in q if t in ts}
                    score=sum(1+math.log(c) for c in counts.values())/math.sqrt(max(len(ts),30))
                    if str(meta.get('status','')).startswith('历史'):score*=0.5
                    if score and (len(counts)>=2 or len(query.strip())<=4):
                        chunks.append({**meta,'text':text,'section':section,'chunk':part,'score':score})
                    part+=1
        return sorted(chunks,key=lambda x:(-x['score'],x['id'],x['chunk']))[:min(limit,8)]

MANIFEST=PROJECT_ROOT/'docs/library/manifest.json'
documents=DocumentLibrary(PROJECT_ROOT,json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else [],manifest_path=MANIFEST)
library=documents.list
search=documents.search
