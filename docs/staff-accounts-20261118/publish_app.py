from pathlib import Path
import json,os,hashlib,subprocess
STAGE=Path('/opt/pd-rehab/releases/staff-accounts-20261118');ROOT=Path('/var/www/pd-rehab/app-releases');V=ROOT/'0.1.73';NAME='PianoForParkinson-0.1.73-patient-name-QA-arm64.apk';APK=STAGE/'app-0.1.73.apk.upload';SHA='0ed6dd9737a6b7aeb6d5859e4d6f794e431e51bcc396c4451e8e95bf341e2ac7'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def state():return subprocess.check_output(['systemctl','show','pd-rehab-backend','nginx','-p','MainPID','-p','ActiveState'],text=True)
assert APK.stat().st_size==119361090 and digest(APK)==SHA
assert not V.exists() and not ROOT.is_symlink()
for d in ['dist','dist-under-path']:assert (Path('/var/www/pd-rehab')/d/'assets/app-releases').resolve()==ROOT
before=state();V.mkdir(mode=0o755);os.replace(APK,V/NAME);os.chown(V/NAME,0,0)
meta={'version':'0.1.73+74','sourceCommit':'cf12656de3cfdb90b98535b4f57a412f739f1fed','kind':'isolated-arm64-debug-QA','applicationId':'com.pianoforparkinson.piano_practice.validation','bytes':119361090,'sha256':SHA,'apk':NAME,'flutterTests':{'passed':908,'skipped':2},'analyze':'no issues','signatureVerified':True,'courseCount':3,'parts':10,'physicalDeviceValidation':'not-performed-no-device'}
(V/'SHA256SUMS.txt').write_text(SHA+'  '+NAME+'\n');(V/'release.json').write_text(json.dumps(meta,indent=2)+'\n')
for p in V.iterdir():p.chmod(0o644)
assert state()==before
(STAGE/'app-publication-result.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))
