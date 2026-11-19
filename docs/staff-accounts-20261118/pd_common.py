import os,json,hashlib,sqlite3,subprocess,urllib.request
from pathlib import Path
STAGE=Path('/opt/pd-rehab/releases/staff-accounts-20261118');WEB=Path('/opt/pd-rehab/app/PD-Rehab-Web');DB=Path('/opt/pd-rehab/data/pd.db');OLD='1c15a6304557e320748c7a511d54b1d2d4f1ace2'
UNITS=['pd-rehab-backend','nginx','exercises','foodcircle-api','his-18092-tls','llm-api-platform','smoking-monitor-api','smoking-monitoring-system-api']
def cmd(*a):return subprocess.check_output(a,text=True).strip()
def git(*a):return cmd('sudo','-u','ubuntu','git','-c','core.quotepath=false','-C',str(WEB),*a)
def states():return {u:cmd('systemctl','show',u,'-p','ActiveState','-p','MainPID') for u in UNITS}
def request(p):
 with urllib.request.urlopen('http://127.0.0.1:18086/api/'+p,timeout=15) as r:return json.load(r)
def env():
 pid=cmd('systemctl','show','pd-rehab-backend','-p','MainPID','--value');out={}
 for field in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
  if b'=' in field:
   k,v=field.split(b'=',1);out[k.decode()]=v.decode()
 assert out.get('DATABASE_URL')=='sqlite:////opt/pd-rehab/data/pd.db'
 return out

def backup(target):
 assert target.resolve().is_relative_to(STAGE.resolve()) and not target.exists()
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
 with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True,timeout=30) as a,sqlite3.connect(target) as b:a.backup(b)
def snapshot(path=DB):
 with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as c:
  assert c.execute('pragma integrity_check').fetchone()[0]=='ok';assert not c.execute('pragma foreign_key_check').fetchall()
  out={}
  for name,sql in c.execute("select name,sql from sqlite_master where type='table' order by name").fetchall():
   if name.startswith('sqlite_') or name=='alembic_version':continue
   q='"'+name.replace('"','""')+'"';h=hashlib.sha256();count=0
   for row in c.execute('select * from '+q+' order by rowid'):
    h.update((json.dumps(row,ensure_ascii=False,default=lambda v:v.hex() if isinstance(v,bytes) else str(v))+'\n').encode());count+=1
   out[name]={'schema':sql,'count':count,'digest':h.hexdigest()}
  return out
if __name__=='__main__':
 assert git('rev-parse','HEAD')==OLD and not git('status','--porcelain')
 STAGE.mkdir(mode=0o700,exist_ok=True);assert request('system/models')['summary']['ready']==4
 result={'sha':OLD,'services':states(),'modelsReady':4,'migration':None,'freeBytes':__import__('shutil').disk_usage(STAGE).free}
 with sqlite3.connect('file:'+str(DB)+'?mode=ro',uri=True) as c:result['migration']=c.execute('select version_num from alembic_version').fetchone()[0]
 assert result['migration']=='o1d3e5f7a9b1'
 backup(STAGE/'rehearsal.sqlite');result['oldBusinessTables']=len(snapshot(STAGE/'rehearsal.sqlite'))
 (STAGE/'baseline.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
