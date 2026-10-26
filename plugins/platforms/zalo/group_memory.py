"""Per-Zalo-group persistent conversation summary.

Each Zalo GROUP chat gets its own rolling summary file, isolated from every
other chat by construction (keyed on the bridge's own ``"g:<threadId>"``
chat_id). When the summary would grow past a char cap, it is rewritten via
one auxiliary LLM call into a shorter summary instead of being silently
truncated or dropped — old context survives as a summary, never lost.

This is deliberately NOT a ``tools.memory_tool.MemoryStore`` subclass: that
class is tightly coupled to the single global ``MEMORY.md``/``USER.md``
pair, the agent-tool-call JSON-response shape, and per-turn
consolidation-failure bookkeeping a background per-group job doesn't need.
This module borrows the same defensive idea (atomic writes, never silently
drop data) scoped to one plain file per group chat_id instead.

Data flow: the gateway's ``pre_gateway_dispatch`` hook fires once per inbound
``MessageEvent`` that already passed the Zalo adapter's own mention/access
gating in ``_build_message_event`` (see adapter.py) -- ordinary group
chatter the bot was never addressed in never reaches here, so "group
memory" covers what the bot was actually asked about, not a silent full
transcript of everyone's chatter. Every ``_ROTATE_EVERY_N_MESSAGES`` such
turns, a background task reads the group's session transcript since the
last cursor and appends/rotates the summary.
"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_CHAR_LIMIT = 2200
_ROTATE_EVERY_N_MESSAGES = 20

# Per-process, best-effort bookkeeping -- losing counts on a gateway restart
# just means the next rotation happens a bit later than usual, never a bug.
_group_msg_counts: Dict[str, int] = {}


def _sanitize_chat_id(chat_id: str) -> str:
    return chat_id.replace(":", "_").replace("/", "_")


def _group_dir(chat_id: str) -> Path:
    from hermes_constants import get_hermes_home

    d = get_hermes_home() / "zalo_group_memory" / _sanitize_chat_id(chat_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _summary_path(chat_id: str) -> Path:
    return _group_dir(chat_id) / "GROUP_SUMMARY.md"


def _cursor_path(chat_id: str) -> Path:
    return _group_dir(chat_id) / ".cursor.json"


def _read_cursor(chat_id: str) -> int:
    try:
        data = json.loads(_cursor_path(chat_id).read_text(encoding="utf-8"))
        return int(data.get("last_message_id") or 0)
    except Exception:
        return 0


def _write_cursor(chat_id: str, last_message_id: int) -> None:
    try:
        _cursor_path(chat_id).write_text(
            json.dumps({"last_message_id": last_message_id}), encoding="utf-8"
        )
    except OSError as e:
        logger.warning("Failed to persist zalo group memory cursor for %s: %s", chat_id, e)


def read_group_summary(chat_id: str) -> str:
    try:
        return _summary_path(chat_id).read_text(encoding="utf-8")
    except OSError:
        return ""


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _format_messages(messages) -> str:
    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines).strip()


def _summarize_blocking(existing_summary: str, new_text: str) -> str:
    """Blocking (sync) one-off LLM call — run off the event loop by the
    caller via ``asyncio.to_thread``. Never raises: falls back to a plain
    concatenation on any failure so a flaky summarizer never drops data."""
    try:
        from agent.auxiliary_client import call_llm, extract_content_or_reasoning

        prompt = (
            "Ban dang tom tat lich su tro chuyen cua mot nhom chat Zalo de bot "
            "nho ngu canh nhom cho cac lan tra loi sau. Duoi day la ban tom tat "
            "hien tai (co the trong) va cac tin nhan moi ke tu lan tom tat truoc. "
            "Viet lai thanh MOT ban tom tat moi, ngan gon, suc tich (duoi "
            f"{_CHAR_LIMIT} ky tu), giu lai thong tin/quyet dinh/ngu canh quan "
            "trong cua nhom; bo qua chit-chat khong quan trong.\n\n"
            f"## Tom tat hien tai\n{existing_summary or '(chua co)'}\n\n"
            f"## Tin nhan moi\n{new_text}"
        )
        response = call_llm(
            task="zalo_group_summary", messages=[{"role": "user", "content": prompt}]
        )
        summary = extract_content_or_reasoning(response).strip()
        if summary:
            return summary[:_CHAR_LIMIT]
    except Exception as e:
        logger.warning("Zalo group summary LLM call failed: %s", e)
    # Never lose data: fall back to a plain (possibly oversized) concat
    # rather than dropping content silently.
    return f"{existing_summary}\n\n{new_text}".strip()


async def rotate_group_history(chat_id: str, session_id: str) -> None:
    """Append new messages since the last cursor into the group's rolling
    summary, rewriting it via the summarizer when it would exceed the cap."""
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        cursor = _read_cursor(chat_id)
        messages = await asyncio.to_thread(db.get_messages, session_id, after_id=cursor)
    except Exception as e:
        logger.warning("Zalo group memory: failed to read session messages for %s: %s", chat_id, e)
        return
    if not messages:
        return

    new_text = _format_messages(messages)
    if not new_text:
        return

    current = read_group_summary(chat_id)
    if len(current) + len(new_text) > _CHAR_LIMIT:
        updated = await asyncio.to_thread(_summarize_blocking, current, new_text)
    else:
        updated = f"{current}\n\n{new_text}".strip() if current else new_text

    try:
        _atomic_write(_summary_path(chat_id), updated)
    except OSError as e:
        logger.warning("Failed to persist zalo group summary for %s: %s", chat_id, e)
        return

    last_id = messages[-1].get("id")
    if last_id is not None:
        _write_cursor(chat_id, int(last_id))


def on_pre_gateway_dispatch(event=None, gateway=None, session_store=None, **kwargs) -> None:
    """``pre_gateway_dispatch`` hook.

    Must stay a plain sync function: the plugin manager invokes hook
    callbacks as ``callback(**payload)`` with no ``await``
    (hermes_cli/plugins.py's ``_invoke_hook_callback``) -- an ``async def``
    here would hand back an un-awaited, never-executed coroutine and this
    whole feature would silently do nothing. Runs while the gateway's event
    loop is active, so scheduling a background task via
    ``asyncio.create_task`` from this sync frame is safe.
    """
    try:
        source = getattr(event, "source", None)
        if source is None:
            return None
        chat_id = str(getattr(source, "chat_id", "") or "")
        platform = getattr(source, "platform", None)
        platform_value = getattr(platform, "value", None) or str(platform or "")
        if platform_value != "zalo" or not chat_id.startswith("g:"):
            return None

        _group_msg_counts[chat_id] = _group_msg_counts.get(chat_id, 0) + 1
        if _group_msg_counts[chat_id] < _ROTATE_EVERY_N_MESSAGES:
            return None
        _group_msg_counts[chat_id] = 0

        if session_store is None:
            return None
        entry = session_store.get_or_create_session(source)
        session_id = getattr(entry, "session_id", None)
        if session_id:
            asyncio.create_task(rotate_group_history(chat_id, session_id))
    except Exception as e:
        logger.warning("Zalo group memory pre_gateway_dispatch hook failed: %s", e)
    return None


def zalo_group_summary_section(session_info: Dict[str, Any]) -> str:
    """``register_system_prompt_section`` content callable."""
    if session_info.get("platform") != "zalo":
        return ""
    chat_id = session_info.get("chat_id") or ""
    if not chat_id.startswith("g:"):
        return ""
    return read_group_summary(chat_id)
