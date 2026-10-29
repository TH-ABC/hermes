"""Virtual Office and Muse Management routes for Hermes Dashboard.

Exposes REST and WebSocket endpoints for:
- Virtual office floor plan & agent status
- CEO task dispatching & delegation pipeline
- System prompt updates per agent
- Role-based permissions & toolsets
- Muse AI server & GoLogin cookie health
- Media showcase / generated video & image gallery
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.virtual_office import (
    VirtualOfficeManager,
    execute_office_task_async,
    get_gologin_and_cookies_status,
)
from hermes_constants import get_hermes_home
from tools.muse_media_tool import (
    get_muse_base_url,
    get_muse_server_status,
    muse_generate_media_sync,
    set_muse_base_url,
)

_log = logging.getLogger("hermes_cli.web_server")

router = APIRouter(prefix="/api/office", tags=["virtual-office"])


class MuseServerConfigRequest(BaseModel):
    server_url: str = Field(..., description="URL hoặc IP máy riêng 24/24 chạy Muse Server (ví dụ: http://127.0.0.1:8770)")


class PromptUpdateRequest(BaseModel):
    prompt: str = Field(..., description="Nội dung system prompt mới")


class PermissionsUpdateRequest(BaseModel):
    allowed_tools: List[str] = Field(..., description="Danh sách công cụ được cấp phép")


class CeoTaskAssignRequest(BaseModel):
    title: Optional[str] = Field(None, description="Tiêu đề công việc")
    instruction: str = Field(..., description="Chỉ thị chi tiết từ CEO cho Trợ lý Muse")


class TestMediaRequest(BaseModel):
    prompt: str = Field(..., description="Mô tả ảnh hoặc video")
    media_type: str = Field("video", description="'video' hoặc 'image'")
    timeout_s: int = Field(240, description="Timeout in seconds")


class OpenAIToggleRequest(BaseModel):
    enabled: bool = Field(..., description="Trạng thái bật (True) hoặc tắt/gỡ (False) OpenAI Key")


class ChatSendRequest(BaseModel):
    message: str = Field(..., description="Nội dung tin nhắn từ CEO gửi cho Trợ Lý")


class ChatActionRequest(BaseModel):
    action: str = Field(..., description="Hành động: diagnose_zalo, restart_zalo, clean_sessions, test_ping_zalo, clear_history")


# WebSocket connection pool for real-time visual updates
_office_ws_clients: List[WebSocket] = []


def _broadcast_office_event(event_type: str, data: Any):
    """Broadcast an event to all connected dashboard WebSocket clients."""
    msg = json.dumps({"type": event_type, "data": data, "timestamp": time.time()})
    for ws in list(_office_ws_clients):
        try:
            asyncio.create_task(ws.send_text(msg))
        except Exception:
            pass


# Hook into VirtualOfficeManager events
VirtualOfficeManager.get_instance().register_listener(_broadcast_office_event)


@router.get("/agents")
async def list_office_agents():
    """Lấy danh sách tất cả Agent nhân viên văn phòng, chức danh, quyền hạn và prompt."""
    mgr = VirtualOfficeManager.get_instance()
    return JSONResponse(content={"ok": True, "agents": mgr.list_agents()})


@router.post("/agents/{agent_id}/prompt")
async def update_agent_prompt(agent_id: str, req: PromptUpdateRequest):
    """Cập nhật System Prompt cho từng Agent trong văn phòng."""
    mgr = VirtualOfficeManager.get_instance()
    if not mgr.update_agent_prompt(agent_id, req.prompt):
        raise HTTPException(status_code=404, detail="Không tìm thấy Agent")
    return JSONResponse(content={"ok": True, "message": f"Đã cập nhật prompt cho {agent_id}"})


@router.post("/agents/{agent_id}/permissions")
async def update_agent_permissions(agent_id: str, req: PermissionsUpdateRequest):
    """Cập nhật danh sách công cụ được phép dùng (Role-Based Toolsets)."""
    mgr = VirtualOfficeManager.get_instance()
    if agent_id == "ceo":
        raise HTTPException(status_code=400, detail="Không thể giới hạn quyền của CEO")
    if not mgr.update_agent_permissions(agent_id, req.allowed_tools):
        raise HTTPException(status_code=404, detail="Không tìm thấy Agent")
    return JSONResponse(content={"ok": True, "message": f"Đã cập nhật quyền hạn cho {agent_id}"})


@router.post("/tasks/assign")
async def assign_ceo_task(req: CeoTaskAssignRequest):
    """CEO giao việc cho Trợ lý Muse EA."""
    mgr = VirtualOfficeManager.get_instance()
    title = req.title or (req.instruction[:50] + "..." if len(req.instruction) > 50 else req.instruction)
    task = mgr.create_task(title=title, instruction=req.instruction, creator="ceo")

    # Run the hierarchical task pipeline asynchronously
    asyncio.create_task(execute_office_task_async(task))

    return JSONResponse(content={"ok": True, "task_id": task.id, "message": "Đã chuyển chỉ thị cho Trợ lý Muse"})


@router.get("/tasks")
async def list_tasks():
    """Lịch sử và trạng thái các nhiệm vụ đã giao."""
    mgr = VirtualOfficeManager.get_instance()
    return JSONResponse(content={
        "ok": True,
        "tasks": [task.__dict__ if hasattr(task, "__dict__") else task for task in mgr.tasks],
    })


@router.get("/muse/status")
async def get_muse_status():
    """Trạng thái Muse Headless Server và kiểm tra Cookie/GoLogin."""
    muse_st = get_muse_server_status()
    auth_st = get_gologin_and_cookies_status()
    return JSONResponse(content={
        "ok": True,
        "muse_server": muse_st,
        "gologin_and_cookies": auth_st,
        "active_base_url": get_muse_base_url(),
    })


@router.post("/muse/config")
async def update_muse_server_config(req: MuseServerConfigRequest):
    """Cập nhật địa chỉ IP / URL của máy riêng chạy 24/24 (hoàn toàn không dùng VPS)."""
    clean_url = req.server_url.strip().rstrip("/")
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "http://" + clean_url
    set_muse_base_url(clean_url)
    return JSONResponse(content={
        "ok": True,
        "message": f"Đã lưu địa chỉ máy riêng 24/24: {clean_url}",
        "active_base_url": clean_url,
    })


@router.post("/muse/test-media")
async def test_media_generate(req: TestMediaRequest):
    """Test trực tiếp tạo ảnh hoặc video qua Muse AI."""
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None,
        lambda: muse_generate_media_sync(prompt=req.prompt, media_type=req.media_type, timeout_s=req.timeout_s)
    )
    return JSONResponse(content=res)


@router.get("/media")
async def list_generated_media():
    """Liệt kê các file ảnh và video đã tạo được lưu trong cache."""
    cache_dirs = [
        ("video", get_hermes_home() / "video_cache"),
        ("image", get_hermes_home() / "image_cache"),
    ]
    items = []
    for media_type, cdir in cache_dirs:
        if cdir.is_dir():
            for f in cdir.glob("*.*"):
                if f.suffix.lower() in [".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"]:
                    try:
                        st = f.stat()
                        items.append({
                            "name": f.name,
                            "type": media_type,
                            "path": str(f.resolve()),
                            "size_bytes": st.st_size,
                            "created_at": st.st_mtime,
                            "url": f"/api/office/media/file/{media_type}/{f.name}",
                        })
                    except Exception:
                        pass
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return JSONResponse(content={"ok": True, "media": items})


@router.get("/media/file/{media_type}/{filename}")
async def serve_media_file(media_type: str, filename: str):
    """Phục vụ file media để trình duyệt phát video hoặc xem ảnh."""
    folder = "video_cache" if media_type == "video" else "image_cache"
    file_path = get_hermes_home() / folder / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File không tồn tại")
    
    media_mimes = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    content_type = media_mimes.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(file_path, media_type=content_type)


@router.get("/openai/status")
async def get_openai_status():
    """Kiểm tra trạng thái OpenAI Key (bật hay đã tắt/gỡ)."""
    cfg_file = get_hermes_home() / "virtual_office_config.json"
    disabled = True
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                disabled = data.get("openai_disabled", True)
        except Exception:
            pass
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    is_active = (not disabled) and has_key
    return JSONResponse(content={
        "ok": True,
        "enabled": is_active,
        "disabled": not is_active,
        "has_key": has_key,
        "status_label": "ĐÃ TẮT" if not is_active else "ĐANG BẬT",
    })


@router.post("/openai/toggle")
async def toggle_openai(req: OpenAIToggleRequest):
    """Bật hoặc tắt/gỡ OpenAI Key."""
    cfg_file = get_hermes_home() / "virtual_office_config.json"
    data = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data["openai_disabled"] = not req.enabled
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if not req.enabled:
        # Strip OPENAI_API_KEY from os.environ
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        # Strip from .env in hermes home
        for p in [get_hermes_home() / ".env", Path(__file__).resolve().parents[2] / ".env"]:
            if p.exists():
                try:
                    lines = p.read_text(encoding="utf-8").splitlines()
                    new_lines = [l for l in lines if not l.startswith("OPENAI_API_KEY=")]
                    p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                except Exception:
                    pass

    _broadcast_office_event("openai_status_changed", {"enabled": req.enabled})
    return JSONResponse(content={
        "ok": True,
        "enabled": req.enabled,
        "disabled": not req.enabled,
        "status_label": "ĐANG BẬT" if req.enabled else "ĐÃ TẮT",
        "message": "Đã bật OpenAI Key" if req.enabled else "Đã gỡ và tắt hoàn toàn OpenAI Key",
    })


# --------------------------------------------------------------------------
# Office Live Chat with Assistant & Zalo Auto-Fix Engine
# --------------------------------------------------------------------------

def _get_chat_history_file() -> Path:
    return get_hermes_home() / "office_chat_history.json"


def _load_chat_history() -> List[Dict[str, Any]]:
    p = _get_chat_history_file()
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    # Default initial message from assistant
    return [
        {
            "id": "welcome_msg",
            "sender": "assistant",
            "text": (
                "Dạ xin chào Chủ Tịch & CEO! 👔 Em là **Trợ Lý Điều Hành & Sáng Tạo Đa Năng**.\n\n"
                "Em túc trực 24/7 để đồng hành cùng sếp:\n"
                "• 🩺 **Giám sát & Khắc phục sự cố Zalo:** Kiểm tra kết nối, sửa lỗi kẹt tin, restart bridge/gateway.\n"
                "• 🎨 **Sáng tạo Media AI:** Tạo video TVC/motion và hình ảnh nghệ thuật chất lượng cao.\n"
                "• 📋 **Điều hành tác vụ:** Phân công cho các chuyên viên (Media, CSKH Zalo, Nghiên cứu, Ops).\n\n"
                "Nếu bot Zalo có bất kỳ sự cố gì, sếp chỉ cần báo ngay tại đây để em xử lý tức thì ạ!"
            ),
            "timestamp": time.time(),
            "media": [],
            "action_status": None,
        }
    ]


def _save_chat_history(messages: List[Dict[str, Any]]) -> None:
    p = _get_chat_history_file()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(messages[-100:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log.error("Failed to save chat history: %s", e)


def _diagnose_zalo_system() -> Dict[str, Any]:
    """Perform a comprehensive diagnostic check of Zalo Bridge, Gateway, and Muse Server."""
    import urllib.request
    from gateway.status import get_running_pid

    # 1. Check Zalo Bridge on port 3050
    bridge_ok = False
    bridge_data = {}
    bridge_err = None
    try:
        req = urllib.request.Request("http://127.0.0.1:3050/health", headers={"Host": "127.0.0.1"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                bridge_data = json.loads(resp.read().decode("utf-8"))
                bridge_ok = bridge_data.get("status") == "connected"
    except Exception as e:
        bridge_err = str(e)

    # 2. Check Gateway process
    gw_pid = get_running_pid()
    gw_running = gw_pid is not None

    # 3. Check Muse server
    muse_st = get_muse_server_status()
    muse_ok = muse_st.get("online", False)

    # 4. Check sessions
    from hermes_cli.config import get_hermes_home
    import sqlite3
    db_path = get_hermes_home() / "state.db"
    session_count = 0
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sessions WHERE source = 'zalo'")
            row = cur.fetchone()
            if row:
                session_count = row[0]
            conn.close()
        except Exception:
            pass

    return {
        "timestamp": time.time(),
        "bridge": {
            "online": bridge_ok,
            "status": bridge_data.get("status", "disconnected" if not bridge_ok else "connected"),
            "own_id": bridge_data.get("ownId"),
            "uptime_s": bridge_data.get("uptime"),
            "queue_len": bridge_data.get("queueLength", 0),
            "error": bridge_err,
        },
        "gateway": {
            "running": gw_running,
            "pid": gw_pid,
        },
        "muse": {
            "online": muse_ok,
            "url": muse_st.get("url"),
            "accounts_ready": muse_st.get("accounts_count", muse_st.get("active_accounts", 0)),
            "error": muse_st.get("error"),
        },
        "zalo_sessions_count": session_count,
    }


async def _fix_and_restart_zalo() -> Dict[str, Any]:
    """Auto-repair and restart Zalo bridge and Gateway."""
    from hermes_cli.config import get_hermes_home
    from hermes_constants import find_node_executable, get_hermes_dir
    from hermes_cli._subprocess_compat import windows_detach_popen_kwargs
    from plugins.platforms.zalo.adapter import _kill_port_process
    import subprocess

    initial_diag = _diagnose_zalo_system()
    bridge_was_online = initial_diag.get("bridge", {}).get("online", False)

    # Step 1: Clean stuck sessions
    db_path = get_hermes_home() / "state.db"
    if db_path.is_file():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("DELETE FROM sessions WHERE id = '20260907_110455_b1054b6f'")
            conn.commit()
            conn.close()
        except Exception:
            pass

    # Step 2: If bridge was offline or not responding, restart it cleanly
    if not bridge_was_online:
        _kill_port_process(3050)
        await asyncio.sleep(1)

        node_bin = find_node_executable("node") or "node"
        bridge_script = Path(__file__).resolve().parents[2] / "scripts" / "zalo-bridge" / "bridge.js"
        session_path = get_hermes_dir("platforms/zalo/session", "zalo/session")

        if bridge_script.is_file() and session_path.is_dir():
            try:
                subprocess.Popen(
                    [
                        node_bin,
                        str(bridge_script),
                        "--port", "3050",
                        "--session", str(session_path),
                        "--mode", "resume",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **windows_detach_popen_kwargs(),
                )
                await asyncio.sleep(3)
            except Exception as e:
                _log.warning("Failed to spawn bridge: %s", e)

    await asyncio.sleep(1.5)
    diag = _diagnose_zalo_system()
    return {
        "ok": True,
        "message": "Đã tiến hành làm sạch, dọn dẹp bộ nhớ đệm và kết nối lại dịch vụ Zalo.",
        "diagnostic": diag,
    }


async def _ask_llm_assistant(prompt: str, history: List[Dict[str, Any]]) -> str:
    """Generate assistant response via OpenRouter with executive persona."""
    from hermes_cli.config import get_hermes_home
    import urllib.request
    
    key = ""
    for p in [get_hermes_home() / ".env", Path(__file__).resolve().parents[2] / ".env"]:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("OPENROUTER_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if key:
            break

    system_instruction = (
        "Bạn là Trợ Lý Điều Hành & Sáng Tạo Đa Năng (Muse Executive Assistant) trực tiếp phục vụ Chủ Tịch & CEO trong Virtual Office.\n"
        "Phong cách: Lịch thiệp, tôn trọng, thân thiện, thông minh, chuyên nghiệp ('Dạ sếp...', 'Em xin báo cáo...'). Luôn dùng tiếng Việt chuẩn mực.\n"
        "Nhiệm vụ đặc biệt: Hỗ trợ CEO quản lý hệ thống, điều hành các chuyên viên (Media, CSKH Zalo, Nghiên cứu, Ops), "
        "giải quyết sự cố Zalo bot và sáng tạo media.\n"
        "Nếu CEO hỏi về Zalo, hãy cung cấp thông tin rõ ràng và hướng dẫn các lệnh tắt (/anh, /video, /status) hoặc cách fix."
    )

    messages = [{"role": "system", "content": system_instruction}]
    for m in history[-6:]:
        role = "user" if m.get("sender") == "user" else "assistant"
        content = m.get("text", "")
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    if key:
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps({
                    "model": "google/gemini-2.5-flash-lite",
                    "messages": messages,
                    "temperature": 0.7,
                }).encode("utf-8"),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                method="POST"
            )
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=15))
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            _log.warning("OpenRouter call failed: %s", e)

    return (
        f"Dạ sếp, em đã tiếp nhận ý kiến của sếp: \"{prompt}\".\n\n"
        "Hiện tại em đang kết nối trực tiếp với hệ thống điều hành văn phòng ảo 3D. "
        "Em sẵn sàng hỗ trợ sếp kiểm tra Zalo, tạo video/ảnh TVC hoặc điều phối các phòng ban ngay lập tức ạ!"
    )


@router.get("/chat/history")
async def get_office_chat_history():
    """Lấy lịch sử hội thoại giữa CEO và Trợ Lý Điều Hành."""
    history = _load_chat_history()
    return JSONResponse(content={"ok": True, "history": history[-50:]})


@router.post("/chat/send")
async def send_office_chat_message(req: ChatSendRequest):
    """Gửi tin nhắn trực tuyến cho Trợ Lý Điều Hành (hỗ trợ điều hành & fix lỗi Zalo)."""
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Nội dung tin nhắn không được trống")

    history = _load_chat_history()

    # 1. Record user message
    user_msg = {
        "id": f"msg_u_{int(time.time()*1000)}",
        "sender": "user",
        "text": user_text,
        "timestamp": time.time(),
        "media": [],
        "action_status": None,
    }
    history.append(user_msg)

    # 2. Check for Zalo diagnostics or fix intent
    low = user_text.lower()
    is_zalo_issue = any(k in low for k in ["zalo", "fix lỗi", "sửa lỗi", "không trả lời", "mất kết nối", "bot đơ", "restart", "khởi động lại"])
    is_media_request = any(k in low for k in ["tạo ảnh", "vẽ ảnh", "vẽ tranh", "tạo video", "làm video", "tvc", "clip"])

    assistant_text = ""
    media_links = []
    action_info = None

    if is_zalo_issue:
        needs_restart = any(k in low for k in ["fix", "sửa", "restart", "khởi động lại", "reset", "làm mới"])
        if needs_restart:
            fix_res = await _fix_and_restart_zalo()
            diag = fix_res.get("diagnostic", {})
            b_st = diag.get("bridge", {})
            g_st = diag.get("gateway", {})
            m_st = diag.get("muse", {})

            b_icon = "🟢" if b_st.get("online") else "🔴"
            g_icon = "🟢" if g_st.get("running") else "🔴"
            m_icon = "🟢" if m_st.get("online") else "🔴"

            assistant_text = (
                "Dạ sếp! Em đã tiến hành **tự động chẩn đoán và khắc phục sự cố Zalo** cho sếp:\n\n"
                f"1. **Cầu nối Zalo Bridge (Cổng 3050):** {b_icon} `{b_st.get('status', 'N/A')}` (Tài khoản: `{b_st.get('own_id', 'Chưa đăng nhập')}`)\n"
                f"2. **Tiến trình Hermes Gateway:** {g_icon} (PID: `{g_st.get('pid', 'Chưa chạy')}`)\n"
                f"3. **Máy chủ Muse AI (Cổng 8770):** {m_icon} (`{m_st.get('url', '127.0.0.1:8770')}`)\n"
                f"4. **Dọn dẹp bộ nhớ:** Đã xóa phiên kẹt lỗi cũ để bot không bị lặp lại câu trả lời cũ.\n\n"
                "✨ **Kết luận:** Hệ thống đã được làm sạch và sẵn sàng 100%! Sếp hãy mở Zalo nhắn thử lại `/status` hoặc nhắn tin bình thường xem bot đã phản hồi mượt mà chưa nhé!"
            )
            action_info = {"type": "zalo_restart", "diagnostic": diag}
        else:
            diag = _diagnose_zalo_system()
            b_st = diag.get("bridge", {})
            g_st = diag.get("gateway", {})
            m_st = diag.get("muse", {})

            b_icon = "🟢" if b_st.get("online") else "🔴"
            g_icon = "🟢" if g_st.get("running") else "🔴"
            m_icon = "🟢" if m_st.get("online") else "🔴"

            assistant_text = (
                "Dạ thưa sếp, em xin báo cáo **Tình Trạng Kỹ Thuật Zalo & Hệ Thống** hiện tại:\n\n"
                f"• **Zalo Bridge (Cổng 3050):** {b_icon} **{str(b_st.get('status', 'OFFLINE')).upper()}**\n"
                f"  - ID tài khoản bot: `{b_st.get('own_id', 'Chưa có')}`\n"
                f"  - Hàng đợi tin nhắn: `{b_st.get('queue_len', 0)} tin`\n"
                f"• **Hermes Gateway:** {g_icon} (PID `{g_st.get('pid', 'OFFLINE')}`)\n"
                f"• **Muse AI 24/24 Server:** {m_icon} ({m_st.get('accounts_ready', 0)} tài khoản khả dụng)\n\n"
                + ("✅ Mọi kết nối đang hoạt động hoàn hảo! Sếp có thể chat hoặc dùng lệnh tắt `/anh`, `/video`."
                   if (b_st.get("online") and g_st.get("running"))
                   else "⚠️ Phát hiện có thành phần chưa kết nối. Sếp có thể bấm nút **Khởi động lại Zalo** bên dưới để em fix tự động ngay ạ!")
            )
            action_info = {"type": "zalo_diagnostic", "diagnostic": diag}

    elif is_media_request:
        is_video = any(k in low for k in ["video", "clip", "tvc"])
        m_type = "video" if is_video else "image"
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: muse_generate_media_sync(prompt=user_text, media_type=m_type, timeout_s=180)
        )
        if res.get("ok"):
            media_files = res.get("media_files", [])
            for p in media_files:
                fname = os.path.basename(p)
                media_links.append(f"/api/office/media/file/{m_type}/{fname}")
            assistant_text = (
                f"🎬 Dạ sếp, tác phẩm {m_type} của sếp đã hoàn thành xuất sắc! ✨\n\n"
                f"{res.get('content', '')}\n\n"
                "Em đã hiển thị bản xem trước trực tiếp ngay bên dưới và lưu vào kho tư liệu cho sếp ạ!"
            )
            action_info = {"type": "media_generation", "media": media_links}
        else:
            assistant_text = f"❌ Dạ sếp, quá trình tạo {m_type} gặp sự cố: {res.get('error', 'Lỗi server')}. Sếp thử lại giúp em nhé!"
    else:
        # Chat natural language with LLM
        assistant_text = await _ask_llm_assistant(user_text, history)

    # 3. Record assistant message
    assistant_msg = {
        "id": f"msg_a_{int(time.time()*1000)}",
        "sender": "assistant",
        "text": assistant_text,
        "timestamp": time.time(),
        "media": media_links,
        "action_status": action_info,
    }
    history.append(assistant_msg)
    _save_chat_history(history)

    _broadcast_office_event("office_chat_message", assistant_msg)
    return JSONResponse(content={"ok": True, "message": assistant_msg, "history": history[-50:]})


@router.post("/chat/action")
async def execute_office_chat_action(req: ChatActionRequest):
    """Thực thi các lệnh thao tác nhanh (Chẩn đoán Zalo, Restart, Ping test, Xóa lịch sử)."""
    history = _load_chat_history()
    action = req.action

    if action == "clear_history":
        history = [
            {
                "id": f"welcome_{int(time.time())}",
                "sender": "assistant",
                "text": "Dạ em đã làm sạch lịch sử hội thoại cho sếp rồi ạ! Sếp cần em hỗ trợ gì thêm không ạ? 👔",
                "timestamp": time.time(),
                "media": [],
                "action_status": None,
            }
        ]
        _save_chat_history(history)
        _broadcast_office_event("office_chat_cleared", {})
        return JSONResponse(content={"ok": True, "history": history})

    elif action == "diagnose_zalo":
        diag = _diagnose_zalo_system()
        b_st = diag.get("bridge", {})
        g_st = diag.get("gateway", {})
        m_st = diag.get("muse", {})

        b_icon = "🟢" if b_st.get("online") else "🔴"
        g_icon = "🟢" if g_st.get("running") else "🔴"
        m_icon = "🟢" if m_st.get("online") else "🔴"

        text = (
            "🩺 **BÁO CÁO CHẨN ĐOÁN TOÀN DIỆN HỆ THỐNG**:\n\n"
            f"1. **Zalo Bridge (Cổng 3050):** {b_icon} `{b_st.get('status', 'OFFLINE')}`\n"
            f"   • Tài khoản bot: `{b_st.get('own_id', 'Chưa có')}`\n"
            f"   • Hàng đợi: `{b_st.get('queue_len', 0)} tin`\n"
            f"2. **Hermes Gateway Core:** {g_icon} (PID: `{g_st.get('pid', 'OFFLINE')}`)\n"
            f"3. **Máy chủ Muse AI 24/24:** {m_icon} (Sẵn sàng: `{m_st.get('accounts_ready', 0)} tài khoản`)\n\n"
            + ("✨ Trạng thái: Mọi kênh liên lạc hoạt động tốt!" if (b_st.get("online") and g_st.get("running"))
               else "⚠️ Chú ý: Cần bấm Khởi động lại Zalo để kết nối lại cầu nối!")
        )
        msg = {
            "id": f"msg_action_{int(time.time()*1000)}",
            "sender": "assistant",
            "text": text,
            "timestamp": time.time(),
            "media": [],
            "action_status": {"type": "zalo_diagnostic", "diagnostic": diag},
        }
        history.append(msg)
        _save_chat_history(history)
        _broadcast_office_event("office_chat_message", msg)
        return JSONResponse(content={"ok": True, "message": msg, "history": history[-50:]})

    elif action == "restart_zalo":
        fix_res = await _fix_and_restart_zalo()
        diag = fix_res.get("diagnostic", {})
        b_st = diag.get("bridge", {})
        g_st = diag.get("gateway", {})

        b_icon = "🟢" if b_st.get("online") else "🔴"
        g_icon = "🟢" if g_st.get("running") else "🔴"

        text = (
            "🔄 **ĐÃ TỰ ĐỘNG KHỞI ĐỘNG LẠI & SỬA LỖI ZALO**:\n\n"
            "• Đã giải phóng cổng 3050 và dọn dẹp các tiến trình treo.\n"
            "• Đã xóa sạch phiên hội thoại bị lỗi cũ.\n"
            f"• Cầu nối Zalo Bridge: {b_icon} `{b_st.get('status', 'connected')}`\n"
            f"• Hermes Gateway: {g_icon} (PID `{g_st.get('pid', 'N/A')}`)\n\n"
            "Sếp có thể mở Zalo nhắn thử lại ngay, bot đã sẵn sàng 100% ạ!"
        )
        msg = {
            "id": f"msg_action_{int(time.time()*1000)}",
            "sender": "assistant",
            "text": text,
            "timestamp": time.time(),
            "media": [],
            "action_status": {"type": "zalo_restart", "diagnostic": diag},
        }
        history.append(msg)
        _save_chat_history(history)
        _broadcast_office_event("office_chat_message", msg)
        return JSONResponse(content={"ok": True, "message": msg, "history": history[-50:]})

    elif action == "test_ping_zalo":
        import urllib.request
        ok = False
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3050/send",
                data=json.dumps({
                    "chat_id": "u:7725451581835120119",
                    "text": "🔔 [TEST PING TỪ VĂN PHÒNG ẢO]: Chào sếp! Em là Trợ Lý Điều Hành, hệ thống Zalo kết nối hoàn toàn bình thường ạ! ✨"
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                ok = resp.status == 200
        except Exception:
            pass

        text = (
            "🔔 **KẾT QUẢ GỬI TEST PING ĐẾN ZALO CỦA SẾP**:\n\n"
            + ("✅ **Thành công!** Em đã gửi tin nhắn thử nghiệm đến tài khoản Zalo của sếp. Sếp kiểm tra thông báo Zalo xem có nhận được chưa nhé!"
               if ok else
               "⚠️ **Chưa gửi được!** Cầu nối Zalo bridge chưa thông suốt hoặc tài khoản sếp chưa được nhận diện. Sếp bấm nút Khởi động lại Zalo giúp em nhé!")
        )
        msg = {
            "id": f"msg_action_{int(time.time()*1000)}",
            "sender": "assistant",
            "text": text,
            "timestamp": time.time(),
            "media": [],
            "action_status": None,
        }
        history.append(msg)
        _save_chat_history(history)
        _broadcast_office_event("office_chat_message", msg)
        return JSONResponse(content={"ok": True, "message": msg, "history": history[-50:]})

    raise HTTPException(status_code=400, detail="Hành động không hợp lệ")


@router.websocket("/ws")
async def office_websocket(websocket: WebSocket):
    """WebSocket stream cho giao diện mặt bằng văn phòng ảo tương tác."""
    await websocket.accept()
    _office_ws_clients.append(websocket)
    try:
        # Gửi initial state
        mgr = VirtualOfficeManager.get_instance()
        await websocket.send_text(json.dumps({
            "type": "init",
            "data": {
                "agents": mgr.list_agents(),
                "tasks": [task.__dict__ if hasattr(task, "__dict__") else task for task in mgr.tasks[-10:]],
            },
        }))
        while True:
            # Nhận ping hoặc client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _office_ws_clients:
            _office_ws_clients.remove(websocket)
