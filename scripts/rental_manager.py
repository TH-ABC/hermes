# -*- coding: utf-8 -*-
"""
HERMES ZALO ENTERPRISE PLATFORM - RENTAL MANAGER ENGINE
Quản lý Hệ Thống Cho Thuê Bot Trợ Lý Zalo:
1. Tạo mã QR Onboarding cho khách hàng mới nhắn tin cho Bot Chủ Bth.
2. Khởi tạo Profile và Phân vùng Thư mục Sandbox cô lập tuyệt đối 100%.
3. Gán Bot độc quyền từ Kho Bot trống theo gói (1, 2, 3 Bot) và kiểm soát hạn 30 ngày.
4. Tuyệt đối không cho phép dùng chung hay cấp trùng Bot đang trong hợp đồng thuê.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = Path("D:/hermes-main")
STORAGE_DIR = ROOT_DIR / "storage"
EMPTY_POOL_PATH = STORAGE_DIR / "empty_bot_pool.json"
PROFILES_PATH = STORAGE_DIR / "rental_profiles.json"
TENANTS_PATH = STORAGE_DIR / "tenants.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[rental_manager] Lỗi đọc {path.name}: {e}", file=sys.stderr)
        return {}


def _write_json(path: Path, data: Dict[str, Any]) -> bool:
    try:
        data["updated_at"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[rental_manager] Lỗi ghi {path.name}: {e}", file=sys.stderr)
        return False


def get_empty_pool() -> Dict[str, Any]:
    return _read_json(EMPTY_POOL_PATH)


def get_rental_profiles() -> Dict[str, Any]:
    return _read_json(PROFILES_PATH)


def request_onboarding_qr(user_zalo_id: str) -> Dict[str, Any]:
    """
    Bước 1.1: Tạo mã QR kết nối Zalo cho khách hàng mới nhắn tin cho Bot Chủ Bth.
    """
    safe_uid = str(user_zalo_id).strip().replace(":", "_")
    qr_data = f"hermes-rental-onboard-{safe_uid}-{int(time.time())}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_data}"

    return {
        "ok": True,
        "user_zalo_id": user_zalo_id,
        "qr_url": qr_url,
        "instructions": (
            "📱 **HƯỚNG DẪN KẾT NỐI TRỢ LÝ HERMES VÀO ZALO:**\n"
            "1. Mở ứng dụng Zalo trên điện thoại của Anh/Chị.\n"
            "2. Nhấn biểu tượng Quét mã QR ở góc trên màn hình.\n"
            "3. Quét mã QR bên dưới để xác thực liên kết Trợ Lý.\n"
            "───────────────────────────────\n"
            "⚡ Sau khi quét xong, Bot Chủ Bth sẽ tự động gửi thông báo kích hoạt thành công!"
        )
    }


def complete_onboarding(user_zalo_id: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Bước 1.2: Tạo Profile độc lập và khởi tạo Thư mục Sandbox cô lập 100%.
    """
    safe_uid = str(user_zalo_id).strip().replace(":", "_")
    tenant_dir = STORAGE_DIR / "tenants" / safe_uid

    # Tạo đầy đủ các phân vùng cô lập vật lý
    (tenant_dir / "data").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "memory").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "files").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "bots").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "media_cache").mkdir(parents=True, exist_ok=True)

    name = display_name or f"Khách Hàng {safe_uid[-6:]}"

    # Cập nhật rental_profiles.json
    profiles_data = get_rental_profiles()
    customers = profiles_data.setdefault("customers", [])

    existing = next((c for c in customers if c.get("user_zalo_id") == user_zalo_id), None)
    if not existing:
        customer_record = {
            "user_zalo_id": user_zalo_id,
            "display_name": name,
            "package_name": "Chưa kích hoạt gói",
            "assigned_bots_count": 0,
            "assigned_bots": [],
            "sandbox_path": str(tenant_dir).replace("\\", "/"),
            "created_at": datetime.now().isoformat(),
            "expires_at": None,
            "days_remaining": 0,
            "status": "onboarded_pending_package"
        }
        customers.append(customer_record)
        profiles_data["total_customers"] = len(customers)
        profiles_data["active_customers"] = sum(1 for c in customers if c.get("status") == "active")
        _write_json(PROFILES_PATH, profiles_data)
    else:
        customer_record = existing

    # Ghi file profile nội bộ riêng tư của khách
    with open(tenant_dir / "profile.json", "w", encoding="utf-8") as pf:
        json.dump(customer_record, pf, indent=2, ensure_ascii=False)

    return {
        "ok": True,
        "user_zalo_id": user_zalo_id,
        "display_name": name,
        "sandbox_path": str(tenant_dir).replace("\\", "/"),
        "welcome_message": (
            f"🎉 **CHÚC MỪNG {name.upper()} ĐÃ KẾT NỐI THÀNH CÔNG!**\n"
            "───────────────────────────────\n"
            "🔒 Hệ thống đã khởi tạo Profile Trợ Lý riêng biệt và phân vùng bảo mật cô lập 100% cho Anh/Chị.\n\n"
            "📋 **DANH SÁCH GÓI CƯỚC THUÊ BOT TRỢ LÝ (HẠN DÙNG 30 NGÀY):**\n"
            "• Gói 1: Thuê 1 Bot Trợ Lý riêng 👉 Gửi lệnh: `/connect_bot 1`\n"
            "• Gói 2: Thuê 2 Bot Trợ Lý riêng 👉 Gửi lệnh: `/connect_bot 2`\n"
            "• Gói 3: Thuê 3 Bot Trợ Lý riêng 👉 Gửi lệnh: `/connect_bot 3`\n"
            "───────────────────────────────\n"
            "💡 *Bot được cấp là tài khoản độc quyền, chỉ phục vụ riêng Anh/Chị trong suốt 30 ngày!*"
        )
    }


