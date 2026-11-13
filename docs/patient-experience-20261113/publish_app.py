from pathlib import Path
import json,os,hashlib,subprocess
STAGE=Path('/opt/pd-rehab/releases/patient-experience-20261113');ROOT=Path('/var/www/pd-rehab/app-releases');V=ROOT/'0.1.69';NAME='PianoForParkinson-0.1.69-patient-pace-QA-arm64.apk';APK=STAGE/'app-0.1.69.apk.upload';SHA='3293ec32bd8afb0951eb26a30375693ec1b15ec3fe4b2498c666dca1ee545d45'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def state():return subprocess.check_output(['systemctl','show','pd-rehab-backend','nginx','-p','MainPID','-p','ActiveState'],text=True)
assert APK.stat().st_size==119011850 and digest(APK)==SHA
assert not V.exists() and not ROOT.is_symlink()
for d in ['dist','dist-under-path']:assert (Path('/var/www/pd-rehab')/d/'assets/app-releases').resolve()==ROOT
before=state();V.mkdir(mode=0o755);os.replace(APK,V/NAME);os.chown(V/NAME,0,0)
meta={'version':'0.1.69+70','sourceCommit':'89190559cb7eed1731f33ac2c0d17b0374005fc8','kind':'isolated-arm64-debug-QA','applicationId':'com.pianoforparkinson.piano_practice.validation','bytes':119011850,'sha256':SHA,'apk':NAME,'flutterTests':{'passed':852,'skipped':2},'analyze':'no issues','signatureVerified':True,'courseCount':3,'parts':10,'physicalDeviceValidation':'not-performed-no-device'}
(V/'SHA256SUMS.txt').write_text(SHA+'  '+NAME+'\n');(V/'release.json').write_text(json.dumps(meta,indent=2)+'\n')
for p in V.iterdir():p.chmod(0o644)
assert state()==before
(STAGE/'app-publication-result.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))
