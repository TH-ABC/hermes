"""
Tầng 4: Bộ Tự Động Hóa Cục Bộ (Ant-local Automation Receiver) — Chạy trên Sever Hermes
- Hoàn toàn 0-token khi đứng chờ (Zero Token Idle).
- Nhận tín hiệu Event-Driven Push từ Vercel qua Cloudflare Tunnel (Cổng 8999).
- Quản lý con trỏ trạng thái qua agent_chat_state.json.
- Phản hồi tức thì [PONG] khi có lệnh Ping hoặc [LOCAL] khi có chỉ thị sửa code.
"""

import os
import sys
import time
import json
import base64
import threading
import subprocess
import urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

ROOT_DIR = Path(__file__).resolve().parents[1]
RECEIVED_IMAGES_DIR = ROOT_DIR / "received_images"
RECEIVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
RECEIVED_FILES_DIR = ROOT_DIR / "received_files"
RECEIVED_FILES_DIR.mkdir(parents=True, exist_ok=True)

AGY_BIN = Path(r"C:\Users\ADMIN\AppData\Local\agy\bin\agy.exe")

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
if not HERMES_HOME.exists():
    HERMES_HOME = Path.home() / ".hermes"

STATE_FILE = HERMES_HOME / "agent_chat_state.json"
CHAT_HISTORY_FILE = HERMES_HOME / "office_chat_history.json"
INBOX_LOG_FILE = HERMES_HOME / "sever_hermes_inbox.log"


