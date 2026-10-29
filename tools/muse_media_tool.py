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
from datetime import datetime
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


def _generate_standard_media_filename(is_video: bool, ext: str) -> str:
    """Quy chuẩn đặt tên: ddmmyyyy-video01, ddmmyyyy-photo01... Tuyệt đối không dùng tiền tố muse."""
    date_str = datetime.now().strftime("%d%m%Y")
    cache_dir = get_hermes_home() / ("video_cache" if is_video else "image_cache")
    prefix = "video" if is_video else "photo"

    index = 1
    while True:
        candidate = f"{date_str}-{prefix}{index:02d}{ext}"
        if not (cache_dir / candidate).exists():
            return candidate
        index += 1


def _download_media_file(media_rel_path: str, is_video: bool = True) -> str:
    """Download media from server to local cache with standard ddmmyyyy naming."""
    cache_dir = get_hermes_home() / ("video_cache" if is_video else "image_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    _, ext = os.path.splitext(media_rel_path)
    if not ext:
        ext = ".mp4" if is_video else ".webp"

    filename = _generate_standard_media_filename(is_video, ext)
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

    return str(local_path.resolve()).replace("\\", "/")


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
                f"Không thể kết nối tới hệ thống đồ họa tại {base_url}. "
                "Vui lòng đảm bảo server đang chạy trên máy 24/24 "
                f"hoặc kiểm tra mạng nội bộ. Lỗi: {status.get('error')}"
            ),
        }

    # Ensure prompt has an explicit creative directive so Muse doesn't treat it as conversation
    clean_prompt = prompt.strip()
    low = clean_prompt.lower()
    if media_type == "image":
        if not any(w in low for w in ["vẽ", "tạo ảnh", "tạo hình", "bức ảnh", "hình ảnh", "photo", "image", "picture"]):
            clean_prompt = f"Vẽ một bức ảnh chất lượng cao chi tiết: {clean_prompt}"
    elif media_type == "video":
        if not any(w in low for w in ["video", "clip", "phim", "motion", "hoạt cảnh", "chuyển động"]):
            clean_prompt = f"Tạo một video clip chuyển động chất lượng cao: {clean_prompt}"

    formatted_files = []
    if input_images:
        for p in input_images:
            if os.path.isfile(p):
                formatted_files.append(_file_to_data_url(p))
            elif p.startswith("data:") or p.startswith("http"):
                formatted_files.append(p)

    payload = {
        "prompt": clean_prompt,
        "files": formatted_files,
        "timeout_s": timeout_s,
        "media_type": media_type,
    }

    url = f"{base_url}/v1/chat"
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = _get_headers()
    if media_type == "video":
        headers["X-Mode"] = "video"
    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s + 30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if not data.get("ok"):
            err = data.get("error", "Lỗi không xác định từ hệ thống đồ họa")
            return {"ok": False, "error": err}

        media_list = data.get("media", [])
        downloaded_paths = []

        for m_path in media_list:
            is_vid = any(m_path.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm", ".m4v"])
            downloaded = _download_media_file(m_path, is_video=is_vid)
            downloaded_paths.append(downloaded)
            try:
                caption = f"🎬 Tác phẩm video gửi sếp: \"{clean_prompt}\"" if is_vid else f"🎨 Tác phẩm ảnh gửi sếp: \"{clean_prompt}\""
                send_media_to_active_chat(downloaded, caption=caption)
            except Exception as e:
                logger.warning("Auto deliver media to chat failed: %s", e)

        raw_content = data.get("content", "Đã tạo media thành công.")
        import re
        content = re.sub(r'\[\[hatch_widget:[^\]]+\]\]', '', raw_content).strip()
        if not content:
            content = "Đã tạo media thành công!"

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
        return {"ok": False, "error": f"Lỗi gọi API hệ thống đồ họa: {str(e)}"}


_ACTIVE_CHAT_TRACKER: Dict[str, Any] = {
    "chat_id": None,
    "bridge_port": 3050,
    "last_seen": 0.0,
}


def set_active_chat(chat_id: str, bridge_port: int = 3050) -> None:
    """Record the most recent active chat ID for immediate progress notifications."""
    if chat_id:
        _ACTIVE_CHAT_TRACKER["chat_id"] = str(chat_id)
        _ACTIVE_CHAT_TRACKER["bridge_port"] = bridge_port
        _ACTIVE_CHAT_TRACKER["last_seen"] = time.time()


_RECENT_INBOUND_IMAGES: Dict[str, list] = {}


def set_last_inbound_image(chat_id: str, image_path: str) -> None:
    """Lưu lại ảnh mới nhất nhận được từ chat Zalo để tự động dùng khi tạo video."""
    if chat_id and image_path and os.path.exists(image_path):
        _ACTIVE_CHAT_TRACKER["last_inbound_image"] = image_path
        _ACTIVE_CHAT_TRACKER[f"last_img_{chat_id}"] = image_path
        cid = str(chat_id)
        if cid not in _RECENT_INBOUND_IMAGES:
            _RECENT_INBOUND_IMAGES[cid] = []
        _RECENT_INBOUND_IMAGES[cid] = [
            (p, t) for p, t in _RECENT_INBOUND_IMAGES[cid] if p != image_path
        ]
        _RECENT_INBOUND_IMAGES[cid].append((image_path, time.time()))
        if len(_RECENT_INBOUND_IMAGES[cid]) > 10:
            _RECENT_INBOUND_IMAGES[cid] = _RECENT_INBOUND_IMAGES[cid][-10:]
        logger.info("[media_tool] Đã lưu ảnh mới nhất cho chat %s: %s (Đệm gần nhất: %d ảnh)", chat_id, image_path, len(_RECENT_INBOUND_IMAGES[cid]))


def get_recent_inbound_images(chat_id: Optional[str] = None, max_age_seconds: int = 600) -> list:
    """Lấy danh sách tất cả các ảnh nhận được trong 10 phút gần đây (khi Sếp gửi nhiều ảnh)."""
    now = time.time()
    cid = str(chat_id or _ACTIVE_CHAT_TRACKER.get("chat_id") or "")
    imgs = _RECENT_INBOUND_IMAGES.get(cid, [])
    valid = [p for p, t in imgs if (now - t <= max_age_seconds) and os.path.exists(p)]
    return valid


def get_last_inbound_image(chat_id: Optional[str] = None) -> Optional[str]:
    """Lấy ảnh mới nhất của đúng khung chat hiện tại (cô lập 100%, không lôi từ chat khác)."""
    target_cid = str(chat_id or _ACTIVE_CHAT_TRACKER.get("chat_id") or "")
    if target_cid and f"last_img_{target_cid}" in _ACTIVE_CHAT_TRACKER:
        p = _ACTIVE_CHAT_TRACKER[f"last_img_{target_cid}"]
        if os.path.exists(p):
            return p
    return None


def notify_active_chat(message: str) -> bool:
    """Send an immediate notification to the active Zalo chat if recent (< 5 mins)."""
    chat_id = _ACTIVE_CHAT_TRACKER.get("chat_id")
    port = _ACTIVE_CHAT_TRACKER.get("bridge_port", 3050)
    last_seen = _ACTIVE_CHAT_TRACKER.get("last_seen", 0.0)
    if not chat_id or (time.time() - last_seen > 300):
        return False
    try:
        url = f"http://127.0.0.1:{port}/send"
        req = urllib.request.Request(
            url,
            data=json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return resp.status == 200
    except Exception as e:
        logger.debug("Failed to notify active chat: %s", e)
        return False


_DELIVERED_MEDIA_CACHE: set = set()


def send_media_to_active_chat(file_path: str, caption: str = "") -> bool:
    """Send native media directly to the active Zalo chat via bridge, strictly avoiding duplicates."""
    chat_id = _ACTIVE_CHAT_TRACKER.get("chat_id")
    port = _ACTIVE_CHAT_TRACKER.get("bridge_port", 3050)
    last_seen = _ACTIVE_CHAT_TRACKER.get("last_seen", 0.0)

    if not chat_id or (time.time() - last_seen > 1800):
        try:
            cd_file = get_hermes_home() / "channel_directory.json"
            if cd_file.exists():
                with open(cd_file, "r", encoding="utf-8") as f:
                    cd = json.load(f)
                    zalo_channels = cd.get("platforms", {}).get("zalo", [])
                    if zalo_channels:
                        chat_id = zalo_channels[0].get("id")
        except Exception:
            pass
    if not chat_id:
        chat_id = "u:7725451581835120119"

    # Tránh gửi lặp 2 lần cho cùng 1 file
    norm_path = str(file_path).replace("\\", "/")
    cache_key = f"{chat_id}::{norm_path}"
    if cache_key in _DELIVERED_MEDIA_CACHE:
        return True

    try:
        url = f"http://127.0.0.1:{port}/send-media"
        req = urllib.request.Request(
            url,
            data=json.dumps({"chat_id": str(chat_id), "file_path": str(file_path), "caption": caption}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            if resp.status == 200:
                _DELIVERED_MEDIA_CACHE.add(cache_key)
                return True
            return False
    except Exception as e:
        logger.warning("Failed to deliver media directly to active chat: %s", e)
        return False


def _handle_muse_generate(args: Any = None, **kwargs) -> str:
    """Tool handler for Hermes Agent."""
    if isinstance(args, dict):
        merged = {**args, **kwargs}
    elif isinstance(args, str):
        merged = {"prompt": args, **kwargs}
    else:
        merged = dict(kwargs)

    prompt = str(merged.get("prompt") or "").strip()
    media_type = merged.get("media_type")
    if not media_type:
        low = prompt.lower()
        if any(w in low for w in ["ảnh", "bức ảnh", "hình", "image", "photo", "picture"]):
            media_type = "image"
        else:
            media_type = "video"

    input_images = merged.get("input_images")
    if not input_images:
        current_chat_id = str(merged.get("chat_id") or _ACTIVE_CHAT_TRACKER.get("chat_id") or "")
        recent_imgs = get_recent_inbound_images(current_chat_id)
        if recent_imgs:
            input_images = recent_imgs
            logger.info("[media_tool] Tu dong nap %d anh gan nhat cho yeu cau trong chat %s: %s", len(recent_imgs), current_chat_id, recent_imgs)
        else:
            recent_img = get_last_inbound_image(current_chat_id)
            if recent_img:
                input_images = [recent_img]
                logger.info("[media_tool] Tu dong nap anh gan nhat cho yeu cau trong chat %s: %s", current_chat_id, recent_img)

    timeout_s = int(merged.get("timeout_s") or 240)

    # Immediate acknowledgement for UX so user on Zalo knows generation is running
    action_vn = "video clip" if media_type == "video" else "hình ảnh"
    duration_vn = "1-2 phút" if media_type == "video" else "15-30 giây"
    notify_active_chat(
        f"⚡ Đã nhận yêu cầu! Em đang tạo {action_vn} cho sếp: \"{prompt}\"...\n"
        f"Quá trình này mất khoảng {duration_vn}, sếp đợi em xíu nhé! 🎨⏳"
    )

    res = muse_generate_media_sync(
        prompt=prompt,
        media_type=media_type,
        input_images=input_images,
        timeout_s=timeout_s,
    )

    if not res.get("ok"):
        return f"❌ Lỗi tạo {media_type}: {res.get('error')}"

    media_paths = res.get("media_files", [])
    if not media_paths:
        raw_reply = res.get("content", "").strip()
        return (
            f"❌ Hệ thống chưa tạo được tệp {media_type} nào (Máy chủ phản hồi: \"{raw_reply}\"). "
            f"Vui lòng mô tả chi tiết hơn hoặc yêu cầu rõ hành động vẽ tranh/tạo video."
        )

    file_names = ", ".join([os.path.basename(p) for p in media_paths])
    return (
        f"✅ {res.get('content', 'Đã tạo media thành công!')}\n"
        f"Em đã tạo xong và gửi trực tiếp tác phẩm tới khung chat cho sếp rồi ạ! (Tệp: {file_names})"
    )


def _handle_muse_status(args: Any = None, **kwargs) -> str:
    st = get_muse_server_status()
    base_url = get_muse_base_url()
    if not st.get("online"):
        return f"⚠️ Hệ thống đồ họa ({base_url}) đang OFFLINE: {st.get('error')}"
    
    acc_count = st.get("accounts_count", st.get("active_accounts", "N/A"))
    return (
        f"✅ Hệ thống đồ họa ({base_url}) đang ONLINE (Máy riêng 24/24).\n"
        f"- Số tài khoản khả dụng: {acc_count}\n"
        f"- Concurrency: {st.get('concurrency', 'N/A')}\n"
        f"- Trạng thái: {st.get('status', 'ready')}"
    )


MUSE_GENERATE_SCHEMA = {
    "name": "muse_generate_media",
    "description": (
        "Tạo ảnh hoặc video TVC/motion chân thực cho sếp qua hệ thống đồ họa riêng. "
        "Sử dụng khi người dùng trên Zalo hoặc hệ thống yêu cầu: vẽ tranh, tạo ảnh, tạo video clip, tạo TVC giới thiệu sản phẩm. "
        "Tự động gửi trực tiếp file gốc chất lượng cao tới người dùng mà không cần thêm thẻ MEDIA:."
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
    "description": "Kiểm tra kết nối và tình trạng tài khoản của hệ thống đồ họa.",
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
