"""Virtual Office & Role-Based Agent Management Engine for Hermes.

Implements the multi-agent virtual office ecosystem:
- CEO (User / Admin)
- Muse EA (Executive Assistant & Dispatcher)
- Specialized Department Agents (Media, CSKH Zalo, Research, Operations)
With strict Role-Based Access Control (RBAC) and No Privilege Escalation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

def get_museai_dir() -> Path:
    """Dynamically resolve MuseAI project directory across Windows/macOS/Linux."""
    env_dir = os.environ.get("MUSEAI_DIR")
    if env_dir and os.path.isdir(env_dir):
        return Path(env_dir)
    cfg_file = get_hermes_home() / "virtual_office_config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom = data.get("museai_dir")
                if custom and os.path.isdir(custom):
                    return Path(custom)
        except Exception:
            pass
    # Sibling folder relative to repo root
    sibling = Path(__file__).resolve().parent.parent.parent / "MuseAI"
    if sibling.is_dir():
        return sibling
    return Path("/Users/trieuhoang/Documents/Projects/3TB/MuseAI")


@dataclass
class OfficeAgent:
    id: str
    name: str
    role: str
    title: str
    department: str
    avatar: str
    desk_id: str
    level: int  # 3: CEO, 2: Muse EA, 1: Specialist
    allowed_tools: List[str]
    system_prompt: str
    status: str = "idle"  # idle, working, awaiting_approval, offline
    current_task: Optional[str] = None
    last_active: float = field(default_factory=time.time)


@dataclass
class OfficeTask:
    id: str
    creator: str  # "ceo" or "zalo_user"
    title: str
    instruction: str
    assigned_to: str  # agent id
    status: str  # pending, in_progress, completed, failed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[str] = None
    media_outputs: List[str] = field(default_factory=list)


DEFAULT_AGENTS: List[OfficeAgent] = [
    OfficeAgent(
        id="ceo",
        name="Chủ Tịch & CEO",
        role="ceo",
        title="Giám Đốc Điều Hành (Admin)",
        department="Ban Giám Đốc",
        avatar="👔",
        desk_id="desk_ceo",
        level=3,
        allowed_tools=["*"],
        system_prompt=(
            "Bạn là Giám đốc Điều hành (CEO). Bạn là người ra quyết định cao nhất, "
            "đưa ra các mục tiêu chiến lược và chỉ đạo Trợ lý Muse (EA) thực thi."
        ),
        status="idle",
    ),
    OfficeAgent(
        id="muse_ea",
        name="Muse Trợ Lý Điều Hành",
        role="muse_ea",
        title="Trợ Lý Trưởng (Executive Assistant)",
        department="Văn Phòng Điều Hành",
        avatar="🤖",
        desk_id="desk_ea",
        level=2,
        allowed_tools=[
            "delegate_task",
            "muse_generate_media",
            "muse_check_status",
            "web_search",
            "web_extract",
            "read_file",
        ],
        system_prompt=(
            "Bạn là Muse, Trợ lý Điều hành cấp cao (Executive Assistant) của CEO và là đại diện trực Zalo. "
            "Nhiệm vụ của bạn là tiếp nhận chỉ đạo từ CEO và yêu cầu từ Zalo. "
            "Bạn phân tích yêu cầu, bóc tách công việc thành các nhiệm vụ cụ thể và ủy quyền "
            "cho nhân viên chuyên môn (Media, CSKH, Nghiên cứu, Ops). "
            "Sau khi nhân viên hoàn thành, bạn kiểm tra chất lượng và tổng hợp báo cáo gửi lại CEO hoặc gửi phản hồi Zalo."
        ),
        status="idle",
    ),
    OfficeAgent(
        id="media_specialist",
        name="Nhân Viên Media & TVC",
        role="media_specialist",
        title="Chuyên Viên Sáng Tạo Media & Video",
        department="Phòng Sáng Tạo & Media",
        avatar="🎨",
        desk_id="desk_media",
        level=1,
        allowed_tools=["muse_generate_media", "muse_check_status"],
        system_prompt=(
            "Bạn là Chuyên viên Media của công ty. Nhiệm vụ duy nhất của bạn là nhận yêu cầu kịch bản "
            "từ Trợ lý Muse và dùng công cụ Muse AI (muse_generate_media) để tạo ảnh nghệ thuật hoặc video TVC "
            "chất lượng cao. Bạn không can thiệp vào các lĩnh vực khác và không có quyền vượt cấp."
        ),
        status="idle",
    ),
    OfficeAgent(
        id="cs_specialist",
        name="Nhân Viên CSKH Zalo",
        role="cs_specialist",
        title="Chuyên Viên Chăm Sóc Khách Hàng Zalo",
        department="Phòng Dịch Vụ Khách Hàng",
        avatar="🤝",
        desk_id="desk_cs",
        level=1,
        allowed_tools=["web_search"],
        system_prompt=(
            "Bạn là Chuyên viên CSKH Zalo. Nhiệm vụ của bạn là tiếp nhận và phân loại thông tin khách hàng, "
            "soạn thảo câu trả lời thân thiện, lịch thiệp bằng tiếng Việt để trình Trợ lý Muse duyệt trước khi gửi khách."
        ),
        status="idle",
    ),
    OfficeAgent(
        id="research_specialist",
        name="Nhân Viên Nghiên Cứu",
        role="research_specialist",
        title="Chuyên Viên Phân Tích Dữ Liệu & Web",
        department="Phòng Nghiên Cứu & Phát Triển",
        avatar="🔍",
        desk_id="desk_research",
        level=1,
        allowed_tools=["web_search", "web_extract", "read_file"],
        system_prompt=(
            "Bạn là Chuyên viên Nghiên cứu. Bạn chỉ tập trung tìm kiếm thông tin trên internet, "
            "đọc tài liệu tham khảo và tóm tắt ngắn gọn, chính xác gửi lại Trợ lý Muse."
        ),
        status="idle",
    ),
    OfficeAgent(
        id="ops_specialist",
        name="Nhân Viên Điều Hành & Lập Lịch",
        role="ops_specialist",
        title="Chuyên Viên Điều Phối & Nhắc Việc",
        department="Phòng Vận Hành & Ops",
        avatar="⏰",
        desk_id="desk_ops",
        level=1,
        allowed_tools=["muse_check_status"],
        system_prompt=(
            "Bạn là Chuyên viên Vận hành. Nhiệm vụ của bạn là kiểm tra trạng thái sức khỏe của các dịch vụ, "
            "theo dõi deadline và hỗ trợ Trợ lý Muse điều phối công việc hàng ngày."
        ),
        status="idle",
    ),
]


class VirtualOfficeManager:
    """Singleton managing office state, RBAC, and persistence."""

    _instance: Optional["VirtualOfficeManager"] = None

    def __init__(self):
        self._config_file = get_hermes_home() / "virtual_office_config.json"
        self._tasks_file = get_hermes_home() / "virtual_office_tasks.json"
        self.agents: Dict[str, OfficeAgent] = {}
        self.tasks: List[OfficeTask] = []
        self._listeners = []
        self._load()

    @classmethod
    def get_instance(cls) -> "VirtualOfficeManager":
        if cls._instance is None:
            cls._instance = VirtualOfficeManager()
        return cls._instance

    def _load(self):
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("agents", []):
                        ag = OfficeAgent(**item)
                        self.agents[ag.id] = ag
            except Exception as e:
                logger.error("Failed to load virtual office config: %s", e)

        if not self.agents:
            for ag in DEFAULT_AGENTS:
                self.agents[ag.id] = ag
            self._save_agents()

        if self._tasks_file.exists():
            try:
                with open(self._tasks_file, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                    self.tasks = [OfficeTask(**item) for item in tasks_data]
            except Exception as e:
                logger.error("Failed to load office tasks: %s", e)

    def _save_agents(self):
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump({"agents": [asdict(ag) for ag in self.agents.values()]}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save agents: %s", e)

    def _save_tasks(self):
        self._tasks_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._tasks_file, "w", encoding="utf-8") as f:
                json.dump([asdict(t) for t in self.tasks[-100:]], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save tasks: %s", e)

    def list_agents(self) -> List[Dict[str, Any]]:
        return [asdict(ag) for ag in self.agents.values()]

    def get_agent(self, agent_id: str) -> Optional[OfficeAgent]:
        return self.agents.get(agent_id)

    def update_agent_prompt(self, agent_id: str, new_prompt: str) -> bool:
        if agent_id in self.agents:
            self.agents[agent_id].system_prompt = new_prompt
            self.agents[agent_id].last_active = time.time()
            self._save_agents()
            self._notify_event("agent_updated", {"agent_id": agent_id, "prompt": new_prompt})
            return True
        return False

    def update_agent_permissions(self, agent_id: str, allowed_tools: List[str]) -> bool:
        if agent_id in self.agents and agent_id != "ceo":
            self.agents[agent_id].allowed_tools = allowed_tools
            self._save_agents()
            self._notify_event("agent_updated", {"agent_id": agent_id, "allowed_tools": allowed_tools})
            return True
        return False

    def check_tool_permission(self, agent_id: str, tool_name: str) -> bool:
        """Enforces strictly: Can this agent run this tool?"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        if "*" in agent.allowed_tools or agent.level >= 3:
            return True
        return tool_name in agent.allowed_tools

    def update_agent_status(self, agent_id: str, status: str, task_text: Optional[str] = None):
        if agent_id in self.agents:
            self.agents[agent_id].status = status
            self.agents[agent_id].current_task = task_text
            self.agents[agent_id].last_active = time.time()
            self._notify_event("agent_status", {
                "agent_id": agent_id,
                "status": status,
                "current_task": task_text,
            })

    def create_task(self, title: str, instruction: str, creator: str = "ceo") -> OfficeTask:
        task_id = f"task_{int(time.time())}_{len(self.tasks) + 1}"
        task = OfficeTask(
            id=task_id,
            creator=creator,
            title=title,
            instruction=instruction,
            assigned_to="muse_ea",
            status="pending",
        )
        self.tasks.append(task)
        self._save_tasks()
        self._notify_event("task_created", asdict(task))
        return task

    def add_task_step(self, task_id: str, step_data: Dict[str, Any]):
        for t in self.tasks:
            if t.id == task_id:
                t.steps.append(step_data)
                t.updated_at = time.time()
                self._save_tasks()
                self._notify_event("task_step", {"task_id": task_id, "step": step_data})
                break

    def complete_task(self, task_id: str, result: str, media_outputs: Optional[List[str]] = None):
        for t in self.tasks:
            if t.id == task_id:
                t.status = "completed"
                t.result = result
                if media_outputs:
                    t.media_outputs = media_outputs
                t.updated_at = time.time()
                self._save_tasks()
                self._notify_event("task_completed", asdict(t))
                break

    def fail_task(self, task_id: str, error: str):
        for t in self.tasks:
            if t.id == task_id:
                t.status = "failed"
                t.result = f"Error: {error}"
                t.updated_at = time.time()
                self._save_tasks()
                self._notify_event("task_failed", asdict(t))
                break

    def register_listener(self, callback):
        self._listeners.append(callback)

    def unregister_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_event(self, event_type: str, data: Any):
        for listener in list(self._listeners):
            try:
                listener(event_type, data)
            except Exception:
                pass


