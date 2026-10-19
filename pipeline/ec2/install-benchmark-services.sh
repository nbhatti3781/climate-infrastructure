#!/usr/bin/env bash
# Run only on the approved Ubuntu EC2 instance, after copying the saved repo.
# Installs services; does not start the benchmark or shutdown timer.
set -euo pipefail
if [[ "$(uname -s)" != Linux || "$EUID" != 0 ]]; then
  echo 'Run with sudo on the Ubuntu EC2 instance, not on the Mac.' >&2
  exit 1
fi
repo=/srv/climate-assessment
test -f "$repo/pipeline/process_state_assessment.py"
test -f "$repo/data/processed/national-current/manifest.json"
test -x "$repo/.venv-wildfire/bin/python"
id ubuntu >/dev/null
install -d -o ubuntu -g ubuntu "$repo/data/cache/national-current" \
  "$repo/data/processed/national-current/benchmarks/10" "$repo/data/benchmark-logs"
install -m 644 "$repo/pipeline/ec2/climate-delaware-benchmark.service" /etc/systemd/system/
cat > /etc/systemd/system/climate-benchmark-stop.service <<'EOF'
[Unit]
Description=Checkpoint Delaware benchmark and power off EC2

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl stop climate-delaware-benchmark.service
ExecStart=/usr/bin/sync
ExecStart=/usr/bin/systemctl --no-block poweroff
TimeoutStartSec=120
EOF
cat > /etc/systemd/system/climate-benchmark-stop.timer <<'EOF'
[Unit]
Description=Stop EC2 two hours after boot, including setup time

[Timer]
OnBootSec=2h
AccuracySec=1s
Unit=climate-benchmark-stop.service

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/climate-delaware-benchmark.service \
  /etc/systemd/system/climate-benchmark-stop.service /etc/systemd/system/climate-benchmark-stop.timer
echo 'Installed only. Verify EC2 shutdown behavior=stop and EBS DeleteOnTermination=false before arming.'
echo 'Arm early in setup: sudo systemctl enable --now climate-benchmark-stop.timer'
echo 'Start/resume after checks: sudo systemctl start climate-delaware-benchmark.service'
