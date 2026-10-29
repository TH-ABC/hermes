#!/usr/bin/env python3
"""
Muse.ai Multi-Account Bridge Pool (headless Noise_XX engine, no browser)
Each job opens its own encrypted socket to the account's Muse VM (client/muse_noise_engine.py),
so an account runs several generations at once and the whole pool needs no Chromium.

- Batch items are spread over all healthy accounts (least-busy first).
- An account answering 503 / "busy" is cooled down and its item re-queued elsewhere.
- The cookies dir is watched: drop a new file in -> it is loaded, delete it -> it is retired.
- A periodic health check marks accounts whose session expired.

Usage:
  python bridge/pool.py --cookies-dir cookies --port 8770 [--per-account 2] [--host 0.0.0.0]
Env:
  MUSE_API_KEY          if set, /v1/* and /media/* require header X-API-Key (or Authorization: Bearer)
  MUSE_SESSION_COOKIE   session cookie name used to detect logout (default hatch_sess)
"""

import argparse
import hashlib
import hmac
import asyncio
import json
import io
import mimetypes
import random
import re
import os
import shutil
import sys
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any

from concurrent.futures import ThreadPoolExecutor

from aiohttp import web

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from client.muse_noise_engine import MuseNoiseClient  # noqa: E402
from bridge import drive_offload  # noqa: E402
from bridge import notify  # noqa: E402
from tools.import_cookies import normalize as normalize_cookies, parse_header as parse_cookie_header  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(ROOT_DIR, "scratch", "media")
UPLOAD_DIR = os.path.join(ROOT_DIR, "scratch", "uploads")
INDEX_HTML = os.path.join(ROOT_DIR, "bridge", "index.html")
DOCS_HTML = os.path.join(ROOT_DIR, "bridge", "docs.html")
for _d in (MEDIA_DIR, UPLOAD_DIR):
    os.makedirs(_d, exist_ok=True)
# Every running job blocks one thread on its socket; the default executor (cpu+4) would cap the pool.
WORKER_THREADS = int(os.environ.get("MUSEAI_WORKER_THREADS", "128"))
DEFAULT_FILE_PROMPT = "Hãy xem và phân tích hình ảnh/video này."
# A reply with no media that says one of these is a failed render, not a text answer.
RENDER_FAIL_KEYWORDS = ["503", "lỗi 503", "tạm ngưng", "không render được", "chưa tạo được video",
                        "không khả dụng", "hệ thống tạo video đang bận", "lỗi kỹ thuật"]
STATE_DIR = os.path.join(ROOT_DIR, "scratch", "pool")
SESSION_COOKIE = os.environ.get("MUSE_SESSION_COOKIE", "hatch_sess")
# Muse's fixed refusal for accounts whose region/plan can't render video (retrying never helps).
NO_VIDEO_KEYWORDS = ["quốc gia/khu vực", "quốc gia, khu vực", "giới hạn cố định",
                     "giới hạn lâu dài", "không khả dụng ở khu vực", "khu vực hiện tại", "lỗi 403",
                     "khả dụng ở khu vực", "khu vực của bạn", "chưa tạo được video", "chưa hỗ trợ video",
                     "chặn tạo video", "chặn theo vùng", "theo vùng"]
BUSY_KEYWORDS = ["503", "đang bận", "busy", "tạm ngưng", "không khả dụng", "cluster"]
LOGIN_URL_HINTS = ["/login", "/signin", "/sign-in", "/auth", "/signup"]
DASHBOARD_HTML = os.path.join(ROOT_DIR, "bridge", "dashboard.html")
ACCOUNT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
VIDEO_EXTS = (".mp4", ".webm", ".mov")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
# Pool-wide cap on simultaneously open render pages (RAM bound); 0 = only per-account limits.
MAX_PAGES = int(os.environ.get("MUSEAI_MAX_PAGES", "0") or 0)
# An account whose job timed out (its VM is often wedged on a session) rests this long.
STUCK_COOLDOWN_S = int(os.environ.get("MUSEAI_STUCK_COOLDOWN_S", "900"))


# ---- Supabase session auth (staff log in with accounts created by an admin) ----
SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_PUB = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or ""
SB_SVC = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
# Staff may only call chat/status/media. Everything else (eval, accounts, shared threads/history,
# batch) stays API-key only so staff cannot see each other's chats, run JS, or skip the rules file.
STAFF_EXACT = {"/v1/chat", "/v1/status"}
# Server-side rules+history prompt is off by default (it made replies much slower); set MUSE_STAFF_RULES=1 to enable.
STAFF_RULES = os.environ.get("MUSE_STAFF_RULES") == "1"
HISTORY_BUDGET = int(os.environ.get("MUSE_HISTORY_CHARS", "6000"))
_jwt_cache: Dict[str, tuple] = {}
_rules_cache: Dict[str, tuple] = {}


def staff_allowed(path: str) -> bool:
    return path in STAFF_EXACT or path.startswith("/media/")


# The video checklist is for admins only: a Supabase session is accepted for these paths if its role is admin.
ADMIN_JWT_PATHS = {"/v1/video-accounts", "/v1/video-accounts/reset", "/v1/video-accounts/probe"}
PROBE_PROMPT = "Tạo video 5 giây: một chú mèo đi dạo"
PROBE_WINDOW_S = int(os.environ.get("MUSEAI_PROBE_WINDOW_S", "60"))  # Muse refuses within ~20s; still rendering after this = can make video
PROBE_CONCURRENCY = int(os.environ.get("MUSEAI_PROBE_CONCURRENCY", "8"))


async def is_admin_uid(uid: str) -> bool:
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as ses:
            rows = await _sb_get(ses, f"profiles?id=eq.{uid}&select=role,disabled")
        return bool(rows and rows[0].get("role") == "admin" and not rows[0].get("disabled"))
    except Exception:
        return False



# ---- Sticky UI chat -> Muse account (a side-chat thread only exists inside the account that created it) ----
# conv -> {"account", "session_id"}: a Muse session only exists inside the account that created it.
CONV_SESSION_FILE = os.path.join(ROOT_DIR, "scratch", "conv_sessions.json")


def _json_load(path: str) -> Dict:
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _json_save(path: str, data: Dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)
    except Exception as e:
        print(f"[Pool] could not save {path}: {e}")

# ---- Dashboard admin gate ----
# /dashboard is admin-only: the page itself is never served without a session. A session is an
# HttpOnly cookie signed with MUSE_API_KEY, minted either by typing the key on the login page or by
# a one-time SSO link that Flowboard's /admin mints server-side (same HMAC, key never leaves it).
DASH_COOKIE = "muse_dash"
DASH_SESSION_S = int(os.environ.get("MUSE_DASH_SESSION_S", str(12 * 3600)))
SSO_MAX_TTL_S = 300
_sso_used: Dict[str, float] = {}


def _dash_sig(key: str, msg: str) -> str:
    return hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()


def dash_session_token(key: str) -> str:
    exp = int(time.time()) + DASH_SESSION_S
    return f"{exp}.{_dash_sig(key, f'dash:{exp}')}"


def dash_session_ok(key: Optional[str], tok: str) -> bool:
    if not key or not tok or "." not in tok:
        return False
    exp, sig = tok.split(".", 1)
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, _dash_sig(key, f"dash:{exp}"))


def sso_ok(key: Optional[str], tok: str) -> bool:
    """One-time `exp.nonce.sig` link, sig = HMAC(key, "sso:exp:nonce"), at most SSO_MAX_TTL_S ahead."""
    parts = (tok or "").split(".")
    if not key or len(parts) != 3 or not parts[0].isdigit():
        return False
    exp, nonce, sig = int(parts[0]), parts[1], parts[2]
    now = time.time()
    if not (now < exp <= now + SSO_MAX_TTL_S) or nonce in _sso_used:
        return False
    if not hmac.compare_digest(sig, _dash_sig(key, f"sso:{exp}:{nonce}")):
        return False
    for n, e in list(_sso_used.items()):
        if e < now:
            _sso_used.pop(n, None)
    _sso_used[nonce] = exp
    return True


