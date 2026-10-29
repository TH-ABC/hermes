#!/usr/bin/env python3
"""
Tien ich gui tin nhan / bao cao truc tiep ve Zalo cua Sep Hoang qua Zalo Bridge (Port 3050).
"""

import sys
import json
import urllib.request
import os
import argparse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

DEFAULT_CHAT_ID = "u:7725451581835120119"
BRIDGE_URL = "http://127.0.0.1:3050"


def send_to_zalo(text: str, chat_id: str = None) -> bool:
    """Gui tin nhan van ban toi khung chat Zalo."""
    if not chat_id:
        chat_id = DEFAULT_CHAT_ID

    payload = json.dumps({"chat_id": str(chat_id).strip(), "text": str(text).strip()}).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as he:
        body = he.read().decode('utf-8', errors='replace')
        print(f"[send_to_zalo] HTTP {he.code}: {body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[send_to_zalo] Loi: {e}", file=sys.stderr)
        return False


def send_media_to_zalo(file_path: str, caption: str = "", chat_id: str = None) -> bool:
    """Gui anh / video goc toi khung chat Zalo."""
    if not chat_id:
        chat_id = DEFAULT_CHAT_ID

    p = Path(file_path).resolve()
    if not p.exists():
        print(f"[send_media_to_zalo] Khong tim thay tep: {file_path}", file=sys.stderr)
        return False

    payload = json.dumps({
        "chat_id": str(chat_id).strip(),
        "file_path": str(p),
        "caption": str(caption).strip(),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/send-media",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[send_media_to_zalo] Loi: {e}", file=sys.stderr)
        return False


def send_link_to_zalo(link: str, msg: str = "", chat_id: str = None) -> bool:
    """Gui the card lien ket (Link Preview Card) truc tiep toi Zalo."""
    if not chat_id:
        chat_id = DEFAULT_CHAT_ID

    payload = json.dumps({
        "chat_id": str(chat_id).strip(),
        "link": str(link).strip(),
        "msg": str(msg).strip(),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/send-link",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[send_link_to_zalo] Loi: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Gửi tin nhắn về Zalo")
    parser.add_argument("message", nargs="?", default="", help="Nội dung tin nhắn")
    parser.add_argument("--text", type=str, default="", help="Nội dung tin nhắn (flag)")
    parser.add_argument("--file", type=str, default="", help="Đường dẫn file văn bản chứa nội dung cần gửi")
    parser.add_argument("--chat-id", type=str, default=DEFAULT_CHAT_ID, help="ID khung chat Zalo")
    parser.add_argument("--media", type=str, default="", help="Đường dẫn file ảnh/video")
    parser.add_argument("--caption", type=str, default="", help="Chú thích media")
    parser.add_argument("--link", type=str, default="", help="Gửi thẻ link preview card")

    args = parser.parse_args()
    msg_text = args.text or args.message

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                msg_text = f.read().strip()
        except Exception as fe:
            print(f"❌ Lỗi đọc file {args.file}: {fe}", file=sys.stderr)
            sys.exit(1)

    if args.media:
        ok = send_media_to_zalo(args.media, caption=args.caption or msg_text, chat_id=args.chat_id)
    elif args.link:
        ok = send_link_to_zalo(args.link, msg=msg_text or args.caption, chat_id=args.chat_id)
    else:
        if not msg_text:
            print("❌ Vui lòng nhập nội dung tin nhắn!", file=sys.stderr)
            sys.exit(1)
        ok = send_to_zalo(msg_text, chat_id=args.chat_id)

    if ok:
        print("✅ Đã gửi thành công tới Zalo!")
        sys.exit(0)
    else:
        print("❌ Gửi thất bại!", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
