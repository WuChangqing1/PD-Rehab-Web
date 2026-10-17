"""Build a checksummed release archive from verified frontend builds and main."""
import hashlib,json,subprocess,tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'_deploy'/'followup-release-20261017'
out.mkdir(parents=True,exist_ok=True)
def git(*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git('branch','--show-current')=='main'
revision=git('rev-parse','HEAD')
git('bundle','create',str(out/'release.bundle'),'7c4f59269c4c8cf984c91190406be0a2de8499f8..main')
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
(out/'deploy.sh').write_text((root/'scripts/followup_deploy_20261017.sh').read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
(out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256((out/name).read_bytes()).hexdigest()}  {name}\n' for name in ['release.bundle','frontend.tar.gz','assets.json','deploy.sh']),encoding='ascii')
(out/'revision.txt').write_text(revision,encoding='ascii')
print(json.dumps({'revision':revision,'files':len(manifest),'archive_bytes':(out/'frontend.tar.gz').stat().st_size,'folder':str(out)}))
