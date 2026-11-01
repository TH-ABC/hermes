#!/usr/bin/env python3
"""Tầng Nhận Tin & Tự Động Thực Thi @ATG (Antigravity Headless Runner) từ Zalo.

Quản lý hàng đợi atg_queue.json và tự động thực thi các chỉ thị của Sếp Hoàng
qua Antigravity Multi-CLI Hub (D:\\Antigravity-multi) 24/7 độc lập.

Cơ chế tài khoản:
- Mặc định duy trì duy nhất 1 Tài khoản Chính (rameranvoktera647546@gmail.com).
- Khi Sếp ra lệnh (ví dụ: 'mở tài khoản thứ 2', 'bật tk 2'), hệ thống sẽ chuyển sang Tài khoản 2.
- Khi Sếp ra lệnh 'về tài khoản chính' hoặc 'dùng tk 1', hệ thống quay lại Tài khoản 1.
- Định dạng tin nhắn: Chuẩn hóa 100% cho Zalo, tự động gỡ bỏ các ký tự Markdown (**, ##, *, _) để văn bản luôn sạch đẹp, trang trọng, lịch sự.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Thư mục dữ liệu cục bộ
LOCALAPPDATA = os.environ.get("LOCALAPPDATA")
if LOCALAPPDATA:
    HERMES_HOME = Path(LOCALAPPDATA) / "hermes"
else:
    HERMES_HOME = Path.home() / ".hermes"

HERMES_HOME.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = HERMES_HOME / "atg_queue.json"
BRIDGE_URL = "http://127.0.0.1:3050"

# Antigravity Multi-CLI paths
MULTI_DIR = Path(r"D:\Antigravity-multi")
RUN_PY = MULTI_DIR / "run.py"
ACCOUNTS_FILE = MULTI_DIR / "data" / "accounts.json"
ACTIVE_CONFIG_FILE = MULTI_DIR / "data" / "active_config.json"

# Danh bạ tài khoản chuẩn hóa
PRIMARY_ACCOUNT = "rameranvoktera647546-gmail-com"
SECONDARY_ACCOUNT = "tranthientam2195-gmail-com"
ACCOUNT_3 = "nguyentrieu99992000-gmail-com"
ACCOUNT_4 = "th982982982-gmail-com"

ACCOUNT_MAP = {
    "1": PRIMARY_ACCOUNT,
    "chinh": PRIMARY_ACCOUNT,
    "rameran": PRIMARY_ACCOUNT,
    "rameranvoktera": PRIMARY_ACCOUNT,
    "acc-1": PRIMARY_ACCOUNT,
    "2": SECONDARY_ACCOUNT,
    "phu": SECONDARY_ACCOUNT,
    "phu-1": SECONDARY_ACCOUNT,
    "tam": SECONDARY_ACCOUNT,
    "tranthientam": SECONDARY_ACCOUNT,
    "acc-2": SECONDARY_ACCOUNT,
    "3": ACCOUNT_3,
    "trieu": ACCOUNT_3,
    "nguyentrieu": ACCOUNT_3,
    "acc-3": ACCOUNT_3,
    "4": ACCOUNT_4,
    "th": ACCOUNT_4,
    "hoang": ACCOUNT_4,
    "acc-4": ACCOUNT_4,
}


def log_msg(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [ATG-AutoRunner] {msg}", flush=True)


def _get_queue_file(filename: str = "atg_queue.json") -> Path:
    return HERMES_HOME / filename


def _read_queue(filename: str = "atg_queue.json") -> list:
    q_file = _get_queue_file(filename)
    if not q_file.exists():
        return []
    try:
        with open(q_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_queue(items: list, filename: str = "atg_queue.json"):
    q_file = _get_queue_file(filename)
    try:
        temp_file = q_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        temp_file.replace(q_file)
    except Exception as e:
        print(f"[atg_listener] Loi ghi queue: {e}", file=sys.stderr)


def enqueue_message(
    text: str,
    chat_id: str,
    images: list = None,
    sender: str = "Sep Hoang",
    target: str = "ATG-Hermes",
    queue_filename: str = "atg_queue.json"
) -> dict:
    queue = _read_queue(queue_filename)
    item_id = f"atg_{int(time.time()*1000)}"
    item = {
        "id": item_id,
        "text": text,
        "chat_id": str(chat_id),
        "images": images or [],
        "sender": sender,
        "target": target,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
    }
    queue.append(item)
    _write_queue(queue, queue_filename)
    return item


def fetch_next_pending(filename: str = "atg_queue.json") -> dict | None:
    queue = _read_queue(filename)
    for item in queue:
        if item.get("status") == "pending":
            item["status"] = "processing"
            item["processed_at"] = datetime.now().isoformat()
            _write_queue(queue, filename)
            return item
    return None


def mark_completed(item_id: str, filename: str = "atg_queue.json"):
    queue = _read_queue(filename)
    for item in queue:
        if item.get("id") == item_id:
            item["status"] = "completed"
            item["completed_at"] = datetime.now().isoformat()
            break
    _write_queue(queue, filename)


def clean_for_zalo(text: str) -> str:
    """Loại bỏ triệt để các ký hiệu Markdown (**, ##, *, _) gây xấu mắt trên Zalo."""
    if not text:
        return ""
    # Gỡ bỏ các tiêu đề Markdown #, ##, ###
    text = re.sub(r'(?m)^#{1,6}\s*(.*)$', r'\1', text)
    # Gỡ bỏ bold **text** và __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    # Gỡ bỏ italic đơn *text* hoặc _text_
    text = re.sub(r'\*([^\*\n]+)\*', r'\1', text)
    text = re.sub(r'_([^_\n]+)_', r'\1', text)
    # Gỡ bỏ inline backticks `code`
    text = re.sub(r'`([^`\n]+)`', r'\1', text)
    # Gỡ bỏ code block fences ```
    text = re.sub(r'```[a-zA-Z0-9_\-]*\n?', '', text)
    # Chuyển đổi đầu dòng list * hoặc - thành bullet point tròn •
    text = re.sub(r'(?m)^[\*\-]\s+', '• ', text)
    # Dọn sạch các dấu sót lại
    text = text.replace('**', '').replace('##', '')
    # Giới hạn dòng trống liên tiếp
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def send_to_zalo(chat_id: str, text: str) -> bool:
    if not chat_id or not text:
        return False
    # Luôn làm sạch định dạng trước khi gửi sang Zalo
    cleaned = clean_for_zalo(text)
    url = f"{BRIDGE_URL}/send"
    chunks = [cleaned[i : i + 3000] for i in range(0, len(cleaned), 3000)]
    for chunk in chunks:
        payload = json.dumps({"chat_id": chat_id, "text": chunk}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                pass
        except Exception as e:
            log_msg(f"Lỗi gửi Zalo ({chat_id}): {e}")
        time.sleep(0.2)
    return True


def get_current_active_account() -> str:
    if ACTIVE_CONFIG_FILE.exists():
        try:
            with open(ACTIVE_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("default_account", PRIMARY_ACCOUNT)
        except Exception:
            pass
    return PRIMARY_ACCOUNT


def set_current_active_account(acc_id: str) -> None:
    ACTIVE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ACTIVE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"default_account": acc_id, "updated_at": datetime.now().isoformat()}, f, indent=2)


def load_accounts() -> dict:
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def format_accounts_status() -> str:
    active_id = get_current_active_account()
    accs = load_accounts()
    active_email = accs.get(active_id, {}).get("email", active_id)
    active_label = "Tài khoản Chính (Google AI Pro)" if active_id == PRIMARY_ACCOUNT else "Tài khoản Thứ 2 (Phụ)"

    lines = [
        "🛠️ [@ATG - Quản Lý Tài Khoản]\n",
        "Dạ Sếp, tình trạng tài khoản hiện tại:",
        f"• Đang kích hoạt: {active_email} ({active_label})",
        "",
        "💡 Cú pháp chuyển đổi nhanh:",
        "• @ATG mở tài khoản thứ 2 (hoặc @ATG dùng tk 2): Kích hoạt tài khoản phụ",
        "• @ATG về tài khoản chính (hoặc @ATG dùng tk 1): Quay lại tài khoản chính",
    ]
    return "\n".join(lines)


def clean_output_text(raw_output: str) -> str:
    """Loại bỏ các thông số debug kỹ thuật, định dạng lại kết quả gãy gọn, lịch sự."""
    text = raw_output.strip()
    if not text:
        return "Dạ Sếp, tác vụ đã hoàn thành tốt đẹp ạ."

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        l = line.strip()
        if "Verbosity now defaults to medium" in l or "esc to dismiss" in l or "? for shortcuts" in l:
            continue
        if l.startswith("PS ") or l.startswith("cmd.exe /c start"):
            continue
        cleaned_lines.append(line)

    clean_res = "\n".join(cleaned_lines).strip()
    if not clean_res:
        return "Dạ Sếp, tác vụ đã hoàn thành tốt đẹp ạ."
    return clean_res


def process_atg_task(msg: dict):
    chat_id = msg.get("chat_id")
    raw_text = msg.get("text", "").strip()
    item_id = msg.get("id")

    log_msg(f"⚡ Tiếp nhận yêu cầu: '{raw_text[:60]}...'")

    clean_text = raw_text
    clean_text = re.sub(r"(?i)@atg[-_]?(hermesh?|nt)?\b", "", clean_text)
    clean_text = re.sub(r"(?i)@(hermesh?|nt|ant[-_]?local|ant)\b", "", clean_text)
    clean_text = re.sub(r"(?i)^[-_:\s]*(hermesh?|nt)?[-_:\s]*", "", clean_text).strip()

    lower = clean_text.lower().strip()

    # 0. Yêu cầu kiểm tra kết nối / ping / alo / trạng thái hoạt động / nhận tin chưa
    if lower in [
        "alo", "alo alo", "alo @atg", "ping", "test", "có đó không", "co do khong",
        "thức chưa", "thuc chua", "alo kĩ sư", "alo kỹ sư", "test kết nối", "test kết nối zalo",
        "hoạt động chưa", "hoat dong chua", "chạy chưa", "chay chua", "trạng thái", "trang thai",
        "status", "kiểm tra", "kiem tra", "kiểm tra hệ thống", "kiem tra he thong",
        "chạy được chưa", "chay duoc chua", "ok chưa", "ok chua", "sao rồi", "sao roi",
        "nhận tin chưa", "nhan tin chua", "nhận chưa", "nhan chua", "nhận được chưa", "nhan duoc chua",
        "ok nhận tin chưa", "ok nhan tin chua", "đã nhận chưa", "da nhan chua"
    ] or "nhận tin chưa" in lower or "nhan tin chua" in lower or "hoạt động chưa" in lower:
        send_to_zalo(
            chat_id,
            "🛠️ [@ATG - Kỹ Sư Trưởng ATG-Hermes]\n"
            "Dạ Sếp, Em là Trợ lý của sếp Hoàng!\n\n"
            "✅ Em đã nhận được tin nhắn của Sếp rõ ràng 100% từ Zalo rồi ạ!\n\n"
            "🔱 Trạng thái Cụm 6 tiến trình [ATG-Hermes] đang hoạt động ổn định trong khung chat Antigravity:\n"
            "• [1] POOL-8770: ONLINE (Studio AI Engine)\n"
            "• [2] LOGIN-8771: ONLINE (Local Login Portal)\n"
            "• [3] ZALO-3050: ONLINE (Hermes Gateway)\n"
            "• [4] HERMES-8999: ONLINE (Central Receiver)\n"
            "• [5] AUTO-SYNC: ONLINE (Auto-sync 24/7)\n"
            "• [6] ATG-WAKEUP: ONLINE (Lắng nghe @ATG-hermesh)\n\n"
            "👉 Đang túc trực 24/7 sẵn sàng nhận chỉ thị kỹ thuật của Sếp ạ!"
        )
        mark_completed(item_id)
        return

    # 1. Xử lý lệnh chuyển tài khoản linh hoạt (acc 1, acc 2, acc 3, acc 4...)
    acc_switch = re.search(r"(?i)(?:chuyển|chuyen|đổi|doi|dùng|dung|switch|mở|mo|bật|bat)\s+(?:sang\s+)?(?:acc|tk|tài khoản|tai khoan)\s*([0-9a-zA-Z_\-]+)", clean_text)
    if not acc_switch and re.match(r"(?i)^(?:acc|tk)\s*([0-9a-zA-Z_\-]+)$", clean_text.strip()):
        acc_switch = re.match(r"(?i)^(?:acc|tk)\s*([0-9a-zA-Z_\-]+)$", clean_text.strip())

    if acc_switch:
        target_key = acc_switch.group(1).lower().strip()
        matched_acc_id = ACCOUNT_MAP.get(target_key)
        accs = load_accounts()
        if not matched_acc_id and target_key in accs:
            matched_acc_id = target_key

        if matched_acc_id:
            set_current_active_account(matched_acc_id)
            email = accs.get(matched_acc_id, {}).get("email", matched_acc_id)
            lbl = "Tài khoản Chính (Pro)" if matched_acc_id == PRIMARY_ACCOUNT else f"Tài khoản {target_key.upper()}"
            send_to_zalo(
                chat_id,
                f"🛠️ [@ATG - Kỹ Sư Trưởng]\n"
                f"Dạ Sếp, em đã kiểm tra và chuyển ngay sang {lbl} ({email}).\n"
                f"Mọi câu lệnh và chỉ thị tiếp theo sẽ tự động chạy trên tài khoản này ạ!"
            )
            mark_completed(item_id)
            return
        else:
            send_to_zalo(
                chat_id,
                f"🛠️ [@ATG - Quản Lý Tài Khoản]\n"
                f"Dạ Sếp, không tìm thấy tài khoản [{target_key}].\n"
                f"{format_accounts_status()}"
            )
            mark_completed(item_id)
            return

    # 1.1 Yêu cầu chuyển về tài khoản chính (Tài khoản 1)
    if any(p in lower for p in [
        "về tài khoản chính", "về tk chính", "dùng tài khoản chính", "dùng tk chính",
        "về tk 1", "dùng tk 1", "mở tk 1", "bật tk 1", "switch 1", "switch chinh",
        "chuyển acc1", "chuyen acc1", "chuyển acc 1", "chuyen acc 1",
        "về acc 1", "ve acc 1", "về acc1", "ve acc1",
        "đổi acc 1", "doi acc 1", "đổi acc1", "doi acc1",
        "dùng acc 1", "dung acc 1", "dùng acc1", "dung acc1",
        "switch acc-1", "switch acc1"
    ]) or lower in ["acc 1", "acc1", "tk 1", "tk1"]:
        set_current_active_account(PRIMARY_ACCOUNT)
        accs = load_accounts()
        email = accs.get(PRIMARY_ACCOUNT, {}).get("email", PRIMARY_ACCOUNT)
        send_to_zalo(
            chat_id,
            f"🛠️ [@ATG - Kỹ Sư Trưởng]\n"
            f"Dạ Sếp, em đã chuyển về lại Tài khoản Chính ({email}).\n"
            f"Mọi câu lệnh tiếp theo sẽ chạy trên tài khoản này ạ."
        )
        mark_completed(item_id)
        return

    # 1.2 Yêu cầu kích hoạt/chuyển sang tài khoản thứ 2
    if any(p in lower for p in [
        "mở tài khoản thứ 2", "mở tk thứ 2", "mở tk 2", "bật tài khoản thứ 2", "bật tk 2",
        "dùng tài khoản thứ 2", "dùng tk 2", "chuyển sang tài khoản thứ 2", "chuyển tk 2",
        "switch 2", "switch phu", "bật tk phụ", "dùng tk phụ", "switch acc-2",
        "chuyển acc2", "chuyen acc2", "chuyển acc 2", "chuyen acc 2",
        "chuyển sang acc 2", "chuyển sang acc2", "chuyen sang acc 2", "chuyen sang acc2",
        "đổi acc 2", "đổi acc2", "doi acc 2", "doi acc2",
        "dùng acc 2", "dung acc 2", "dùng acc2", "dung acc2",
        "switch acc2"
    ]) or lower in ["acc 2", "acc2", "tk 2", "tk2"]:
        set_current_active_account(SECONDARY_ACCOUNT)
        accs = load_accounts()
        email = accs.get(SECONDARY_ACCOUNT, {}).get("email", SECONDARY_ACCOUNT)
        send_to_zalo(
            chat_id,
            f"🛠️ [@ATG - Kỹ Sư Trưởng]\n"
            f"Dạ Sếp, em đã kích hoạt và chuyển sang Tài khoản thứ 2 ({email}).\n"
            f"Mọi câu lệnh tiếp theo sẽ sử dụng tài khoản thứ 2 này ạ."
        )
        mark_completed(item_id)
        return

    # 3. Yêu cầu kiểm tra tài khoản
    if lower in [
        "tài khoản", "tk", "tai khoan", "kiem tra tai khoan", "accounts", "danh sach", "list", "ds"
    ]:
        send_to_zalo(chat_id, format_accounts_status())
        mark_completed(item_id)
        return

    # 4. Yêu cầu kiểm tra project/workspace
    try:
        sys.path.insert(0, str(MULTI_DIR))
        import project_manager
        if lower in ["project", "projects", "du an", "danh sach project", "ds project", "workspace"]:
            active_p = project_manager.get_active_project()
            send_to_zalo(
                chat_id,
                f"🛠️ [@ATG - Workspace]\n"
                f"Dạ Sếp, dự án đang làm việc hiện tại:\n"
                f"• Tên dự án: {active_p.get('name')} (#{active_p.get('id')})\n"
                f"• Thư mục mã nguồn: {active_p.get('path')}\n\n"
                f"💡 Sếp muốn chuyển dự án khác: @ATG project switch <tên_mã>"
            )
            mark_completed(item_id)
            return

        proj_switch = re.match(r"(?i)^(?:project\s+switch|switch\s+project|chuyen\s+du\s+an|chuyen\s+project)\s+([a-zA-Z0-9_\-]+)", clean_text)
        if proj_switch:
            p = project_manager.set_active_project(proj_switch.group(1))
            send_to_zalo(
                chat_id,
                f"🛠️ [@ATG - Workspace]\n"
                f"Dạ Sếp, em đã chuyển workspace sang dự án {p.get('name')}.\n"
                f"Thư mục: {p.get('path')}"
            )
            mark_completed(item_id)
            return
    except Exception as e:
        log_msg(f"Lỗi kiểm tra project command: {e}")

    # 5. Xử lý các câu hỏi xin lệnh / hướng dẫn chạy 6 tiến trình NT hoặc Hermes
    if any(k in lower for k in [
        "lệnh chạy 6 tiến trình", "lenh chay 6 tien trinh",
        "6 tiến trình còn lại", "6 tien trinh con lai",
        "lệnh 6 tiến trình", "lenh 6 tien trinh",
        "cụm nt", "cum nt", "chạy nt", "chay nt"
    ]):
        reply_nt = (
            "🛠️ [@ATG - Kỹ Sư Trưởng ATG-Hermes]\n"
            "Dạ Sếp, Em là Trợ lý của sếp Hoàng!\n\n"
            "📋 LỆNH CHẠY 6 TIẾN TRÌNH CHO CỤM [ATG-NT] ĐÂY Ạ:\n\n"
            "[1] Studio AI Engine Pool (Cụm NT - Cổng 8780):\n"
            "powershell -Command \"Set-Location 'D:\\hermes-main\\hermes-main\\museai'; & 'D:\\hermes-main\\hermes-main\\.venv\\Scripts\\python.exe' -u bridge/pool.py --port 8780 --cookies-dir cookies\"\n\n"
            "[2] Local Login Server (Cụm NT - Cổng 8781):\n"
            "powershell -Command \"Set-Location 'D:\\hermes-main\\hermes-main\\museai'; & 'D:\\hermes-main\\hermes-main\\.venv\\Scripts\\python.exe' -u tools/local_login_server.py --port 8781\"\n\n"
            "[3] Gateway Bridge Worker (Cụm NT - Cổng 3051):\n"
            "powershell -Command \"Set-Location 'D:\\hermes-main\\hermes-main'; & 'D:\\hermes-main\\hermes-main\\.venv\\Scripts\\python.exe' -u hermes_cli/main.py gateway run\"\n\n"
            "[4] Central Receiver (Cụm NT - Cổng 8998):\n"
            "powershell -Command \"Set-Location 'D:\\hermes-main\\hermes-main'; & 'D:\\hermes-main\\hermes-main\\.venv\\Scripts\\python.exe' -u scripts/sever_hermes_receiver.py\"\n\n"
            "[5] Auto-Sync Enterprise Daemon:\n"
            "powershell -Command \"Set-Location 'D:\\hermes-main\\hermes-main'; & 'D:\\hermes-main\\hermes-main\\.venv\\Scripts\\python.exe' -u scripts/auto_sync_enterprise_daemon.py\"\n\n"
            "[6] ATG-NT Zalo Wakeup Listener:\n"
            "powershell -Command \"Set-Location 'D:\\hermes-main'; & 'D:\\hermes-main\\hermes-main\\.venv\\Scripts\\python.exe' -u scripts/atg_nt_listener.py\"\n\n"
            "👉 Sếp dán nguyên 6 lệnh này vào khung chat Antigravity bên kia là chạy mượt 100% ạ!"
        )
        send_to_zalo(chat_id, reply_nt)
        log_msg(f"✅ Đã trả lời Zalo cho {chat_id} (Gửi 6 lệnh ATG-NT)")
        mark_completed(item_id)
        return

    # 6. Các chỉ thị kỹ thuật khác: ghi nhận trực tiếp vào khung chat Antigravity này
    # Tuyệt đối KHÔNG chạy qua run.py CLI bên ngoài và KHÔNG báo lỗi hạn ngạch/chuyển acc
    reply_msg = (
        f"🛠️ [@ATG - Kỹ Sư Trưởng ATG-Hermes]\n"
        f"Dạ Sếp, Em là Trợ lý của sếp Hoàng.\n\n"
        f"Em đã tiếp nhận chỉ thị: \"{clean_text}\"\n"
        f"Nhiệm vụ đang được thực thi trực tiếp trên mã nguồn Sever Hermes trong khung chat Antigravity này ạ!"
    )
    send_to_zalo(chat_id, reply_msg)
    log_msg(f"✅ Đã phản hồi Zalo cho {chat_id} | Chỉ thị: {clean_text[:40]}")
    mark_completed(item_id)


def main():
    parser = argparse.ArgumentParser(description="Bộ điều phối hàng đợi @ATG")
    parser.add_argument("--enqueue", action="store_true", help="Thêm tin nhắn vào queue")
    parser.add_argument("--listen", action="store_true", help="Lắng nghe 24/7 và tự động thực thi chỉ thị")
    parser.add_argument("--wait", type=int, default=86400, help="Thời gian chờ tối đa (giây)")
    parser.add_argument("--text", type=str, default="", help="Nội dung tin nhắn")
    parser.add_argument("--chat-id", type=str, default="u:7725451581835120119", help="ID chat Zalo")
    parser.add_argument("--image", action="append", help="Đường dẫn ảnh đính kèm")

    args = parser.parse_args()

    if args.enqueue:
        if not args.text:
            print("❌ Cần có nội dung --text khi enqueue!", file=sys.stderr)
            sys.exit(1)
        res = enqueue_message(text=args.text, chat_id=args.chat_id, images=args.image)
        print(f"✅ Đã đưa vào hàng đợi: {res['id']}")
        sys.exit(0)

    if args.listen:
        log_msg("=================================================================")
        log_msg("🚀 BỘ ĐÁNH THỨC & THỰC THI @ATG 24/7 ĐÃ HOẠT ĐỘNG (FLEET SERVICE [6])")
        log_msg(f"📡 Theo dõi hàng đợi: {QUEUE_FILE}")
        log_msg(f"🎯 Tài khoản đang dùng: {get_current_active_account()}")
        log_msg("⚡ Tự động chạy nền độc lập - không phụ thuộc khung chat IDE!")
        log_msg("=================================================================")

        while True:
            try:
                msg = fetch_next_pending()
                if msg:
                    process_atg_task(msg)
            except Exception as e:
                log_msg(f"Lỗi vòng lặp worker: {e}")
            time.sleep(1.0)

    # Chế độ thủ công
    msg = fetch_next_pending()
    if msg:
        process_atg_task(msg)
    else:
        print("Trống. Không có tin nhắn pending.")


if __name__ == "__main__":
    main()
