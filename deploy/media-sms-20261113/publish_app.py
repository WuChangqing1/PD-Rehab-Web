import os,json,hashlib
from pathlib import Path
from migration_common import STAGE,states,command
root=Path('/var/www/pd-rehab/app-releases');version=root/'0.1.68'
incoming=STAGE/'app-0.1.68.apk.upload';name='PianoForParkinson-0.1.68-media-sms-QA-arm64.apk'
expected='7346f873278f74bdf9d06bf502ae9058de1d5c4436bf5afceaaf3d31694f8b25'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
assert incoming.stat().st_size==124882291 and digest(incoming)==expected
assert not version.exists() and not version.is_symlink() and not root.is_symlink()
for folder in ['dist','dist-under-path']:assert (Path('/var/www/pd-rehab')/folder/'assets/app-releases').resolve()==root
before=states();version.mkdir(mode=0o755);target=version/name
os.replace(incoming,target);os.chown(target,0,0);target.chmod(0o644)
assert digest(target)==expected
(version/'SHA256SUMS.txt').write_text(expected+'  '+name+'\n')
meta={'version':'0.1.68+69','sourceCommit':'80018104f4cd8c37d1258dd3dea7e97e8e2f8f67','webSourceCommit':command('git','-c','safe.directory=/opt/pd-rehab/app/PD-Rehab-Web','-C','/opt/pd-rehab/app/PD-Rehab-Web','rev-parse','HEAD'),'kind':'isolated-arm64-debug-QA','applicationId':'com.pianoforparkinson.piano_practice.validation','apk':name,'bytes':124882291,'sha256':expected,'courseCount':3,'parts':10,'physicalDeviceValidation':'not-performed-no-device','flutterTests':{'passed':836,'skipped':2},'nativeTests':{'passed':106,'skipped':0},'smsRealProviderVerified':True,'smsRepeatIdentityVerified':True}
(version/'release.json').write_text(json.dumps(meta,indent=2)+'\n')
for p in version.iterdir():p.chmod(0o644)
assert states()==before
(STAGE/'app-publication-result.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))