def connect_bot_subscription(
    user_zalo_id: str,
    requested_count: int = 1,
    package_name: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Bước 2: Gán Bot trợ lý độc quyền từ Kho Bot Trống cho người dùng theo gói (30 ngày).
    Tuyệt đối khóa chặt, không cấp trùng cho người khác.
    """
    safe_uid = str(user_zalo_id).strip().replace(":", "_")
    tenant_dir = STORAGE_DIR / "tenants" / safe_uid
    if not tenant_dir.exists():
        complete_onboarding(user_zalo_id)

    empty_pool_data = get_empty_pool()
    all_bots = empty_pool_data.get("empty_bots", [])
    available_bots = [b for b in all_bots if b.get("status") == "available"]

    if len(available_bots) < requested_count:
        return {
            "ok": False,
            "error": f"Kho hiện chỉ còn {len(available_bots)} bot trống sẵn sàng, không đủ {requested_count} bot theo yêu cầu. Sếp Hoàng sẽ nạp thêm ngay!"
        }

    # Trích xuất và khóa độc quyền
    selected_bots = available_bots[:requested_count]
    now = datetime.now()
    exp_date = now + timedelta(days=days)
    now_iso = now.isoformat()
    exp_iso = exp_date.isoformat()

    assigned_info = []

    for idx, bot in enumerate(selected_bots):
        bot["status"] = "rented"
        bot["rented_to"] = user_zalo_id
        bot["rented_at"] = now_iso
        bot["expires_at"] = exp_iso
        bot_custom_code = f"#BOT{idx+1}_{safe_uid[-4:]}"
        bot["active_code"] = bot_custom_code

        # Tạo sandbox thư mục bot con riêng trong tenant của khách
        bot_sandbox = tenant_dir / "bots" / bot["bot_id"]
        bot_sandbox.mkdir(parents=True, exist_ok=True)
        with open(bot_sandbox / "config.json", "w", encoding="utf-8") as bf:
            json.dump(bot, bf, indent=2, ensure_ascii=False)

        assigned_info.append({
            "bot_id": bot["bot_id"],
            "name": bot["name"],
            "code": bot_custom_code,
            "mode": bot.get("mode", "chat"),
            "ai_engine": bot.get("ai_engine_account")
        })

    # Cập nhật lại kho
    empty_pool_data["available_count"] = sum(1 for b in all_bots if b.get("status") == "available")
    empty_pool_data["rented_count"] = sum(1 for b in all_bots if b.get("status") == "rented")
    _write_json(EMPTY_POOL_PATH, empty_pool_data)

    # Cập nhật hồ sơ khách
    profiles_data = get_rental_profiles()
    customers = profiles_data.setdefault("customers", [])
    cust = next((c for c in customers if c.get("user_zalo_id") == user_zalo_id), None)
    pkg = package_name or f"Gói {requested_count} Bot Trợ Lý ({days} ngày)"

    if cust:
        cust["package_name"] = pkg
        cust["assigned_bots_count"] = requested_count
        cust["assigned_bots"] = [b["bot_id"] for b in selected_bots]
        cust["expires_at"] = exp_iso
        cust["days_remaining"] = days
        cust["status"] = "active"
    else:
        customers.append({
            "user_zalo_id": user_zalo_id,
            "display_name": f"Khách Hàng {safe_uid[-6:]}",
            "package_name": pkg,
            "assigned_bots_count": requested_count,
            "assigned_bots": [b["bot_id"] for b in selected_bots],
            "sandbox_path": str(tenant_dir).replace("\\", "/"),
            "created_at": now_iso,
            "expires_at": exp_iso,
            "days_remaining": days,
            "status": "active"
        })

    profiles_data["active_customers"] = sum(1 for c in customers if c.get("status") == "active")
    _write_json(PROFILES_PATH, profiles_data)

    # Đồng bộ vào tenants.json để Bot Router nhận diện ngay lập tức
    _sync_to_tenants_json(user_zalo_id, selected_bots)

    # Soạn thảo thông báo thành công
    lines = [
        f"✅ **ĐÃ KÍCH HOẠT THÀNH CÔNG {pkg.upper()}!**",
        "───────────────────────────────",
        f"⏱️ **Thời hạn hợp đồng:** {days} ngày (Đến ngày: {exp_date.strftime('%d/%m/%Y %H:%M')})",
        "🔒 **Độc quyền sở hữu:** Bot chỉ phục vụ riêng cho tài khoản của Anh/Chị, không dùng chung với bất kỳ ai.",
        "",
        "🤖 **DANH SÁCH BOT TRỢ LÝ ĐÃ CẤP CHO ANH/CHỊ:**"
    ]
    for b in assigned_info:
        action_type = "🎬 Tạo Video & Ảnh" if b["mode"] == "video" else "💬 Chat & Công Việc"
        lines.append(f"• **{b['name']}**\n  👉 Cú pháp gọi: `{b['code']} [Nội dung yêu cầu]` ({action_type})")

    lines.append("\n👉 *Anh/Chị có thể bắt đầu gửi lệnh ngay trong khung chat này với cú pháp trên!*")

    return {
        "ok": True,
        "user_zalo_id": user_zalo_id,
        "assigned_bots": assigned_info,
        "expires_at": exp_iso,
        "days_remaining": days,
        "message": "\n".join(lines)
    }


def _sync_to_tenants_json(user_zalo_id: str, assigned_bots: List[Dict[str, Any]]):
    """Đồng bộ Bot vào tenants.json để bot_router.py nhận diện luồng."""
    tenants_data = _read_json(TENANTS_PATH)
    t_list = tenants_data.setdefault("tenants", [])

    safe_uid = str(user_zalo_id).strip().replace(":", "_")
    tenant_obj = next((t for t in t_list if t.get("zalo_id") == user_zalo_id), None)

    if not tenant_obj:
        tenant_obj = {
            "tenant_id": f"tenant_{safe_uid}",
            "name": f"Khách Thuê {safe_uid[-6:]}",
            "role": "rental_customer",
            "zalo_id": user_zalo_id,
            "status": "active",
            "max_bots": len(assigned_bots),
            "bots": []
        }
        t_list.append(tenant_obj)

    existing_bot_ids = {b["bot_id"] for b in tenant_obj.get("bots", [])}

    for b in assigned_bots:
        if b["bot_id"] not in existing_bot_ids:
            tenant_obj.setdefault("bots", []).append({
                "bot_id": b["bot_id"],
                "name": b["name"],
                "routing_code": b.get("active_code", b.get("default_code")),
                "aliases": [b.get("default_code")],
                "persona": f"Trợ lý riêng của khách hàng {safe_uid[-6:]}",
                "system_prompt": f"Em là {b['name']}, trợ lý độc quyền của Anh/Chị. Sẵn sàng phục vụ chu đáo, chuyên nghiệp.",
                "mode": b.get("mode", "chat"),
                "linked_pool_account": b.get("ai_engine_account", "ellinabetheny4127"),
                "sandbox_dir": str(STORAGE_DIR / "tenants" / safe_uid / "bots" / b["bot_id"]).replace("\\", "/"),
                "status": "active",
                "created_at": datetime.now().isoformat()
            })

    _write_json(TENANTS_PATH, tenants_data)


def check_lease_status(user_zalo_id: str) -> Dict[str, Any]:
    """Kiểm tra tình trạng gói cước và hạn dùng của khách."""
    profiles_data = get_rental_profiles()
    customers = profiles_data.get("customers", [])
    cust = next((c for c in customers if c.get("user_zalo_id") == user_zalo_id), None)

    if not cust or not cust.get("expires_at"):
        return {
            "ok": False,
            "has_subscription": False,
            "message": "Anh/Chị chưa đăng ký gói thuê Bot nào. Hãy nhắn 'thuê bot' hoặc gửi `/connect_bot 1` để đăng ký nhé!"
        }

    try:
        exp_dt = datetime.fromisoformat(cust["expires_at"])
        remaining_seconds = (exp_dt - datetime.now()).total_seconds()
        remaining_days = max(0, int(remaining_seconds // 86400))
        is_active = remaining_seconds > 0

        cust["days_remaining"] = remaining_days
        cust["status"] = "active" if is_active else "expired"
        _write_json(PROFILES_PATH, profiles_data)

        if is_active:
            msg = (
                f"📊 **THÔNG TIN GÓI THUÊ BOT CỦA ANH/CHỊ:**\n"
                f"• **Gói đang dùng:** {cust.get('package_name')}\n"
                f"• **Số lượng Bot độc quyền:** {cust.get('assigned_bots_count', len(cust.get('assigned_bots', [])))} Bot\n"
                f"• **Thời hạn còn lại:** 🟢 {remaining_days} ngày (Hết hạn lúc: {exp_dt.strftime('%d/%m/%Y %H:%M')})\n"
                f"• **Trạng thái:** Đang hoạt động bình thường & bảo mật riêng tư."
            )
        else:
            msg = (
                f"⚠️ **GÓI TRỢ LÝ CỦA ANH/CHỊ ĐÃ HẾT HẠN!**\n"
                f"• Hạn dùng đã kết thúc lúc: {exp_dt.strftime('%d/%m/%Y %H:%M')}\n"
                f"👉 Anh/Chị vui lòng liên hệ Sếp Hoàng hoặc gửi lệnh gia hạn để tiếp tục sử dụng nhé!"
            )

        return {
            "ok": True,
            "has_subscription": True,
            "is_active": is_active,
            "days_remaining": remaining_days,
            "expires_at": cust["expires_at"],
            "message": msg
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "Có lỗi khi tra cứu thời hạn."}


def add_empty_bot_to_pool(
    name: str,
    mode: str = "chat",
    ai_engine_account: str = "ellinabetheny4127",
    price_package: str = "Gói 1 Bot (30 ngày)"
) -> Dict[str, Any]:
    """Sếp Hoàng nạp thêm Bot trống vào kho để sẵn sàng cho khách thuê."""
    empty_pool_data = get_empty_pool()
    all_bots = empty_pool_data.setdefault("empty_bots", [])

    new_id = f"bot_empty_{int(time.time()*1000)}"
    code = f"#BOT_{len(all_bots)+1:02d}"

    new_bot = {
        "bot_id": new_id,
        "name": name,
        "default_code": code,
        "mode": mode,
        "ai_engine_account": ai_engine_account,
        "status": "available",
        "rented_to": null,
        "rented_at": null,
        "expires_at": null,
        "price_package": price_package
    }
    all_bots.append(new_bot)
    empty_pool_data["total_capacity"] = len(all_bots)
    empty_pool_data["available_count"] = sum(1 for b in all_bots if b.get("status") == "available")
    empty_pool_data["rented_count"] = sum(1 for b in all_bots if b.get("status") == "rented")
    _write_json(EMPTY_POOL_PATH, empty_pool_data)

    return {"ok": True, "bot_id": new_id, "name": name, "code": code}
