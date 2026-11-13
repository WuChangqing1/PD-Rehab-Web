import getpass,json,os,re,stat,tempfile
from pathlib import Path
p=Path('/opt/pd-rehab/.env')
key=getpass.getpass('AccessKey ID (hidden): ')
secret=getpass.getpass('AccessKey Secret (hidden): ')
if not re.fullmatch(r'LTAI[A-Za-z0-9]{12,40}',key) or not re.fullmatch(r'[A-Za-z0-9+/=_-]{20,80}',secret):
 raise SystemExit('Invalid credentials format; configuration unchanged')
values={'MOBILE_SMS_ACCESS_KEY_ID':key,'MOBILE_SMS_ACCESS_KEY_SECRET':secret,'MOBILE_SMS_ENABLED':'true','MOBILE_SMS_SIGN_NAME':'恒创联众','MOBILE_SMS_TEMPLATE_CODE':'100001','MOBILE_SMS_SCHEME_NAME':'','MOBILE_SMS_DAILY_BUDGET':'100','MOBILE_WECHAT_ENABLED':'false'}
old=p.read_text(encoding='utf-8')
backup=Path('/opt/pd-rehab/releases/media-sms-20261113/.env-before-sms')
if not backup.exists():
 fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(old)
lines=[line for line in old.splitlines() if not any(re.match(r'^\s*(?:export\s+)?'+re.escape(k)+r'\s*=',line) for k in values)]
new='\n'.join(lines)+'\n'+''.join(k+'='+json.dumps(v,ensure_ascii=False)+'\n' for k,v in values.items())
info=p.stat()
fd,name=tempfile.mkstemp(prefix='.sms-env-',dir=p.parent)
try:
 with os.fdopen(fd,'w',encoding='utf-8') as out:out.write(new);out.flush();os.fsync(out.fileno())
 os.chown(name,info.st_uid,info.st_gid);os.chmod(name,0o600);os.replace(name,p)
finally:
 if os.path.exists(name):os.unlink(name)
print('SMS configuration saved privately. Existing database/JWT/model/AI configuration preserved. No restart performed.')