DASH_LOGIN_HTML = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Muse Pool — đăng nhập</title>
<style>body{font:15px system-ui,sans-serif;background:#0f1115;color:#e7e9ee;display:grid;place-items:center;min-height:100vh;margin:0}
form{background:#181b22;padding:28px;border-radius:12px;width:min(360px,90vw)}h1{font-size:18px;margin:0 0 6px}
p{color:#9aa1ad;margin:0 0 16px;font-size:13px}input{width:100%;box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid #333a46;background:#0f1115;color:inherit}
button{margin-top:12px;width:100%;padding:10px;border:0;border-radius:8px;background:#4f7cff;color:#fff;font-weight:600;cursor:pointer}
.bad{color:#ff6b6b;font-size:13px;min-height:18px;margin-top:8px}</style></head><body>
<form id="f"><h1>Muse Pool — chỉ admin</h1><p>Mở từ trang /admin của Flowboard, hoặc nhập API key của pool.</p>
<input id="k" type="password" autocomplete="off" placeholder="MUSE_API_KEY" autofocus><button>Đăng nhập</button><div class="bad" id="m"></div></form>
<script>document.getElementById("f").onsubmit=async e=>{e.preventDefault();const k=document.getElementById("k").value.trim();if(!k)return;
const r=await fetch("/dashboard/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({key:k})});
if(r.ok)location.replace("/dashboard");else document.getElementById("m").textContent="Sai API key.";};</script></body></html>"""


async def _sb_get(ses, path: str):
    async with ses.get(f"{SB_URL}/rest/v1/{path}", headers={"apikey": SB_SVC, "Authorization": f"Bearer {SB_SVC}"}) as r:
        return await r.json() if r.status == 200 else None


async def verify_staff_jwt(token: str) -> Optional[str]:
    """Returns the user id if the Supabase session is valid and the account is not disabled."""
    if not (SB_URL and SB_PUB and SB_SVC and token):
        return None
    hit = _jwt_cache.get(token)
    if hit and hit[0] > time.time():
        return hit[1]
    uid = None
    definitive = False  # a real answer from Supabase (valid / invalid), as opposed to a network hiccup
    import aiohttp
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as ses:
                async with ses.get(f"{SB_URL}/auth/v1/user",
                                   headers={"apikey": SB_PUB, "Authorization": f"Bearer {token}"}) as r:
                    if r.status == 200:
                        cand = (await r.json()).get("id")
                        rows = await _sb_get(ses, f"profiles?id=eq.{cand}&select=disabled")
                        if rows and not rows[0].get("disabled"):
                            uid = cand
                        definitive = True
                    elif r.status in (400, 401, 403):
                        definitive = True
            if definitive:
                break
        except Exception as e:  # noqa: BLE001
            print(f"[Auth] Supabase check failed (try {attempt + 1}): {type(e).__name__} {e}")
            await asyncio.sleep(0.5)
    if not definitive:
        return None  # transient failure: do not cache, the next request retries
    if len(_jwt_cache) > 500:
        _jwt_cache.clear()
    _jwt_cache[token] = (time.time() + 120, uid)
    return uid


async def get_rules() -> str:
    hit = _rules_cache.get("rules")
    if hit and hit[0] > time.time():
        return hit[1]
    text = ""
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as ses:
            on = await _sb_get(ses, "a3t_settings?key=eq.rules_enabled&select=value")
            if not (on and on[0]["value"] == "false"):
                rows = await _sb_get(ses, "a3t_settings?key=eq.rules_md&select=value")
                text = rows[0]["value"] if rows else ""
    except Exception as e:
        print(f"[Rules] load failed: {e}")
    _rules_cache["rules"] = (time.time() + 30, text)
    return text


# Rules file = numbered sections ("1. ..."). Section 1 is the general rules; the others are per product/task.
# Only the section matching what the user is working on is sent, and each at most once per conversation.
RULE_KEYS = {
    2: ("ornament", "suncatcher", "doormat", "clipboard", "wooden sign", "pod", "acrylic", "treo"),
    3: ("áo", "ao thun", "shirt", "tshirt", "t-shirt", "jersey", "baseball"),
    4: ("lật", "mirror", "flip"),
    5: ("khôi phục", "restore", "bóc nền", "boc nen"),
    6: ("đổi tên", "đổi màu", "thêm dây", "khoen", "tách thành phần"),
    7: ("phân tích", "analy"),
}


def unwrap_reply(t):
    """Muse sometimes answers {"reply": "...", "action": null}; keep only the reply text."""
    t = (t or "").strip()
    if t.startswith("{") and '"reply"' in t:
        try:
            o = json.loads(t)
            if isinstance(o.get("reply"), str):
                return o["reply"]
        except Exception:
            pass
    return t


def split_rules(text: str) -> Dict[int, str]:
    parts = re.split(r"\n(?=\d\. )", text)
    out = {}
    for part in parts:
        m = re.match(r"(\d)\. ", part)
        if m:
            out[int(m.group(1))] = part.strip()
    return out


def detect_rule_keys(text: str) -> set:
    t = (text or "").lower()
    return {k for k, words in RULE_KEYS.items() if any(w in t for w in words)}


async def build_staff_prompt(uid: str, conversation_id: Optional[str], prompt: str) -> str:
    """Server-side prompt for staff: the rules section(s) for the product being worked on (once per chat),
    the current conversation's recent history, then the new message. Done here so staff cannot skip the rules."""
    rules = split_rules(await get_rules())
    history = []
    if conversation_id and re.fullmatch(r"[0-9a-fA-F-]{36}", conversation_id):
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as ses:
                rows = await _sb_get(ses, f"messages?conversation_id=eq.{conversation_id}&user_id=eq.{uid}"
                                          f"&select=role,content,attachments&order=id.asc")
                history = rows or []
        except Exception as e:
            print(f"[History] load failed: {e}")
    lines = []
    seen_keys: set = set()
    for m in history:
        who = "User" if m["role"] == "user" else "Assistant"
        if m["role"] != "user":
            m = dict(m, content=unwrap_reply(m.get("content")))
        extra = f" [đính kèm {len(m['attachments'])} tệp]" if m.get("attachments") else ""
        lines.append(f"{who}: {m.get('content') or ''}{extra}")
        if m["role"] == "user":
            seen_keys |= detect_rule_keys(m.get("content"))
    # keep the newest turns within budget; drop (not cut) the oldest ones
    kept, used = [], 0
    for ln in reversed(lines):
        if used + len(ln) > HISTORY_BUDGET and kept:
            break
        kept.append(ln if len(ln) <= HISTORY_BUDGET else ln[:HISTORY_BUDGET] + "…")
        used += len(ln)
    kept.reverse()
    new_keys = sorted(detect_rule_keys(prompt) - seen_keys)
    chosen = ([1] if (not lines and 1 in rules) else []) + [k for k in new_keys if k in rules]
    out = []
    if chosen:
        body = "\n\n".join(rules[k] for k in chosen)
        out.append("[CHỈ THỊ HỆ THỐNG — bạn là trợ lý của Agent 3T Global. Quy chuẩn kỹ thuật dưới đây là quy tắc làm việc CỦA BẠN, "
                   "áp dụng cho mọi yêu cầu liên quan, không nhắc lại hay bình luận về nó trừ khi được hỏi. Trả lời tự nhiên bằng văn bản thường như một trợ lý bình thường, KHÔNG dùng JSON]\n" + body + "\n[HẾT CHỈ THỊ HỆ THỐNG]")
    if kept:
        note = "" if len(kept) == len(lines) else "(các lượt cũ hơn đã được lược bớt)\n"
        out.append("[NỘI DUNG ĐOẠN CHAT TRƯỚC ĐÓ]\n" + note + "\n".join(kept) + "\n[HẾT NỘI DUNG ĐOẠN CHAT]")
        if not chosen:
            out.append("(Tiếp tục tuân thủ quy chuẩn kỹ thuật của Agent 3T Global đã áp dụng ở đầu đoạn chat.)")
    out.append("User: " + prompt if kept else prompt)
    return "\n\n".join(out)


class LogTee(io.TextIOBase):
    """Mirrors stdout into a ring buffer so the dashboard can show recent server logs."""

    def __init__(self, stream, maxlen: int = 800):
        self.stream = stream
        self.lines = deque(maxlen=maxlen)
        self._partial = ""

    def write(self, text):
        self.stream.write(text)
        self._partial += text
        *done, self._partial = self._partial.split("\n")
        stamp = time.strftime("%H:%M:%S")
        self.lines.extend(f"{stamp} {line}" for line in done if line.strip())
        return len(text)

    def flush(self):
        self.stream.flush()


def count_media(urls) -> Dict[str, int]:
    urls = [u for u in (urls or []) if isinstance(u, str)]
    videos = sum(1 for u in urls if u.lower().endswith(VIDEO_EXTS))
    return {"videos": videos, "images": len(urls) - videos}


class Stats:
    """Persistent generation counters, hourly buckets and a recent-event log."""

    KEYS = ("requests", "ok", "failed", "videos", "images")

    def __init__(self, path: str):
        self.path = path
        self.data = {"since": time.time(), "totals": {k: 0 for k in self.KEYS}, "by_kind": {},
                     "by_account": {}, "hourly": {}, "events": []}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except Exception as e:
                print(f"[Pool] Warning: could not load stats: {e}")

    @staticmethod
    def _bump(bucket: Dict, ok: bool, media: Dict[str, int]):
        for k in Stats.KEYS:
            bucket.setdefault(k, 0)
        bucket["requests"] += 1
        bucket["ok" if ok else "failed"] += 1
        bucket["videos"] += media["videos"]
        bucket["images"] += media["images"]

    def record(self, kind: str, account: str, res: Dict, prompt: str = "", duration_ms: Optional[float] = None):
        ok = bool(res.get("ok"))
        media_urls = res.get("media") or []
        media = count_media(media_urls)
        d = self.data
        self._bump(d["totals"], ok, media)
        self._bump(d["by_kind"].setdefault(kind, {}), ok, media)
        self._bump(d["by_account"].setdefault(account or "-", {}), ok, media)
        hour = time.strftime("%Y-%m-%dT%H:00", time.localtime())
        self._bump(d["hourly"].setdefault(hour, {}), ok, media)
        if len(d["hourly"]) > 24 * 14:
            for old in sorted(d["hourly"])[:-24 * 14]:
                del d["hourly"][old]
        d["events"].append({
            "ts": time.time(), "kind": kind, "account": account or "-", "ok": ok,
            "videos": media["videos"], "images": media["images"], "media": media_urls[:6],
            "duration_ms": duration_ms if duration_ms is not None else res.get("duration_ms"),
            "prompt": (prompt or res.get("prompt") or "")[:160],
            "error": "" if ok else str(res.get("error") or "")[:200],
        })
        d["events"] = d["events"][-500:]
        self.save()

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception as e:
            print(f"[Pool] Warning: could not save stats: {e}")


def _wants_video(prompt: str) -> bool:
    return "video" in (prompt or "").lower()


VIDEO_STATE_FILE = os.path.join(ROOT_DIR, "scratch", "video_state.json")
VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v")
_video_states: Dict[str, str] = {}  # account -> "ok" | "blocked"  (absent = not tried yet)


class Account:
    def __init__(self, name: str, path: str, max_concurrency: int):
        self.name = name
        self.path = path
        self.mtime = os.path.getmtime(path)
        self.max_concurrency = max_concurrency
        self.on_change = None  # set by the pool: (account, old, new) -> None
        self._status = None
        self.status = "starting"  # starting | ready | not_ready | expired | error | retired
        self.cooldown_until = 0.0
        self.active = 0
        self.done = 0
        self.failed = 0
        self.last_check = 0.0
        self.last_error = ""

    @property
    def video_state(self) -> str:
        """unknown (never tried) | ok (made a video) | blocked (Muse refuses video for its region/plan)."""
        return _video_states.get(self.name, "unknown")

    @video_state.setter
    def video_state(self, new: str):
        # An account that once produced a real video is never downgraded automatically (a later probe or
        # refusal only rests it); only an explicit per-account reset (force_video_state) clears it.
        if _video_states.get(self.name) == "ok" and new != "ok":
            return
        if new == "unknown":
            _video_states.pop(self.name, None)
        else:
            _video_states[self.name] = new
        _json_save(VIDEO_STATE_FILE, _video_states)

    def force_video_state(self, new: str):
        """Explicit override (per-account reset): the only way to take an account out of "ok"."""
        _video_states.pop(self.name, None)
        self.video_state = new

    @property
    def no_video(self) -> bool:
        return self.video_state == "blocked"

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, new: str):
        old, self._status = self._status, new
        if old != new and self.on_change:
            try:
                self.on_change(self, old, new)
            except Exception as e:
                print(f"[Pool] status hook failed: {e}")

    @property
    def available(self) -> bool:
        return self.status == "ready" and time.time() >= self.cooldown_until

    @property
    def idle(self) -> bool:
        return self.active == 0

    def info(self) -> Dict:
        return {
            "name": self.name,
            "file": os.path.basename(self.path),
            "status": self.status,
            "cooldown_s": max(0, round(self.cooldown_until - time.time())),
            "active": self.active,
            "max_concurrency": self.max_concurrency,
            "done": self.done,
            "failed": self.failed,
            "last_check": self.last_check,
            "last_error": self.last_error,
            "video_state": self.video_state,
        }


class MusePool:
    def __init__(self, cookies_dir: str, port: int, host: Optional[str], per_account: int,
                 headless: bool, health_interval: int, cooldown_s: int, max_attempts: int):
        self.cookies_dir = os.path.abspath(cookies_dir)
        self.port = port
        self.host = host
        self.per_account = per_account
        self.headless = headless
        self.health_interval = health_interval
        self.cooldown_s = cooldown_s
        self.max_attempts = max_attempts
        self.api_key = os.environ.get("MUSE_API_KEY") or None
        self.drive = drive_offload.DriveOffload(MEDIA_DIR)
        self.started_at = time.time()
        self.log_tee = None
        self.accounts: Dict[str, Account] = {}
        self.video_probe = {"running": False, "done": 0, "total": 0}
        _video_states.update({k: v for k, v in _json_load(VIDEO_STATE_FILE).items() if v in ("ok", "blocked")})
        self.recent_turns: deque = deque(maxlen=100)  # /v1/history: the last finished turns, newest last
        self.conv_locks: Dict[str, asyncio.Lock] = {}
        self.reload_lock = asyncio.Lock()
        os.makedirs(STATE_DIR, exist_ok=True)
        self.stats = Stats(os.path.join(STATE_DIR, "stats.json"))
        # Any account that ever delivered a video (per the stats) is proven "ok": restores marks lost earlier.
        proven = [n for n, v in self.stats.data.get("by_account", {}).items()
                  if n != "-" and v.get("videos", 0) > 0 and _video_states.get(n) != "ok"]
        for n in proven:
            _video_states[n] = "ok"
        if proven:
            _json_save(VIDEO_STATE_FILE, _video_states)
            print(f"[Pool] restored video=ok from stats: {', '.join(proven)}")
        self.alerts = notify.ExpiryAlerts()
        self.jobs_file = os.path.join(STATE_DIR, "batch_jobs.json")
        self.batch_jobs: Dict[str, Dict] = {}
        if os.path.exists(self.jobs_file):
            try:
                with open(self.jobs_file, "r", encoding="utf-8") as f:
                    self.batch_jobs = json.load(f)
            except Exception as e:
                print(f"[Pool] Warning: could not load batch jobs: {e}")

    def _save_jobs(self):
        try:
            recent = dict(list(self.batch_jobs.items())[-200:])
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(recent, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Pool] Warning: could not save batch jobs: {e}")

    # ---------------------------------------------------------------- accounts

    def _scan_files(self) -> Dict[str, str]:
        found = {}
        if not os.path.isdir(self.cookies_dir):
            return found
        for fn in sorted(os.listdir(self.cookies_dir)):
            if fn.endswith(".json") and not fn.startswith((".", "_")):
                found[fn[:-5]] = os.path.join(self.cookies_dir, fn)
        return found

    async def _start_account(self, acc: Account):
        acc.status = "starting"
        await self._check_account(acc)
        if acc.status == "ready" and acc.video_state == "unknown":
            self._auto_probe(acc)  # freshly connected account: find out right away if it can make video

    def _auto_probe(self, acc: Account):
        if getattr(self, "_probe_sem", None) is None:
            self._probe_sem = asyncio.Semaphore(PROBE_CONCURRENCY)

        async def run():
            async with self._probe_sem:
                if acc.video_state == "unknown" and acc.status == "ready":
                    await self._probe_one(acc)
        asyncio.create_task(run())

    async def _stop_account(self, acc: Account):
        pass  # nothing is held open between jobs: each job owns (and closes) its own socket

    @staticmethod
    def _probe(acc: Account) -> tuple:
        """Cheap liveness check: a logged-in muse.ai page carries the VM gatewayUrl."""
        try:
            with open(acc.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            names = {c.get("name") for c in raw} if isinstance(raw, list) else set(raw or {})
            if SESSION_COOKIE not in names:
                return "expired", f"session cookie {SESSION_COOKIE} missing"
            client = MuseNoiseClient(acc.path, media_dir=MEDIA_DIR, account_name=acc.name)
            last = ""
            for attempt in range(3):
                try:
                    status, html = client._http_call("GET", "https://muse.ai/")
                except Exception as e:  # DNS / TLS hiccup: retry
                    last = f"{type(e).__name__}: {e}"
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if status in (401, 403):
                    return "expired", f"muse.ai answered {status}"
                if status != 200:
                    last = f"muse.ai answered {status}"
                    time.sleep(2.0 * (attempt + 1) + random.random())  # 429 at boot: stagger
                    continue
                if re.search(rb'gatewayUrl.*?wss://', html) or (b"gatewayUrl" in html and b"wss://" in html):
                    return "ready", ""
                return "expired", "gatewayUrl missing (session cookie expired or logged out)"
            return "error", last[:300]
        except Exception as e:
            return "error", str(e)[:300]

    async def _check_account(self, acc: Account, navigate: bool = True):
        """Decides ready / expired / error without a browser (busy accounts are alive by definition)."""
        if acc.active and acc.status == "ready":
            return
        acc.last_check = time.time()
        status, err = await asyncio.to_thread(self._probe, acc)
        acc.status, acc.last_error = status, err
        print(f"[Pool] Health {acc.name}: {acc.status}{' — ' + err if err else ''}")

    async def reload_accounts(self) -> Dict:
        """Syncs self.accounts with the cookies dir (new / changed / removed files)."""
        async with self.reload_lock:
            found = self._scan_files()
            added, changed, removed = [], [], []
            for name, path in found.items():
                acc = self.accounts.get(name)
                if acc is None:
                    acc = Account(name, path, self.per_account)
                    acc.on_change = self.alerts.transition
                    self.accounts[name] = acc
                    added.append(name)
                elif os.path.getmtime(path) != acc.mtime and acc.idle:
                    await self._stop_account(acc)
                    acc.mtime = os.path.getmtime(path)
                    changed.append(name)
                else:
                    continue
            for name, acc in list(self.accounts.items()):
                if name not in found and acc.idle:
                    await self._stop_account(acc)
                    del self.accounts[name]
                    self.alerts.forget(name)
                    removed.append(name)
            to_start = [self.accounts[n] for n in added + changed]
            await asyncio.gather(*[self._start_account(a) for a in to_start])
            if added or changed or removed:
                print(f"[Pool] Reload: +{added} ~{changed} -{removed}")
            return {"added": added, "changed": changed, "removed": removed}

    def pick(self, only: Optional[List[str]] = None, video: bool = False) -> Optional[Account]:
        if MAX_PAGES and sum(a.active for a in self.accounts.values()) >= MAX_PAGES:
            return None  # RAM ceiling: callers wait for a page to close
        cands = [a for a in self.accounts.values()
                 if a.available and a.active < a.max_concurrency and (not only or a.name in only)
                 and not (video and a.no_video)]
        if video and any(a.video_state == "ok" and a.available for a in self.accounts.values()):
            # proven accounts exist: send every video there (callers wait if they are busy) instead of burning untried ones
            cands = [a for a in cands if a.video_state == "ok"]
        if not cands:
            return None
        # Video jobs try proven accounts first, then untried ones (blocked are excluded above).
        # Everything else prefers accounts that can't render video, keeping the video-capable ones free.
        rank = {"ok": 0, "unknown": 1, "blocked": 2}
        def key(a):
            r = rank[a.video_state]
            return (r if video else -r, a.active / a.max_concurrency, a.active, a.name)
        return min(cands, key=key)

    def default_account(self) -> Optional[Account]:
        ready = [a for a in self.accounts.values() if a.status == "ready"]
        return min(ready, key=lambda a: (a.active / a.max_concurrency, a.name)) if ready else None

    async def _watch_loop(self):
        last_health = time.time()
        while True:
            await asyncio.sleep(30)
            try:
                await self.reload_accounts()
                if time.time() - last_health >= self.health_interval:
                    last_health = time.time()
                    await asyncio.gather(*[self._check_account(a) for a in list(self.accounts.values())])
                    self.alerts.check_ready(list(self.accounts.values()))
            except Exception as e:
                print(f"[Pool] Watch loop error: {e}")

    # ---------------------------------------------------------------- batch engine

    @staticmethod
    def _is_busy(res: Dict) -> bool:
        if res.get("ok"):
            return False
        text = f"{res.get('error', '')} {res.get('content', '')}".lower()
        return any(k in text for k in BUSY_KEYWORDS)

    @staticmethod
    def _engine_files(raw_files) -> list:
        """Request `files` -> what MuseNoiseClient.upload_file takes (data URL / URL / path / base64)."""
        out = []
        for rf in raw_files or []:
            if isinstance(rf, dict):
                data = rf.get("data") or ""
                if data and not data.startswith("data:"):
                    mime = mimetypes.guess_type(rf.get("name") or "")[0] or "image/png"
                    data = f"data:{mime};base64,{data}"
                if data:
                    out.append(data)
            elif isinstance(rf, str) and rf:
                out.append(rf)
        return out

    @staticmethod
    def _generate_blocking(acc: Account, prompt: str, files: list, timeout_s: int,
                           session_id: Optional[str] = None) -> Dict:
        client = MuseNoiseClient(acc.path, media_dir=MEDIA_DIR, account_name=acc.name)
        try:
            return client.generate(prompt, files=files or None, timeout_s=timeout_s, session_id=session_id)
        finally:
            client.close()

    async def _run_one(self, acc: Account, prompt: str, files: list, timeout_ms: int,
                       session_id: Optional[str] = None, video: Optional[bool] = None) -> Dict:
        """One generation on its own socket. Marks the account on auth failure / timeout."""
        files = self._engine_files(files)
        timeout_s = max(30, int(timeout_ms / 1000))
        t0 = time.time()
        try:
            res = await asyncio.to_thread(self._generate_blocking, acc, prompt, files, timeout_s, session_id)
        except Exception as err:
            msg = str(err)
            res = {"ok": False, "prompt": prompt, "error": msg[:500], "status": "failed"}
            low = msg.lower()
            if "hatch_vm_auth_no_match" in low:
                # Cookie is fine, the account's VM is just not ready: rest it briefly, retry elsewhere.
                acc.cooldown_until = time.time() + STUCK_COOLDOWN_S
                acc.last_error = "VM auth no match — cooling down"
                res["_requeue"] = True
            elif "gatewayurl not found" in low or "hatch token: 401" in low or "hatch token: 403" in low:
                acc.status, acc.last_error = "expired", msg[:300]
                res["_requeue"] = True
            elif "connect failed" in low:
                res["_requeue"] = True
        res.pop("local_paths", None)
        res.setdefault("duration_ms", round((time.time() - t0) * 1000))
        if res.get("ok"):
            res["files_attached"] = len(files)
            content = (res.get("content") or "").lower()
            video = _wants_video(prompt) if video is None else video
            if any(str(m).lower().endswith(VIDEO_EXTS) for m in res.get("media") or []):
                if acc.video_state != "ok":
                    acc.video_state = "ok"
            elif video and any(k in content for k in NO_VIDEO_KEYWORDS):  # Muse may attach a stand-in image
                snippet = " ".join(content.split())[:200]
                if acc.video_state == "ok":
                    # proved itself with a real video before: one refusal only rests it, it keeps its place
                    acc.cooldown_until = time.time() + 120
                    acc.last_error = "refused one video job — resting 120s"
                    print(f"[Pool] {acc.name}: refusal but previously ok, resting 120s: {snippet!r}")
                else:
                    acc.video_state = "blocked"
                    acc.last_error = "video not available for this account's region/plan"
                    print(f"[Pool] {acc.name}: blocked reply: {snippet!r}")
                res.update(ok=False, status="failed", error=f"[{acc.name}] {acc.last_error}", _requeue=True)
                return res
            if not res.get("media") and not content.strip():
                # Muse "completed" with nothing at all (quota spent / account unusable): rest it, retry elsewhere.
                acc.cooldown_until = time.time() + STUCK_COOLDOWN_S
                acc.last_error = f"empty reply from Muse — cooling down {STUCK_COOLDOWN_S}s"
                res.update(ok=False, status="failed", error=f"[{acc.name}] Muse trả về phản hồi rỗng", _requeue=True)
                print(f"[Pool] {acc.name}: empty reply, cooling down {STUCK_COOLDOWN_S}s")
                return res
            if not res.get("media") and any(k in content for k in RENDER_FAIL_KEYWORDS):
                snippet = " ".join((res.get("content") or "").split())[:200]
                res.update(ok=False, status="failed",
                           error=f"Muse video generation failed or service busy (503): {snippet}")
                # Chat turns don't requeue, so rest the account here or the next try hits it again.
                acc.cooldown_until = time.time() + self.cooldown_s
        elif res.get("status") == "timeout":
            # A VM wedged on a session never finishes anything: rest the account, retry elsewhere.
            rest = min(STUCK_COOLDOWN_S, 300) if acc.video_state == "ok" else STUCK_COOLDOWN_S  # video just renders slowly
            acc.cooldown_until = time.time() + rest
            acc.last_error = f"job timed out after {timeout_s}s — cooling down {rest}s"
            res["_requeue"] = True
            print(f"[Pool] {acc.name}: timed out after {timeout_s}s, cooling down {rest}s")
        return res

    async def run_items(self, prompts: List[str], item_files: List[list], timeout_ms: int,
                        concurrency: int, only: Optional[List[str]], on_result):
        report = on_result

        def on_result(i, res):
            self.stats.record("batch", res.get("account", "-"), res, prompts[i])
            report(i, res)

        pending = deque((i, 0) for i in range(len(prompts)))
        running = {}
        # The caller's timeout is a budget for the item, not per attempt: a retry after a stuck
        # account gets whatever is left, and is not started once too little remains.
        deadlines: Dict[int, float] = {}
        while pending or running:
            while pending and len(running) < concurrency:
                acc = self.pick(only, video=_wants_video(prompts[pending[0][0]]))
                if not acc:
                    break
                i, attempt = pending.popleft()
                deadline = deadlines.setdefault(i, time.time() + timeout_ms / 1000)
                left_ms = (deadline - time.time()) * 1000
                if attempt and left_ms < 45000:
                    on_result(i, {"ok": False, "prompt": prompts[i], "status": "timeout", "attempts": attempt,
                                  "error": f"Generation timed out after {round(timeout_ms / 1000)}s"})
                    continue
                acc.active += 1
                task = asyncio.create_task(self._run_one(acc, prompts[i], item_files[i], left_ms))
                running[task] = (i, attempt, acc)
            if not running:
                alive = [a for a in self.accounts.values()
                         if a.status in ("ready", "starting") and (not only or a.name in only)]
                if not alive:
                    while pending:
                        i, _ = pending.popleft()
                        on_result(i, {"ok": False, "prompt": prompts[i], "error": "no healthy account available"})
                    break
                await asyncio.sleep(2)  # everyone cooling down or still starting
                continue
            done, _ = await asyncio.wait(list(running), timeout=2, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                i, attempt, acc = running.pop(task)
                acc.active -= 1
                res = task.result()
                requeue = res.pop("_requeue", False)
                if self._is_busy(res):
                    acc.cooldown_until = time.time() + self.cooldown_s
                    requeue = True
                if requeue and attempt + 1 < self.max_attempts:
                    print(f"[Pool] Item #{i+1} busy/expired/stuck on {acc.name}; re-queue (attempt {attempt+2})")
                    pending.append((i, attempt + 1))
                    continue
                res["account"] = acc.name
                res["attempts"] = attempt + 1
                if res.get("ok"):
                    acc.done += 1
                else:
                    acc.failed += 1
                on_result(i, res)

    def _parse_batch(self, data: Dict):
        prompts = data.get("prompts", [])
        raw_items = data.get("items", [])
        raw_files = data.get("files", [])
        if raw_items:
            kept = [it for it in raw_items if it.get("prompt")]
            return [it.get("prompt", "") for it in kept], [it.get("files") or [] for it in kept]
        if prompts:
            if isinstance(raw_files, list) and raw_files and isinstance(raw_files[0], list):
                return prompts, raw_files
            if isinstance(raw_files, list) and raw_files:
                return prompts, [raw_files for _ in prompts]
            return prompts, [[] for _ in prompts]
        return None, None

    def _capacity(self, only: Optional[List[str]]) -> int:
        return sum(a.max_concurrency for a in self.accounts.values()
                   if a.status in ("ready", "starting") and (not only or a.name in only))

    def _batch_params(self, data: Dict):
        only = data.get("accounts") or ([data["account"]] if data.get("account") else None)
        capacity = max(self._capacity(only), 1)
        requested = data.get("concurrency")
        concurrency = capacity if requested is None else min(max(int(requested), 1), capacity)
        return only, concurrency, data.get("timeout_ms", 180000)

    async def handle_batch_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON or Payload Error: {e}"}, status=400)
        prompts, item_files = self._parse_batch(data)
        if prompts is None:
            return web.json_response({"ok": False, "error": "Either 'items' or 'prompts' array is required"}, status=400)
        only, concurrency, timeout_ms = self._batch_params(data)
        results = [None] * len(prompts)

        def on_result(i, res):
            results[i] = res

        await self.run_items(prompts, item_files, timeout_ms, concurrency, only, on_result)
        completed = sum(1 for r in results if r and r.get("ok"))
        return web.json_response({"ok": True, "total": len(prompts), "completed": completed,
                                  "failed": len(prompts) - completed, "concurrency": concurrency,
                                  "results": results})

    async def handle_batch_async(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON or Payload Error: {e}"}, status=400)
        prompts, item_files = self._parse_batch(data)
        if prompts is None:
            return web.json_response({"ok": False, "error": "Either 'items' or 'prompts' array is required"}, status=400)
        only, concurrency, timeout_ms = self._batch_params(data)
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        job = {"batch_id": batch_id, "status": "running", "created_at": time.time(), "total": len(prompts),
               "completed": 0, "failed": 0, "concurrency": concurrency, "results": [None] * len(prompts)}
        self.batch_jobs[batch_id] = job
        self._save_jobs()

        def on_result(i, res):
            job["results"][i] = res
            job["completed" if res.get("ok") else "failed"] += 1
            self._save_jobs()

        async def run():
            try:
                await self.run_items(prompts, item_files, timeout_ms, concurrency, only, on_result)
            finally:
                job["status"] = "completed"
                job["finished_at"] = time.time()
                self._save_jobs()

        asyncio.create_task(run())
        return web.json_response({"ok": True, "batch_id": batch_id, "status": "running", "total": len(prompts),
                                  "concurrency": concurrency, "status_url": f"/v1/batch/status?id={batch_id}"})

    async def handle_batch_status(self, request: web.Request) -> web.Response:
        batch_id = request.query.get("id") or request.query.get("batch_id")
        if not batch_id:
            recent = list(self.batch_jobs.values())[-20:]
            return web.json_response({"ok": True, "count": len(self.batch_jobs), "recent_jobs": [
                {k: j.get(k) for k in ("batch_id", "status", "total", "completed", "failed", "created_at", "finished_at")}
                for j in recent]})
        if batch_id not in self.batch_jobs:
            return web.json_response({"ok": False, "error": f"Batch job '{batch_id}' not found",
                                      "available_recent": list(self.batch_jobs.keys())[-5:]}, status=404)
        return web.json_response({"ok": True, **self.batch_jobs[batch_id]})

    # ---------------------------------------------------------------- single-turn endpoints

    def _named_account(self, name: Optional[str]):
        """(account, error_response) for an explicit ?account= / X-Muse-Account / body.account."""
        if not name:
            return None, None
        acc = self.accounts.get(name)
        if not acc or acc.status != "ready":
            return None, web.json_response({"ok": False, "error": f"account '{name}' not found or not ready"}, status=404)
        return acc, None

    def _no_account_reason(self) -> str:
        """Why pick() came back empty, for the 503 the chat shows."""
        accs = list(self.accounts.values())
        now = time.time()
        ready = [a for a in accs if a.status == "ready"]
        cooling = [a for a in ready if a.cooldown_until > now]
        full = [a for a in ready if a.cooldown_until <= now and a.active >= a.max_concurrency]
        return (f"no account available ({len(ready)}/{len(accs)} ready, {len(cooling)} cooling down, "
                f"{len(full)} at capacity, {len(accs) - len(ready)} expired/error)")

    async def _wait_pick(self, wait_s: float = 60.0, video: bool = False) -> Optional[Account]:
        """Least-busy ready account; waits a little while the whole pool is saturated."""
        end = time.time() + wait_s
        while True:
            acc = self.pick(video=video)
            if acc or time.time() >= end or not any(a.status == "ready" for a in self.accounts.values()):
                return acc
            await asyncio.sleep(1)

    def _remember_turn(self, prompt: str, res: Dict):
        self.recent_turns.append({"userPrompt": prompt, "assistantText": res.get("content") or "",
                                  "media": res.get("media") or [], "account": res.get("account"),
                                  "ok": bool(res.get("ok")), "ts": time.time()})

    async def _parse_chat_request(self, request: web.Request) -> Dict:
        """Both bodies the old browser bridge took: multipart (files uploaded) or JSON (files inline)."""
        req = {"prompt": "", "timeout_ms": 180000, "new_thread": True, "conv": "", "context": "",
               "files": [], "account": None}
        if "multipart/form-data" in request.headers.get("Content-Type", ""):
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name in ("files", "file"):
                    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", part.filename or "upload.bin")[-80:]
                    save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{filename}")
                    with open(save_path, "wb") as f:
                        while True:
                            chunk = await part.read_chunk()
                            if not chunk:
                                break
                            f.write(chunk)
                    req["files"].append(save_path)
                elif part.name in ("prompt", "conv", "context", "account"):
                    req[part.name] = (await part.text()).strip()
                elif part.name == "timeout_ms":
                    try:
                        req["timeout_ms"] = int(await part.text())
                    except ValueError:
                        pass
                elif part.name == "new_thread":
                    req["new_thread"] = (await part.text()).lower() in ("true", "1")
        else:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
            req.update(prompt=str(data.get("prompt") or "").strip(),
                       timeout_ms=int(data.get("timeout_ms") or 180000),
                       new_thread=bool(data.get("new_thread", data.get("createNewThread", True))),
                       conv=str(data.get("conv") or "").strip(), context=str(data.get("context") or "").strip(),
                       files=[f for f in (data.get("files") or []) if isinstance(f, (str, dict))],
                       account=data.get("account"))
        req["conv"] = req["conv"] or (request.headers.get("X-Conv") or "").strip()
        req["account"] = request.query.get("account") or request.headers.get("X-Muse-Account") or req["account"]
        return req

    async def _chat_turn(self, request: web.Request, prompt: str, files: list, timeout_ms: int,
                         conv: str = "", context: str = "", account: Optional[str] = None):
        """Runs one turn; a `conv` keeps its Muse session (and account) across calls. -> (acc, res)."""
        acc, err = self._named_account(account)
        if err:
            return None, err
        # The video tab sends X-Mode: video; the chat tab only counts as video when the prompt says so.
        video = request.headers.get("X-Mode") == "video" or _wants_video(prompt)
        pinned = acc is not None
        # Video: walk the account list until one renders (blocked ones drop out of the list as we go).
        tries = 1 if pinned else (max(4, len(self.accounts)) if video else 4)
        lock = self.conv_locks.setdefault(conv, asyncio.Lock()) if conv else None
        if lock:
            await lock.acquire()  # turns of one chat are sequential by nature
        try:
            smap = _json_load(CONV_SESSION_FILE) if conv else {}
            entry = smap.get(conv) if isinstance(smap.get(conv), dict) else {}
            sticky = self.accounts.get(entry.get("account", ""))
            session_id = entry.get("session_id")
            last = None
            for _ in range(tries):
                if not acc:
                    acc = sticky if (sticky and sticky.available and not (video and sticky.no_video)) \
                        else await self._wait_pick(video=video)
                if not acc:
                    if last:  # every account we had was tried and refused video
                        res["error"] = "Không còn tài khoản nào tạo được video (đã thử hết danh sách)."
                        return last, res
                    return None, web.json_response({"ok": False, "error": self._no_account_reason()}, status=503)
                run_prompt, sid = prompt, None
                if conv:
                    if acc is sticky and session_id:
                        sid = session_id
                    else:
                        # brand-new Muse session (or the chat moved account): it has no history, send the full context
                        if context:
                            run_prompt = context
                        print(f"[Pool] Chat {conv} -> account {acc.name} (new session)")
                acc.active += 1
                try:
                    res = await self._run_one(acc, run_prompt, files, timeout_ms, session_id=sid, video=video)
                finally:
                    acc.active -= 1
                if not res.pop("_requeue", False) or pinned:
                    break
                print(f"[Pool] {acc.name} refused ({res.get('error')}); trying the next account")
                last, acc = acc, None
            acc = acc or last
            if conv and res.get("session_id"):
                smap = _json_load(CONV_SESSION_FILE)
                smap[conv] = {"account": acc.name, "session_id": res["session_id"], "ts": time.time()}
                if len(smap) > 5000:
                    smap = dict(sorted(smap.items(), key=lambda kv: kv[1].get("ts", 0))[-4000:])
                _json_save(CONV_SESSION_FILE, smap)
            return acc, res
        finally:
            if lock:
                lock.release()

    def _account_result(self, kind: str, acc: Account, prompt: str, res: Dict):
        res["account"] = acc.name
        res.pop("_requeue", None)
        if res.get("ok"):
            acc.done += 1
        else:
            acc.failed += 1
        self.stats.record(kind, acc.name, res, prompt, res.get("duration_ms"))
        self._remember_turn(prompt, res)

    async def handle_chat(self, request: web.Request) -> web.Response:
        try:
            req = await self._parse_chat_request(request)
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid request: {e}"}, status=400)
        prompt, files = req["prompt"], req["files"]
        if not prompt and not files:
            return web.json_response({"ok": False, "error": "prompt or file attachment is required"}, status=400)
        prompt = prompt or DEFAULT_FILE_PROMPT
        wrap = request.get("wrap_prompt")
        if wrap:
            prompt = await wrap(prompt)
        acc, res = await self._chat_turn(request, prompt, files, req["timeout_ms"], req["conv"],
                                         req["context"], req["account"])
        if acc is None:
            return res  # an error response
        self._account_result("chat", acc, prompt, res)
        out = {k: res.get(k) for k in ("ok", "content", "media", "duration_ms", "status", "account",
                                         "files_attached", "error") if res.get(k) is not None}
        out.setdefault("content", "")
        out.setdefault("media", [])
        return web.json_response(out, headers={"X-Muse-Account": acc.name})

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": {"message": "Invalid JSON"}}, status=400)
        prompt, files = "", []
        for msg in reversed(data.get("messages") or []):
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                prompt = content
            elif isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "text":
                        prompt += part.get("text", "") + "\n"
                    elif part.get("type") == "image_url":
                        url = (part.get("image_url") or {}).get("url")
                        if isinstance(url, str) and url.startswith(("data:", "https://")):
                            files.append(url)
            break
        prompt = prompt.strip()
        if not prompt:
            return web.json_response({"error": {"message": "No user message found"}}, status=400)

        # QUY TAC NGAM TOI CAO TU QUAN TRI VIEN (SEP HOANG)
        implicit_rule = (
            '[CHỈ THỊ QUY TẮC NGẦM TỪ QUẢN TRỊ VIÊN]:\n'
            '- Phong cách: Bạn là một Trợ lý AI độc lập, thông minh, tận tâm và giao tiếp tự nhiên, duyên dáng như người thật. '
            'Tuyệt đối KHÔNG trả lời máy móc, cứng nhắc. Không bao giờ nói các câu từ kỹ thuật như "trong khung chat này", "theo quy tắc", "tôi chỉ xử lý file ở đây".\n'
            '- Bảo mật & Không gian riêng: Tự ngầm hiểu cuộc trò chuyện hiện tại là hoàn toàn riêng tư. '
            'Tuyệt đối KHÔNG BAO GIỜ tìm kiếm, nhắc lại hay sử dụng bất kỳ hình ảnh, video, dữ liệu từ các cuộc trò chuyện của người khác hoặc trong profile tài khoản.\n'
            '- Ứng xử linh hoạt: Khi người dùng nhờ ghép video, chỉnh ảnh, tóm tắt tài liệu mà chưa gửi file đính kèm: '
            'Hãy vui vẻ nhận lời ngay và tự nhiên nhờ họ gửi các tệp qua để bạn xử lý liền (Ví dụ: "Dạ được chứ anh ơi! Anh gửi mấy clip đó qua đây em ghép liền một mạch cho anh ngay nha, anh muốn giữ âm thanh gốc hay lồng thêm nhạc nền gì không báo em luôn nhé!").'
        )
        safe_prompt = f"{implicit_rule}\n\n[Tin nhắn người dùng]:\n{prompt}"

        acc, res = await self._chat_turn(request, safe_prompt, files, int(data.get("timeout_ms") or 180000),
                                         str(data.get("conv") or request.headers.get("X-Conv") or ""),
                                         account=request.query.get("account") or data.get("account"))
        if acc is None:
            return res
        self._account_result("completions", acc, prompt, res)
        if not res.get("ok"):
            return web.json_response({"error": {"message": res.get("error") or "generation failed"},
                                      "account": acc.name}, status=502, headers={"X-Muse-Account": acc.name})
        text = res.get("content") or ""
        if data.get("stream"):
            resp = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Muse-Account": acc.name,
                }
            )
            await resp.prepare(request)
            chunk_id = f"chatcmpl-muse-{uuid.uuid4().hex[:12]}"
            c1 = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": data.get("model", "studio-pool"),
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
            }
            await resp.write(f"data: {json.dumps(c1)}\n\n".encode("utf-8"))
            c2 = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": data.get("model", "studio-pool"),
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            await resp.write(f"data: {json.dumps(c2)}\n\n".encode("utf-8"))
            await resp.write(b"data: [DONE]\n\n")
            await resp.write_eof()
            return resp
        return web.json_response({
            "id": f"chatcmpl-muse-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
            "created": int(time.time()), "model": data.get("model", "muse-ai"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "media": res.get("media") or [], "account": acc.name,
            "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": len(text.split()),
                      "total_tokens": len(prompt.split()) + len(text.split())},
        }, headers={"X-Muse-Account": acc.name})

    async def handle_history(self, request: web.Request) -> web.Response:
        """The pool's last finished turns (oldest first), shaped like the old page history."""
        return web.json_response({"ok": True, "turns": list(self.recent_turns)})

    async def handle_threads(self, request: web.Request) -> web.Response:
        # Every call already runs in its own Muse session; there is no shared "current thread" any more.
        return web.json_response({"ok": True, "threads": [], "result": {"ok": True}})

    async def handle_upload(self, request: web.Request) -> web.Response:
        """Stores files server-side; pass the returned paths as `files` in a later /v1/chat call."""
        if "multipart/form-data" not in request.headers.get("Content-Type", ""):
            return web.json_response({"ok": False, "error": "multipart/form-data with files required"}, status=400)
        try:
            req = await self._parse_chat_request(request)
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Error parsing multipart: {e}"}, status=400)
        if not req["files"]:
            return web.json_response({"ok": False, "error": "No valid files received"}, status=400)
        return web.json_response({"ok": True, "files": req["files"]})

    async def handle_eval(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": False, "error": "eval is gone: the pool no longer runs a browser"}, status=410)

    async def handle_api_docs(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "engine": "noise-headless", "endpoints": [
            "GET /v1/status", "POST /v1/chat (JSON or multipart: prompt, files, conv, context, timeout_ms)",
            "POST /v1/chat/completions", "POST /v1/batch/chat", "POST /v1/batch/async {items:[{prompt, files}]}",
            "GET /v1/batch/status?id=", "GET /v1/history", "POST /v1/upload", "GET /media/{name}"]})

    # ---------------------------------------------------------------- status / admin

    async def handle_status(self, request: web.Request) -> web.Response:
        accs = [a.info() for a in sorted(self.accounts.values(), key=lambda a: a.name)]
        ready = [a for a in accs if a["status"] == "ready"]
        return web.json_response({
            "ok": bool(ready), "mode": "pool", "engine": "noise-headless", "bridge_ready": bool(ready), "headless": True,
            "batch_files": True, "accounts_total": len(accs), "accounts_ready": len(ready),
            "capacity": min(sum(a["max_concurrency"] for a in ready), MAX_PAGES or 10**6),
            "max_pages": MAX_PAGES, "active": sum(a["active"] for a in accs),
            "accounts_expired": sum(1 for a in accs if a["status"] in ("expired", "error")),
            "telegram": self.alerts.enabled, "accounts": accs,
        })

    async def handle_accounts(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "accounts": [a.info() for a in sorted(self.accounts.values(), key=lambda a: a.name)]})

    async def handle_video_accounts(self, request: web.Request) -> web.Response:
        accs = sorted(self.accounts.values(), key=lambda a: ({"ok": 0, "unknown": 1, "blocked": 2}[a.video_state], a.name))
        rows = [{"name": a.name, "video_state": a.video_state, "status": a.status, "active": a.active}
                for a in accs]
        counts = {k: sum(1 for r in rows if r["video_state"] == k) for k in ("ok", "unknown", "blocked")}
        return web.json_response({"ok": True, "counts": counts, "accounts": rows, "probe": self.video_probe})

    async def _probe_one(self, acc: Account):
        """One short video attempt: a region/plan refusal marks it blocked, a real video file marks it ok; anything else stays untested."""
        try:
            res = await asyncio.to_thread(self._generate_blocking, acc, PROBE_PROMPT, [], PROBE_WINDOW_S, None)
        except Exception as e:  # noqa: BLE001
            print(f"[Probe] {acc.name}: {str(e)[:120]}")
            return
        content = (res.get("content") or "").lower()
        if any(str(m).lower().endswith(VIDEO_EXTS) for m in res.get("media") or []):
            acc.video_state = "ok"
        elif any(k in content for k in NO_VIDEO_KEYWORDS):
            acc.video_state = "blocked"
        elif res.get("status") == "completed" and content.strip():
            acc.video_state = "blocked"  # Muse answered (offered a still/camera-move instead) but produced no video file
        # A timeout proves nothing (Muse may just be slow to refuse): only a real video file marks "ok".
        print(f"[Probe] {acc.name}: {acc.video_state} status={res.get('status')} media={len(res.get('media') or [])} reply={' '.join(content.split())[:160]!r} err={str(res.get('error') or '')[:100]!r}")

    async def handle_video_probe(self, request: web.Request) -> web.Response:
        """Quick check: tries every ready, untested account in parallel and updates the checklist."""
        if self.video_probe["running"]:
            return web.json_response({"ok": True, "started": False, "probe": self.video_probe})
        try:
            retest = bool((await request.json()).get("retest"))
        except Exception:
            retest = False
        targets = [a for a in self.accounts.values()
                   if a.status == "ready" and (a.video_state == "unknown" or (retest and a.video_state != "ok"))]
        self.video_probe = {"running": True, "done": 0, "total": len(targets)}

        async def run():
            sem = asyncio.Semaphore(PROBE_CONCURRENCY)

            async def one(a):
                async with sem:
                    await self._probe_one(a)
                    self.video_probe["done"] += 1
            try:
                await asyncio.gather(*[one(a) for a in targets])
            finally:
                self.video_probe["running"] = False
        asyncio.create_task(run())
        return web.json_response({"ok": True, "started": True, "probe": self.video_probe})

    async def handle_video_reset(self, request: web.Request) -> web.Response:
        try:
            name = (await request.json()).get("name")
        except Exception:
            name = None
        targets = [self.accounts[name]] if name in self.accounts else ([] if name else list(self.accounts.values()))
        if not name:
            targets = [a for a in targets if a.video_state != "ok"]  # "reset all" keeps proven accounts
        for a in targets:
            a.force_video_state("unknown")
        return web.json_response({"ok": True, "reset": len(targets)})

    async def handle_reload(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, **(await self.reload_accounts())})

    async def handle_check(self, request: web.Request) -> web.Response:
        name = request.query.get("account")
        targets = [self.accounts[name]] if name in self.accounts else list(self.accounts.values())
        await asyncio.gather(*[self._check_account(a) for a in targets])
        return web.json_response({"ok": True, "accounts": [a.info() for a in targets]})

    def _write_account(self, name: str, raw, overwrite: bool) -> Dict:
        """Validates one account's cookies and writes cookies/<name>.json. Returns {ok, error?, status}."""
        name = str(name or "").strip()
        if not ACCOUNT_NAME_RE.match(name):
            return {"ok": False, "status": 400, "error": "Tên tài khoản chỉ gồm chữ, số, - và _ (tối đa 40 ký tự)"}
        path = os.path.join(self.cookies_dir, f"{name}.json")
        existed = os.path.exists(path)
        if existed and not overwrite:
            return {"ok": False, "status": 409, "error": f"Tài khoản '{name}' đã tồn tại"}
        if isinstance(raw, str):
            text = raw.strip()
            try:
                raw = json.loads(text)
            except Exception:
                raw = parse_cookie_header(text)
        if isinstance(raw, dict) and isinstance(raw.get("cookies"), list):
            raw = raw["cookies"]
        cookies = normalize_cookies(raw) if isinstance(raw, (list, dict)) else []
        if not cookies:
            return {"ok": False, "status": 400, "error": "Không đọc được cookie muse.ai nào"}
        if not any(c["name"] == SESSION_COOKIE for c in cookies):
            return {"ok": False, "status": 400, "error": f"Thiếu cookie phiên '{SESSION_COOKIE}' — hãy export khi đang đăng nhập"}
        os.makedirs(self.cookies_dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        return {"ok": True, "status": 200, "cookies": len(cookies), "result": "updated" if existed else "added"}

    async def handle_bulk_accounts(self, request: web.Request) -> web.Response:
        """POST /v1/accounts/bulk {accounts: [{name, cookies}] | {name: cookies}, overwrite}."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)
        items = data.get("accounts")
        if isinstance(items, dict):
            items = [{"name": k, "cookies": c} for k, c in items.items()]
        if not isinstance(items, list) or not items:
            return web.json_response({"ok": False, "error": "accounts must be a non-empty list or map"}, status=400)
        if len(items) > 200:
            return web.json_response({"ok": False, "error": "tối đa 200 tài khoản mỗi lần"}, status=400)
        results = []
        for it in items:
            it = it if isinstance(it, dict) else {}
            r = self._write_account(it.get("name"), it.get("cookies"), bool(data.get("overwrite")))
            results.append({"name": str(it.get("name") or ""), "ok": r["ok"],
                            "result": r.get("result") or "invalid", "error": r.get("error", ""),
                            "cookies": r.get("cookies", 0)})
        reload = await self.reload_accounts() if any(r["ok"] for r in results) else {}
        for r in results:
            acc = self.accounts.get(r["name"])
            r["status"] = acc.status if (acc and r["ok"]) else None
        return web.json_response({"ok": True, "written": sum(r["ok"] for r in results),
                                  "results": results, **reload})

    async def handle_notify_test(self, request: web.Request) -> web.Response:
        ok, err = await self.alerts.send_now("✅ Muse pool: thử thông báo Telegram — "
                                             f"{sum(1 for a in self.accounts.values() if a.status == 'ready')}"
                                             f"/{len(self.accounts)} tài khoản sẵn sàng.")
        return web.json_response({"ok": ok, "error": err}, status=200 if ok else 502)

    async def handle_sheet_import(self, request: web.Request) -> web.Response:
        """POST /v1/accounts/sheet {url} -> {accounts_raw, count}. Public Google Sheet (anyone with the link) -> 'a|b|c' lines."""
        import csv
        from urllib.parse import urlparse, parse_qs
        import aiohttp
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)
        url = str(data.get("url") or "").strip()
        m = re.search(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)", url)
        if not m:
            return web.json_response({"ok": False, "error": "Link Google Sheet không hợp lệ"}, status=400)
        q = parse_qs(urlparse(url).query)
        frag = re.search(r"gid=(\d+)", url)
        gid = (q.get("gid") or [frag.group(1) if frag else "0"])[0]
        export = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={gid}"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as sess:
                async with sess.get(export) as r:
                    text = await r.text()
                    if r.status != 200 or text.lstrip().lower().startswith("<!doctype"):
                        return web.json_response({"ok": False, "error": "Không đọc được Sheet — hãy chia sẻ 'Bất kỳ ai có đường liên kết' (Người xem)"}, status=502)
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Lỗi tải Sheet: {e}"}, status=502)
        lines = []
        for row in csv.reader(io.StringIO(text)):
            cells = [c.strip() for c in row if c.strip()]
            if cells and "@" in cells[0]:  # skips header / blank rows
                lines.append("|".join(cells))
        if not lines:
            return web.json_response({"ok": False, "error": "Sheet không có dòng nào bắt đầu bằng email"}, status=422)
        return web.json_response({"ok": True, "count": len(lines), "accounts_raw": "\n".join(lines)})

    async def handle_auto_extract(self, request: web.Request) -> web.StreamResponse:
        """POST /v1/accounts/auto-extract {accounts_raw, overwrite} -> SSE stream."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

        accounts_raw = str(data.get("accounts_raw") or "").strip()
        overwrite = bool(data.get("overwrite", True))

        if not accounts_raw:
            return web.json_response({"ok": False, "error": "accounts_raw cannot be empty"}, status=400)

        accounts_list = [l.strip() for l in accounts_raw.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not accounts_list:
            return web.json_response({"ok": False, "error": "Không tìm thấy tài khoản hợp lệ"}, status=400)

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await response.prepare(request)

        push_lock = asyncio.Lock()

        async def push_event(ev_type: str, message: str = "", status: str = "", progress: dict = None, res_data: Any = None):
            ev = {
                "type": ev_type,
                "message": message,
                "status": status,
                "progress": progress,
                "data": res_data,
                "timestamp": datetime.now().isoformat()
            }
            line = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8")
            async with push_lock:
                try:
                    await response.write(line)
                except (ConnectionResetError, BrokenPipeError, Exception):
                    pass

        skipped = []
        if data.get("skip_active", True):
            from bridge import auto_login as _al
            todo = []
            for raw_acc in accounts_list:
                try:
                    a = self.accounts.get(_al.parse_account_string(raw_acc)["name"])
                except Exception:
                    a = None
                (skipped if a is not None and a.status == "ready" else todo).append(raw_acc)
            accounts_list = todo
        if skipped:
            await push_event("log", f"⏭ Bỏ qua {len(skipped)} tài khoản đang hoạt động (chỉ chạy lại khi expired)", "SKIP")

        total = len(accounts_list)
        if not total:
            await push_event("done", f"Không có tài khoản nào cần đăng nhập (đã bỏ qua {len(skipped)} tài khoản đang hoạt động).",
                             "ALL_DONE", progress={"total": 0, "current": 0})
            await response.write_eof()
            return response
        await push_event("start", f"Bắt đầu tự động đăng nhập & trích xuất {total} tài khoản...", "START", progress={"total": total, "current": 0})

        # The pool itself runs no browser; this login flow alone needs one, only while it runs.
        try:
            from bridge import auto_login, proxy_manager, gologin_browser
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            
            chrome_candidates = [
                "/home/muse/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome",
                "/usr/bin/google-chrome",
                "/usr/bin/chromium-browser"
            ]
            found_chrome = next((p for p in chrome_candidates if os.path.exists(p)), None)
            args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-infobars",
                "--window-size=1280,800",
            ]
            base_launch_kw = {}
            # MUSE_LOGIN_MANUAL=1: run on a machine with a screen; open a visible Chrome so captchas can be solved by hand.
            manual_login = bool(os.environ.get("MUSE_LOGIN_MANUAL"))
            if found_chrome:
                base_launch_kw["executable_path"] = found_chrome
                if not manual_login:
                    args.insert(0, "--headless=new")
        except Exception as e:
            await push_event("done", f"❌ Không khởi động được Playwright: {e}", "ERROR",
                             progress={"total": total, "current": 0})
            await response.write_eof()
            return response

        use_gologin = gologin_browser.available() and os.environ.get("MUSE_LOGIN_GOLOGIN", "1") != "0"
        if use_gologin:
            await push_event("log", "🦊 Dùng profile GoLogin (token) cho mỗi lần đăng nhập", "GOLOGIN")

        written_count = 0
        for idx, raw_acc in enumerate(accounts_list, 1):
            try:
                acc_info = auto_login.parse_account_string(raw_acc)
                email_label = acc_info["email"]
                acc_proxy = acc_info.get("proxy")
            except Exception:
                email_label = f"Dòng #{idx}"
                acc_proxy = None

            prog = {"current": idx, "total": total, "email": email_label}
            await push_event("account_start", f"Đang xử lý [{idx}/{total}]: {email_label}...", "ACCOUNT_START", progress=prog)

            def on_log(msg, st=None):
                asyncio.create_task(push_event("log", msg, st, progress=prog))

            max_login_attempts = 3 if not acc_proxy else 1
            res = {"ok": False, "error": "Chưa xử lý"}

            for attempt in range(1, max_login_attempts + 1):
                proxy_cfg = None
                if manual_login and not acc_proxy:
                    on_log("🏠 Chạy local (IP máy bạn), không dùng proxy xoay", "PROXY")
                elif acc_proxy:
                    proxy_cfg = proxy_manager.parse_playwright_proxy(acc_proxy)
                    if attempt == 1:
                        on_log(f"🌐 [Proxy riêng] Sử dụng {acc_proxy}", "PROXY")
                else:
                    force_wait = (idx > 1 or attempt > 1)
                    px = await proxy_manager.get_rotating_proxy_async(
                        rotate=True,
                        force_wait=force_wait,
                        max_wait=125,
                        on_status=lambda m: on_log(f"🌐 [TinProxy] {m}", "PROXY")
                    )
                    if px and px.get("playwright"):
                        proxy_cfg = px["playwright"]
                        status_msg = "đã xoay IP mới" if px.get("rotated") else "IP hiện tại"
                        on_log(f"🌐 [TinProxy] {status_msg}: {px.get('ip')} ({px.get('location')})", "PROXY")
                    elif os.environ.get("MUSE_LOGIN_PROXY"):
                        proxy_cfg = {"server": os.environ["MUSE_LOGIN_PROXY"]}

                acc_launch_kw = dict(base_launch_kw)
                if proxy_cfg:
                    acc_launch_kw["proxy"] = proxy_cfg

                try:
                    if use_gologin:
                        handle = await gologin_browser.open_profile(f"muse-{email_label.split('@')[0]}"[:60], proxy_cfg)
                        try:
                            browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{handle['port']}")
                            try:
                                res = await auto_login.extract_account_cookies(
                                    browser, raw_acc, logger=on_log, context=browser.contexts[0])
                            finally:
                                await browser.close()
                        finally:
                            await gologin_browser.close_profile(handle)
                    else:
                        browser = await pw.chromium.launch(headless=not manual_login, args=args, **acc_launch_kw)
                        try:
                            res = await auto_login.extract_account_cookies(browser, raw_acc, logger=on_log)
                        finally:
                            await browser.close()
                except Exception as e:
                    res = {"ok": False, "error": str(e)}

                if res.get("ok"):
                    break

                err_msg = str(res.get("error") or "")
                is_captcha_block = any(k in err_msg.lower() for k in [
                    "automated queries", "try again later", "recaptcha", "chặn giải âm thanh"
                ])
                if is_captcha_block and attempt < max_login_attempts:
                    on_log(f"⚠️ Google chặn IP ('automated queries') — tự động đợi xoay IP mới và thử lại (lần {attempt + 1}/{max_login_attempts})...", "RETRY")
                    await asyncio.sleep(2)
                else:
                    break

            if res.get("ok"):
                name = res["name"]
                w_res = self._write_account(name, res["cookies"], overwrite=overwrite)
                if w_res.get("ok"):
                    written_count += 1
                    await self.reload_accounts()
                    acc_obj = self.accounts.get(name)
                    st = acc_obj.status if acc_obj else "ready"
                    res["pool_status"] = st
                    await push_event("account_done", f"✅ Đã nạp {email_label} ({name}) vào Pool (Trạng thái: {st})", "SUCCESS", progress=prog, res_data=res)
                else:
                    await push_event("account_done", f"❌ Không thể ghi file cookie: {w_res.get('error')}", "ERROR", progress=prog, res_data=res)
            else:
                await push_event("account_done", f"❌ Thất bại {email_label}: {res.get('error')}", "ERROR", progress=prog, res_data=res)

        try:
            await pw.stop()
        except Exception:
            pass
        await push_event("done", f"Hoàn thành: Đã nạp thành công {written_count}/{total} tài khoản vào Pool!", "ALL_DONE", progress={"total": total, "current": total})
        try:
            await response.write_eof()
        except Exception:
            pass
        return response

    async def handle_add_account(self, request: web.Request) -> web.Response:
        """POST /v1/accounts {name, cookies}: cookies = JSON export (list / dict) or a Cookie header string."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)
        name = str(data.get("name") or "").strip()
        r = self._write_account(name, data.get("cookies"), bool(data.get("overwrite")))
        if not r["ok"]:
            return web.json_response({"ok": False, "error": r["error"]}, status=r["status"])
        vs = data.get("video_state")
        if vs in ("ok", "blocked"):
            _video_states[name] = vs
            _json_save(VIDEO_STATE_FILE, _video_states)
        result = await self.reload_accounts()
        acc = self.accounts.get(name)
        if acc and vs in ("ok", "blocked"):
            acc.force_video_state(vs)
        return web.json_response({"ok": True, "name": name, "cookies": r["cookies"], **result,
                                  "account": acc.info() if acc else None})

    async def handle_delete_account(self, request: web.Request) -> web.Response:
        name = request.query.get("name") or request.match_info.get("name", "")
        acc = self.accounts.get(name)
        if not ACCOUNT_NAME_RE.match(name) or not os.path.exists(os.path.join(self.cookies_dir, f"{name}.json")):
            return web.json_response({"ok": False, "error": f"account '{name}' not found"}, status=404)
        if acc and not acc.idle:
            return web.json_response({"ok": False, "error": "Tài khoản đang chạy job, thử lại sau"}, status=409)
        os.remove(os.path.join(self.cookies_dir, f"{name}.json"))
        return web.json_response({"ok": True, **(await self.reload_accounts())})

    async def handle_set_video_state(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        name = str(data.get("name") or request.query.get("name") or "").strip()
        state = str(data.get("state") or data.get("video_state") or "ok").strip().lower()
        if state not in ("ok", "blocked"):
            return web.json_response({"ok": False, "error": "state must be 'ok' or 'blocked'"}, status=400)
        acc = self.accounts.get(name)
        if not acc:
            return web.json_response({"ok": False, "error": f"account '{name}' not found"}, status=404)
        acc.force_video_state(state)
        return web.json_response({"ok": True, "name": name, "video_state": state, "account": acc.info()})

    @staticmethod
    def _system_info() -> Dict:
        info = {"load": list(os.getloadavg()), "cpus": os.cpu_count()}
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    mem[k] = int(v.split()[0]) * 1024
            info["mem_total"] = mem.get("MemTotal")
            info["mem_used"] = mem.get("MemTotal", 0) - mem.get("MemAvailable", 0)
        except Exception:
            pass
        du = shutil.disk_usage(ROOT_DIR)
        info["disk_total"], info["disk_used"] = du.total, du.used
        return info

    @staticmethod
    def _media_files() -> List[Dict]:
        out = []
        try:
            for entry in os.scandir(MEDIA_DIR):
                if entry.is_file():
                    st = entry.stat()
                    if st.st_size < 1024:  # blank placeholders saved from empty blobs
                        continue
                    low = entry.name.lower()
                    kind = "video" if low.endswith(VIDEO_EXTS) else "image" if low.endswith(IMAGE_EXTS) else "other"
                    out.append({"name": entry.name, "url": f"/media/{entry.name}", "type": kind,
                                "size": st.st_size, "mtime": st.st_mtime})
        except FileNotFoundError:
            pass
        return sorted(out, key=lambda m: m["mtime"], reverse=True)

    async def handle_stats(self, request: web.Request) -> web.Response:
        media = self._media_files()
        d = self.stats.data
        now = time.time()
        jobs = list(self.batch_jobs.values())
        return web.json_response({
            "ok": True, "now": now, "uptime_s": round(now - self.started_at), "stats_since": d.get("since"),
            "totals": d["totals"], "by_kind": d["by_kind"], "by_account": d["by_account"],
            "hourly": [{"hour": h, **d["hourly"][h]} for h in sorted(d["hourly"])[-48:]],
            "media_store": {"videos": sum(1 for m in media if m["type"] == "video"),
                            "images": sum(1 for m in media if m["type"] == "image"),
                            "bytes": sum(m["size"] for m in media)},
            "active": sum(a.active for a in self.accounts.values()),
            "batch": {"running": sum(1 for j in jobs if j.get("status") == "running"), "total": len(jobs),
                      "recent": [{k: j.get(k) for k in ("batch_id", "status", "total", "completed", "failed",
                                                         "created_at", "finished_at")} for j in jobs[-10:]][::-1]},
            "system": self._system_info(),
        })

    async def handle_events(self, request: web.Request) -> web.Response:
        limit = min(int(request.query.get("limit", 100)), 500)
        return web.json_response({"ok": True, "events": self.stats.data["events"][-limit:][::-1]})

    async def handle_media_list(self, request: web.Request) -> web.Response:
        media = self._media_files()
        kind = request.query.get("type")
        if kind:
            media = [m for m in media if m["type"] == kind]
        limit = min(int(request.query.get("limit", 60)), 500)
        return web.json_response({"ok": True, "count": len(media), "media": media[:limit]})

    async def handle_logs(self, request: web.Request) -> web.Response:
        limit = min(int(request.query.get("limit", 200)), 800)
        lines = list(self.log_tee.lines)[-limit:] if self.log_tee else []
        return web.json_response({"ok": True, "lines": lines})

    def _set_dash_cookie(self, resp: web.StreamResponse) -> None:
        resp.set_cookie(DASH_COOKIE, dash_session_token(self.api_key), max_age=DASH_SESSION_S,
                        httponly=True, samesite="Strict", path="/")

    async def handle_dashboard(self, request: web.Request) -> web.StreamResponse:
        if self.api_key and not dash_session_ok(self.api_key, request.cookies.get(DASH_COOKIE, "")):
            sso = request.query.get("sso", "")
            if sso and sso_ok(self.api_key, sso):
                resp = web.HTTPSeeOther("/dashboard")
                self._set_dash_cookie(resp)
                return resp
            # never the dashboard itself: only a login form, no data, no account names
            return web.Response(text=DASH_LOGIN_HTML, content_type="text/html", status=401,
                                headers={"Cache-Control": "no-store"})
        if not os.path.exists(DASHBOARD_HTML):
            return web.Response(text="dashboard.html missing", status=404)
        return web.FileResponse(DASHBOARD_HTML, headers={"Cache-Control": "no-store"})

    async def handle_dashboard_login(self, request: web.Request) -> web.Response:
        try:
            given = str((await request.json()).get("key", ""))
        except Exception:
            given = ""
        if not self.api_key or not hmac.compare_digest(given.encode(), self.api_key.encode()):
            await asyncio.sleep(1)  # slow down key guessing
            return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
        resp = web.json_response({"ok": True})
        self._set_dash_cookie(resp)
        return resp

    async def handle_dashboard_logout(self, request: web.Request) -> web.Response:
        resp = web.json_response({"ok": True})
        resp.del_cookie(DASH_COOKIE, path="/")
        return resp

    async def handle_static_page(self, request: web.Request) -> web.StreamResponse:
        path = DOCS_HTML if request.path.startswith("/docs") else INDEX_HTML
        if not os.path.exists(path):
            return web.Response(text="page not found", status=404)
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})

    # ---------------------------------------------------------------- app

    def create_app(self) -> web.Application:
        api_key = self.api_key

        @web.middleware
        async def auth_and_log(request, handler):
            if api_key and (request.path.startswith("/v1") or request.path.startswith("/media")):
                auth = request.headers.get("Authorization", "")
                given = (request.headers.get("X-API-Key") or (auth[7:] if auth.startswith("Bearer ") else "")
                         or (request.query.get("key", "") if request.path.startswith("/media") else ""))
                # a dashboard session cookie (admin logged in on /dashboard) counts as the key
                if given != api_key and dash_session_ok(api_key, request.cookies.get(DASH_COOKIE, "")):
                    given = api_key
                if given != api_key:
                    # <video>/<img> tags cannot send headers, so /media also takes ?access_token=
                    tok = given or (request.query.get("access_token", "") if request.path.startswith("/media") else "")
                    uid = await verify_staff_jwt(tok) if (staff_allowed(request.path) or request.path in ADMIN_JWT_PATHS) else None
                    if uid and request.path in ADMIN_JWT_PATHS and not await is_admin_uid(uid):
                        uid = None
                    if not uid:
                        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)
                    if STAFF_RULES and request.method == "POST" and request.path == "/v1/chat":
                        # staff chats always get the standard rules + their own conversation history,
                        # applied inside handle_chat (works for JSON and multipart bodies alike)
                        conv = request.headers.get("X-Conversation-Id") or None
                        async def wrap(p, _uid=uid, _conv=conv):
                            return await build_staff_prompt(_uid, _conv, p)
                        request["wrap_prompt"] = wrap
            peer = request.headers.get("X-Forwarded-For") or request.remote or "unknown"
            t0 = time.time()
            resp = await handler(request)
            acc = resp.headers.get("X-Muse-Account", "-")
            print(f"[HTTP] {request.method} {request.path} from {peer} acc={acc} -> {resp.status} ({(time.time()-t0)*1000:.0f}ms)")
            return resp

        app = web.Application(client_max_size=100 * 1024 * 1024, middlewares=[auth_and_log])
        r = app.router
        r.add_get("/", self.handle_static_page)
        r.add_get("/docs", self.handle_static_page)
        r.add_get("/docs.html", self.handle_static_page)
        r.add_get("/v1/status", self.handle_status)
        r.add_get("/dashboard", self.handle_dashboard)
        r.add_post("/dashboard/login", self.handle_dashboard_login)
        r.add_post("/dashboard/logout", self.handle_dashboard_logout)
        r.add_get("/v1/stats", self.handle_stats)
        r.add_get("/v1/events", self.handle_events)
        r.add_get("/v1/media", self.handle_media_list)
        r.add_get("/v1/logs", self.handle_logs)
        r.add_post("/v1/accounts", self.handle_add_account)
        r.add_delete("/v1/accounts", self.handle_delete_account)
        r.add_post("/v1/accounts/bulk", self.handle_bulk_accounts)
        r.add_post("/v1/accounts/auto-extract", self.handle_auto_extract)
        r.add_post("/v1/accounts/sheet", self.handle_sheet_import)
        r.add_post("/v1/notify/test", self.handle_notify_test)
        r.add_get("/v1/accounts", self.handle_accounts)
        r.add_get("/v1/video-accounts", self.handle_video_accounts)
        r.add_post("/v1/video-accounts/reset", self.handle_video_reset)
        r.add_post("/v1/video-accounts/probe", self.handle_video_probe)
        r.add_post("/v1/accounts/reload", self.handle_reload)
        r.add_post("/v1/accounts/video-state", self.handle_set_video_state)
        r.add_post("/v1/accounts/check", self.handle_check)
        r.add_post("/v1/batch/chat", self.handle_batch_chat)
        r.add_post("/v1/batch/async", self.handle_batch_async)
        r.add_get("/v1/batch/status", self.handle_batch_status)
        r.add_post("/v1/chat", self.handle_chat)
        r.add_post("/v1/chat/completions", self.handle_chat_completions)
        r.add_get("/v1/threads", self.handle_threads)
        r.add_post("/v1/threads/switch", self.handle_threads)
        r.add_post("/v1/threads/new", self.handle_threads)
        r.add_get("/v1/history", self.handle_history)
        r.add_post("/v1/upload", self.handle_upload)
        r.add_post("/v1/eval", self.handle_eval)
        r.add_get("/v1/docs", self.handle_api_docs)
        r.add_get("/media/{name}", self.drive.handle_media)
        return app

    async def run(self):
        asyncio.get_running_loop().set_default_executor(
            ThreadPoolExecutor(max_workers=WORKER_THREADS, thread_name_prefix="muse"))
        await self.reload_accounts()
        if not self.accounts:
            print(f"[Pool] Warning: no cookie files in {self.cookies_dir} yet; watching for new ones.")
        if drive_offload.enabled():
            asyncio.create_task(self.drive.run())
            print("[Drive] offload ON (images/videos -> Google Drive, local copy removed after grace period)")
        else:
            print("[Drive] offload OFF (set DRIVE_WEBAPP_URL + DRIVE_WEBAPP_SECRET to enable)")
        runner = web.AppRunner(self.create_app())
        await runner.setup()
        await web.TCPSite(runner, host=self.host, port=self.port).start()
        ready = sum(1 for a in self.accounts.values() if a.status == "ready")
        print(f"[Pool] REST API on http://{self.host or '0.0.0.0'}:{self.port} | accounts {ready}/{len(self.accounts)} ready"
              f" | per-account {self.per_account} | max {MAX_PAGES or 'unlimited'} | headless noise engine | api key {'ON' if self.api_key else 'OFF'}")
        await self._watch_loop()


def main():
    ap = argparse.ArgumentParser(description="Muse.ai multi-account bridge pool")
    ap.add_argument("--cookies-dir", default=os.path.join(ROOT_DIR, "cookies"))
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default=None, help="Bind address (default all interfaces; use the Tailscale IP on a VPS)")
    ap.add_argument("--per-account", type=int, default=2, help="Parallel generations per account (1-8)")
    ap.add_argument("--health-interval", type=int, default=600, help="Seconds between session health checks")
    ap.add_argument("--cooldown", type=int, default=180, help="Seconds an account rests after a 503/busy")
    ap.add_argument("--max-attempts", type=int, default=3, help="Tries per item across accounts")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()
    tee = LogTee(sys.stdout)
    sys.stdout = tee
    pool = MusePool(args.cookies_dir, args.port, args.host, min(max(args.per_account, 1), 8),
                    not args.headful, args.health_interval, args.cooldown, args.max_attempts)
    pool.log_tee = tee
    try:
        asyncio.run(pool.run())
    except KeyboardInterrupt:
        print("\n[Pool] Stopped.")


if __name__ == "__main__":
    main()
