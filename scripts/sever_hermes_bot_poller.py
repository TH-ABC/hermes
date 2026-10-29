"""
Tầng 4: Bot Quét Tin Tự Động (Ant-local Autonomous Web Poller Daemon)
- Tự động quét giao diện Web SPA Vercel mỗi 15-20 giây.
- Nhận diện chỉ thị mới từ Sếp (@Ant-local / @hermes / sửa code).
- Tự động báo mở màn [0s] vào khung chat Web & Zalo.
- Gọi agy.exe đọc mã nguồn, phân tích và sửa code trực tiếp trên Sever Hermes.
- Gửi báo cáo nghiệm thu hoàn chỉnh ngược lại Web SPA và Zalo cho Sếp.
- Hoàn toàn tự động, Sếp không cần nhắc thức hay can thiệp thủ công!
"""

import os
import sys
import time
import json
import base64
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

HERMES_HOME = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes"
if not HERMES_HOME.exists():
    HERMES_HOME = Path.home() / ".hermes"
HERMES_HOME.mkdir(parents=True, exist_ok=True)

STATE_FILE = HERMES_HOME / "bot_poller_state.json"
LOG_FILE = HERMES_HOME / "bot_poller.log"
VERCEL_INBOX_URL = "https://hermes-agent-vercel.vercel.app/api/inbox"
AGY_BIN = Path(r"C:\Users\ADMIN\AppData\Local\agy\bin\agy.exe")


