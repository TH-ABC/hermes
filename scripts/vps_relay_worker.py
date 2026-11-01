#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
VPS RELAY WORKER — CLIENT SIÊU NHẸ CHO MÁY CHỦ VPS (KHÔNG CẦN CÀI HERMES)
========================================================================================
- Yêu cầu: Python 3.6+ (Chỉ dùng thư viện chuẩn có sẵn, KHÔNG CẦN pip install).
- Tiêu thụ: ~10MB RAM, 0% CPU, 0 Token khi đứng chờ (Zero-Token Idle).
- Cơ chế 2 chiều:
  1. Luồng 1 (Polling 60s): Tự động quét nhận lệnh từ Sever Hermes mỗi 1 phút.
  2. Luồng 2 (Direct Push - Cổng 8995): Cho phép Sever Hermes ping/bắn lệnh trực tiếp tức thì (<1s).
  3. Tự động thực thi lệnh (PowerShell/CMD/Bash) và gửi báo cáo kết quả nghiệm thu về Zalo qua Hermes.
========================================================================================
"""

import os
import sys
import time
import json
import socket
import platform
import argparse
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Cấu hình mã hóa UTF-8 cho console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [VPS-Worker] {msg}", flush=True)


def get_system_info() -> dict:
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "os": platform.system()
    }


class RelayConfig:
    server_url = "http://127.0.0.1:8998"
    vps_id = "vps-main"
    poll_interval = 60
    listen_port = 8995
    enable_listen = True


def execute_shell_command(command: str, timeout: int = 300) -> dict:
    """Thực thi lệnh shell an toàn trên cả Windows (PowerShell/CMD) và Linux (Bash)."""
    log(f"⚡ Đang thực thi lệnh: {command}")
    start_time = time.time()
    is_win = platform.system() == "Windows"

    try:
        if is_win:
            # Ưu tiên powershell trên Windows nếu có
            cmd_args = ["powershell", "-NoProfile", "-Command", command]
        else:
            cmd_args = ["bash", "-c", command]

        proc = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        duration = round(time.time() - start_time, 2)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()

        combined_output = out
        if err:
            combined_output = f"{out}\n[STDERR]: {err}".strip() if out else err

        status = "success" if proc.returncode == 0 else "failed"
        log(f"✅ Hoàn tất ({status}) trong {duration}s | ExitCode: {proc.returncode}")
        return {
            "status": status,
            "exit_code": proc.returncode,
            "output": combined_output or "(Lệnh đã chạy thành công nhưng không có output text)",
            "duration": duration
        }
    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 2)
        log(f"⏱️ Quá thời gian timeout ({timeout}s)!")
        return {
            "status": "timeout",
            "exit_code": -1,
            "output": f"Lỗi: Quá thời gian chờ ({timeout}s). Lệnh bị hủy bỏ.",
            "duration": duration
        }
    except Exception as e:
        duration = round(time.time() - start_time, 2)
        log(f"❌ Lỗi ngoại lệ: {e}")
        return {
            "status": "error",
            "exit_code": -2,
            "output": f"Lỗi hệ thống khi chạy lệnh: {e}",
            "duration": duration
        }


def poll_and_execute_once():
    """Gửi một nhịp tim (Heartbeat) và nhận lệnh nếu có từ Sever Hermes."""
    url = f"{RelayConfig.server_url}/api/vps/poll?vps_id={RelayConfig.vps_id}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "VPSRelayWorker/1.0", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        if not data.get("ok"):
            return

        if data.get("has_task"):
            task = data.get("task", {})
            task_id = task.get("id")
            cmd = task.get("command")
            log(f"📥 Nhận được chỉ thị mới từ Hermes (Task ID: {task_id}): {cmd}")

            # Thực thi
            res = execute_shell_command(cmd)

            # Gửi kết quả về Hermes
            res_payload = {
                "task_id": task_id,
                "vps_id": RelayConfig.vps_id,
                "status": res["status"],
                "exit_code": res["exit_code"],
                "output": res["output"],
                "duration": res["duration"]
            }
            res_url = f"{RelayConfig.server_url}/api/vps/result"
            post_req = urllib.request.Request(
                res_url,
                data=json.dumps(res_payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(post_req, timeout=15) as p_resp:
                pass
            log(f"📤 Đã gửi báo cáo kết quả Task {task_id} về Hermes thành công!")
        else:
            log("💓 Nhịp tim OK — Không có lệnh chờ.")

    except urllib.error.URLError as ue:
        log(f"⚠️ Không thể kết nối tới Hermes ({RelayConfig.server_url}): {ue.reason}")
    except Exception as e:
        log(f"⚠️ Lỗi xử lý poll: {e}")


def poller_thread_loop():
    """Vòng lặp quét ngầm chu kỳ 60s."""
    log(f"🚀 Bắt đầu luồng Polling: Chu kỳ {RelayConfig.poll_interval}s quét 1 lần.")
    while True:
        try:
            poll_and_execute_once()
        except Exception as e:
            log(f"Lỗi ngoài ý muốn trong Poller: {e}")
        time.sleep(RelayConfig.poll_interval)


class DirectPushHandler(BaseHTTPRequestHandler):
    """Bộ thu tín hiệu Ping / Push trực tiếp từ Sever Hermes trên Cổng 8995."""
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == "/execute" or self.path == "/api/execute" or self.path == "/ping":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                cmd = payload.get("command", "")
                task_id = payload.get("id") or payload.get("task_id") or f"direct_{int(time.time())}"
                
                if not cmd:
                    self._send_json({"ok": False, "error": "Thiếu lệnh command"}, 400)
                    return

                log(f"🚀 [DIRECT-PUSH] Nhận lệnh tức thì từ Hermes: {cmd}")
                
                # Thực thi đồng bộ hoặc bất đồng bộ
                res = execute_shell_command(cmd)

                # Gửi phản hồi HTTP cho Hermes
                self._send_json({
                    "ok": True,
                    "task_id": task_id,
                    "status": res["status"],
                    "output": res["output"],
                    "duration": res["duration"]
                })

                # Gửi thêm kết quả về Hermes qua POST /api/vps/result
                try:
                    res_payload = {
                        "task_id": task_id,
                        "vps_id": RelayConfig.vps_id,
                        "status": res["status"],
                        "exit_code": res["exit_code"],
                        "output": res["output"],
                        "duration": res["duration"]
                    }
                    post_req = urllib.request.Request(
                        f"{RelayConfig.server_url}/api/vps/result",
                        data=json.dumps(res_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(post_req, timeout=5) as resp:
                        pass
                except Exception:
                    pass
                return

            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/health", "/status"):
            self._send_json({
                "ok": True,
                "service": "VPS Relay Worker",
                "vps_id": RelayConfig.vps_id,
                "system": get_system_info(),
                "server_url": RelayConfig.server_url,
                "poll_interval": RelayConfig.poll_interval
            })
            return
        self.send_response(404)
        self.end_headers()

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


def start_direct_listener():
    """Khởi động Webhook listener cục bộ trên cổng 8995."""
    try:
        server = HTTPServer(("0.0.0.0", RelayConfig.listen_port), DirectPushHandler)
        log(f"📡 Webhook Push Listener sẵn sàng trên cổng {RelayConfig.listen_port} (0.0.0.0:{RelayConfig.listen_port})")
        server.serve_forever()
    except Exception as e:
        log(f"⚠️ Không thể mở Webhook listener cổng {RelayConfig.listen_port} ({e}) — Chế độ Polling vẫn hoạt động 100%!")


def main():
    parser = argparse.ArgumentParser(description="VPS Relay Worker — Client siêu nhẹ 1 luồng cho VPS")
    parser.add_argument("--server", type=str, default="http://127.0.0.1:8998", help="URL Hermes Receiver (ví dụ http://192.168.1.112:8998 hoặc domain)")
    parser.add_argument("--vps-id", type=str, default="vps-main", help="Tên định danh của VPS này (mặc định: vps-main)")
    parser.add_argument("--interval", type=int, default=60, help="Chu kỳ quét nhận lệnh (giây, mặc định: 60s)")
    parser.add_argument("--port", type=int, default=8995, help="Cổng Webhook nhận Ping trực tiếp (mặc định: 8995)")
    parser.add_argument("--no-listen", action="store_true", help="Tắt Webhook listener, chỉ dùng chế độ Polling")

    args = parser.parse_args()

    RelayConfig.server_url = args.server.rstrip("/")
    RelayConfig.vps_id = args.vps_id
    RelayConfig.poll_interval = args.interval
    RelayConfig.listen_port = args.port
    RelayConfig.enable_listen = not args.no_listen

    log("=================================================================")
    log("🚀 KHỞI ĐỘNG VPS RELAY WORKER (CLIENT SIÊU NHẸ 24/7)")
    log(f"📍 Định danh VPS: {RelayConfig.vps_id}")
    log(f"🌐 Máy chủ Hermes: {RelayConfig.server_url}")
    log(f"⏱️ Chu kỳ quét lệnh (Polling): Mỗi {RelayConfig.poll_interval} giây (1 phút)")
    log(f"📡 Chế độ Push trực tiếp: {'BẬT (Cổng ' + str(RelayConfig.listen_port) + ')' if RelayConfig.enable_listen else 'TẮT'}")
    log(f"💻 Hệ điều hành: {platform.system()} ({platform.platform()})")
    log("=================================================================")

    # Luồng 1: Chạy Webhook Listener (nếu bật)
    if RelayConfig.enable_listen:
        t_listener = threading.Thread(target=start_direct_listener, daemon=True)
        t_listener.start()

    # Luồng chính: Chạy Poller quét lệnh định kỳ
    poller_thread_loop()


if __name__ == "__main__":
    main()