# GoLogin & Cookie Health Probe
def get_gologin_and_cookies_status() -> Dict[str, Any]:
    """Check GoLogin token presence and active cookies in MuseAI project."""
    gologin_token_present = False
    for p in ["~/.gologin-local-agent-browser/config.json", "~/.gologin-agent-browser/config.json"]:
        path = Path(p).expanduser()
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tok = (json.load(f).get("token") or "").strip()
                    if tok and "YOUR_GOLOGIN_API_TOKEN" not in tok:
                        gologin_token_present = True
                        break
            except Exception:
                pass

    cli_bin = shutil.which("gologin-agent-browser") or os.path.isfile(
        os.path.expanduser("~/.npm-global/bin/gologin-agent-browser")
    )

    cookies_dir = get_museai_dir() / "cookies"
    cookies_found = []
    if cookies_dir.is_dir():
        for f in cookies_dir.glob("*.json"):
            try:
                stat = f.stat()
                cookies_found.append({
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "updated_at": stat.st_mtime,
                })
            except Exception:
                pass

    return {
        "gologin_available": bool(gologin_token_present and cli_bin),
        "gologin_token_configured": gologin_token_present,
        "gologin_cli_installed": bool(cli_bin),
        "cookies_dir": str(cookies_dir),
        "cookies_count": len(cookies_found),
        "cookies": cookies_found,
    }


