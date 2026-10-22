#!/usr/bin/env bash
# Copy reviewed private weights separately from Git. No activation or database writes.
set -euo pipefail
umask 077
REV=$1
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-weights-20261022
BACKUP=/opt/pd-rehab/backups/weights-20261022
MODEL=/opt/pd-rehab/models/microflow-da
cd "$WORK"
sha256sum -c SHA256SUMS
test "$(realpath "$MODEL")" = /opt/pd-rehab/models/microflow-da
test -w "$MODEL"
for path in recognition.pth spotting/checkpoint_epoch_054.pth.tar checkpoint-installation.json; do test ! -e "$MODEL/$path"; done
test "$(git -C "$APP" branch --show-current)" = main
test -z "$(git -C "$APP" status --porcelain)"
PREV=$(git -C "$APP" rev-parse HEAD)
git -C "$APP" bundle verify "$WORK/release.bundle"
git -C "$APP" fetch "$WORK/release.bundle" main
test "$(git -C "$APP" rev-parse FETCH_HEAD)" = "$REV"
git -C "$APP" merge-base --is-ancestor "$PREV" "$REV"
test ! -e "$BACKUP"
mkdir "$BACKUP" staged model-staged
printf '%s\n' "$PREV" > "$BACKUP/revision.txt"
cp /var/www/pd-rehab/dist/index.html "$BACKUP/root-index.html"
cp /var/www/pd-rehab/dist-under-path/index.html "$BACKUP/subpath-index.html"
sha256sum "$MODEL/runtime.env" "$MODEL/model-config.yaml" /etc/systemd/system/pd-rehab-backend.service.d/microflow.conf > "$BACKUP/config-sha256.txt"
tar -xzf frontend.tar.gz -C staged
tar -xzf model-weights.tar.gz -C model-staged
CODE_CHANGED=0
WEIGHTS_CHANGED=0
rollback() {
  rc=$?;trap - ERR
  sudo -n systemctl stop pd-rehab-backend
  if [ "$WEIGHTS_CHANGED" = 1 ]; then
    rm -f -- "$MODEL/recognition.pth" "$MODEL/spotting/checkpoint_epoch_054.pth.tar" "$MODEL/checkpoint-installation.json"
  fi
  if [ "$CODE_CHANGED" = 1 ]; then git -C "$APP" checkout --detach "$PREV"; fi
  sudo -n install -m 644 "$BACKUP/root-index.html" /var/www/pd-rehab/dist/index.html
  sudo -n install -m 644 "$BACKUP/subpath-index.html" /var/www/pd-rehab/dist-under-path/index.html
  sudo -n systemctl start pd-rehab-backend
  echo 'Release failed; old entries/code restored, newly added weights removed. Backup retained.'
  exit "$rc"
}
trap rollback ERR
sudo -n systemctl stop pd-rehab-backend
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
mkdir -p "$MODEL/spotting"
WEIGHTS_CHANGED=1
for path in recognition.pth spotting/checkpoint_epoch_054.pth.tar checkpoint-installation.json; do install -m 640 "$WORK/model-staged/$path" "$MODEL/$path"; done
cd "$APP"
PYTHONPATH=backend /opt/pd-rehab/venv/bin/python - <<'PY'
import json,pathlib
from app.ml.micro_expression.microflow import sha256,source_digest,MicroFlowRuntime
root=pathlib.Path('/opt/pd-rehab/models/microflow-da')
receipt=json.loads((root/'checkpoint-installation.json').read_text())
assert sha256(root/'recognition.pth')==receipt['checkpoint_sha256']
assert sha256(root/'spotting/checkpoint_epoch_054.pth.tar')==receipt['spotting_sha256']
assert sha256(root/'model-config.yaml')==receipt['config_sha256']
assert source_digest(root/'source')==receipt['source_sha256']
assert receipt['activation_allowed'] is False and receipt['training_contract_verified'] is False
status=MicroFlowRuntime(root).inspect()
assert status.extra['checkpoint_present'] is True and status.state.value!='READY'
assert 'checkpoint' not in status.extra['missing'] and '权重已安置' in status.detail
print(json.dumps({'checkpoint_present':True,'activation_allowed':False,'state':status.state.value,'source_issue':status.extra.get('known_source_issue')},ensure_ascii=True))
PY
sha256sum -c "$BACKUP/config-sha256.txt"
sudo -n systemctl start pd-rehab-backend
ready=0
for attempt in $(seq 1 30); do
  if curl -fsS --max-time 2 http://127.0.0.1:18086/api/system/health > "$WORK/health.json" 2>/dev/null; then ready=1;break;fi
  sleep 1
done
test "$ready" = 1
for variant in dist dist-under-path; do
  sudo -n rsync -a --chmod=D755,F644 --exclude=index.html "$WORK/staged/$variant/" "/var/www/pd-rehab/$variant/"
  sudo -n chown -R www-data:www-data "/var/www/pd-rehab/$variant"
  sudo -n install -m 644 "$WORK/staged/$variant/index.html" "/var/www/pd-rehab/$variant/index.html.next"
  sudo -n mv -T "/var/www/pd-rehab/$variant/index.html.next" "/var/www/pd-rehab/$variant/index.html"
done
/opt/pd-rehab/venv/bin/python - <<'PY'
import pathlib,hashlib,json,urllib.request,sqlite3
work=pathlib.Path('/tmp/pd-weights-20261022');manifest=json.loads((work/'assets.json').read_text())
for name,digest in manifest.items():assert hashlib.sha256((pathlib.Path('/var/www/pd-rehab')/name).read_bytes()).hexdigest()==digest,name
for variant,base in [('dist','http://127.0.0.1:18085/'),('dist-under-path','https://ccqspace.site/pd-rehab/')]:
    with urllib.request.urlopen(base,timeout=20) as response:assert hashlib.sha256(response.read()).hexdigest()==manifest[variant+'/index.html']
    with urllib.request.urlopen(base+'api/system/health',timeout=20) as response:assert json.load(response)['status']=='ok'
with sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro',uri=True) as db:
    assert db.execute('pragma quick_check').fetchone()[0]=='ok'
    assert not db.execute('pragma foreign_key_check').fetchall()
    assert db.execute('select version_num from alembic_version').fetchone()[0]=='i5d7e9f1a3b4'
print('Verified',len(manifest),'static files, both entries, installed weight hashes and DB integrity; model remains unavailable')
PY
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
trap - ERR
echo "RELEASE_OK $REV"
