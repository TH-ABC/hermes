"""Muse AI Media Generation Tool for Hermes Agent.

Provides image and video generation powered by Muse AI headless server (:8770).
Generated media is saved to local cache and formatted with MEDIA:/path/to/file
so platforms like Zalo, Telegram, and Discord automatically deliver native attachments.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import json

from hermes_constants import get_hermes_home
from tools.registry import registry

logger = logging.getLogger(__name__)

MUSE_BASE_URL = os.environ.get("MUSE_BASE_URL", "http://127.0.0.1:8770").rstrip("/")
MUSE_API_KEY = os.environ.get("MUSE_API_KEY", "").strip()


def get_muse_base_url() -> str:
    """Return the active Muse server URL (custom 24/7 dedicated machine or localhost)."""
    cfg_file = get_hermes_home() / "virtual_office_config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_url = data.get("muse_server_url")
                if custom_url and custom_url.strip():
                    return custom_url.strip().rstrip("/")
        except Exception:
            pass
    return os.environ.get("MUSE_BASE_URL", "http://127.0.0.1:8770").rstrip("/")


def set_muse_base_url(new_url: str) -> None:
    """Save custom 24/7 dedicated machine IP/URL to configuration."""
    cfg_file = get_hermes_home() / "virtual_office_config.json"
    data = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["muse_server_url"] = new_url.strip().rstrip("/")
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _get_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if MUSE_API_KEY:
        headers["X-API-Key"] = MUSE_API_KEY
    return headers


def _file_to_data_url(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "image/jpeg"
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def check_muse_available() -> bool:
    """Return True if Muse server is configured or reachable."""
    # Always allow registering if MUSE_BASE_URL is set or default localhost
    return True


def get_muse_server_status() -> Dict[str, Any]:
    """Query /v1/status from Muse headless server."""
    base_url = get_muse_base_url()
    url = f"{base_url}/v1/status"
    req = urllib.request.Request(url, headers=_get_headers())
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"online": True, "url": base_url, **data}
    except Exception as e:
        return {"online": False, "error": str(e), "url": base_url}


def _download_media_file(media_rel_path: str, is_video: bool = True) -> str:
    """Download media from /media/... to local cache."""
    cache_dir = get_hermes_home() / ("video_cache" if is_video else "image_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    filename = os.path.basename(media_rel_path)
    local_path = cache_dir / filename

    media_url = f"{get_muse_base_url()}{media_rel_path}"
    headers = {}
    if MUSE_API_KEY:
        headers["X-API-Key"] = MUSE_API_KEY

    req = urllib.request.Request(media_url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp, open(local_path, "wb") as f:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)

    return str(local_path.resolve())


def muse_generate_media_sync(
    prompt: str,
    media_type: str = "video",
    input_images: Optional[List[str]] = None,
    timeout_s: int = 240,
) -> Dict[str, Any]:
    """Synchronous core implementation for Muse media generation."""
    status = get_muse_server_status()
    base_url = get_muse_base_url()
    if not status.get("online"):
        return {
            "ok": False,
            "error": (
                f"Không thể kết nối tới Muse Server tại {base_url}. "
                "Vui lòng đảm bảo server đang chạy trên máy 24/24 (python run.py headless --port 8770) "
                f"hoặc kiểm tra mạng nội bộ. Lỗi: {status.get('error')}"
            ),
        }

    formatted_files = []
    if input_images:
        for p in input_images:
            if os.path.isfile(p):
                formatted_files.append(_file_to_data_url(p))
            elif p.startswith("data:") or p.startswith("http"):
                formatted_files.append(p)

    payload = {
        "prompt": prompt,
        "files": formatted_files,
        "timeout_s": timeout_s,
    }

    url = f"{base_url}/v1/chat"
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body_bytes, headers=_get_headers(), method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s + 30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if not data.get("ok"):
            err = data.get("error", "Lỗi không xác định từ Muse server")
            return {"ok": False, "error": err}

        media_list = data.get("media", [])
        downloaded_paths = []

        for m_path in media_list:
            is_vid = m_path.lower().endswith((".mp4", ".mov", ".webm")) or media_type == "video"
            downloaded = _download_media_file(m_path, is_video=is_vid)
            downloaded_paths.append(downloaded)

        content = data.get("content", "Đã tạo media thành công.")
        return {
            "ok": True,
            "content": content,
            "media_files": downloaded_paths,
            "raw_media": media_list,
        }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        return {"ok": False, "error": f"Lỗi gọi Muse API: {str(e)}"}


def _handle_muse_generate(
    prompt: str,
    media_type: str = "video",
    input_images: Optional[List[str]] = None,
    timeout_s: int = 240,
) -> str:
    """Tool handler for Hermes Agent."""
    res = muse_generate_media_sync(
        prompt=prompt,
        media_type=media_type,
        input_images=input_images,
        timeout_s=timeout_s,
    )

    if not res.get("ok"):
        return f"❌ Lỗi tạo {media_type}: {res.get('error')}"

    media_paths = res.get("media_files", [])
    response_lines = [
        f"✅ {res.get('content', 'Đã tạo media thành công!')}"
    ]

    for p in media_paths:
        response_lines.append(f"MEDIA:{p}")

    return "\n".join(response_lines)


def _handle_muse_status() -> str:
    st = get_muse_server_status()
    base_url = get_muse_base_url()
    if not st.get("online"):
        return f"⚠️ Muse Server ({base_url}) đang OFFLINE: {st.get('error')}"
    
    acc_count = st.get("accounts_count", st.get("active_accounts", "N/A"))
    return (
        f"✅ Muse Server ({base_url}) đang ONLINE (Máy riêng 24/24).\n"
        f"- Số tài khoản khả dụng: {acc_count}\n"
        f"- Concurrency: {st.get('concurrency', 'N/A')}\n"
        f"- Trạng thái: {st.get('status', 'ready')}"
    )


MUSE_GENERATE_SCHEMA = {
    "name": "muse_generate_media",
    "description": (
        "Tạo ảnh hoặc video TVC/motion chân thực thông qua Muse AI. "
        "Sử dụng khi người dùng trên Zalo hoặc hệ thống yêu cầu: vẽ tranh, tạo ảnh, tạo video clip, tạo TVC giới thiệu sản phẩm. "
        "Trả về định dạng MEDIA:/path/to/file để nền tảng tự động gửi đính kèm file gốc."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Mô tả chi tiết nội dung ảnh hoặc video cần tạo bằng tiếng Việt hoặc tiếng Anh.",
            },
            "media_type": {
                "type": "string",
                "enum": ["video", "image"],
                "default": "video",
                "description": "Loại media cần tạo: 'video' (clip chuyển động ngắn 5s-10s) hoặc 'image' (ảnh tĩnh chất lượng cao).",
            },
            "input_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Đường dẫn file ảnh cục bộ trên máy nếu muốn làm video từ ảnh có sẵn (Image to Video).",
            },
            "timeout_s": {
                "type": "integer",
                "default": 240,
                "description": "Thời gian chờ tối đa (giây). Video thường cần 60-120 giây.",
            },
        },
        "required": ["prompt"],
    },
}

MUSE_STATUS_SCHEMA = {
    "name": "muse_check_status",
    "description": "Kiểm tra kết nối và tình trạng tài khoản của Muse AI server.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

registry.register(
    name="muse_generate_media",
    toolset="muse",
    schema=MUSE_GENERATE_SCHEMA,
    handler=_handle_muse_generate,
    check_fn=check_muse_available,
    requires_env=[],
    is_async=False,
    emoji="🎨",
)

registry.register(
    name="muse_check_status",
    toolset="muse",
    schema=MUSE_STATUS_SCHEMA,
    handler=_handle_muse_status,
    check_fn=check_muse_available,
    requires_env=[],
    is_async=False,
    emoji="📡",
)
