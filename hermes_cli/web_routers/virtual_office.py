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
