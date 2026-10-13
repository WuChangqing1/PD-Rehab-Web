#!/usr/bin/env bash
# Authorized incremental release; no schema, environment or nginx changes.
set -euo pipefail
APP=/opt/pd-rehab/app/PD-Rehab-Web
WORK=/tmp/pd-ui-piano-20261013-19dba0f
BACKUP=/opt/pd-rehab/backups/ui-piano-20261013-19dba0f
REV=19dba0f5165b0c06104422437deb0a14654a5ce2
PY=/opt/pd-rehab/venv/bin/python
cd "$WORK"
echo '07f51685c5f66e0548ea786391d713ee7bfea5d170e118a4d01e33a2cd776d67  frontend.tar.gz' | sha256sum -c -
echo '465dcb6d857419d8ff16b6fa0e53818dc8b518e3bb7310fb60f0e4ebd0632a61  release.bundle' | sha256sum -c -
test "$(git -C "$APP" branch --show-current)" = main
test -z "$(git -C "$APP" status --porcelain)"
git -C "$APP" bundle verify "$WORK/release.bundle"
PREV=$(git -C "$APP" rev-parse HEAD)
git -C "$APP" fetch "$WORK/release.bundle" main
test "$(git -C "$APP" rev-parse FETCH_HEAD)" = "$REV"
git -C "$APP" merge-base --is-ancestor "$PREV" "$REV"
mkdir "$BACKUP"
printf '%s\n' "$PREV" > "$BACKUP/revision.txt"
cp /var/www/pd-rehab/dist/index.html "$BACKUP/index-root-before.html"
cp /var/www/pd-rehab/dist-under-path/index.html "$BACKUP/index-subpath-before.html"
tar -czf "$BACKUP/frontend-before.tar.gz" -C /var/www/pd-rehab dist dist-under-path
tar -czf "$BACKUP/uploads-before.tar.gz" -C /opt/pd-rehab/data uploads
"$PY" - "$BACKUP" <<'PY'
import sqlite3,json,sys,pathlib
dest=pathlib.Path(sys.argv[1])
src=sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro',uri=True)
copy=sqlite3.connect(dest/'pd.db')
src.backup(copy)
assert copy.execute('pragma quick_check').fetchone()[0]=='ok'
tables=[r[0] for r in copy.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
counts={t:copy.execute('select count(*) from "'+t+'"').fetchone()[0] for t in tables}
manifest={'table_counts':counts,'alembic':[r[0] for r in copy.execute('select version_num from alembic_version')]}
(dest/'data-before.json').write_text(json.dumps(manifest,indent=2))
print('WAL-aware backup:',json.dumps(manifest))
copy.close();src.close()
PY
mkdir "$WORK/staged"
tar -xzf "$WORK/frontend.tar.gz" -C "$WORK/staged"
test -f "$WORK/staged/dist/index.html"
test -f "$WORK/staged/dist-under-path/index.html"
grep -q '"/assets/' "$WORK/staged/dist/index.html"
grep -q '"/pd-rehab/assets/' "$WORK/staged/dist-under-path/index.html"
CODE_CHANGED=0
rollback() {
  rc=$?
  trap - ERR
  echo "Release failed (exit $rc), restoring previous code and entrypoints"
  if [ "$CODE_CHANGED" = 1 ]; then
    git -C "$APP" checkout --detach "$PREV"
    sudo -n systemctl restart pd-rehab-backend
  fi
  for pair in 'dist:index-root-before.html' 'dist-under-path:index-subpath-before.html'; do
    target=${pair%%:*}; source=${pair##*:}
    sudo -n install -m 644 "$BACKUP/$source" "/var/www/pd-rehab/$target/index.html.rollback"
    sudo -n mv -T "/var/www/pd-rehab/$target/index.html.rollback" "/var/www/pd-rehab/$target/index.html"
  done
  echo "Backup preserved: $BACKUP"
  exit "$rc"
}
trap rollback ERR
git -C "$APP" merge --ff-only FETCH_HEAD
CODE_CHANGED=1
cd "$APP/backend"
"$PY" - <<'PY'
from app.schemas.piano import PianoSessionCreate,NEW_RECIPE_BASE_MODES,DifficultyConfigSchema
for recipe,mode in NEW_RECIPE_BASE_MODES.items():
    PianoSessionCreate(mode=mode,recipe_id=recipe,difficulty=DifficultyConfigSchema(tempo_ceiling_bpm=66),input_source='SYNTHETIC_SELFTEST')
print('Production Python: all five new recipe schemas valid; no sessions created')
PY
sudo -n systemctl restart pd-rehab-backend
ready=0
for attempt in $(seq 1 30); do
  if curl -fsS --max-time 2 http://127.0.0.1:18086/api/system/health > "$WORK/health.json"; then ready=1; break; fi
  sleep 1
done
test "$ready" = 1
cat "$WORK/health.json"
for variant in dist dist-under-path; do
  # Preserve hashed assets needed by tabs opened before the release. The index
  # changes only after all new modules and samples have arrived.
  sudo -n rsync -a --exclude=index.html "$WORK/staged/$variant/" "/var/www/pd-rehab/$variant/"
  sudo -n chown -R www-data:www-data "/var/www/pd-rehab/$variant"
  sudo -n install -m 644 "$WORK/staged/$variant/index.html" "/var/www/pd-rehab/$variant/index.html.next"
  sudo -n mv -T "/var/www/pd-rehab/$variant/index.html.next" "/var/www/pd-rehab/$variant/index.html"
done
sudo -n nginx -t
test "$(git -C "$APP" rev-parse HEAD)" = "$REV"
test -z "$(git -C "$APP" status --porcelain)"
systemctl is-active pd-rehab-backend nginx
"$PY" - "$BACKUP" <<'PY'
import sqlite3,json,pathlib,sys
before=json.loads((pathlib.Path(sys.argv[1])/'data-before.json').read_text())
db=sqlite3.connect('file:/opt/pd-rehab/data/pd.db?mode=ro',uri=True)
after={t:db.execute('select count(*) from "'+t+'"').fetchone()[0] for t in before['table_counts']}
assert after==before['table_counts'],(before['table_counts'],after)
assert [r[0] for r in db.execute('select version_num from alembic_version')]==before['alembic']
print('All production table counts and schema revision unchanged:',json.dumps(after))
assert db.execute('pragma quick_check').fetchone()[0]=='ok'
PY
trap - ERR
echo "RELEASE_OK $REV backup=$BACKUP"
