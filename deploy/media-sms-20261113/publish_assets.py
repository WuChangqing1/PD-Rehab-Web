import json,hashlib,os,subprocess
from pathlib import Path
stage=Path('/opt/pd-rehab/releases/media-sms-20261113/assets-upload')
target=Path('/var/www/pd-rehab/course-media/dance/v2')
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def states():
 return {u:subprocess.check_output(['systemctl','show',u,'-p','ActiveState','-p','MainPID'],text=True).strip() for u in ['pd-rehab-backend','nginx','exercises','foodcircle-api','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api']}
before=states()
assert not target.exists() and not target.is_symlink()
manifest=json.loads((stage/'resources-v2.json').read_text())
assert len(manifest['courses'])==3 and len(manifest['items'])==10
expected={'resources-v2.json'}|{f"poster-{c['courseId']}.jpg" for c in manifest['courses']}|{i['fileName'] for i in manifest['items'] if i['resourceVersion']=='v2'}
assert {p.name for p in stage.iterdir()}==expected
verified=[]
for item in manifest['items']:
 p=stage/item['fileName'] if item['resourceVersion']=='v2' else target.parent/'v1'/item['fileName']
 assert p.is_file() and not p.is_symlink() and p.stat().st_size==item['bytes'] and digest(p)==item['sha256']
 verified.append(item['partId'])
for p in stage.iterdir():
 assert p.is_file() and not p.is_symlink()
 p.chmod(0o644);os.chown(p,0,0)
stage.chmod(0o755);os.chown(stage,0,0)
assert stage.stat().st_dev==target.parent.stat().st_dev
os.replace(stage,target)
after=states();assert before==after
result={'publishedDirectory':str(target),'verifiedPartIds':verified,'newFiles':sorted(expected),'serviceStatesUnchanged':True,'services':after}
Path('/opt/pd-rehab/releases/media-sms-20261113/assets-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
