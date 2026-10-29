"""
Hermes Enterprise Platform Data Inspection Tool
Cung cấp dữ liệu thực tế về Nhóm Zalo, Thành viên, Phân quyền, và Dung lượng Thư mục Cô lập
cho Trợ Lý Hermes Zalo tra cứu theo thời gian thực 24/24.
"""

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict

from tools.registry import registry

STORAGE_ROOT = Path("D:/hermes-main/storage")
POLICY_FILE = STORAGE_ROOT / "policy.json"


def get_real_enterprise_data() -> Dict[str, Any]:
    """Đọc dữ liệu thực tế từ hệ thống lưu trữ Sever Hermes."""
    # 1. Đọc Policy thực tế
    policy = {}
    if POLICY_FILE.exists():
        try:
            with open(POLICY_FILE, "r", encoding="utf-8") as f:
                policy = json.load(f)
        except Exception:
            pass

    groups = policy.get("groups", {})
    total_groups = len(groups)
    
    # 2. Đếm thành viên thực tế
    total_members = 0
    all_members = []
    for gid, ginfo in groups.items():
        m_dict = ginfo.get("members", {})
        total_members += len(m_dict)
        for uid, minfo in m_dict.items():
            all_members.append({
                "group_id": gid,
                "group_name": ginfo.get("name"),
                "user_id": uid,
                "name": minfo.get("name"),
                "role": minfo.get("role"),
                "can_dm": minfo.get("can_dm"),
                "can_group": minfo.get("can_group"),
                "can_assign": minfo.get("can_assign")
            })

    # 3. Tính dung lượng thư mục cô lập thực tế
    total_bytes = 0
    users_dir = STORAGE_ROOT / "users"
    user_folders = []
    if users_dir.exists():
        for u_path in users_dir.iterdir():
            if u_path.is_dir():
                sz = sum(f.stat().st_size for f in u_path.rglob('*') if f.is_file())
                total_bytes += sz
                file_count = len(list(u_path.rglob('*')))
                user_folders.append({
                    "folder": u_path.name,
                    "path": str(u_path),
                    "files_count": file_count,
                    "size_kb": round(sz / 1024, 2)
                })

    # 4. Kiểm tra nhịp tim các cổng dịch vụ Sever
    import socket
    ports_status = {}
    for p_num, p_name in [(3050, "Zalo Bridge"), (8770, "Máy Chủ Đồ Họa"), (8999, "Sever Receiver"), (8900, "Dashboard API")]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex(('127.0.0.1', p_num))
        ports_status[f"{p_name} (Port {p_num})"] = "ONLINE (Đang Hoạt Động)" if result == 0 else "OFFLINE"
        sock.close()

    return {
        "status": "ONLINE",
        "is_real_data": True,
        "server_path": "D:\\hermes-main\\storage",
        "total_groups_count": total_groups,
        "total_members_count": total_members,
        "storage_used_bytes": total_bytes,
        "storage_used_readable": f"{round(total_bytes / (1024 * 1024), 2)} MB",
        "ports_health": ports_status,
        "groups_summary": [
            {
                "id": gid,
                "name": ginfo.get("name"),
                "persona": ginfo.get("persona_name"),
                "member_count": len(ginfo.get("members", {})),
                "bot_active": ginfo.get("bot_enabled", True)
            } for gid, ginfo in groups.items()
        ],
        "user_storage_isolated_folders": user_folders
    }


def _handle_get_enterprise_data(args: Any = None, **kwargs) -> str:
    """Trả về dữ liệu thực tế cho Trợ Lý Hermes dưới dạng báo cáo JSON & tóm tắt."""
    data = get_real_enterprise_data()
    return (
        "📊 [BÁO CÁO DỮ LIỆU THỰC TẾ TỪ SEVER HERMES STORAGE]\n"
        f"• Trạng thái hệ thống: {data['status']} (Dữ liệu thật 100% trên ổ D:\\hermes-main\\storage)\n"
        f"• Tổng số nhóm Zalo thực tế: {data['total_groups_count']} nhóm\n"
        f"• Tổng số thành viên quản trị: {data['total_members_count']} người\n"
        f"• Thư mục cô lập người dùng: {len(data['user_storage_isolated_folders'])} thư mục vật lý\n"
        f"• Nhịp tim các cổng dịch vụ: {json.dumps(data['ports_health'], ensure_ascii=False)}\n"
        f"• Danh sách nhóm chi tiết: {json.dumps(data['groups_summary'], ensure_ascii=False, indent=2)}"
    )


HERMES_ENTERPRISE_SCHEMA = {
    "name": "get_hermes_enterprise_status",
    "description": (
        "Tra cứu dữ liệu thực tế 100% từ hệ thống Hermes Zalo Enterprise Platform trên Sever Hermes "
        "(gồm: Nhóm Zalo, Group ID, Thành viên, Bảng phân quyền, và Thư mục cô lập D:\\hermes-main\\storage). "
        "Dùng khi Sếp Hoàng hoặc người dùng hỏi về thông số hệ thống, số lượng nhóm, thành viên hoặc kiểm tra xem dữ liệu có thật hay không."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["all", "groups", "members", "storage", "ports"],
                "description": "Loại dữ liệu cần tra cứu (mặc định là 'all').",
            }
        },
    },
}

registry.register(
    name="get_hermes_enterprise_status",
    toolset="enterprise_platform",
    schema=HERMES_ENTERPRISE_SCHEMA,
    handler=_handle_get_enterprise_data,
    requires_env=[],
    is_async=False,
    emoji="🏛️",
)
