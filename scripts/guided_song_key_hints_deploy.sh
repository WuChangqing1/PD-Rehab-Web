#!/usr/bin/env bash
# Frontend-only release: keep backend, DB and Nginx running unchanged.
set -euo pipefail
umask 077
REV=$1
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-key-hints-20261016
BACKUP=/opt/pd-rehab/backups/key-hints-20261016
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
mkdir "$BACKUP"
printf '%s\n' "$PREV" > "$BACKUP/revision.txt"
cp /var/www/pd-rehab/dist/index.html "$BACKUP/root-index.html"
cp /var/www/pd-rehab/dist-under-path/index.html "$BACKUP/subpath-index.html"
mkdir staged
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
  echo "Release failed; previous entries restored, backup preserved at $BACKUP"
  exit "$rc"
}
trap rollback ERR
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
for variant in dist dist-under-path; do
  sudo -n rsync -a --chmod=D755,F644 --exclude=index.html "$WORK/staged/$variant/" "/var/www/pd-rehab/$variant/"
  sudo -n chown -R www-data:www-data "/var/www/pd-rehab/$variant"
  sudo -n install -m 644 "$WORK/staged/$variant/index.html" "/var/www/pd-rehab/$variant/index.html.next"
  sudo -n mv -T "/var/www/pd-rehab/$variant/index.html.next" "/var/www/pd-rehab/$variant/index.html"
done
/opt/pd-rehab/venv/bin/python - <<'PY'
import hashlib,json,pathlib,urllib.request
work=pathlib.Path('/tmp/pd-key-hints-20261016')
manifest=json.loads((work/'assets.json').read_text())
for name,digest in manifest.items():
    p=pathlib.Path('/var/www/pd-rehab')/name
    assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name
for variant,base in [('dist','http://127.0.0.1:18085/'),('dist-under-path','https://ccqspace.site/pd-rehab/')]:
    with urllib.request.urlopen(base,timeout=20) as r:
        assert hashlib.sha256(r.read()).hexdigest()==manifest[variant+'/index.html'],variant
with urllib.request.urlopen('http://127.0.0.1:18086/api/system/health',timeout=10) as r:
    assert json.load(r)['status']=='ok'
(work/'release-ok.json').write_text(json.dumps({'assets_verified':len(manifest),'backend_health':'ok'}))
print('Verified',len(manifest),'static files and both live entries')
PY
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
trap - ERR
echo "RELEASE_OK $REV"
