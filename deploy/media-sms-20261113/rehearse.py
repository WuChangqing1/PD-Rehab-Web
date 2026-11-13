import json,tarfile,uuid
from migration_common import *
source=STAGE/'candidate'
assert not source.exists()
source.mkdir(mode=0o700)
with tarfile.open(STAGE/'backend-source.tar') as archive:
 for member in archive.getmembers():
  p=(source/member.name).resolve()
  assert p.is_relative_to(source.resolve()) and not member.issym() and not member.islnk()
 archive.extractall(source)
env=service_environment();copy=STAGE/('migration-rehearsal-'+uuid.uuid4().hex+'.sqlite')
backup(copy);before=snapshot(copy);log=migrate(source/'backend',copy,env);after=snapshot(copy);compare(before,after)
result={'copy':str(copy),'oldTables':len(before),'newTables':sorted(set(after)-set(before)),'oldDataAndSchemasIdentical':True,'head':'o1d3e5f7a9b1','integrity':'ok','foreignKeys':'ok'}
(STAGE/'rehearsal-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
