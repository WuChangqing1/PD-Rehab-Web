#!/usr/bin/env bash
# Run as the PD service user. Only stages files below the fixed staging root.
set -euo pipefail
umask 077
stage=/opt/pd-rehab/staging/training-face-20261104
app="$stage/PD-Rehab-Web"
py=/opt/pd-rehab/venv/bin/python
model=/opt/pd-rehab/models/causalnet
cd "$stage"
case "${1:-}" in
prepare)
  mkdir -p "$app" "$stage/bin" "$stage/db" "$stage/media" "$stage/outputs" "$stage/reports"
  tar -xf release.tar -C "$app"
  libs="$stage/media-runtime/usr/lib/x86_64-linux-gnu"
  for tool in ffmpeg ffprobe; do
    cat >"$stage/bin/$tool" <<EOF
#!/bin/sh
export LD_LIBRARY_PATH="$libs:$libs/pulseaudio:$libs/blas:$libs/lapack"
exec "$stage/media-runtime/usr/bin/$tool" "\$@"
EOF
    chmod 700 "$stage/bin/$tool"
  done
  "$stage/bin/ffmpeg" -hide_banner -encoders 2>/dev/null | grep -w libx264
  "$stage/bin/ffprobe" -version | sed -n '1p'
  if [[ ! -s secrets.env ]]; then
    printf 'JWT_SECRET=%s\nBOOTSTRAP_ADMIN_USERNAME=stageqa\nBOOTSTRAP_ADMIN_PASSWORD=%s\n' \
      "$("$py" -c 'import secrets; print(secrets.token_hex(32))')" \
      "$("$py" -c 'import secrets; print(secrets.token_hex(20))')" >secrets.env
  fi
  ;;
run)
  set -a
  source "$stage/secrets.env"
  # This PD model file is sourced without the production application environment.
  source "$model/runtime.env"
  set +a
  export PATH="$stage/bin:$PATH"
  export APP_ENV=staging DATABASE_URL="sqlite:///$stage/db/stage.db"
  export UPLOAD_DIR="$stage/media" OUTPUT_DIR="$stage/outputs" REPORT_DIR="$stage/reports"
  export TRAINING_VIDEO_ENABLED=true USE_GPU=false TORCH_NUM_THREADS=1
  export EXPERT_LLM_BASE_URL= EXPERT_LLM_API_KEY= EXPERT_LLM_MODEL=
  cd "$app/backend"
  "$py" -m alembic upgrade head
  # Launch exactly one process, loopback only. SSH forwarding is used for QA.
  exec flock -n "$stage/dispatcher.lock" "$py" -m uvicorn staging_app:app --host 127.0.0.1 --port 18193 --workers 1
  ;;
*) printf '%s\n' 'usage: training-face-staging.sh prepare|run' >&2; exit 2 ;;
esac
