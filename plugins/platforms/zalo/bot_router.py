# -*- coding: utf-8 -*-
"""
HERMES ZALO ENTERPRISE PLATFORM - VIRTUAL BOT ROUTER & DISPATCHER
Quản lý định tuyến 1 tài khoản Zalo vật lý -> Nhiều Virtual Bot độc lập.
Tự động bóc tách mã riêng (#MÃ, !mã, @mã), cách ly luồng và liên kết tài khoản AI.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

logger = logging.getLogger("hermes.zalo.bot_router")

ROOT_DIR = Path("D:/hermes-main")
STORAGE_DIR = ROOT_DIR / "storage"
TENANTS_FILE = STORAGE_DIR / "tenants.json"


def _load_tenants_data() -> Dict[str, Any]:
    if not TENANTS_FILE.exists():
        return {"version": "1.0-UNLIMITED-VIRTUAL-BOTS", "tenants": []}
    try:
        with open(TENANTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[bot_router] Lỗi đọc tenants.json: {e}")
        return {"version": "1.0-UNLIMITED-VIRTUAL-BOTS", "tenants": []}


def _save_tenants_data(data: Dict[str, Any]) -> bool:
    try:
        data["updated_at"] = datetime.now().isoformat()
        with open(TENANTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"[bot_router] Lỗi ghi tenants.json: {e}")
        return False


def get_all_bots(tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các bot, hoặc bot theo tenant_id."""
    data = _load_tenants_data()
    bots = []
    for tenant in data.get("tenants", []):
        if tenant_id and tenant.get("tenant_id") != tenant_id:
            continue
        for b in tenant.get("bots", []):
            bot_copy = dict(b)
            bot_copy["tenant_id"] = tenant.get("tenant_id")
            bot_copy["tenant_name"] = tenant.get("name")
            bots.append(bot_copy)
    return bots


def route_inbound_message(raw_text: str, sender_id: str = "") -> Dict[str, Any]:
    """
    Phân tích cú pháp tin nhắn và tìm Bot khớp mã.
    Hỗ trợ các dạng:
    - #CODE: nội dung
    - #CODE nội dung
    - !code nội dung
    - @code nội dung
    """
    if not raw_text:
        return {"matched": False, "clean_text": ""}

    text = raw_text.strip()
    data = _load_tenants_data()
    all_bots = get_all_bots()

    # Pattern nhận diện mã: #ABC, !ABC, @ABC ở đầu tin nhắn
    match = re.match(r'^([#!@][A-Za-z0-9_\-]+)(?:[:\s\-,]+|\s*)(.*)$', text, re.DOTALL | re.IGNORECASE)

    extracted_code = ""
    clean_text = text

    if match:
        extracted_code = match.group(1).strip()
        clean_text = match.group(2).strip()

    # Tìm bot khớp extracted_code
    if extracted_code:
        code_low = extracted_code.lower()
        for b in all_bots:
            if b.get("status") != "active":
                continue
            
            main_code = b.get("routing_code", "").lower()
            aliases = [a.lower() for a in b.get("aliases", [])]

            if code_low == main_code or code_low in aliases:
                # Tìm thấy bot khớp mã
                sandbox = b.get("sandbox_dir") or str(STORAGE_DIR / "tenants" / b["tenant_id"] / "bots" / b["bot_id"])
                Path(sandbox).mkdir(parents=True, exist_ok=True)

                logger.info(f"[bot_router] ✅ Khớp mã '{extracted_code}' -> Bot '{b['name']}' ({b['bot_id']})")
                return {
                    "matched": True,
                    "bot_id": b["bot_id"],
                    "bot_name": b["name"],
                    "tenant_id": b["tenant_id"],
                    "routing_code": b.get("routing_code"),
                    "matched_code": extracted_code,
                    "clean_text": clean_text if clean_text else text,
                    "persona": b.get("persona", ""),
                    "system_prompt": b.get("system_prompt", ""),
                    "mode": b.get("mode", "chat"),
                    "linked_pool_account": b.get("linked_pool_account"),
                    "sandbox_dir": sandbox,
                    "response_prefix": f"🤖 [{b['name']}] "
                }

    # Nếu người dùng hỏi hướng dẫn mã bot
    low = text.lower()
    if any(k in low for k in ["danh sách bot", "ds bot", "các bot", "menu bot", "hướng dẫn bot", "!help", "#help"]):
        guide_lines = ["📋 **DANH SÁCH CÁC TRỢ LÝ BOT ĐANG HOẠT ĐỘNG (1 ZALO ĐA BOT):**"]
        for b in all_bots:
            codes = [b.get("routing_code")] + b.get("aliases", [])
            code_str = " / ".join(filter(None, codes))
            guide_lines.append(f"• **{b['name']}**: Gửi `{code_str} [Nội dung]` ({b.get('persona', '')})")
        guide_lines.append("\n👉 *Chỉ cần gõ mã ở đầu tin nhắn, hệ thống sẽ tự động chuyển đúng luồng bot phục vụ!*")
        
        return {
            "matched": True,
            "is_help": True,
            "bot_id": "system_help",
            "bot_name": "Điều Phối Hệ Thống",
            "clean_text": text,
            "help_message": "\n".join(guide_lines)
        }

    # Không khớp mã -> Không can thiệp, chạy luồng mặc định
    return {"matched": False, "clean_text": text}


