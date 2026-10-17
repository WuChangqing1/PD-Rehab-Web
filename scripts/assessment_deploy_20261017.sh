#!/usr/bin/env bash
# Assessment workflow release: no migrations, model/config changes or patient mutations.
set -euo pipefail
umask 077
REV=$1
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-assessment-20261017
BACKUP=/opt/pd-rehab/backups/assessment-20261017
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
CODE_CHANGED=0
rollback() {
  rc=$?
  trap - ERR
  if [ "$CODE_CHANGED" = 1 ]; then git -C "$APP" checkout --detach "$PREV"; fi
  sudo -n install -m 644 "$BACKUP/root-index.html" /var/www/pd-rehab/dist/index.html
  sudo -n install -m 644 "$BACKUP/subpath-index.html" /var/www/pd-rehab/dist-under-path/index.html
  sudo -n systemctl restart pd-rehab-backend
  echo "Release failed; previous code and entries restored. Backup retained at $BACKUP"
  exit "$rc"
}
trap rollback ERR
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
sudo -n systemctl restart pd-rehab-backend
ready=0
for attempt in $(seq 1 30); do
  if curl -fsS --max-time 2 http://127.0.0.1:18086/api/system/health > health.json 2>/dev/null; then ready=1; break; fi
  sleep 1
done
test "$ready" = 1
for variant in dist dist-under-path; do
  sudo -n rsync -a --chmod=D755,F644 --exclude=index.html "$WORK/staged/$variant/" "/var/www/pd-rehab/$variant/"
  sudo -n chown -R www-data:www-data "/var/www/pd-rehab/$variant"
  sudo -n install -m 644 "$WORK/staged/$variant/index.html" "/var/www/pd-rehab/$variant/index.html.next"
  sudo -n mv -T "/var/www/pd-rehab/$variant/index.html.next" "/var/www/pd-rehab/$variant/index.html"
done
sha256sum -c "$BACKUP/config-sha256.txt"
/opt/pd-rehab/venv/bin/python - <<'PY'
import pathlib,hashlib,json,urllib.request,sqlite3
work=pathlib.Path('/tmp/pd-assessment-20261017')
manifest=json.loads((work/'assets.json').read_text())
for name,digest in manifest.items():
    assert hashlib.sha256((pathlib.Path('/var/www/pd-rehab')/name).read_bytes()).hexdigest()==digest,name
for variant,base in [('dist','http://127.0.0.1:18085/'),('dist-under-path','https://ccqspace.site/pd-rehab/')]:
    with urllib.request.urlopen(base,timeout=20) as r:
        assert hashlib.sha256(r.read()).hexdigest()==manifest[variant+'/index.html']
    with urllib.request.urlopen(base+'api/system/health',timeout=20) as r:
        assert json.load(r)['status']=='ok'
db=sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro',uri=True)
assert db.execute('pragma quick_check').fetchone()[0]=='ok'
assert db.execute('select version_num from alembic_version').fetchone()[0]=='h4c6d8e0f2a3'
db.close()
(work/'release-ok.json').write_text(json.dumps({'assets_verified':len(manifest),'database_check':'ok','clinical_records_mutated':False,'model_config_unchanged':True}))
print('Verified',len(manifest),'static files, both entry points, backend health and DB integrity')
PY
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
trap - ERR
echo "RELEASE_OK $REV"
