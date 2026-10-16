#!/usr/bin/env bash
# Single authorized release. SHA256SUMS and REV are uploaded from the tested main.
set -euo pipefail
umask 077
REV=$1
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-guided-song-20261016
BACKUP=/opt/pd-rehab/backups/guided-song-20261016
PY=/opt/pd-rehab/venv/bin/python
cd "$WORK"
sha256sum -c SHA256SUMS
test "$(git -C "$APP" branch --show-current)" = main
test -z "$(git -C "$APP" status --porcelain)"
test ! -e "$BACKUP"
PREV=$(git -C "$APP" rev-parse HEAD)
git -C "$APP" bundle verify "$WORK/release.bundle"
git -C "$APP" fetch "$WORK/release.bundle" main
test "$(git -C "$APP" rev-parse FETCH_HEAD)" = "$REV"
git -C "$APP" merge-base --is-ancestor "$PREV" "$REV"
mkdir "$BACKUP"
printf '%s\n' "$PREV" > "$BACKUP/revision.txt"
cp /var/www/pd-rehab/dist/index.html "$BACKUP/root-index.html"
cp /var/www/pd-rehab/dist-under-path/index.html "$BACKUP/subpath-index.html"
cp /etc/nginx/snippets/pd-rehab-locations.conf "$BACKUP/pd-rehab-locations.conf"
cp /etc/nginx/conf.d/pd-rehab.conf "$BACKUP/pd-rehab.conf"
mkdir "$WORK/staged"
tar -xzf "$WORK/frontend.tar.gz" -C "$WORK/staged"
test -f "$WORK/staged/dist/index.html"
test -f "$WORK/staged/dist-under-path/index.html"
STOPPED=0
CODE_CHANGED=0
rollback() {
  rc=$?
  trap - ERR
  if [ "$CODE_CHANGED" = 1 ]; then git -C "$APP" checkout --detach "$PREV"; fi
  sudo -n install -m 644 "$BACKUP/pd-rehab-locations.conf" /etc/nginx/snippets/pd-rehab-locations.conf
  sudo -n install -m 644 "$BACKUP/pd-rehab.conf" /etc/nginx/conf.d/pd-rehab.conf
  sudo -n install -m 644 "$BACKUP/root-index.html" /var/www/pd-rehab/dist/index.html
  sudo -n install -m 644 "$BACKUP/subpath-index.html" /var/www/pd-rehab/dist-under-path/index.html
  sudo -n nginx -t && sudo -n systemctl reload nginx
  if [ "$STOPPED" = 1 ]; then sudo -n systemctl restart pd-rehab-backend; fi
  echo "Release failed; previous code and entries restored; additive schema retained; backup preserved at $BACKUP"
  exit "$rc"
}
trap rollback ERR
sudo -n systemctl stop pd-rehab-backend
STOPPED=1
"$PY" "$WORK/deploy_checks.py" snapshot
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
cd "$APP/backend"
"$PY" - <<'PY'
from app.core.config import settings
from app.db.session import DATABASE_URL
from app.services.live_emotion_service import capabilities
assert DATABASE_URL == 'sqlite:////opt/pd-rehab/data/pd.db', DATABASE_URL
assert settings.app_env == 'production'
assert settings.emotion_simulation_mode is False
assert capabilities()['status']=='MODEL_NOT_CONFIGURED'
print('Production configuration verified: simulation off, real model not configured')
PY
"$PY" -m alembic upgrade head
"$PY" "$WORK/deploy_checks.py" stage-nginx
sudo -n install -m 644 "$WORK/pd-rehab-locations.conf" /etc/nginx/snippets/pd-rehab-locations.conf
sudo -n install -m 644 "$WORK/pd-rehab.conf" /etc/nginx/conf.d/pd-rehab.conf
sudo -n nginx -t
sudo -n systemctl start pd-rehab-backend
ready=0
for attempt in $(seq 1 30); do
  if curl -fsS --max-time 2 http://127.0.0.1:18086/api/system/health > "$WORK/health.json"; then ready=1; break; fi
  sleep 1
done
test "$ready" = 1
for variant in dist dist-under-path; do
  sudo -n rsync -a --exclude=index.html "$WORK/staged/$variant/" "/var/www/pd-rehab/$variant/"
  sudo -n chown -R www-data:www-data "/var/www/pd-rehab/$variant"
  sudo -n install -m 644 "$WORK/staged/$variant/index.html" "/var/www/pd-rehab/$variant/index.html.next"
  sudo -n mv -T "/var/www/pd-rehab/$variant/index.html.next" "/var/www/pd-rehab/$variant/index.html"
done
sudo -n systemctl reload nginx
"$PY" "$WORK/deploy_checks.py" verify-assets
"$PY" "$WORK/deploy_checks.py" verify-data
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
trap - ERR
"$PY" - "$REV" <<'PY'
import json,sys,pathlib
pathlib.Path('/tmp/pd-guided-song-20261016/release-ok.json').write_text(json.dumps({'revision':sys.argv[1],'deployment_verified':True}))
PY
echo "RELEASE_OK $REV"
