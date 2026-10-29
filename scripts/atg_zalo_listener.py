#!/usr/bin/env python3
"""
Tầng Nhận Tin & Đánh Thức @ATG (Antigravity IDE Chat) từ Zalo.
Quản lý hàng đợi atg_queue.json giữa Zalo Adapter và Khung Chat Antigravity.
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Xác định thư mục dữ liệu cục bộ
LOCALAPPDATA = os.environ.get("LOCALAPPDATA")
if LOCALAPPDATA:
    HERMES_HOME = Path(LOCALAPPDATA) / "hermes"
else:
    HERMES_HOME = Path.home() / ".hermes"

HERMES_HOME.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = HERMES_HOME / "atg_queue.json"


def _read_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_queue(items: list):
    try:
        temp_file = QUEUE_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        temp_file.replace(QUEUE_FILE)
    except Exception as e:
        print(f"[atg_listener] Loi ghi queue: {e}", file=sys.stderr)


def enqueue_message(text: str, chat_id: str, images: list = None, sender: str = "Sep Hoang") -> dict:
    """Được gọi bởi Zalo Adapter khi phát hiện tin nhắn có tag @ATG."""
    queue = _read_queue()
    item_id = f"atg_{int(time.time()*1000)}"
    item = {
        "id": item_id,
        "text": text,
        "chat_id": str(chat_id),
        "images": images or [],
        "sender": sender,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
    }
    queue.append(item)
    _write_queue(queue)
    return item


def fetch_next_pending() -> dict | None:
    """Lấy và đánh dấu tin nhắn pending sớm nhất."""
    queue = _read_queue()
    for item in queue:
        if item.get("status") == "pending":
            item["status"] = "processing"
            item["processed_at"] = datetime.now().isoformat()
            _write_queue(queue)
            return item
    return None


def wait_for_message(timeout_s: int = 300) -> dict | None:
    """Chờ cho đến khi có tin nhắn @ATG mới hoặc hết timeout."""
    start_t = time.time()
    while time.time() - start_t < timeout_s:
        msg = fetch_next_pending()
        if msg:
            return msg
        time.sleep(1.0)
    return None


def main():
    parser = argparse.ArgumentParser(description="Bộ điều phối hàng đợi @ATG")
    parser.add_argument("--enqueue", action="store_true", help="Thêm tin nhắn vào queue")
    parser.add_argument("--listen", action="store_true", help="Chờ và nhận tin nhắn để đánh thức ATG")
    parser.add_argument("--wait", type=int, default=300, help="Thời gian chờ tối đa (giây)")
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
        # Chế độ listener: chờ tin nhắn đến
        msg = wait_for_message(timeout_s=args.wait)
        if msg:
            sys.stdout.reconfigure(encoding='utf-8')
            print("=================================================================")
            print(f"🚨 [TÍN HIỆU ĐÁNH THỨC @ATG TỪ SẾP HOÀNG QUA ZALO]")
            print(f"• ID: {msg['id']}")
            print(f"• Khung chat: {msg['chat_id']}")
            print(f"• Thời gian: {msg['timestamp']}")
            print(f"• CHỈ THỊ CỦA SẾP:")
            print(f"\"{msg['text']}\"")
            if msg.get("images"):
                print(f"• Ảnh đính kèm: {msg['images']}")
            print("=================================================================")
            sys.exit(0)
        else:
            print("⏳ Hết thời gian chờ (timeout), chưa có tin nhắn mới nào được tag @ATG.")
            sys.exit(0)

    # Mặc định: kiểm tra xem có tin nhắn nào đang chờ không
    msg = fetch_next_pending()
    if msg:
        sys.stdout.reconfigure(encoding='utf-8')
        print(f"🚨 [TÍN HIỆU @ATG TỒN ĐỌNG]: \"{msg['text']}\"")
    else:
        print("Trống. Không có tin nhắn pending.")


if __name__ == "__main__":
    main()
