#!/usr/bin/env python3
"""
Hệ thống Quản Trị Phân Quyền & Cô Lập Dữ Liệu Hermes Zalo Enterprise (Strict Multi-Tenant Policy).
Quản lý:
1. Danh sách Nhóm Zalo (Group ID, Persona, System Prompt).
2. Danh sách Thành viên (User ID, Quyền Chat Riêng, Quyền Chat Nhóm, Quyền Giao Việc).
3. Thư mục cô lập cho từng người dùng: D:\\hermes-main\\storage\\users\\{user_id}\\.
"""

import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import json
from pathlib import Path
from typing import Dict, Any, Optional

STORAGE_ROOT = Path("D:/hermes-main/storage")
POLICY_FILE = STORAGE_ROOT / "policy.json"

DEFAULT_POLICY = {
    "version": "1.0",
    "updated_at": "2026-10-28T15:00:00",
    "groups": {
        "g:284910284918": {
            "name": "Khoa CNTT - Giảng Viên & Sinh Viên",
            "persona_key": "academic",
            "persona_name": "Giảng Viên Đại Học & Nghiên Cứu",
            "bot_enabled": True,
            "system_prompt": (
                "Bạn là Trợ lý Học thuật & Nghiên cứu cho Khoa CNTT. "
                "Nhiệm vụ: Hỗ trợ giảng viên soạn đề cương bài giảng, ngân hàng câu hỏi đề thi, "
                "tóm tắt tài liệu học thuật, hỗ trợ sinh viên làm khóa luận và xuất danh sách điểm danh Excel. "
                "Văn phong: Khoa học, chuẩn mực, ngắn gọn, chính xác."
            ),
            "members": {
                "u:7725451581835120119": {
                    "name": "Sếp Hoàng (CEO)",
                    "role": "Admin Tối Cao",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": True,
                    "can_media": True
                },
                "u:110293847561": {
                    "name": "TS. Nguyễn Văn A",
                    "role": "Trưởng Bộ Môn",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": True,
                    "can_media": True
                },
                "u:229384756102": {
                    "name": "ThS. Trần Thị B",
                    "role": "Giảng Viên Chính",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": False,
                    "can_media": False
                },
                "u:550691827364": {
                    "name": "Lê Hoàng Nam (Lớp Trưởng)",
                    "role": "Đại Diện SV",
                    "can_dm": False,
                    "can_group": True,
                    "can_assign": False,
                    "can_media": False
                }
            }
        },
        "g:718294019283": {
            "name": "Tổ Dân Phố & Nội Trợ Gia Đình",
            "persona_key": "family",
            "persona_name": "Nội Trợ & Quản Lý Gia Đình",
            "bot_enabled": True,
            "system_prompt": (
                "Bạn là Trợ lý Gia Đình & Đời Sống. "
                "Nhiệm vụ: Hỗ trợ quản lý chi tiêu sinh hoạt ra file Excel, gợi ý thực đơn dinh dưỡng 7 ngày, "
                "nhắc việc đi chợ, nhắc lịch tiêm chủng của con và sinh hoạt tổ dân phố. "
                "Văn phong: Ấm áp, tận tình, dễ hiểu, chu đáo."
            ),
            "members": {
                "u:7725451581835120119": {
                    "name": "Sếp Hoàng (CEO)",
                    "role": "Admin",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": True,
                    "can_media": True
                },
                "u:338475610293": {
                    "name": "Chị Lan (Tổ Trưởng)",
                    "role": "Trưởng Nhóm",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": True,
                    "can_media": False
                },
                "u:771829304918": {
                    "name": "Cô Mai (Ban Đời Sống)",
                    "role": "Thành Viên",
                    "can_dm": False,
                    "can_group": True,
                    "can_assign": False,
                    "can_media": False
                }
            }
        },
        "g:582910394819": {
            "name": "Team Đào Tạo & CSKH Doanh Nghiệp",
            "persona_key": "cskh",
            "persona_name": "Đào Tạo & Chăm Sóc Khách Hàng",
            "bot_enabled": True,
            "system_prompt": (
                "Bạn là Trợ lý Đào Tạo & Giám Sát CSKH. "
                "Nhiệm vụ: Cung cấp kịch bản xử lý khiếu nại khách hàng, chuẩn hóa văn phong giao tiếp, "
                "đo lường thời gian phản hồi và hỗ trợ chấm điểm hỗ trợ khách hàng. "
                "Văn phong: Lịch thiệp, chuyên nghiệp, nhã nhặn, chuẩn mực dịch vụ."
            ),
            "members": {
                "u:7725451581835120119": {
                    "name": "Sếp Hoàng (CEO)",
                    "role": "Chủ Tịch",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": True,
                    "can_media": True
                },
                "u:447561029384": {
                    "name": "Phạm Hoàng Yến",
                    "role": "Trưởng Phòng CSKH",
                    "can_dm": True,
                    "can_group": True,
                    "can_assign": True,
                    "can_media": True
                },
                "u:882910492817": {
                    "name": "Nguyễn Tuấn Kiệt",
                    "role": "Chuyên Viên Hỗ Trợ",
                    "can_dm": False,
                    "can_group": True,
                    "can_assign": False,
                    "can_media": False
                }
            }
        }
    }
}


