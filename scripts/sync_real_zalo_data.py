#!/usr/bin/env python3
"""
Đồng bộ 100% dữ liệu thực tế từ Zalo Bridge (port 3050) vào D:\\hermes-main\\storage\\policy.json
"""

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
import urllib.request
from pathlib import Path

STORAGE_ROOT = Path("D:/hermes-main/storage")
POLICY_FILE = STORAGE_ROOT / "policy.json"


def sync_real_data():
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "groups").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "users").mkdir(parents=True, exist_ok=True)

    # 1. Gọi bridge lấy danh sách nhóm thực tế
    req_groups = urllib.request.Request("http://127.0.0.1:3050/groups", headers={"User-Agent": "HermesSync"})
    try:
        with urllib.request.urlopen(req_groups, timeout=10) as resp:
            data_groups = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Lỗi lấy nhóm: {e}")
        data_groups = {"groups": []}

    # 2. Gọi bridge lấy danh sách bạn bè / danh bạ thực tế
    req_friends = urllib.request.Request("http://127.0.0.1:3050/friends", headers={"User-Agent": "HermesSync"})
    try:
        with urllib.request.urlopen(req_friends, timeout=10) as resp:
            data_friends = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Lỗi lấy friends: {e}")
        data_friends = {"friends": []}

    friends_map = {}
    for fr in data_friends.get("friends", []):
        uid = str(fr.get("userId"))
        friends_map[uid] = {
            "name": fr.get("displayName") or fr.get("zaloName") or f"Zalo User {uid[:4]}",
            "phone": fr.get("phoneNumber") or "",
            "avatar": fr.get("avatar") or ""
        }

    # Bổ sung thông tin Sếp Hoàng
    friends_map["7725451581835120119"] = {
        "name": "Sếp Hoàng (CEO)",
        "phone": "84888149202",
        "avatar": "https://s120-26-ava-talk.zadn.vn/42/97ae7ee6770000211f335aefc8378eff.jpg"
    }

    # Xây dựng policy thực tế
    policy = {
        "version": "3.0-REAL",
        "account_id": "715842971730458158",
        "total_groups": len(data_groups.get("groups", [])),
        "groups": {}
    }

    for g in data_groups.get("groups", []):
        gid = g["id"]
        g_name = g["name"]
        
        # Xác định persona theo tên nhóm thực tế
        persona_key = "general"
        persona_name = "Trợ Lý Đa Năng Doanh Nghiệp"
        if "HKD" in g_name or "3T" in g_name or "Quản lý" in g_name:
            persona_key = "business"
            persona_name = "Quản Trị Doanh Nghiệp & HKD"
        elif "Nhà" in g_name or "🏠" in g_name or "Huỳnh" in g_name or "Voi" in g_name:
            persona_key = "family"
            persona_name = "Nội Trợ & Quản Lý Gia Đình"
        elif "công việc" in g_name.lower() or "trợ lý" in g_name.lower():
            persona_key = "assistant"
            persona_name = "Trợ Lý Điều Phối Công Việc 24/7"

        members_dict = {}
        for m_item in g.get("members", []):
            if isinstance(m_item, dict):
                raw_uid = str(m_item.get("uid", ""))
                real_name = m_item.get("name")
                avatar = m_item.get("avatar")
            else:
                raw_uid = str(m_item).split("_")[0]
                real_name = None
                avatar = None

            fr_info = friends_map.get(raw_uid, {})
            m_name = real_name or fr_info.get("name") or (f"Sếp Hoàng (CEO)" if raw_uid == "7725451581835120119" else f"Thành Viên {raw_uid[-4:]}")
            if raw_uid == "7725451581835120119":
                m_name = "Sếp Hoàng (CEO)"
            is_ceo = (raw_uid == "7725451581835120119")
            
            members_dict[f"u:{raw_uid}"] = {
                "name": m_name,
                "role": "Chủ Tịch (CEO)" if is_ceo else "Thành Viên",
                "phone": fr_info.get("phone", ""),
                "avatar": avatar or fr_info.get("avatar", ""),
                "can_dm": is_ceo or True,
                "can_group": True,
                "can_assign": is_ceo,
                "can_media": is_ceo
            }

            # Tạo thư mục cô lập cho từng người dùng
            u_dir = STORAGE_ROOT / "users" / f"u_{raw_uid}"
            u_dir.mkdir(parents=True, exist_ok=True)
            (u_dir / "files").mkdir(parents=True, exist_ok=True)
            (u_dir / "context").mkdir(parents=True, exist_ok=True)

        policy["groups"][gid] = {
            "name": g_name,
            "total_members": g.get("totalMembers", len(members_dict)),
            "avatar": g.get("avatar"),
            "persona_key": persona_key,
            "persona_name": persona_name,
            "bot_enabled": True,
            "members": members_dict
        }

        # Tạo thư mục chung nhóm
        g_dir = STORAGE_ROOT / "groups" / gid.replace(":", "_")
        g_dir.mkdir(parents=True, exist_ok=True)

    with open(POLICY_FILE, "w", encoding="utf-8") as f:
        json.dump(policy, f, indent=2, ensure_ascii=False)

    print(f"✅ Đã đồng bộ thành công {len(policy['groups'])} nhóm Zalo thực tế vào {POLICY_FILE}!")


if __name__ == "__main__":
    sync_real_data()