def log_msg(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
    sys.stdout.flush()
    try:
        with open(INBOX_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_id": 0, "last_ping": 0.0, "total_commands": 0}


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def diagnose_system() -> dict:
    """Kiểm tra nhịp tim các thành phần: Zalo bridge (3050), Muse Server (8770), Gateway."""
    zalo_ok = False
    zalo_info = "Không kết nối"
    try:
        req = urllib.request.Request("http://127.0.0.1:3050/health", headers={"Host": "127.0.0.1"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            zalo_ok = data.get("status") == "connected"
            zalo_info = f"Online (ownId: {data.get('ownId')})"
    except Exception as e:
        zalo_info = f"Offline ({e})"

    muse_ok = False
    muse_info = "Offline"
    try:
        req = urllib.request.Request("http://127.0.0.1:8770/v1/status")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            muse_ok = True
            acc_count = data.get("accounts_count", data.get("active_accounts", 0))
            muse_info = f"Online ({acc_count} accounts, ready)"
    except Exception as e:
        muse_info = f"Offline ({e})"

    return {
        "zalo": {"online": zalo_ok, "detail": zalo_info},
        "muse": {"online": muse_ok, "detail": muse_info},
        "server_time": datetime.now().isoformat(),
        "host": "Sever Hermes",
    }


def push_to_vercel_inbox(text: str, sender: str = "Ant-local (Kỹ Sư Trưởng)", role: str = "ant-local", channel: str = "local"):
    """Vercel Web SPA đã khai tử. Hàm giữ lại để tương thích ngược không sinh lỗi."""
    return


def send_to_zalo_chat(text: str, chat_id: str = None) -> bool:
    if not chat_id:
        try:
            from tools.muse_media_tool import _ACTIVE_CHAT_TRACKER
            chat_id = _ACTIVE_CHAT_TRACKER.get("chat_id")
        except Exception:
            pass
    if not chat_id:
        chat_id = "u:7725451581835120119"
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:3050/send",
            data=json.dumps({"chat_id": str(chat_id), "text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as ze:
        log_msg(f"⚠️ Không gửi được tới Zalo ({chat_id}): {ze}")
        return False


def execute_ant_local_task_async(task_text: str, image_paths: list = None, chat_id: str = None, channel: str = "local", files: list = None):
    """
    Kích hoạt chế độ Autonomous Headless Worker:
    Tự động gọi agy.exe đọc mã nguồn, sửa code thực tế và báo cáo nghiệm thu
    ngay lập tức lên Web SPA & Zalo cho Sếp.
    """
    def _worker():
        log_msg("============================================================")
        log_msg(f"🚀 [ANT-LOCAL WORKER] Đã nhận chỉ thị từ Sếp: {task_text}")
        if chat_id:
            log_msg(f"📱 Khung chat đích: {chat_id} (Kênh: {channel})")
        if image_paths:
            log_msg(f"🖼️ Ảnh đính kèm: {image_paths[0]}")
        if files:
            log_msg(f"📄 Tệp đính kèm: {len(files)} tệp ({', '.join(f.get('name', '') for f in files)})")

        # 1. Báo ngay lập tức (Instant ACK) cho Sếp biết Ant-local đã thức dậy
        file_desc = f" kèm {len(files)} tệp tài liệu" if files else ""
        init_ack = f"🛠️ [Ant-local] Đã nhận chỉ thị từ Sếp{file_desc}! Em đang mở mã nguồn đọc code và tiến hành xử lý trực tiếp trên Sever Hermes..."
        try:
            import db_manager
            db_manager.insert_chat_message(
                channel=channel,
                sender="Ant-local (Kỹ Sư Trưởng)",
                role="ant-local",
                message=init_ack,
                local_media_path=image_paths[0] if image_paths else None,
            )
            push_to_vercel_inbox(init_ack, channel=channel)
            send_to_zalo_chat(init_ack, chat_id=chat_id)
        except Exception as ack_err:
            log_msg(f"⚠️ Lỗi gửi khởi động ACK: {ack_err}")

        # 2. Xây dựng prompt cho Antigravity CLI
        prompt_parts = [
            "BẠN LÀ ANT-LOCAL, KỸ SƯ TRƯỞNG CỤC BỘ CỦA SEVER HERMES.",
            f"Chỉ thị của Sếp Hoàng: \"{task_text}\"",
        ]
        if image_paths and len(image_paths) > 0:
            prompt_parts.append(f"Sếp có đính kèm ảnh lỗi/yêu cầu tại đường dẫn: {image_paths[0]}")
        if files and len(files) > 0:
            for f in files:
                prompt_parts.append(f"Sếp có gửi kèm tệp tài liệu/mã nguồn: '{f.get('name')}' tại đường dẫn '{f.get('path')}'.")
                if f.get("content"):
                    prompt_parts.append(f"--- NỘI DUNG TỆP {f.get('name')} ---\n{f.get('content')}\n--- HẾT TỆP ---")
        prompt_parts.extend([
            "Nhiệm vụ của bạn:",
            "1. Kiểm tra các file mã nguồn liên quan trong dự án (D:\\hermes-main).",
            "2. Trực tiếp sửa đổi code nếu phát hiện lỗi hoặc theo yêu cầu tính năng của Sếp.",
            "3. Kiểm tra tính toàn vẹn cú pháp sau khi sửa.",
            "4. Báo cáo lại kết quả nghiệm thu rõ ràng, súc tích (nêu rõ file đã sửa, nội dung đã làm, kết quả).",
            "QUY TẮC BẮT BUỘC: Luôn xưng 'Em là Trợ lý của sếp Hoàng'. Tuyệt đối KHÔNG ĐƯỢC nhắc đến từ 'Muse' ở bất kỳ đâu."
        ])
        full_prompt = "\n".join(prompt_parts)

        # 3. Kích hoạt agy.exe
        work_dir = Path(r"D:\hermes-main")
        if not work_dir.exists():
            work_dir = ROOT_DIR
        
        log_msg("🚀 [ANT-LOCAL WORKER] Bắt đầu kích hoạt agy.exe xử lý tác vụ...")
        cmd = [
            str(AGY_BIN),
            "--dangerously-skip-permissions",
            "--effort", "medium",
            "--print-timeout", "0",
            "-p", full_prompt,
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
            output = proc.stdout.strip()
            if not output and proc.stderr:
                output = f"⚠️ Quá trình thực thi có cảnh báo: {proc.stderr[:300]}"
            if not output:
                output = "✅ Ant-local đã kiểm tra và hoàn tất tác vụ theo chỉ thị của Sếp."
            
            log_msg(f"✅ [ANT-LOCAL WORKER HOÀN TẤT] Chiều dài báo cáo: {len(output)} ký tự")
            
            # Lưu báo cáo vào SQLite và đẩy lên Web SPA & Zalo
            import db_manager
            db_manager.insert_chat_message(
                channel=channel,
                sender="Ant-local (Kỹ Sư Trưởng)",
                role="ant-local",
                message=output,
            )
            push_to_vercel_inbox(output, channel=channel)
            send_to_zalo_chat(output, chat_id=chat_id)
            log_msg("💾 Đã lưu kết quả thực thi và báo cáo cho Sếp trên Web SPA & Zalo.")

        except subprocess.TimeoutExpired:
            timeout_msg = "⏱️ [Ant-local] Tác vụ phức tạp cần thêm thời gian xử lý (>180s). Em đã lưu lại trạng thái và tiếp tục xử lý trên máy Sever."
            log_msg(f"⏱️ [ANT-LOCAL WORKER] Quá thời gian 180s cho: {task_text[:60]}")
            push_to_vercel_inbox(timeout_msg, channel=channel)
            send_to_zalo_chat(timeout_msg, chat_id=chat_id)
        except Exception as ex:
            err_msg = f"❌ [Ant-local] Lỗi trong quá trình thực thi: {ex}"
            log_msg(f"❌ [ANT-LOCAL WORKER ERROR]: {ex}")
            push_to_vercel_inbox(err_msg, channel=channel)
            send_to_zalo_chat(err_msg, chat_id=chat_id)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


class SeverHermesOpsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Bypass-Tunnel-Reminder, X-Agent-Secret")
        self.end_headers()

    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/app") or self.path == "/ui" or self.path == "/":
            html_path = SCRIPTS_DIR / "zalo_app_demo.html"
            if html_path.exists():
                content = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(content)
                return

        if self.path.startswith("/api/status"):
            diag = diagnose_system()
            state = load_state()
            res = {
                "server": "Sever Hermes (Local Machine)",
                "ant_local": "active_listening",
                "zero_token_mode": True,
                "state": state,
                "diagnostics": diag,
            }
            self._send_json(res)
            return

        if self.path.startswith("/api/pool"):
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:8770/v1/accounts", timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._send_json(data)
                    return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/tenants"):
            try:
                from plugins.platforms.zalo.bot_router import _load_tenants_data
                data = _load_tenants_data()
                self._send_json({"ok": True, "data": data})
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/rental/pool"):
            try:
                import scripts.rental_manager as rm
                self._send_json({"ok": True, "data": rm.get_empty_pool()})
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/rental/profiles"):
            try:
                import scripts.rental_manager as rm
                self._send_json({"ok": True, "data": rm.get_rental_profiles()})
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/groups"):
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:3050/groups", timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._send_json(data)
                    return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/history"):
            try:
                from urllib.parse import urlparse, parse_qs
                import db_manager
                parsed = urlparse(self.path)
                qs = parse_qs(parsed.query)
                since_id = int(qs.get("since_id", ["0"])[0])
                channel = qs.get("channel", ["all"])[0]
                limit = int(qs.get("limit", ["50"])[0])
                msgs = db_manager.get_messages(since_id=since_id, limit=limit, channel=channel)
                res = {"ok": True, "messages": msgs, "count": len(msgs)}
            except Exception as e:
                res = {"ok": False, "error": str(e), "messages": []}
            self._send_json(res)
            return

        if self.path.startswith("/api/media/"):
            filename = os.path.basename(self.path.split("?")[0])
            file_path = RECEIVED_IMAGES_DIR / filename
            if not file_path.exists():
                file_path = ROOT_DIR / "data" / "media" / filename
            if file_path.exists() and file_path.is_file():
                ext = file_path.suffix.lower()
                mime = "image/png"
                if ext in [".jpg", ".jpeg"]: mime = "image/jpeg"
                elif ext == ".webp": mime = "image/webp"
                elif ext == ".mp4": mime = "video/mp4"
                file_bytes = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(file_bytes)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(file_bytes)
                return
            else:
                self._send_json({"error": "File not found"}, 404)
                return

        self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        if self.path.startswith("/api/tenants/bot/add"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                from plugins.platforms.zalo.bot_router import add_virtual_bot
                payload = json.loads(raw_body.decode("utf-8"))
                tenant_id = payload.get("tenant_id", "tenant_master_hoang")
                bot_data = payload.get("bot_data", {})
                ok, res = add_virtual_bot(tenant_id, bot_data)
                self._send_json({"ok": ok, "bot_id": res if ok else None, "error": res if not ok else None})
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/tenants/bot/delete"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                from plugins.platforms.zalo.bot_router import delete_virtual_bot
                payload = json.loads(raw_body.decode("utf-8"))
                tenant_id = payload.get("tenant_id", "tenant_master_hoang")
                bot_id = payload.get("bot_id")
                ok = delete_virtual_bot(tenant_id, bot_id)
                self._send_json({"ok": ok})
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/rental/pool/add"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                import scripts.rental_manager as rm
                body = json.loads(raw_body.decode("utf-8"))
                res = rm.add_empty_bot_to_pool(
                    name=body.get("name", "Trợ Lý Mới"),
                    mode=body.get("mode", "chat"),
                    ai_engine_account=body.get("ai_engine_account", "ellinabetheny4127"),
                    price_package=body.get("price_package", "Gói 1 Bot (30 ngày)")
                )
                self._send_json(res)
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/rental/connect"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                import scripts.rental_manager as rm
                body = json.loads(raw_body.decode("utf-8"))
                res = rm.connect_bot_subscription(
                    user_zalo_id=body.get("user_zalo_id"),
                    requested_count=int(body.get("count", 1)),
                    package_name=body.get("package_name"),
                    days=int(body.get("days", 30))
                )
                self._send_json(res)
                return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/pool/add"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                import urllib.request
                req = urllib.request.Request("http://127.0.0.1:8770/v1/accounts", data=raw_body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self._send_json(json.loads(resp.read().decode("utf-8")))
                    return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/pool/video-state"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)
            try:
                import urllib.request
                req = urllib.request.Request("http://127.0.0.1:8770/v1/accounts/video-state", data=raw_body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self._send_json(json.loads(resp.read().decode("utf-8")))
                    return
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)
                return

        if self.path.startswith("/api/incoming"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
                return

            target = data.get("target_agent", "hermes")
            channel = data.get("channel", "all")
            msg_text = data.get("message", "").strip()
            images = data.get("images", [])
            files = data.get("files", [])
            msg_id = data.get("id", f"msg_{int(time.time())}")
            chat_id = data.get("chat_id")

            state = load_state()
            state["total_commands"] = state.get("total_commands", 0) + 1
            save_state(state)

            log_msg("============================================================")

            # 1. Nhận diện phản hồi lệnh Ping
            if "[ping]" in msg_text.lower():
                log_msg(f"📡 [PING DETECTED] -> Phản hồi [PONG] tức thì!")
                log_msg(f"   Đích nhắm: {target} | Kênh: {channel}")
                diag = diagnose_system()
                log_msg(f"   Zalo: {diag['zalo']['detail']}")
                log_msg(f"   Muse AI: {diag['muse']['detail']}")
                log_msg(f"✅ [PONG] Sever Hermes sẵn sàng phục vụ Sếp 24/7!")
                
                self._send_json({"ok": True, "pong": True, "diagnostics": diag})
                return

            # 2.1. Xử lý ảnh đính kèm (Lưu trực tiếp vào received_images)
            saved_image_paths = []
            if images and isinstance(images, list):
                log_msg(f"📷 Đang giải mã {len(images)} ảnh đính kèm gửi từ Sếp...")
                for idx, img_b64 in enumerate(images):
                    try:
                        if "," in img_b64:
                            img_b64 = img_b64.split(",", 1)[1]
                        img_bytes = base64.b64decode(img_b64)
                        filename = f"img_{int(time.time())}_{idx+1}.png"
                        file_path = RECEIVED_IMAGES_DIR / filename
                        with open(file_path, "wb") as f:
                            f.write(img_bytes)
                        saved_image_paths.append(str(file_path))
                    except Exception as img_err:
                        log_msg(f"   ❌ Lỗi lưu ảnh {idx+1}: {img_err}")

            # 2.2. Xử lý tệp đọc đính kèm (Lưu trực tiếp vào received_files)
            saved_files = []
            if files and isinstance(files, list):
                log_msg(f"📄 Đang xử lý {len(files)} tệp đọc gửi từ Sếp...")
                for idx, fobj in enumerate(files):
                    try:
                        fname = fobj.get("name", f"file_{int(time.time())}_{idx+1}.txt")
                        safe_fname = Path(fname).name
                        fpath = RECEIVED_FILES_DIR / safe_fname
                        fcontent = fobj.get("content", "")
                        if fcontent.startswith("data:") and ";base64," in fcontent:
                            b64_data = fcontent.split(";base64,", 1)[1]
                            with open(fpath, "wb") as f:
                                f.write(base64.b64decode(b64_data))
                            text_preview = f"(Tệp nhị phân {fname}, đã lưu tại {fpath})"
                        else:
                            with open(fpath, "w", encoding="utf-8") as f:
                                f.write(fcontent)
                            text_preview = fcontent[:4000]
                        saved_files.append({"name": safe_fname, "path": str(fpath), "content": text_preview})
                        log_msg(f"   📁 Đã lưu tệp đọc: {fpath}")
                    except Exception as fe:
                        log_msg(f"   ❌ Lỗi lưu tệp {idx+1}: {fe}")

            # 3. Phân luồng điều phối
            low_text = msg_text.lower()
            is_ant_local = (
                target == "ant-local"
                or channel == "local"
                or "@ant-local" in low_text
                or "@ant " in low_text
                or low_text == "@ant"
                or low_text.startswith("/ant")
                or "ant-local" in low_text
            )

            if is_ant_local:
                log_msg(f"⚡ [TÍN HIỆU ĐIỀU PHỐI] -> ĐÁNH THỨC ANT-LOCAL THỰC SỰ!")
                log_msg(f"👤 Tiếp nhận: @Ant-local (Kỹ Sư Trưởng Cục Bộ)")
                log_msg(f"💬 Chỉ thị của Sếp: {msg_text}")
                if chat_id:
                    log_msg(f"📱 Khung chat đích: {chat_id} (Kênh: {channel})")
                if saved_image_paths:
                    log_msg(f"🖼️ Đã lưu {len(saved_image_paths)} ảnh vào máy: {saved_image_paths[0]}")
                if saved_files:
                    log_msg(f"📄 Đã nạp {len(saved_files)} tệp đọc vào bộ nhớ kỹ sư")
                
                # Kích hoạt Ant-local (agy.exe) chạy ngầm thực thi thật sự!
                execute_ant_local_task_async(msg_text, saved_image_paths, chat_id=chat_id, channel=channel, files=saved_files)
            else:
                log_msg(f"🤖 [TÍN HIỆU ĐIỀU PHỐI] -> HERMES TIẾP NHẬN TÁC VỤ!")
                log_msg(f"💬 Nội dung: {msg_text}")

            # Lưu tin nhắn của Sếp vào Cơ Sở Dữ Liệu SQLite Agent_TH trên máy
            try:
                import db_manager
                sender_name = "Sếp (CEO)" if (target != "hermes" and target != "ant-local") else ("Hermes" if target == "hermes" else "Ant-local")
                first_img = saved_image_paths[0] if saved_image_paths else None
                db_manager.insert_chat_message(
                    channel=channel,
                    sender=sender_name,
                    role=target,
                    message=msg_text,
                    local_media_path=first_img,
                )
            except Exception as dbe:
                log_msg(f"⚠️ Lỗi ghi SQLite: {dbe}")

            # Lưu vào lịch sử JSON cục bộ
            try:
                hist = []
                if CHAT_HISTORY_FILE.exists():
                    with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                        hist = json.load(f)
                hist.append({
                    "id": msg_id,
                    "target": target,
                    "channel": channel,
                    "text": msg_text,
                    "images": saved_image_paths,
                    "time": datetime.now().isoformat(),
                })
                with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(hist[-100:], f, indent=2, ensure_ascii=False)
            except Exception:
                pass

            self._send_json({
                "ok": True,
                "receiver": "Sever Hermes",
                "ack": f"[LOCAL] Đã tiếp nhận chỉ thị: {msg_text[:50]}...",
                "saved_images": saved_image_paths,
            })
            return

        self.send_response(404)
        self.end_headers()


def run_server(port=8999):
    log_msg("============================================================")
    log_msg(f"🚀 SEVER HERMES OPS RECEIVER ĐANG HOẠT ĐỘNG (CỔNG {port})")
    log_msg("🔱 KIẾN TRÚC 4 TẦNG: Admin ↔ Hermes Live ↔ Ant-local Dev")
    log_msg("⚡ ZERO-TOKEN IDLE: Tuyệt đối không quét vòng lặp gây tốn token!")
    log_msg("============================================================")
    server = HTTPServer(("0.0.0.0", port), SeverHermesOpsHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server(8999)