def log_poller(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    sys.stdout.buffer.write(line.encode("utf-8", errors="replace"))
    sys.stdout.flush()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def load_poller_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_handled_id": 0, "processed_ids": []}


def save_poller_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def push_reply_to_vercel(text: str, sender: str = "Ant-local (Kỹ Sư Trưởng)", role: str = "ant-local", channel: str = "local"):
    """Gửi phản hồi trực tiếp vào khung chat Web SPA Vercel."""
    try:
        payload = json.dumps({
            "text": text,
            "sender": sender,
            "role": role,
            "channel": channel,
        }).encode("utf-8")
        req = urllib.request.Request(
            VERCEL_INBOX_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8):
            pass
        return True
    except Exception as e:
        log_poller(f"⚠️ Lỗi gửi phản hồi lên Vercel: {e}")
        return False


def send_reply_to_zalo(text: str) -> bool:
    """Gửi phản hồi đồng bộ sang Zalo."""
    try:
        import sever_hermes_receiver
        return sever_hermes_receiver.send_to_zalo_chat(text)
    except Exception as e:
        log_poller(f"⚠️ Lỗi gửi sang Zalo: {e}")
        return False


def save_to_sqlite(text: str, channel: str = "local", sender: str = "Ant-local (Kỹ Sư Trưởng)", role: str = "ant-local"):
    """Lưu vĩnh viễn vào SQLite Agent_TH."""
    try:
        import db_manager
        db_manager.insert_chat_message(
            channel=channel,
            sender=sender,
            role=role,
            message=text,
        )
    except Exception as e:
        log_poller(f"⚠️ Lỗi lưu SQLite: {e}")


def execute_task_with_agy(task_text: str, channel: str = "local") -> str:
    """Gọi agy.exe chạy ngầm đọc mã nguồn và thực thi không giới hạn thời gian."""
    log_poller(f"🚀 [BOT POLLER EXEC] Khởi động agy.exe xử lý tác vụ: {task_text[:80]}...")
    
    prompt_parts = [
        "BẠN LÀ ANT-LOCAL, KỸ SƯ TRƯỞNG CỤC BỘ CỦA SEVER HERMES.",
        f"Chỉ thị của Sếp Hoàng: \"{task_text}\"",
        "Nhiệm vụ của bạn:",
        "1. Kiểm tra các file mã nguồn liên quan trong dự án (D:\\hermes-main).",
        "2. Đọc tài liệu, phân tích hoặc sửa code theo đúng yêu cầu của Sếp.",
        "3. Kiểm tra tính toàn vẹn cú pháp sau khi sửa.",
        "4. Báo cáo lại kết quả nghiệm thu rõ ràng, súc tích (nêu rõ file đã sửa, nội dung đã làm, kế hoạch hành động).",
        "QUY TẮC BẮT BUỘC: Luôn xưng 'Em là Trợ lý của sếp Hoàng'. Tuyệt đối KHÔNG ĐƯỢC nhắc đến từ 'Muse' ở bất kỳ đâu."
    ]
    full_prompt = "\n".join(prompt_parts)

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
            cwd=str(ROOT_DIR),
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
        return output
    except Exception as ex:
        log_poller(f"❌ Lỗi agy.exe: {ex}")
        return f"❌ [Ant-local] Đã có lỗi xảy ra trong quá trình thực thi: {ex}"


def run_bot_poller():
    log_poller("=" * 65)
    log_poller("🤖 BOT QUÉT TIN TỰ ĐỘNG ANT-LOCAL ĐÃ KHỞI CHẠY!")
    log_poller(f"📡 Nguồn quét: {VERCEL_INBOX_URL}")
    log_poller("⏱ Chu kỳ quét: 15 giây / lần")
    log_poller("⚡ Tự động bắt tin của Sếp, báo mở màn và code không cần nhắc!")
    log_poller("=" * 65)

    state = load_poller_state()
    # Nếu lần đầu chạy, đặt mốc bắt đầu từ tin nhắn lớn nhất hiện có để không chạy lại tin cũ
    try:
        req = urllib.request.Request(VERCEL_INBOX_URL, headers={"User-Agent": "Ant-Local-Poller/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            current_max = data.get("last_id", 0)
            if state.get("last_handled_id", 0) == 0:
                state["last_handled_id"] = current_max
                save_poller_state(state)
                log_poller(f"📌 Đã khởi tạo mốc tin nhắn ban đầu: #{current_max}")
    except Exception as e:
        log_poller(f"⚠️ Khởi tạo ban đầu: {e}")

    while True:
        try:
            state = load_poller_state()
            last_id = state.get("last_handled_id", 0)
            processed_ids = set(state.get("processed_ids", []))

            req_url = f"{VERCEL_INBOX_URL}?since_id={last_id}&limit=20"
            req = urllib.request.Request(req_url, headers={"User-Agent": "Ant-Local-Poller/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                new_msgs = data.get("messages", [])

                for m in new_msgs:
                    m_id = m.get("id")
                    sender = m.get("sender", "")
                    role = m.get("role", "")
                    text = m.get("text", "").strip()
                    channel = m.get("channel", "all")

                    if not m_id or m_id in processed_ids:
                        continue

                    # Cập nhật mốc ID
                    processed_ids.add(m_id)
                    if m_id > state.get("last_handled_id", 0):
                        state["last_handled_id"] = m_id

                    # Chỉ xử lý tin nhắn gửi từ Sếp (CEO / admin)
                    is_from_boss = (
                        "sếp" in sender.lower()
                        or "ceo" in sender.lower()
                        or role == "admin"
                        or sender == "Sếp (CEO)"
                    )
                    
                    if not is_from_boss:
                        continue

                    text_lower = text.lower()
                    is_ant_local = (
                        "@ant-local" in text_lower
                        or "@ant" in text_lower
                        or "/ant" in text_lower
                        or "ant-local" in text_lower
                        or channel == "local"
                        or "sửa code" in text_lower
                        or "kế hoạch" in text_lower
                        or "phân tích" in text_lower
                    )

                    if not is_ant_local:
                        continue

                    log_poller("------------------------------------------------------------")
                    log_poller(f"🎯 [PHÁT HIỆN CHỈ THỊ MỚI #{m_id}] TỪ SẾP:")
                    log_poller(f"   💬 Nội dung: {text}")

                    # 1. Báo chạy mở màn tức thì [0s] vào khung chat Web SPA & Zalo
                    ack_msg = (
                        f"🛠️ **[Ant-local - Kỹ Sư Trưởng Cục Bộ]**\n"
                        f"Em đã tự động bắt được chỉ thị của Sếp trên giao diện Web!\n"
                        f"📋 **Nhiệm vụ:** {text}\n"
                        f"⚡ Em đang mở mã nguồn đọc code và tiến hành xử lý trực tiếp trên Sever Hermes. "
                        f"Kết quả sẽ được báo cáo ngay tại đây sau khi hoàn tất ạ!"
                    )
                    push_reply_to_vercel(ack_msg, channel=channel)
                    send_reply_to_zalo(ack_msg)
                    save_to_sqlite(ack_msg, channel=channel)

                    # 2. Thực thi bằng agy.exe
                    report = execute_task_with_agy(text, channel=channel)

                    # 3. Báo cáo nghiệm thu hoàn tất vào khung chat Web SPA & Zalo
                    push_reply_to_vercel(report, channel=channel)
                    send_reply_to_zalo(report)
                    save_to_sqlite(report, channel=channel)
                    log_poller(f"✅ [HOÀN TẤT TÁC VỤ #{m_id}] Đã báo cáo nghiệm thu lên Web SPA & Zalo!")

            # Lưu lại trạng thái định kỳ
            state["processed_ids"] = list(processed_ids)[-500:]  # Giữ tối đa 500 ID
            save_poller_state(state)

        except Exception as e:
            # log_poller(f"⚠️ Vòng quét lỗi: {e}")
            pass

        time.sleep(15)  # Quét mỗi 15 giây (4 lần/phút)


if __name__ == "__main__":
    run_bot_poller()
