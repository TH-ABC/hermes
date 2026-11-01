#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bộ kích hoạt đánh thức Khung Chat Antigravity IDE khi có tin nhắn từ Zalo Sếp Hoàng.
Khi có tin nhắn mới trong atg_nt_queue.json, script sẽ xuất nội dung và kết thúc để Antigravity IDE thức dậy.
"""

import os
import sys
import time
import json
from pathlib import Path

# UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

LOCALAPPDATA = os.environ.get("LOCALAPPDATA")
if LOCALAPPDATA:
    HERMES_HOME = Path(LOCALAPPDATA) / "hermes"
else:
    HERMES_HOME = Path.home() / ".hermes"

QUEUE_FILE = HERMES_HOME / "atg_nt_queue.json"


def read_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def main():
    initial_items = read_queue()
    seen_ids = set(item.get("id") for item in initial_items)
    
    # In thông báo chờ
    print(f"📡 [IDE-Wakeup-Daemon] Đang túc trực lắng nghe tin nhắn từ Zalo vào Khung Chat IDE... (Đã biết {len(seen_ids)} tin cũ)", flush=True)

    # Chờ tin nhắn mới
    while True:
        current_items = read_queue()
        for item in current_items:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                # Có tin nhắn mới từ Zalo!
                msg_text = item.get("text", "").strip()
                chat_id = item.get("chat_id", "")
                sender = item.get("sender", "Sếp Hoàng")
                print("\n" + "=" * 60, flush=True)
                print(f"🔔 [TÍN HIỆU ĐÁNH THỨC KHUNG CHAT ANTIGRAVITY IDE]", flush=True)
                print(f"👤 Người gửi: {sender} (Zalo)", flush=True)
                print(f"📋 Nội dung chỉ thị: {msg_text}", flush=True)
                print(f"📱 Chat ID: {chat_id}", flush=True)
                print("=" * 60 + "\n", flush=True)
                # Thoát ngay để Antigravity IDE nhận sự kiện Reactive Wakeup và bắt đầu xử lý ngay trên màn hình này!
                sys.exit(0)
        time.sleep(1.0)


if __name__ == "__main__":
    main()