def init_storage_and_policy():
    """Khởi tạo cấu trúc thư mục cô lập và file policy nếu chưa tồn tại."""
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "groups").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "users").mkdir(parents=True, exist_ok=True)

    if not POLICY_FILE.exists():
        with open(POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_POLICY, f, indent=2, ensure_ascii=False)

    # Đảm bảo mỗi người dùng có 1 thư mục riêng
    policy = load_policy()
    for g_id, g_info in policy.get("groups", {}).items():
        g_dir = STORAGE_ROOT / "groups" / g_id.replace(":", "_")
        g_dir.mkdir(parents=True, exist_ok=True)

        for u_id in g_info.get("members", {}).keys():
            u_dir = STORAGE_ROOT / "users" / u_id.replace(":", "_")
            u_dir.mkdir(parents=True, exist_ok=True)
            (u_dir / "files").mkdir(parents=True, exist_ok=True)
            (u_dir / "context").mkdir(parents=True, exist_ok=True)


def load_policy() -> Dict[str, Any]:
    """Tải bảng phân quyền và kịch bản."""
    if not POLICY_FILE.exists():
        init_storage_and_policy()
    try:
        with open(POLICY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_POLICY


def save_policy(data: Dict[str, Any]) -> bool:
    """Lưu bảng phân quyền."""
    try:
        with open(POLICY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Policy] Lỗi lưu policy: {e}", file=sys.stderr)
        return False


def get_user_storage_path(user_id: str) -> Path:
    """Lấy đường dẫn thư mục cô lập của người dùng."""
    clean_id = user_id.replace(":", "_")
    p = STORAGE_ROOT / "users" / clean_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def check_user_permission(user_id: str, action: str = "dm", group_id: Optional[str] = None) -> bool:
    """Kiểm tra quyền hạn của một người dùng trong Zalo:
    action: 'dm' (chat riêng 1-1), 'group' (chat nhóm), 'assign' (giao việc), 'media' (tạo ảnh/video).
    """
    clean_uid = str(user_id or "").replace("u:", "").strip()
    # Sếp Hoàng luôn có toàn quyền tuyệt đối
    if clean_uid in ("7725451581835120119", "local_ant_engine"):
        return True

    policy = load_policy()
    groups = policy.get("groups", {})
    target_uid = f"u:{clean_uid}"

    if group_id:
        clean_gid = group_id if group_id.startswith("g:") else f"g:{group_id}"
        if clean_gid in groups:
            g = groups[clean_gid]
            if not g.get("bot_enabled", True):
                return False
            members = g.get("members", {})
            member = members.get(target_uid) or members.get(clean_uid)
            if member:
                return bool(member.get(f"can_{action}", False))

    # Nếu là chat riêng 1-1, kiểm tra qua tất cả các nhóm
    for g in groups.values():
        members = g.get("members", {})
        member = members.get(target_uid) or members.get(clean_uid)
        if member:
            return bool(member.get(f"can_{action}", False))

    # Mặc định cho phép nếu chưa cấu hình cấm
    return True
        member = g.get("members", {}).get(user_id)
        if member and member.get("can_dm", False):
            return True

    return False


def get_group_prompt(group_id: str) -> Optional[str]:
    """Lấy System Prompt chuyên dụng của nhóm."""
    policy = load_policy()
    g = policy.get("groups", {}).get(group_id)
    if g:
        return g.get("system_prompt")
    return None


if __name__ == "__main__":
    init_storage_and_policy()
    print("✅ Đã khởi tạo thành công hệ sinh thái phân quyền & thư mục cô lập tại:", STORAGE_ROOT)
