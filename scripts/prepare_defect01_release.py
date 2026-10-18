"""Package verified root/subpath builds with exact main revision and LF scripts."""
import hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'_deploy'/'defect01-release-20261018'
out.mkdir(parents=True,exist_ok=True)
def git(*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git('branch','--show-current')=='main'
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
revision=git('rev-parse','HEAD')
git('bundle','create',str(out/'release.bundle'),'4823889c9365ff82097cda7e4b07bf9ec5b752d0..main')
manifest={}
with tarfile.open(out/'frontend.tar.gz','w:gz') as archive:
    for variant in ['dist','dist-under-path']:
        folder=root/'frontend'/variant
        assert (folder/'index.html').is_file()
        archive.add(folder,arcname=variant)
        for path in folder.rglob('*'):
            if path.is_file():
                manifest[f'{variant}/{path.relative_to(folder).as_posix()}']=hashlib.sha256(path.read_bytes()).hexdigest()
(out/'assets.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for source,target in [('defect01_deploy_20261018.sh','deploy.sh'),('defect01_database_guard.py','database-guard.py')]:
    (out/target).write_text((root/'scripts'/source).read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
files=['release.bundle','frontend.tar.gz','assets.json','deploy.sh','database-guard.py']
(out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256((out/name).read_bytes()).hexdigest()}  {name}\n' for name in files),encoding='ascii',newline='\n')
(out/'revision.txt').write_text(revision,encoding='ascii')
print(json.dumps({'revision':revision,'files':len(manifest),'archive_bytes':(out/'frontend.tar.gz').stat().st_size,'folder':str(out)}))
