import os,hashlib,json,sqlite3,subprocess
from pathlib import Path
STAGE=Path('/opt/pd-rehab/releases/media-sms-20261113')
DB=Path('/opt/pd-rehab/data/pd.db')
UNITS=['pd-rehab-backend','nginx','exercises','foodcircle-api','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api']
def command(*a):return subprocess.check_output(a,text=True).strip()
def states():return {u:command('systemctl','show',u,'-p','ActiveState','-p','MainPID') for u in UNITS}
def service_environment():
 pid=command('systemctl','show','pd-rehab-backend','-p','MainPID','--value')
 env={}
 for line in Path('/proc/'+pid+'/environ').read_bytes().split(b'\x00'):
  if b'=' in line:
   k,v=line.split(b'=',1);env[k.decode()]=v.decode()
 assert env.get('DATABASE_URL')=='sqlite:////opt/pd-rehab/data/pd.db','Unexpected effective DB'
 return env
def backup(destination):
 assert destination.resolve().is_relative_to(STAGE.resolve()) and not destination.exists()
 fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
 with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True,timeout=30) as src,sqlite3.connect(destination) as dst:src.backup(dst)
def snapshot(path):
 result={}
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
  assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
  assert not c.execute('pragma foreign_key_check').fetchall()
  for (name,sql) in c.execute("select name,sql from sqlite_master where type='table' order by name").fetchall():
   if name.startswith('sqlite_') or name=='alembic_version':continue
   q='"'+name.replace('"','""')+'"';h=hashlib.sha256();count=0
   for row in c.execute('select * from '+q+' order by rowid'):
    h.update((json.dumps(row,ensure_ascii=False,default=lambda v:v.hex() if isinstance(v,bytes) else str(v))+'\n').encode());count+=1
   result[name]={'schema':sql,'count':count,'digest':h.hexdigest()}
 return result
def compare(before,after):
 assert set(after)-set(before)=={'mobile_identities','mobile_login_challenges','mobile_auth_limits'}
 assert all(after.get(t)==v for t,v in before.items()),'Existing data/schema changed'
def migrate(backend,db,env):
 e=dict(env);e['DATABASE_URL']='sqlite:///'+str(db);e['PYTHONPATH']=str(backend)
 r=subprocess.run(['/opt/pd-rehab/venv/bin/python','-m','alembic','upgrade','head'],cwd=backend,env=e,capture_output=True,text=True)
 if r.returncode:raise RuntimeError('Alembic failed: '+r.stderr[-1500:])
 with sqlite3.connect(db) as c:assert c.execute('select version_num from alembic_version').fetchall()==[('o1d3e5f7a9b1',)]
 return r.stdout+r.stderr
