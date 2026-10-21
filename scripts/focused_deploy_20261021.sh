#!/usr/bin/env bash
set -euo pipefail
umask 077
REV=$1
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-focused-polish-20261021
BACKUP=/opt/pd-rehab/backups/focused-polish-20261021
cd "$WORK"
sha256sum -c SHA256SUMS
test "$(git -C "$APP" branch --show-current)" = main
test -z "$(git -C "$APP" status --porcelain)"
PREV=$(git -C "$APP" rev-parse HEAD)
git -C "$APP" bundle verify "$WORK/release.bundle"
git -C "$APP" fetch "$WORK/release.bundle" main
test "$(git -C "$APP" rev-parse FETCH_HEAD)" = "$REV"
git -C "$APP" merge-base --is-ancestor "$PREV" "$REV"
test ! -e "$BACKUP"
mkdir "$BACKUP" staged
printf '%s\n' "$PREV" > "$BACKUP/revision.txt"
cp /var/www/pd-rehab/dist/index.html "$BACKUP/root-index.html"
cp /var/www/pd-rehab/dist-under-path/index.html "$BACKUP/subpath-index.html"
sha256sum /opt/pd-rehab/models/microflow-da/runtime.env /etc/systemd/system/pd-rehab-backend.service.d/microflow.conf > "$BACKUP/config-sha256.txt"
tar -xzf frontend.tar.gz -C staged
test -f staged/dist/index.html
test -f staged/dist-under-path/index.html
STOPPED=0
CODE_CHANGED=0
rollback() {
  rc=$?;trap - ERR
  if [ "$STOPPED" = 1 ] && [ -f "$BACKUP/pd.db" ]; then
    sudo -n systemctl stop pd-rehab-backend
    /opt/pd-rehab/venv/bin/python - <<'PY'
import sqlite3
with sqlite3.connect('/opt/pd-rehab/backups/focused-polish-20261021/pd.db') as old, sqlite3.connect('/opt/pd-rehab/data/pd.db') as target:old.backup(target)
PY
  fi
  if [ "$CODE_CHANGED" = 1 ]; then git -C "$APP" checkout --detach "$PREV"; fi
  sudo -n install -m 644 "$BACKUP/root-index.html" /var/www/pd-rehab/dist/index.html
  sudo -n install -m 644 "$BACKUP/subpath-index.html" /var/www/pd-rehab/dist-under-path/index.html
  sudo -n systemctl start pd-rehab-backend
  echo 'Release failed; previous database, source and entries restored. Backup retained.'
  exit "$rc"
}
trap rollback ERR
sudo -n systemctl stop pd-rehab-backend
STOPPED=1
/opt/pd-rehab/venv/bin/python "$WORK/database_guard.py" before
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
cd "$APP"
/opt/pd-rehab/venv/bin/python scripts/polish_patient_data.py > "$WORK/data-preview.json"
/opt/pd-rehab/venv/bin/python scripts/polish_patient_data.py --apply > "$WORK/data-applied.json"
/opt/pd-rehab/venv/bin/python "$WORK/database_guard.py" after
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
import pathlib,hashlib,json,urllib.request,urllib.error
work=pathlib.Path('/tmp/pd-focused-polish-20261021')
manifest=json.loads((work/'assets.json').read_text())
for name,digest in manifest.items():
    assert hashlib.sha256((pathlib.Path('/var/www/pd-rehab')/name).read_bytes()).hexdigest()==digest,name
for variant,base in [('dist','http://127.0.0.1:18085/'),('dist-under-path','https://ccqspace.site/pd-rehab/')]:
    with urllib.request.urlopen(base,timeout=20) as r:assert hashlib.sha256(r.read()).hexdigest()==manifest[variant+'/index.html']
    with urllib.request.urlopen(base+'api/system/health',timeout=20) as r:assert json.load(r)['status']=='ok'
    for image in ['comprehensive','face','finger']:
        with urllib.request.urlopen(base+'images/assessment-20261021/'+image+'.webp',timeout=20) as r:assert r.headers['Content-Type'].startswith('image/')
    try:urllib.request.urlopen(base+'api/patients/verification/training/active',timeout=20)
    except urllib.error.HTTPError as e:assert e.code==401
    else:raise AssertionError('New API must require authentication')
print('Verified',len(manifest),'static files, covers, new API authentication, both entry points and health')
print((work/'data-applied.json').read_text())
PY
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
trap - ERR
echo "RELEASE_OK $REV"
