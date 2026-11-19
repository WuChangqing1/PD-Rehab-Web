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
    def __init__(self, root:Path, manifest:list[dict]):
        self.root=root.resolve();self.manifest={};self.cache={};self.lock=RLock()
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

    def entry(self, document_id,role):
        entry=self.manifest.get(document_id)
        if not entry:raise KeyError(document_id)
        if ACCESS.get(role,-1)<ACCESS[entry['access']]:raise PermissionError(document_id)
        return entry

    def read(self,document_id,role):
        entry=self.entry(document_id,role);p=self.path(entry['path'])
        if not p.is_file():raise KeyError(document_id)
        content=p.read_bytes();sha=hashlib.sha256(content).hexdigest()
        with self.lock:
            cached=self.cache.get(document_id)
            if cached and cached['sha256']==sha:return dict(cached)
            suffix=p.suffix.lower()
            if suffix not in ('.md','.pdf'):raise ValueError('Unsupported document format')
            result={**entry,'sha256':sha,'format':suffix[1:],'url':'/pd-rehab/docs/'+document_id,
                    'content':content.decode('utf-8') if suffix=='.md' else None}
            self.cache[document_id]=result
            return dict(result)

    def list(self,role):
        result=[]
        for key in self.manifest:
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
        q=set(tokens(query[:3000]))-{'这个','什么','怎么','如何','可以','是否','查询','问题','的是','相关'};chunks=[];seen=set()
        for meta in self.list(role):
            d=self.read(meta['id'],role)
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
                    if score and (len(counts)>=2 or len(query.strip())<=4):
                        chunks.append({**meta,'text':text,'section':section,'chunk':part,'score':score})
                    part+=1
        return sorted(chunks,key=lambda x:(-x['score'],x['id'],x['chunk']))[:min(limit,8)]

MANIFEST=PROJECT_ROOT/'docs/library/manifest.json'
documents=DocumentLibrary(PROJECT_ROOT,json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else [])
library=documents.list
search=documents.search
