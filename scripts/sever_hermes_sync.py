"""
Sever Hermes Sync Daemon — Đồng bộ tin nhắn & hình ảnh từ Vercel về máy tính Sever Hermes.
Chạy trực tiếp trên máy chủ Sever Hermes để nhận thông tin theo thời gian thực từ Sếp.
"""

import os
import sys
import time
import json
import base64
import urllib.request
from pathlib import Path
from datetime import datetime

VERCEL_INBOX_URL = "https://hermes-agent-vercel.vercel.app/api/inbox"
ROOT_DIR = Path(__file__).resolve().parents[1]
RECEIVED_IMAGES_DIR = ROOT_DIR / "received_images"
RECEIVED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
if not HERMES_HOME.exists():
    HERMES_HOME = Path.home() / ".hermes"

CHAT_HISTORY_FILE = HERMES_HOME / "office_chat_history.json"
INBOX_LOG_FILE = HERMES_HOME / "sever_hermes_inbox.log"


def log_event(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
    sys.stdout.flush()
    try:
        with open(INBOX_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def append_to_office_history(user_text: str, image_paths: list):
    try:
        history = []
        if CHAT_HISTORY_FILE.is_file():
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)

        entry = {
            "id": f"msg_vercel_{int(time.time() * 1000)}",
            "sender": "user",
            "source": "vercel_web",
            "text": user_text,
            "images": image_paths,
            "timestamp": time.time(),
        }
        history.append(entry)
        if len(history) > 100:
            history = history[-100:]

        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_event(f"Lỗi lưu lịch sử văn phòng: {e}")


def mark_processed_on_vercel(msg_id: str):
    try:
        payload = json.dumps({
            "id": msg_id,
            "status": "processed_by_sever_hermes",
            "reply": "Đã tiếp nhận và đồng bộ trực tiếp lên máy chủ Sever Hermes."
        }).encode("utf-8")

        req = urllib.request.Request(
            VERCEL_INBOX_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception:
        pass


def poll_inbox():
    processed_ids = set()
    log_event("=" * 60)
    log_event("⚡ SEVER HERMES SYNC DAEMON ĐÃ KHỞI CHẠY!")
    log_event(f"📡 Lắng nghe từ: {VERCEL_INBOX_URL}")
    log_event(f"📁 Thư mục ảnh nhận: {RECEIVED_IMAGES_DIR}")
    log_event(f"🖥️ Trạng thái: Sẵn sàng nhận tin nhắn & ảnh từ Sếp qua Vercel...")
    log_event("=" * 60)

    while True:
        try:
            req = urllib.request.Request(
                VERCEL_INBOX_URL,
                headers={"User-Agent": "Sever-Hermes-Daemon/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])

                for item in items:
                    msg_id = item.get("id")
                    if not msg_id or msg_id in processed_ids:
                        continue

                    processed_ids.add(msg_id)
                    text = item.get("text", "")
                    images = item.get("images", [])
                    ts = item.get("timestamp", time.time())
                    dt_str = datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d %H:%M:%S")

                    # Lưu các ảnh đính kèm về ổ đĩa cục bộ
                    saved_images = []
                    for idx, img_b64 in enumerate(images):
                        try:
                            if "," in img_b64:
                                header, data_part = img_b64.split(",", 1)
                                ext = "jpg"
                                if "png" in header:
                                    ext = "png"
                                elif "webp" in header:
                                    ext = "webp"
                            else:
                                data_part = img_b64
                                ext = "jpg"

                            raw_bytes = base64.b64decode(data_part)
                            img_filename = f"img_{int(ts)}_{idx+1}.{ext}"
                            img_path = RECEIVED_IMAGES_DIR / img_filename
                            with open(img_path, "wb") as f_img:
                                f_img.write(raw_bytes)
                            saved_images.append(str(img_path))
                        except Exception as err:
                            log_event(f"Lỗi decode ảnh: {err}")

                    # Báo sự kiện to rõ lên máy Sever Hermes
                    print("\n" + "=" * 65)
                    log_event(f"🔔 [SEVER HERMES] ĐÃ NHẬN ĐƯỢC TIN NHẮN TỪ SẾP TRÊN VERCEL!")
                    log_event(f"⏱ Thời gian: {dt_str}")
                    log_event(f"💬 Nội dung: {text if text else '(Chỉ gửi ảnh)'}")
                    if saved_images:
                        log_event(f"🖼️ Hình ảnh ({len(saved_images)} ảnh) đã lưu về Sever Hermes:")
                        for p in saved_images:
                            log_event(f"    👉 {p}")
                    log_event("⚙️ Trạng thái: Đã đưa vào tiến trình xử lý của Sever Hermes!")
                    print("=" * 65 + "\n")

                    # Ghi vào lịch sử văn phòng ảo của Sever Hermes
                    append_to_office_history(text, saved_images)

                    # Báo lại Vercel là máy Sever Hermes đã nhận thành công
                    mark_processed_on_vercel(msg_id)

        except Exception as e:
            # log_event(f"Poll check error: {e}")
            pass

        time.sleep(3)


if __name__ == "__main__":
    poll_inbox()
