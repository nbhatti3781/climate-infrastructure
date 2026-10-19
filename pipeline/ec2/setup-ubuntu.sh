#!/usr/bin/env bash
# Future approved EC2 only. No EC2/AWS API calls; no processing is started.
set -euo pipefail
if [[ "$(uname -s)" != Linux || "$EUID" != 0 ]]; then
  echo 'Run with sudo on the approved Ubuntu EC2 instance, not the Mac.' >&2
  exit 1
fi
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]]
repo=/srv/climate-assessment
test -f "$repo/pipeline/requirements-wildfire.txt"
test -f "$repo/data/processed/national-current/manifest.json"
test ! -L "$repo"
free_bytes=$(df --output=avail -B1 "$repo" | tail -n1 | tr -d ' ')
(( free_bytes > 10 * 1024 * 1024 * 1024 ))
# The independent AWS stop schedule must already be armed by the operator.
test -f "$repo/data/benchmark-logs/external-stop-verification.json"
# Normalize remote transfer ownership, including cached mode-0600 files.
# Do not follow symlinks; content hashes remain unchanged.
chown -R --no-dereference ubuntu:ubuntu "$repo"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip \
  ca-certificates curl time gdal-bin libgeos-c1t64 libproj25
if [[ ! -x "$repo/.venv-wildfire/bin/python" ]]; then
  sudo -u ubuntu python3 -m venv "$repo/.venv-wildfire"
fi
bash "$repo/pipeline/ec2/install-benchmark-services.sh"
systemctl enable --now climate-benchmark-stop.timer
sudo -u ubuntu "$repo/.venv-wildfire/bin/python" -m pip install --only-binary=:all: \
  -r "$repo/pipeline/requirements-wildfire.txt"
sudo -u ubuntu "$repo/.venv-wildfire/bin/python" -m unittest discover -s "$repo/pipeline" -p 'test_*.py'
echo 'Dependencies and services prepared. No benchmark started.'
echo 'Complete disconnect/restart validation before permitting laptop shutdown.'
