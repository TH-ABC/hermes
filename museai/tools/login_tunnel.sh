#!/usr/bin/env bash
# Mở đường hầm để nút "Tự động nạp Mail | Password" trên dashboard VPS đăng nhập bằng IP máy này.
# Tự kết nối lại khi rớt. VPS dùng proxy socks5://127.0.0.1:1080 (MUSE_LOGIN_PROXY).
# Chạy nền:  nohup tools/login_tunnel.sh >/dev/null 2>&1 &     (caffeinate -i để máy không ngủ)
while true; do
  ssh -N -R 1080 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes "${VPS_HOST:-reclip-vps}"
  sleep 3
done
