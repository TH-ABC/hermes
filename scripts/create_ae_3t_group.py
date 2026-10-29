#!/usr/bin/env python3
"""
Tạo nhóm Zalo mới 'Ae 3T' và đưa toàn bộ thành viên từ nhóm '3TGLOBAL - TIMELESS' vào nhóm mới.
"""

import sys
import os
import json
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def create_ae_3t_group():
    # 1. Lấy thông tin nhóm 3TGLOBAL - TIMELESS
    print("1. Đang truy vấn danh sách thành viên nhóm '3TGLOBAL - TIMELESS'...")
    req = urllib.request.Request("http://127.0.0.1:3050/groups")
    with urllib.request.urlopen(req, timeout=10) as resp:
        groups_data = json.loads(resp.read().decode("utf-8"))

    source_group = None
    for g in groups_data.get("groups", []):
        if "3TGLOBAL" in g.get("name", ""):
            source_group = g
            break

    if not source_group:
        print("❌ Không tìm thấy nhóm 3TGLOBAL - TIMELESS!")
        return

    print(f"✅ Đã tìm thấy nhóm nguồn: {source_group['name']} (ID: {source_group['id']})")
    print(f"Tổng số thành viên: {len(source_group.get('members', []))}")

    # Lấy danh sách UID (loại bỏ bot id 715842971730458158 vì bot là người tạo)
    members_to_add = []
    member_names = []
    for m in source_group.get("members", []):
        uid = str(m.get("uid", "")).replace("u:", "").split("_")[0]
        name = m.get("name", f"Thành viên {uid[-4:]}")
        if uid != "715842971730458158":  # Bot ID
            members_to_add.append(uid)
            member_names.append(f"{name} ({uid})")

    print(f"Danh sách thành viên sẽ đưa vào nhóm mới 'Ae 3T':")
    for mn in member_names:
        print(f"  + {mn}")

    # 2. Gọi API tạo nhóm mới "Ae 3T"
    print("\n2. Đang gửi yêu cầu tạo nhóm 'Ae 3T' qua Zalo Bridge...")
    payload = {
        "name": "Ae 3T",
        "members": members_to_add
    }
    
    post_data = json.dumps(payload).encode("utf-8")
    req_create = urllib.request.Request(
        "http://127.0.0.1:3050/create-group",
        data=post_data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req_create, timeout=15) as resp:
            create_res = json.loads(resp.read().decode("utf-8"))
            print(f"✅ Kết quả tạo nhóm: {json.dumps(create_res, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"❌ Lỗi tạo nhóm: {e}")
        return

    new_group_info = create_res.get("group", {})
    new_group_id = new_group_info.get("groupId") or new_group_info.get("grid") or new_group_info.get("id")
    print(f"\n🎉 ĐÃ TẠO THÀNH CÔNG NHÓM 'Ae 3T'! Group ID: {new_group_id}")

    # 3. Lấy Invite Link của nhóm mới (nếu có)
    invite_link = None
    if new_group_id:
        try:
            req_link = urllib.request.Request(f"http://127.0.0.1:3050/group-link?group_id={new_group_id}")
            with urllib.request.urlopen(req_link, timeout=5) as resp:
                link_data = json.loads(resp.read().decode("utf-8"))
                invite_link = link_data.get("link", {}).get("link")
                print(f"🔗 Link tham gia nhóm: {invite_link}")
        except Exception:
            pass

    # 4. Gửi lời chào mở màn vào nhóm mới
    if new_group_id:
        print("\n3. Đang gửi lời chào mở màn vào nhóm mới...")
        welcome_msg = (
            "Dạ Sếp, Em là Trợ lý của sếp Hoàng.\n\n"
            "Em xin chào toàn thể anh em 3TGLOBAL! "
            "Nhóm 'Ae 3T' đã được khởi tạo thành công theo đúng chỉ đạo của Sếp Hoàng ạ! 🚀🤝"
        )
        msg_payload = {
            "chat_id": f"g:{new_group_id}",
            "text": welcome_msg
        }
        req_msg = urllib.request.Request(
            "http://127.0.0.1:3050/send",
            data=json.dumps(msg_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req_msg, timeout=10) as resp:
                print("✅ Đã gửi lời chào thành công vào nhóm 'Ae 3T'!")
        except Exception as e:
            print(f"⚠️ Gửi tin nhắn mở màn: {e}")

    return {
        "new_group_id": new_group_id,
        "members_added": member_names,
        "invite_link": invite_link
    }


if __name__ == "__main__":
    create_ae_3t_group()