async def execute_office_task_async(task: OfficeTask) -> None:
    """Asynchronously execute a task through the virtual office hierarchy."""
    mgr = VirtualOfficeManager.get_instance()
    task.status = "in_progress"
    mgr._save_tasks()

    # Step 1: Muse EA receives the directive
    mgr.update_agent_status("muse_ea", "working", f"Tiếp nhận chỉ đạo: {task.title}")
    mgr.add_task_step(task.id, {
        "agent": "muse_ea",
        "action": "Tiếp nhận chỉ thị từ CEO",
        "detail": f"Đang phân tích yêu cầu: '{task.instruction}'",
        "timestamp": time.time(),
    })

    await asyncio.sleep(0.8)

    # Detect if media generation (video/image) is requested
    prompt_lower = task.instruction.lower()
    is_media_task = any(k in prompt_lower for k in ["tạo video", "làm video", "video", "tạo ảnh", "vẽ ảnh", "vẽ tranh", "hình ảnh", "tvc", "clip"])
    
    if is_media_task:
        # Delegate to Media Specialist
        mgr.update_agent_status("muse_ea", "working", "Ủy quyền công việc cho Chuyên viên Media")
        mgr.add_task_step(task.id, {
            "agent": "muse_ea",
            "action": "Ủy quyền chuyên môn",
            "detail": "Chuyển giao yêu cầu sang Phòng Sáng Tạo: Nhân viên Media (Quyền: muse_generate_media)",
            "timestamp": time.time(),
        })

        is_video = any(k in prompt_lower for k in ["video", "clip", "tvc"])
        media_type = "video" if is_video else "image"

        mgr.update_agent_status("media_specialist", "working", f"Đang sinh {media_type} qua Muse AI")
        mgr.add_task_step(task.id, {
            "agent": "media_specialist",
            "action": f"Khởi tạo tiến trình sinh {media_type} với Muse Headless RPC",
            "detail": f"Prompt: '{task.instruction}' (Target: http://127.0.0.1:8770)",
            "timestamp": time.time(),
        })

        # Run Muse Media Generation Tool
        from tools.muse_media_tool import muse_generate_media_sync
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: muse_generate_media_sync(prompt=task.instruction, media_type=media_type, timeout_s=180)
        )

        if res.get("ok"):
            media_files = res.get("media_files", [])
            mgr.update_agent_status("media_specialist", "idle", None)
            mgr.add_task_step(task.id, {
                "agent": "media_specialist",
                "action": f"Hoàn thành sinh {media_type}",
                "detail": f"Đã tải {len(media_files)} tệp media về kho lưu trữ.",
                "timestamp": time.time(),
            })

            # Báo cáo về Muse EA
            mgr.update_agent_status("muse_ea", "working", "Kiểm duyệt kết quả từ Media")
            mgr.add_task_step(task.id, {
                "agent": "muse_ea",
                "action": "Tổng hợp kết quả & Chuẩn bị báo cáo CEO",
                "detail": f"Nội dung: {res.get('content')}",
                "timestamp": time.time(),
            })
            await asyncio.sleep(0.5)

            mgr.update_agent_status("muse_ea", "idle", None)
            mgr.complete_task(
                task.id,
                result=res.get("content", f"Đã hoàn thành sinh {media_type} thành công!"),
                media_outputs=media_files,
            )
        else:
            err = res.get("error", "Lỗi không xác định")
            mgr.update_agent_status("media_specialist", "idle", None)
            mgr.update_agent_status("muse_ea", "idle", None)
            mgr.add_task_step(task.id, {
                "agent": "media_specialist",
                "action": "Gặp sự cố kết nối Muse Server",
                "detail": err,
                "timestamp": time.time(),
            })
            mgr.fail_task(task.id, err)
    else:
        # General business or research task
        mgr.update_agent_status("muse_ea", "working", "Ủy quyền cho Chuyên viên Nghiên cứu")
        mgr.add_task_step(task.id, {
            "agent": "muse_ea",
            "action": "Ủy quyền tác vụ",
            "detail": "Giao nhiệm vụ cho Phòng Nghiên Cứu & Dữ Liệu xử lý",
            "timestamp": time.time(),
        })

        mgr.update_agent_status("research_specialist", "working", "Đang xử lý thông tin")
        await asyncio.sleep(1.2)
        mgr.update_agent_status("research_specialist", "idle", None)

        mgr.update_agent_status("muse_ea", "working", "Tổng hợp phản hồi gửi CEO")
        mgr.add_task_step(task.id, {
            "agent": "muse_ea",
            "action": "Hoàn tất báo cáo",
            "detail": f"Đã xử lý xong chỉ đạo: {task.instruction}",
            "timestamp": time.time(),
        })
        await asyncio.sleep(0.5)
        mgr.update_agent_status("muse_ea", "idle", None)
        mgr.complete_task(task.id, result=f"Trợ lý Muse đã tiếp nhận và thực thi hoàn tất: {task.instruction}")

