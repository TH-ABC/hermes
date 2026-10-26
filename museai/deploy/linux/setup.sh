#!/usr/bin/env bash
# setup.sh - one-shot install of the MuseAI bridge pool on Ubuntu 22.04/24.04
# Run from the repo root as a sudo-capable user:  sudo bash deploy/linux/setup.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SVC_USER="${MUSE_USER:-muse}"
PORT="${MUSEAI_PORT:-8770}"

apt-get update -y
apt-get install -y python3 python3-venv python3-pip fonts-noto-cjk fonts-noto-color-emoji

id "$SVC_USER" >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin "$SVC_USER"
chown -R "$SVC_USER":"$SVC_USER" "$APP_DIR"
install -d -m 700 -o "$SVC_USER" -g "$SVC_USER" "$APP_DIR/cookies"
find "$APP_DIR/cookies" -name '*.json' -exec chmod 600 {} \; -exec chown "$SVC_USER":"$SVC_USER" {} \;

sudo -u "$SVC_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$SVC_USER" "$APP_DIR/.venv/bin/pip" install -q --upgrade pip
sudo -u "$SVC_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/deploy/windows/requirements.txt"
"$APP_DIR/.venv/bin/python" -m playwright install-deps chromium
sudo -u "$SVC_USER" "$APP_DIR/.venv/bin/python" -m playwright install chromium

if [ ! -f /etc/musebridge.env ]; then
  cat > /etc/musebridge.env <<ENV
# MuseAI bridge pool settings
MUSEAI_PORT=$PORT
# Bind to the Tailscale IP (tailscale ip -4) so the API is not on the public internet
MUSEAI_HOST=$(command -v tailscale >/dev/null && tailscale ip -4 | head -1 || echo 127.0.0.1)
MUSEAI_PER_ACCOUNT=2
MUSE_API_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')
ENV
  chmod 600 /etc/musebridge.env
fi

sed "s#__APP_DIR__#$APP_DIR#g; s#__USER__#$SVC_USER#g" "$APP_DIR/deploy/linux/musebridge.service" \
  > /etc/systemd/system/musebridge.service
systemctl daemon-reload
systemctl enable --now musebridge
sleep 5
systemctl --no-pager status musebridge | head -15
echo "Done. Logs: journalctl -u musebridge -f   |   API key: sudo grep MUSE_API_KEY /etc/musebridge.env"
