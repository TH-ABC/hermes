"""
Ant-local Autonomous Dispatch Tool for Hermes Gateway
Cho phép Hermes chủ động đánh thức Kỹ Sư Trưởng Ant-local (Antigravity CLI)
khi Sếp Hoàng yêu cầu kỹ thuật, sửa mã nguồn hoặc bảo trì Sever Hermes.
"""

import json
import logging
import time
import urllib.request
from typing import Any, Dict, Optional

from tools.registry import registry
from tools.muse_media_tool import _ACTIVE_CHAT_TRACKER

logger = logging.getLogger(__name__)


def _dispatch_ant_local_task(task: str, chat_id: Optional[str] = None) -> str:
    """Đánh thức và giao tác vụ kỹ thuật cho Ant-local."""
    if not chat_id:
        chat_id = _ACTIVE_CHAT_TRACKER.get("chat_id")

    # 1. Gửi thông báo tức thì tới khung chat Zalo/Web nếu có chat_id
    wake_msg = (
        "🛠️ [Ant-local] Đã thức dậy nhận chỉ thị từ Hermes & Sếp!\n"
        f"📋 Nhiệm vụ: {task}\n"
        "⚡ Em đang mở mã nguồn đọc code và tiến hành xử lý trực tiếp trên Sever Hermes..."
    )
    if chat_id:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3050/send",
                data=json.dumps({"chat_id": str(chat_id), "text": wake_msg}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4):
                pass
        except Exception:
            pass

    # 2. Bắn tín hiệu tới Receiver :8999
    dispatched = False
    try:
        payload = json.dumps({
            "id": f"msg_gw_{int(time.time())}",
            "target_agent": "ant-local",
            "channel": "local",
            "chat_id": chat_id,
            "message": task,
            "images": [],
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8999/api/incoming",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                dispatched = True
    except Exception as e:
        logger.warning("Receiver :8999 không phản hồi: %s, fallback trực tiếp", e)

    # 3. Fallback worker
    if not dispatched:
        try:
            import sys
            from pathlib import Path
            scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            import sever_hermes_receiver
            sever_hermes_receiver.execute_ant_local_task_async(
                task_text=task,
                image_paths=[],
                chat_id=chat_id,
                channel="local",
            )
            dispatched = True
        except Exception as ex:
            return f"❌ Không thể đánh thức Ant-local: {ex}"

    return (
        f"✅ Hermes đã đánh thức Kỹ Sư Trưởng Ant-local thành công!\n"
        f"Ant-local đang đọc code D:\\hermes-main và chạy ngầm agy.exe để xử lý: \"{task}\".\n"
        f"Báo cáo nghiệm thu sẽ được Ant-local gửi trực tiếp lại cho Sếp."
    )


def _handle_trigger_ant_local(args: Any = None, **kwargs) -> str:
    params = kwargs or {}
    if isinstance(args, dict):
        params.update(args)
    task = params.get("task", "").strip()
    chat_id = params.get("chat_id")
    if not task:
        return "⚠️ Vui lòng cung cấp nội dung nhiệm vụ kỹ thuật cần Ant-local xử lý."
    return _dispatch_ant_local_task(task, chat_id=chat_id)


ANT_LOCAL_SCHEMA = {
    "name": "trigger_ant_local",
    "description": (
        "Đánh thức Kỹ Sư Trưởng Ant-local (Antigravity CLI ngầm) trên máy chủ Sever Hermes "
        "để đọc mã nguồn, chẩn đoán lỗi, sửa code trực tiếp hoặc bảo trì hệ thống. "
        "Dùng khi Sếp yêu cầu kỹ thuật, phát hiện bug, hoặc gắn thẻ @Ant-local."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Mô tả chi tiết nhiệm vụ kỹ thuật, file cần sửa hoặc lỗi cần khắc phục.",
            },
            "chat_id": {
                "type": "string",
                "description": "ID khung chat hiện tại (Zalo hoặc hệ thống) để Ant-local báo cáo nghiệm thu trực tiếp.",
            },
        },
        "required": ["task"],
    },
}

registry.register(
    name="trigger_ant_local",
    toolset="ant_local",
    schema=ANT_LOCAL_SCHEMA,
    handler=_handle_trigger_ant_local,
    requires_env=[],
    is_async=False,
    emoji="🛠️",
)
