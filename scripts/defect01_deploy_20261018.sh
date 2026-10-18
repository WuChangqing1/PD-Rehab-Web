#!/usr/bin/env bash
# Additive identifier migration; preserve medical records and runtime models.
set -euo pipefail
umask 077
REV=$1
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-defect01-20261018-r2
BACKUP=/opt/pd-rehab/backups/defect01-20261018-r2
PYTHON=/opt/pd-rehab/venv/bin/python
cd "$WORK"
sha256sum -c SHA256SUMS
test "$(git -C "$APP" branch --show-current)" = main
test -z "$(git -C "$APP" status --porcelain)"
PREV=$(git -C "$APP" rev-parse HEAD)
test "$PREV" = 4823889c9365ff82097cda7e4b07bf9ec5b752d0
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
  set +e
  recovery_failed=0
  if [ "$CODE_CHANGED" = 1 ]; then
    if git -C "$APP" checkout --detach "$PREV"; then
      git -C "$APP" update-ref refs/heads/main "$PREV" "$REV" || recovery_failed=1
      git -C "$APP" checkout main || recovery_failed=1
    else
      recovery_failed=1
    fi
  fi
  # Keep the additive allocator table; never discard allocations after publication.
  sudo -n install -m 644 "$BACKUP/root-index.html" /var/www/pd-rehab/dist/index.html || recovery_failed=1
  sudo -n install -m 644 "$BACKUP/subpath-index.html" /var/www/pd-rehab/dist-under-path/index.html || recovery_failed=1
  sudo -n systemctl restart pd-rehab-backend || recovery_failed=1
  echo "Release failed. Recovery failures=$recovery_failed; database backup retained at $BACKUP"
  exit "$rc"
}
trap rollback ERR
sudo -n systemctl stop pd-rehab-backend
"$PYTHON" "$WORK/database-guard.py" before
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
cd "$APP/backend"
DATABASE_URL=sqlite:////opt/pd-rehab/data/pd.db "$PYTHON" -m alembic upgrade head
cd "$WORK"
"$PYTHON" "$WORK/database-guard.py" after
sudo -n systemctl start pd-rehab-backend
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
"$PYTHON" - <<'PY'
import pathlib,hashlib,json,urllib.request
work=pathlib.Path('/tmp/pd-defect01-20261018-r2')
manifest=json.loads((work/'assets.json').read_text())
for name,digest in manifest.items():
    assert hashlib.sha256((pathlib.Path('/var/www/pd-rehab')/name).read_bytes()).hexdigest()==digest,name
for variant,base in [('dist','http://127.0.0.1:18085/'),('dist-under-path','https://ccqspace.site/pd-rehab/')]:
    with urllib.request.urlopen(base,timeout=20) as r:
        assert hashlib.sha256(r.read()).hexdigest()==manifest[variant+'/index.html']
    with urllib.request.urlopen(base+'api/system/health',timeout=20) as r:
        assert json.load(r)['status']=='ok'
result={'assets_verified':len(manifest),'both_entry_points':'ok','model_config_unchanged':True,'test_patients_created_in_production':False}
(work/'release-ok.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
PY
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
trap - ERR
echo "RELEASE_OK $REV"
