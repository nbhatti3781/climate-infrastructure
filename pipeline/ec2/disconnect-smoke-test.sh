#!/usr/bin/env bash
# Approved Ubuntu EC2 instance only. Synthetic heartbeat; no hazard processing.
set -euo pipefail
if [[ "$(uname -s)" != Linux || "$EUID" != 0 ]]; then
  echo 'Run with sudo on the Ubuntu EC2 instance.' >&2
  exit 1
fi
systemctl is-active --quiet climate-benchmark-stop.timer
log=/srv/climate-assessment/data/benchmark-logs/disconnect-heartbeat.log
test -d "$(dirname "$log")"
systemd-run --unit=climate-disconnect-smoke --uid=ubuntu --gid=ubuntu \
  --property=Type=exec --property=RuntimeMaxSec=180 \
  --property="StandardOutput=append:$log" \
  /bin/bash -c 'for i in {1..12}; do date -u +%FT%TZ; sleep 10; done'
echo 'Disconnect now, reconnect after at least 30 seconds, and inspect:'
echo "  cat $log"
echo '  sudo systemctl show climate-disconnect-smoke -p Result -p ExecMainStatus'
echo 'Pass only when heartbeat timestamps span the disconnected interval.'