def add_virtual_bot(tenant_id: str, bot_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Thêm một Virtual Bot mới vào Tenant (Không giới hạn số lượng)."""
    data = _load_tenants_data()
    for tenant in data.get("tenants", []):
        if tenant.get("tenant_id") == tenant_id:
            bots = tenant.setdefault("bots", [])
            max_bots = tenant.get("max_bots", -1)
            if max_bots != -1 and len(bots) >= max_bots:
                return False, f"Đã đạt giới hạn tối đa {max_bots} bot của Tenant này."

            bot_id = bot_data.get("bot_id") or f"bot_{int(datetime.now().timestamp()*1000)}"
            code = bot_data.get("routing_code")
            if not code:
                return False, "Cần có routing_code (ví dụ: #BOT1, #SALE)."

            if not code.startswith("#") and not code.startswith("!") and not code.startswith("@"):
                code = f"#{code}"

            new_bot = {
                "bot_id": bot_id,
                "name": bot_data.get("name", f"Trợ Lý {code}"),
                "routing_code": code,
                "aliases": bot_data.get("aliases", []),
                "persona": bot_data.get("persona", "Trợ lý hỗ trợ nghiệp vụ chuyên sâu."),
                "system_prompt": bot_data.get("system_prompt", f"Em là Trợ lý {code} của sếp Hoàng."),
                "mode": bot_data.get("mode", "chat"),
                "linked_pool_account": bot_data.get("linked_pool_account", "ellinabetheny4127"),
                "sandbox_dir": str(STORAGE_DIR / "tenants" / tenant_id / "bots" / bot_id),
                "status": "active",
                "created_at": datetime.now().isoformat()
            }

            Path(new_bot["sandbox_dir"]).mkdir(parents=True, exist_ok=True)
            bots.append(new_bot)
            _save_tenants_data(data)
            return True, bot_id

    return False, f"Không tìm thấy Tenant {tenant_id}"


def update_virtual_bot(tenant_id: str, bot_id: str, updates: Dict[str, Any]) -> bool:
    """Cập nhật thông tin bot."""
    data = _load_tenants_data()
    for tenant in data.get("tenants", []):
        if tenant.get("tenant_id") == tenant_id:
            for b in tenant.get("bots", []):
                if b.get("bot_id") == bot_id:
                    for k, v in updates.items():
                        if k != "bot_id":
                            b[k] = v
                    return _save_tenants_data(data)
    return False


def delete_virtual_bot(tenant_id: str, bot_id: str) -> bool:
    """Xóa một bot."""
    data = _load_tenants_data()
    for tenant in data.get("tenants", []):
        if tenant.get("tenant_id") == tenant_id:
            init_len = len(tenant.get("bots", []))
            tenant["bots"] = [b for b in tenant.get("bots", []) if b.get("bot_id") != bot_id]
            if len(tenant["bots"]) < init_len:
                return _save_tenants_data(data)
    return False
