#!/usr/bin/env python3
"""
Muse.ai In-Browser RPC Bridge Server
Provides a local REST API that communicates directly with muse.ai
via Playwright / Chrome DevTools Protocol without UI typing.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import uuid
import time
from typing import Optional, List, Dict
from aiohttp import web
from playwright.async_api import async_playwright, BrowserContext, Page

BRIDGE_JS_PATH = os.path.join(os.path.dirname(__file__), "muse_bridge.js")
INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")
DOCS_HTML_PATH = os.path.join(os.path.dirname(__file__), "docs.html")
DEFAULT_COOKIES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cookies.json")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
NEW_THREAD_URL = "https://muse.ai/thread/new"
THREAD_MAP_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "muse_threads.json")


def _load_thread_map() -> dict:
    try:
        with open(THREAD_MAP_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_thread_map(m: dict) -> None:
    try:
        os.makedirs(os.path.dirname(THREAD_MAP_FILE), exist_ok=True)
        with open(THREAD_MAP_FILE + ".tmp", "w") as f:
            json.dump(m, f)
        os.replace(THREAD_MAP_FILE + ".tmp", THREAD_MAP_FILE)
    except Exception as e:  # noqa: BLE001
        print(f"[Bridge] cannot save thread map: {e}")


MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# ── Public access qua Tailscale Funnel (vd Tool-RD trên Vercel) ─────────────────
# Funnel proxy tới http://127.0.0.1:8770 nên request thật xuất hiện là loopback và KHÔNG có
# header "Tailscale-Funnel-Request" (Tailscale không tự thêm). Vì vậy is_public() coi request là
# public khi: loopback, hoặc có X-Forwarded-For, hoặc có header Funnel. Với request public:
#   - BẮT BUỘC API key (MUSE_API_KEY) — chưa set key => chặn hết (fail-closed)
#   - chỉ cho các endpoint tạo ảnh/video cần thiết (không /v1/eval, chat UI, threads…)
#   - "files" chỉ nhận data: URL (chặn đọc file cục bộ / SSRF)
# Client Tailnet gọi thẳng 100.126.145.3:8770 (remote 100.x) giữ nguyên như cũ, không cần key.
# LƯU Ý: script chạy NGAY trên máy Windows qua 127.0.0.1 giờ cũng cần key — dùng IP Tailnet nếu muốn bỏ qua.
API_KEY = os.environ.get("MUSE_API_KEY", "").strip()
CORS_ORIGINS = {o.strip().rstrip("/") for o in os.environ.get(
    "MUSE_CORS_ORIGINS", "https://tool-rd.vercel.app,http://localhost:3000").split(",") if o.strip()}
FUNNEL_ALLOWED = {("GET", "/v1/status"), ("POST", "/v1/batch/async"), ("GET", "/v1/batch/status")}

class MuseBridgeServer:
    def __init__(
        self,
        port: int = 8765,
        cdp_url: Optional[str] = None,
        cookies_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        headless: bool = True,
        name: str = "default",
        shared_browser=None,
        batch_jobs_file: Optional[str] = None
    ):
        self.port = port
        self.cdp_url = cdp_url
        self.cookies_path = cookies_path or (DEFAULT_COOKIES_PATH if os.path.exists(DEFAULT_COOKIES_PATH) else None)
        self.user_data_dir = user_data_dir or os.path.expanduser("~/.muse_chrome_profile")
        self.headless = headless
        self.name = name
        self.shared_browser = shared_browser
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.lock = asyncio.Lock()
        self.batch_jobs: Dict[str, Dict] = {}
        self.batch_jobs_file = batch_jobs_file or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scratch", "batch_jobs.json")
        self.bridge_js = ""
        self._load_bridge_script()
        self._load_batch_jobs()

    def _load_batch_jobs(self):
        if os.path.exists(self.batch_jobs_file):
            try:
                with open(self.batch_jobs_file, "r", encoding="utf-8") as f:
                    self.batch_jobs = json.load(f)
                print(f"[Bridge] Loaded {len(self.batch_jobs)} persistent batch jobs from disk.")
            except Exception as e:
                print(f"[Bridge] Warning: Could not load batch jobs: {e}")

    def _save_batch_jobs(self):
        try:
            os.makedirs(os.path.dirname(self.batch_jobs_file), exist_ok=True)
            with open(self.batch_jobs_file, "w", encoding="utf-8") as f:
                json.dump(self.batch_jobs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Bridge] Warning: Could not save batch jobs: {e}")

    def _load_bridge_script(self):
        with open(BRIDGE_JS_PATH, "r", encoding="utf-8") as f:
            self.bridge_js = f.read()

    def _load_cookies(self) -> List[Dict]:
        if not self.cookies_path or not os.path.exists(self.cookies_path):
            return []
        try:
            with open(self.cookies_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Convert dict format to Playwright list format
                    return [
                        {"name": k, "value": v, "domain": ".muse.ai", "path": "/", "secure": True}
                        for k, v in data.items()
                    ]
        except Exception as e:
            print(f"[Bridge] Warning: Failed to read cookies from {self.cookies_path}: {e}")
        return []

    async def init_browser(self):
        """Initializes connection to Chrome (via CDP or standalone Playwright session with cookies)."""
        if not self.shared_browser:
            self.playwright = await async_playwright().start()

        # 1. Try connecting to existing Chrome instance on CDP port if provided
        if self.cdp_url:
            try:
                print(f"[Bridge] Attempting to connect to existing Chrome via CDP at {self.cdp_url}...")
                browser = await self.playwright.chromium.connect_over_cdp(self.cdp_url)
                contexts = browser.contexts
                if contexts:
                    self.context = contexts[0]
                    pages = self.context.pages
                    for p in pages:
                        if "muse.ai" in p.url:
                            self.page = p
                            print(f"[Bridge] Attached to existing muse.ai tab: {p.url}")
                            break
                    if not self.page and pages:
                        self.page = pages[0]
                print("[Bridge] Successfully connected to existing Chrome via CDP.")
            except Exception as e:
                print(f"[Bridge] Could not connect to CDP ({e}). Launching dedicated browser context.")

        # 2. Launch browser context with persistent profile or cookies
        if not self.page:
            cookies = self._load_cookies()
            if self.shared_browser:
                browser = self.shared_browser
            else:
                print(f"[Bridge] Launching browser (headless={self.headless})...")
                browser = await self.playwright.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"]
                )
            self.context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            if cookies:
                print(f"[Bridge] Injecting {len(cookies)} session cookies...")
                await self.context.add_cookies(cookies)

            self.page = await self.context.new_page()

        # 3. Navigate to muse.ai if not already there
        if "muse.ai" not in self.page.url:
            print("[Bridge] Navigating to https://muse.ai/ ...")
            await self.page.goto("https://muse.ai/", wait_until="domcontentloaded", timeout=30000)
            print("[Bridge] Page loaded. Waiting 3s for React hydration...")
            await asyncio.sleep(3)

        # 4. Inject bridge script
        await self.inject_bridge()

    async def inject_bridge(self, target_page: Optional[Page] = None):
        """Injects bridge script and verifies readiness."""
        p = target_page or self.page
        if not p:
            return False
        try:
            self._load_bridge_script()
            await p.evaluate(self.bridge_js)
            ready = await p.evaluate("typeof window.__muse !== 'undefined' && window.__muse.isReady()")
            print(f"[Bridge] Script injected. Bridge ready: {ready}")
            return ready
        except Exception as e:
            print(f"[Bridge] Error injecting bridge: {e}")
            return False

    async def open_new_side_chat(self, target_page: Optional[Page] = None) -> str:
        """Opens a fresh side chat. Clicks the in-app button when present (SPA route, no reload);
        otherwise navigates to /thread/new from Python so evaluate() isn't cut by the navigation."""
        p = target_page or self.page
        btn = p.locator('button[aria-label="New side chat"]')
        try:
            await btn.first.click(timeout=5000)
            await asyncio.sleep(1.2)
        except Exception:
            await p.goto(NEW_THREAD_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        await self.inject_bridge(p)
        return p.url

    async def handle_status(self, request: web.Request) -> web.Response:
        """Returns bridge status and current muse.ai connection state."""
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser not initialized"}, status=503)

        try:
            url = self.page.url
            title = await self.page.title()
            ready = await self.page.evaluate("typeof window.__muse !== 'undefined' && window.__muse.isReady()")
            return web.json_response({
                "ok": True,
                "url": url,
                "title": title,
                "bridge_ready": ready,
                "headless": self.headless,
                "batch_files": True
            })
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def attach_files(self, file_paths: List[str], target_page: Optional[Page] = None) -> Dict:
        """Attaches local files to the Muse.ai composer via input[type=file]."""
        p = target_page or self.page
        if not p:
            return {"ok": False, "error": "Browser page not connected"}
        if not file_paths:
            return {"ok": True, "attached": 0}

        try:
            file_input = None
            for attempt in range(25):
                file_input = await p.query_selector('input[type="file"]')
                if file_input:
                    break
                if attempt in (6, 12, 18):
                    # composer may render the file input only after the attach ("+") button is touched
                    await p.evaluate("""() => {
                        const b = document.querySelector('button[aria-label*="ttach" i], button[aria-label*="Upload" i], button[aria-label*="Add" i]');
                        if (b) b.click();
                    }""")
                await asyncio.sleep(0.5)
            if not file_input:
                return {"ok": False, "error": "Không tìm thấy ô tải tệp, hãy gửi lại"}

            print(f"[Bridge] Attaching {len(file_paths)} file(s): {file_paths}")
            await file_input.set_input_files(file_paths)

            # Wait for upload processing and attachment chip rendering in composer
            for attempt in range(20):
                await asyncio.sleep(0.8)
                status = await p.evaluate("""() => {
                    const composer = document.querySelector('textarea')?.closest('[data-hatch-composer-root]') 
                        || document.querySelector('textarea')?.parentElement?.parentElement?.parentElement;
                    if (!composer) return { ready: false, count: 0 };
                    
                    const spinners = composer.querySelectorAll('svg[class*="animate-spin"], [role="progressbar"]');
                    const chips = composer.querySelectorAll('[data-attachment-id], img, [aria-label*="Remove"], [aria-label*="Delete"]');
                    return {
                        ready: spinners.length === 0 && chips.length > 0,
                        uploading: spinners.length > 0,
                        count: chips.length
                    };
                }""")
                if status.get("ready"):
                    print("[Bridge] Attachments successfully processed and staged in composer!")
                    break

            return {"ok": True, "attached": len(file_paths)}
        except Exception as e:
            print(f"[Bridge] Error attaching files: {e}")
            return {"ok": False, "error": str(e)}

    async def handle_upload(self, request: web.Request) -> web.Response:
        """
        Uploads and stages files in the Muse.ai composer without immediately sending a prompt.
        POST /v1/upload
        """
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser page not connected"}, status=503)

        file_paths = []
        content_type = request.headers.get("Content-Type", "")
        if "multipart/form-data" in content_type:
            try:
                reader = await request.multipart()
                while True:
                    part = await reader.next()
                    if part is None:
                        break
                    if part.name in ("files", "file"):
                        filename = part.filename or f"upload_{uuid.uuid4().hex[:8]}.bin"
                        save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:6]}_{filename}")
                        with open(save_path, "wb") as f:
                            while True:
                                chunk = await part.read_chunk()
                                if not chunk:
                                    break
                                f.write(chunk)
                        file_paths.append(save_path)
            except Exception as e:
                return web.json_response({"ok": False, "error": f"Error parsing multipart: {e}"}, status=400)
        else:
            try:
                data = await request.json()
                for p in data.get("files", []):
                    if isinstance(p, str) and os.path.exists(p):
                        file_paths.append(os.path.abspath(p))
            except Exception:
                pass

        if not file_paths:
            return web.json_response({"ok": False, "error": "No valid files received"}, status=400)

        res = await self.attach_files(file_paths)
        return web.json_response(res)

    async def save_media_blobs(self, media_list: List, target_page: Optional[Page] = None) -> List[str]:
        """
        Takes media items extracted from page (with blob: URLs or remote URLs),
        fetches their binary data inside the browser context, saves to MEDIA_DIR,
        and returns list of local URLs (/media/filename).
        """
        p = target_page or self.page
        if not p or not media_list:
            return []

        saved_urls = []
        for idx, item in enumerate(media_list):
            url = item.get("url") if isinstance(item, dict) else item
            m_type = item.get("type", "video") if isinstance(item, dict) else ("video" if ".mp4" in str(item) else "image")
            if not url or not isinstance(url, str):
                continue

            if url.startswith("/media/"):
                saved_urls.append(url)
                continue

            try:
                b64_res = await p.evaluate("""
                    async (targetUrl) => {
                        try {
                            const resp = await fetch(targetUrl);
                            const blob = await resp.blob();
                            return await new Promise((resolve, reject) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve({ ok: true, data: reader.result });
                                reader.onerror = () => reject({ ok: false, error: "FileReader failed" });
                                reader.readAsDataURL(blob);
                            });
                        } catch (err) {
                            return { ok: false, error: err.toString() };
                        }
                    }
                """, url)

                if b64_res and b64_res.get("ok") and b64_res.get("data"):
                    data_uri = b64_res["data"]
                    ext = ".mp4" if m_type == "video" else ".png"
                    if "," in data_uri:
                        header, b64_payload = data_uri.split(",", 1)
                        if "video/mp4" in header: ext = ".mp4"
                        elif "image/jpeg" in header: ext = ".jpg"
                        elif "image/webp" in header: ext = ".webp"
                        elif "image/png" in header: ext = ".png"
                    else:
                        b64_payload = data_uri

                    fname = f"muse_{uuid.uuid4().hex[:8]}_{idx}{ext}"
                    local_path = os.path.join(MEDIA_DIR, fname)
                    with open(local_path, "wb") as f:
                        f.write(base64.b64decode(b64_payload))
                    print(f"[Bridge] Saved generated media: {local_path} ({os.path.getsize(local_path)} bytes)")
                    saved_urls.append(f"/media/{fname}")
                else:
                    print(f"[Bridge] Failed fetching media blob {url}: {b64_res.get('error') if b64_res else 'None'}")
            except Exception as e:
                print(f"[Bridge] Error saving media {url}: {e}")

        return saved_urls

    async def handle_chat(self, request: web.Request) -> web.Response:
        """
        Sends a prompt and/or files directly via React composer state and waits for the full response.
        POST /v1/chat
        Supports:
          1. multipart/form-data: prompt, timeout_ms, new_thread, files (one or multiple)
          2. application/json: {"prompt": "...", "files": ["/path/to/file", "data:image/..."]}
        """
        t_recv = time.time()
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser page not connected"}, status=503)

        content_type = request.headers.get("Content-Type", "")
        file_paths = []
        prompt = ""
        timeout_ms = 180000
        new_thread = True
        thread_id = None
        conv = ""        # UI chat id -> one persistent Muse side chat
        ctx_prompt = ""  # full context, used only when the Muse side chat is brand new

        if "multipart/form-data" in content_type:
            try:
                reader = await request.multipart()
                while True:
                    part = await reader.next()
                    if part is None:
                        break
                    if part.name == "prompt":
                        prompt = (await part.text()).strip()
                    elif part.name == "timeout_ms":
                        try:
                            timeout_ms = int(await part.text())
                        except ValueError:
                            pass
                    elif part.name == "new_thread":
                        new_thread = (await part.text()).lower() in ("true", "1")
                    elif part.name == "thread_id":
                        thread_id = (await part.text()).strip()
                    elif part.name == "conv":
                        conv = (await part.text()).strip()
                    elif part.name == "context":
                        ctx_prompt = (await part.text()).strip()
                    elif part.name in ("files", "file"):
                        filename = part.filename or f"upload_{uuid.uuid4().hex[:8]}.bin"
                        save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:6]}_{filename}")
                        with open(save_path, "wb") as f:
                            while True:
                                chunk = await part.read_chunk()
                                if not chunk:
                                    break
                                f.write(chunk)
                        file_paths.append(save_path)
            except Exception as e:
                return web.json_response({"ok": False, "error": f"Error parsing multipart: {e}"}, status=400)
        else:
            try:
                data = await request.json()
            except Exception:
                return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

            prompt = data.get("prompt", "").strip()
            timeout_ms = data.get("timeout_ms", 180000)
            new_thread = bool(data.get("new_thread", data.get("createNewThread", True)))
            conv = str(data.get("conv") or "").strip()
            ctx_prompt = str(data.get("context") or "").strip()

            raw_files = data.get("files", [])
            for rf in raw_files:
                if isinstance(rf, str):
                    if os.path.exists(rf):
                        file_paths.append(os.path.abspath(rf))
                    elif rf.startswith("data:"):
                        header, b64data = rf.split(",", 1)
                        ext = ".png"
                        if "image/jpeg" in header: ext = ".jpg"
                        elif "image/webp" in header: ext = ".webp"
                        elif "video/mp4" in header: ext = ".mp4"
                        save_path = os.path.join(UPLOAD_DIR, f"b64_{uuid.uuid4().hex[:8]}{ext}")
                        with open(save_path, "wb") as f:
                            f.write(base64.b64decode(b64data))
                        file_paths.append(save_path)
                elif isinstance(rf, dict):
                    name = rf.get("name", f"file_{uuid.uuid4().hex[:6]}")
                    data_str = rf.get("data", "")
                    if "," in data_str:
                        data_str = data_str.split(",", 1)[1]
                    save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:6]}_{name}")
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(data_str))
                    file_paths.append(save_path)

        if "multipart/form-data" not in content_type:
            thread_id = data.get("thread_id") if data.get("thread_id") is not None else data.get("index")

        if not prompt and not file_paths:
            return web.json_response({"ok": False, "error": "prompt or file attachment is required"}, status=400)

        # Default prompt if files attached without explicit prompt
        if not prompt and file_paths:
            prompt = "Hãy xem và phân tích hình ảnh/video này."

        wrap = request.get("wrap_prompt")
        if wrap:
            prompt = await wrap(prompt)
            new_thread, thread_id = True, None

        async with self.lock:
            t_lock = time.time()
            # Ensure bridge is ready
            await self.inject_bridge()

            tmap = _load_thread_map() if conv else {}
            if conv and tmap.get(conv):
                # Same UI chat -> same Muse side chat; Muse already has the history, send only the new message.
                try:
                    await self.page.goto(tmap[conv], wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    await self.inject_bridge()
                    nb = await self.page.evaluate("() => window.__muse.waitForHistory(15000)")
                    print(f"[Bridge] Resumed side chat for {conv}: {tmap[conv]} ({nb} bubbles loaded)")
                except Exception as e:  # noqa: BLE001
                    print(f"[Bridge] resume failed ({e}); starting a new side chat with context")
                    tmap.pop(conv, None)
            if conv and not tmap.get(conv):
                url = await self.open_new_side_chat()
                print(f"[Bridge] Opened new side chat for {conv}: {url}")
                if ctx_prompt:
                    prompt = ctx_prompt
            elif conv:
                pass
            elif thread_id is not None:
                print(f"[Bridge] Switching to thread: {thread_id}")
                await self.page.evaluate("async (t) => await window.__muse.switchThread(t)", thread_id)
                await asyncio.sleep(1.0)
            elif new_thread:
                url = await self.open_new_side_chat()
                print(f"[Bridge] Opened new side chat: {url}")

            try:
                # 1. Attach files if present
                if file_paths:
                    attach_res = await self.attach_files(file_paths)
                    if not attach_res.get("ok"):
                        return web.json_response({"ok": False, "error": f"Failed attaching files: {attach_res.get('error')}"}, status=500)

                # 2. Dispatch prompt via internal React setter
                print(f"[Bridge] Dispatching prompt: '{prompt[:50]}...' with {len(file_paths)} file(s)"
                      f" | queue {t_lock - t_recv:.1f}s, open-chat {time.time() - t_lock:.1f}s")
                send_res = await self.page.evaluate("""
                    async (promptText) => {
                        return await window.__muse.sendPrompt(promptText);
                    }
                """, prompt)

                # 3. Wait for completion and stream result
                res = await self.page.evaluate("""
                    async (opts) => {
                        return await window.__muse.waitForCompletion(opts);
                    }
                """, {"timeoutMs": timeout_ms, "prompt": prompt})

                if conv:
                    cur = self.page.url
                    if "/thread/" in cur and not cur.rstrip("/").endswith("/thread/new"):
                        tm = _load_thread_map()
                        if tm.get(conv) != cur:
                            tm[conv] = cur
                            _save_thread_map(tm)
                raw_media = res.get("media", [])
                if not raw_media:
                    try:
                        fresh_turn = await self.page.evaluate("() => window.__muse ? window.__muse.extractCurrentTurn() : null")
                        if fresh_turn and fresh_turn.get("media"):
                            raw_media = fresh_turn.get("media")
                    except Exception:
                        pass
                saved_media = await self.save_media_blobs(raw_media)
                content = res.get("content") or ""
                is_video_error = len(saved_media) == 0 and any(
                    err_kw in content.lower() for err_kw in [
                        "503", "lỗi 503", "tạm ngưng", "không render được", "chưa tạo được video",
                        "không khả dụng", "hệ thống tạo video đang bận", "lỗi kỹ thuật"
                    ]
                )
                ok = not is_video_error and (res.get("status") != "failed_refusal")
                ret = {
                    "ok": ok,
                    "content": content,
                    "media": saved_media,
                    "duration_ms": res.get("durationMs"),
                    "status": "completed" if ok else "failed"
                }
                if not ok:
                    ret["error"] = "Muse video generation failed or service busy (503)"
                return web.json_response(ret)
            except Exception as e:
                return web.json_response({"ok": False, "error": str(e)}, status=500)

    def materialize_files(self, raw_files) -> List[str]:
        """Turns request `files` (local paths, data URLs, remote URLs, or {name, data}) into local file paths."""
        paths: List[str] = []
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for rf in raw_files or []:
            if isinstance(rf, str):
                if os.path.exists(rf):
                    paths.append(os.path.abspath(rf))
                elif rf.startswith("data:"):
                    header, b64data = rf.split(",", 1)
                    ext = ".png"
                    if "image/jpeg" in header: ext = ".jpg"
                    elif "image/webp" in header: ext = ".webp"
                    elif "video/mp4" in header: ext = ".mp4"
                    save_path = os.path.join(UPLOAD_DIR, f"b64_{uuid.uuid4().hex[:8]}{ext}")
                    with open(save_path, "wb") as f:
                        f.write(base64.b64decode(b64data))
                    paths.append(save_path)
                elif rf.startswith("http://") or rf.startswith("https://"):
                    try:
                        import urllib.request
                        ext = ".jpg"
                        if ".png" in rf: ext = ".png"
                        elif ".webp" in rf: ext = ".webp"
                        elif ".mp4" in rf: ext = ".mp4"
                        save_path = os.path.join(UPLOAD_DIR, f"dl_{uuid.uuid4().hex[:8]}{ext}")
                        urllib.request.urlretrieve(rf, save_path)
                        paths.append(save_path)
                    except Exception as e:
                        print(f"[Bridge] Error downloading URL {rf}: {e}")
                elif len(rf) > 200 and not rf.startswith("/") and not rf.startswith("."):
                    try:
                        save_path = os.path.join(UPLOAD_DIR, f"rawb64_{uuid.uuid4().hex[:8]}.jpg")
                        with open(save_path, "wb") as f:
                            f.write(base64.b64decode(rf))
                        paths.append(save_path)
                    except Exception:
                        pass
            elif isinstance(rf, dict):
                name = rf.get("name", f"file_{uuid.uuid4().hex[:6]}")
                data_str = rf.get("data", "")
                if "," in data_str:
                    data_str = data_str.split(",", 1)[1]
                save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:6]}_{name}")
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(data_str))
                paths.append(save_path)
        return paths

    async def execute_prompt_on_page(
        self,
        page: Page,
        prompt: str,
        file_paths: Optional[List[str]] = None,
        timeout_ms: int = 180000
    ) -> Dict:
        """Executes a single prompt on a target browser page, handles attachments, and returns saved media."""
        await self.inject_bridge(page)
        if file_paths:
            attach_res = await self.attach_files(file_paths, page)
            if not attach_res.get("ok"):
                return {"ok": False, "error": f"Failed attaching files: {attach_res.get('error')}"}

        print(f"[Bridge Worker] Dispatching prompt: '{prompt[:50]}...' with {len(file_paths or [])} attachment(s)")
        await page.evaluate("""
            async (promptText) => {
                return await window.__muse.sendPrompt(promptText);
            }
        """, prompt)

        res = await page.evaluate("""
            async (opts) => {
                return await window.__muse.waitForCompletion(opts);
            }
        """, {"timeoutMs": timeout_ms, "prompt": prompt})

        raw_media = res.get("media", [])
        if not raw_media:
            try:
                fresh_turn = await page.evaluate("() => window.__muse ? window.__muse.extractCurrentTurn() : null")
                if fresh_turn and fresh_turn.get("media"):
                    raw_media = fresh_turn.get("media")
            except Exception:
                pass
        saved_media = await self.save_media_blobs(raw_media, page)
        content = res.get("content") or ""
        is_video_error = len(saved_media) == 0 and any(
            err_kw in content.lower() for err_kw in [
                "503", "lỗi 503", "tạm ngưng", "không render được", "chưa tạo được video",
                "không khả dụng", "hệ thống tạo video đang bận", "lỗi kỹ thuật"
            ]
        )
        ok = not is_video_error and (res.get("status") != "failed_refusal")
        res_dict = {
            "ok": ok,
            "prompt": prompt,
            "content": content,
            "media": saved_media,
            "files_attached": len(file_paths or []),
            "duration_ms": res.get("durationMs"),
            "status": "completed" if ok else "failed"
        }
        if not ok:
            res_dict["error"] = "Muse video generation failed or service busy (503)"
        return res_dict

    async def handle_batch_chat(self, request: web.Request) -> web.Response:
        """
        Executes multiple prompts concurrently across worker browser pages.
        Supports both:
          1. {"prompts": ["p1", "p2"], "concurrency": 3}
          2. {"items": [{"prompt": "p1", "files": ["data:image/jpeg;base64,..."]}, ...], "concurrency": 3}
        POST /v1/batch/chat
        """
        if not self.context:
            return web.json_response({"ok": False, "error": "Browser context not ready"}, status=503)

        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON or Payload Error: {e}"}, status=400)

        prompts = data.get("prompts", [])
        raw_items = data.get("items", [])
        raw_files = data.get("files", [])

        if raw_items:
            kept = [it for it in raw_items if it.get("prompt")]
            prompts = [it.get("prompt", "") for it in kept]
            item_files = [it.get("files") or [] for it in kept]
        elif prompts:
            if isinstance(raw_files, list) and len(raw_files) > 0 and isinstance(raw_files[0], list):
                item_files = raw_files
            elif isinstance(raw_files, list) and len(raw_files) > 0:
                item_files = [raw_files for _ in prompts]
            else:
                item_files = [[] for _ in prompts]
        else:
            return web.json_response({"ok": False, "error": "Either 'items' or 'prompts' array is required"}, status=400)

        concurrency = min(max(int(data.get("concurrency", 2)), 1), 5)
        timeout_ms = data.get("timeout_ms", 180000)
        sem = asyncio.Semaphore(concurrency)

        results = [None] * len(prompts)

        async def worker_task(idx: int, p_text: str):
            async with sem:
                page = None
                try:
                    print(f"[Batch Worker #{idx+1}] Launching worker page for prompt: '{p_text[:40]}...'")
                    page = await self.context.new_page()
                    await page.goto(NEW_THREAD_URL, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)
                    await self.inject_bridge(page)
                    file_paths = self.materialize_files(item_files[idx])
                    res = await self.execute_prompt_on_page(page, p_text, file_paths, timeout_ms)
                    results[idx] = res
                except Exception as err:
                    print(f"[Batch Worker #{idx+1}] Error: {err}")
                    results[idx] = {"ok": False, "prompt": p_text, "error": str(err)}
                finally:
                    if page:
                        try:
                            await page.close()
                        except Exception:
                            pass

        tasks = [worker_task(i, p) for i, p in enumerate(prompts)]
        await asyncio.gather(*tasks)

        completed_count = sum(1 for r in results if r and r.get("ok"))
        failed_count = len(results) - completed_count

        return web.json_response({
            "ok": True,
            "total": len(prompts),
            "completed": completed_count,
            "failed": failed_count,
            "results": results
        })

    async def handle_batch_async(self, request: web.Request) -> web.Response:
        """
        Creates an asynchronous batch job and returns immediately with a batch_id.
        POST /v1/batch/async
        """
        if not self.context:
            return web.json_response({"ok": False, "error": "Browser context not ready"}, status=503)

        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON or Payload Error: {e}"}, status=400)

        prompts = data.get("prompts", [])
        raw_items = data.get("items", [])
        raw_files = data.get("files", [])

        if raw_items:
            kept = [it for it in raw_items if it.get("prompt")]
            prompts = [it.get("prompt", "") for it in kept]
            item_files = [it.get("files") or [] for it in kept]
        elif prompts:
            if isinstance(raw_files, list) and len(raw_files) > 0 and isinstance(raw_files[0], list):
                item_files = raw_files
            elif isinstance(raw_files, list) and len(raw_files) > 0:
                item_files = [raw_files for _ in prompts]
            else:
                item_files = [[] for _ in prompts]
        else:
            return web.json_response({"ok": False, "error": "Either 'items' or 'prompts' array is required"}, status=400)

        concurrency = min(max(int(data.get("concurrency", 2)), 1), 5)
        timeout_ms = data.get("timeout_ms", 180000)
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"

        job_info = {
            "batch_id": batch_id,
            "status": "running",
            "created_at": time.time(),
            "total": len(prompts),
            "completed": 0,
            "failed": 0,
            "concurrency": concurrency,
            "results": [None] * len(prompts)
        }
        self.batch_jobs[batch_id] = job_info
        self._save_batch_jobs()

        async def run_batch():
            sem = asyncio.Semaphore(concurrency)
            async def worker(idx: int, p_text: str):
                async with sem:
                    page = None
                    try:
                        print(f"[Async Batch #{batch_id} Worker #{idx+1}] Launching worker page...")
                        page = await self.context.new_page()
                        await page.goto(NEW_THREAD_URL, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3)
                        await self.inject_bridge(page)
                        file_paths = self.materialize_files(item_files[idx])
                        res = await self.execute_prompt_on_page(page, p_text, file_paths, timeout_ms)
                        job_info["results"][idx] = res
                        if res.get("ok"):
                            job_info["completed"] += 1
                        else:
                            job_info["failed"] += 1
                    except Exception as err:
                        job_info["results"][idx] = {"ok": False, "prompt": p_text, "error": str(err)}
                        job_info["failed"] += 1
                    finally:
                        self._save_batch_jobs()
                        if page:
                            try:
                                await page.close()
                            except Exception:
                                pass

            await asyncio.gather(*[worker(i, p) for i, p in enumerate(prompts)])
            job_info["status"] = "completed"
            job_info["finished_at"] = time.time()
            self._save_batch_jobs()

        asyncio.create_task(run_batch())

        return web.json_response({
            "ok": True,
            "batch_id": batch_id,
            "status": "running",
            "total": len(prompts),
            "status_url": f"/v1/batch/status?id={batch_id}"
        })

    async def handle_batch_status(self, request: web.Request) -> web.Response:
        """
        Checks the status of an asynchronous batch job.
        GET /v1/batch/status?id=batch_xxx
        If no id is provided, returns list of all recent batches!
        """
        batch_id = request.query.get("id") or request.query.get("batch_id")
        if not batch_id:
            recent = list(self.batch_jobs.values())[-20:]
            return web.json_response({
                "ok": True,
                "count": len(self.batch_jobs),
                "recent_jobs": [{
                    "batch_id": j.get("batch_id"),
                    "status": j.get("status"),
                    "total": j.get("total"),
                    "completed": j.get("completed"),
                    "failed": j.get("failed"),
                    "created_at": j.get("created_at"),
                    "finished_at": j.get("finished_at")
                } for j in recent]
            })

        if batch_id not in self.batch_jobs:
            print(f"[Batch Status] Requested id '{batch_id}' not found. Recent: {list(self.batch_jobs.keys())[-5:]}")
            return web.json_response({
                "ok": False,
                "error": f"Batch job '{batch_id}' not found",
                "available_recent": list(self.batch_jobs.keys())[-5:]
            }, status=404)

        return web.json_response({"ok": True, **self.batch_jobs[batch_id]})

    async def handle_get_threads(self, request: web.Request) -> web.Response:
        """
        Lists all conversation threads from the Muse.ai sidebar.
        GET /v1/threads
        """
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser not connected"}, status=503)
        try:
            threads = await self.page.evaluate("window.__muse ? window.__muse.getThreads() : []")
            return web.json_response({"ok": True, "threads": threads, "count": len(threads)})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def handle_switch_thread(self, request: web.Request) -> web.Response:
        """
        Switches the active conversation thread.
        POST /v1/threads/switch
        Body: {"thread_id": "thread_1"} or {"index": 1} or {"title": "..."}
        """
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser not connected"}, status=503)
        try:
            data = await request.json()
            target = data.get("thread_id") if data.get("thread_id") is not None else (data.get("id") if data.get("id") is not None else data.get("index"))
            if target is None:
                target = data.get("title")
            if target is None:
                return web.json_response({"ok": False, "error": "Missing thread_id, index, or title"}, status=400)

            res = await self.page.evaluate("async (t) => await window.__muse.switchThread(t)", target)
            turns = await self.page.evaluate("window.__muse ? window.__muse.getHistory() : []")
            for turn in turns:
                raw_media = turn.get("media", [])
                if raw_media:
                    turn["media"] = await self.save_media_blobs(raw_media)
            return web.json_response({"ok": True, "switch_result": res, "turns": turns})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def handle_history(self, request: web.Request) -> web.Response:
        """Returns the full turn-by-turn conversation history with local media URLs.
        Optional query params: ?thread_id=thread_1 or ?index=1
        """
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser not connected"}, status=503)

        try:
            thread_param = request.query.get("thread_id") or request.query.get("index")
            if thread_param:
                try:
                    target = int(thread_param)
                except ValueError:
                    target = thread_param
                await self.page.evaluate("async (t) => await window.__muse.switchThread(t)", target)
                await asyncio.sleep(0.8)

            turns = await self.page.evaluate("window.__muse ? window.__muse.getHistory() : []")
            for turn in turns:
                raw_media = turn.get("media", [])
                if raw_media:
                    turn["media"] = await self.save_media_blobs(raw_media)
            return web.json_response({"ok": True, "turns": turns})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def handle_new_thread(self, request: web.Request) -> web.Response:
        """Starts a new chat thread."""
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser not connected"}, status=503)

        try:
            async with self.lock:
                url = await self.open_new_side_chat()
                threads = await self.page.evaluate("window.__muse ? window.__muse.getThreads() : []")
            return web.json_response({"ok": True, "result": {"ok": True, "currentUrl": url}, "threads": threads})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        """
        OpenAI-compatible /v1/chat/completions endpoint.
        Drop-in replacement for OpenAI API.
        POST /v1/chat/completions
        """
        if not self.page:
            return web.json_response({"error": {"message": "Browser not connected"}}, status=503)
        try:
            data = await request.json()
            messages = data.get("messages", [])
            if not messages:
                return web.json_response({"error": {"message": "messages array is required"}}, status=400)

            prompt = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content")
                    if isinstance(content, str):
                        prompt = content
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "text":
                                prompt += part.get("text", "") + "\n"
                    break

            if not prompt:
                return web.json_response({"error": {"message": "No user message found"}}, status=400)

            thread_id = data.get("thread_id") or data.get("thread")
            new_thread = bool(data.get("new_thread", True))
            timeout_ms = data.get("timeout_ms", 180000)

            async with self.lock:
                await self.inject_bridge()
                if thread_id is not None:
                    await self.page.evaluate("async (t) => await window.__muse.switchThread(t)", thread_id)
                    await asyncio.sleep(0.8)
                elif new_thread:
                    url = await self.open_new_side_chat()
                    print(f"[Bridge] Opened new side chat: {url}")

                await self.page.evaluate("""
                    async (promptText) => {
                        return await window.__muse.sendPrompt(promptText);
                    }
                """, prompt)

                res = await self.page.evaluate("""
                    async (opts) => {
                        return await window.__muse.waitForCompletion(opts);
                    }
                """, {"timeoutMs": timeout_ms, "prompt": prompt})

                raw_media = res.get("media", [])
                saved_media = await self.save_media_blobs(raw_media)
            content_text = res.get("content", "")

            return web.json_response({
                "id": f"chatcmpl-muse-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": data.get("model", "muse-ai"),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content_text
                        },
                        "finish_reason": "stop"
                    }
                ],
                "media": saved_media,
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(content_text.split()),
                    "total_tokens": len(prompt.split()) + len(content_text.split())
                }
            })
        except Exception as e:
            return web.json_response({"error": {"message": str(e)}}, status=500)

    async def handle_api_docs(self, request: web.Request) -> web.Response:
        """Returns API documentation & curl examples."""
        base_url = f"http://localhost:{self.port}"
        docs = {
            "title": "Muse.ai Bridge REST API",
            "version": "1.0.0",
            "base_url": base_url,
            "endpoints": [
                {
                    "method": "POST",
                    "path": "/v1/chat",
                    "description": "Gửi prompt và nhận câu trả lời cùng media.",
                    "curl_example": f'curl -X POST {base_url}/v1/chat -H "Content-Type: application/json" -d \'{{"prompt": "Tạo video TVC 15s sân thượng"}}\''
                },
                {
                    "method": "POST",
                    "path": "/v1/chat (with image/video)",
                    "description": "Đính kèm file ảnh hoặc video khi gửi prompt.",
                    "curl_example": f'curl -X POST {base_url}/v1/chat -F "prompt=Tạo video TVC cho sản phẩm này" -F "files=@/path/to/image.png"'
                },
                {
                    "method": "GET",
                    "path": "/v1/threads",
                    "description": "Lấy danh sách tất cả các cuộc trò chuyện (threads).",
                    "curl_example": f"curl {base_url}/v1/threads"
                },
                {
                    "method": "POST",
                    "path": "/v1/threads/switch",
                    "description": "Chuyển sang cuộc trò chuyện khác bằng thread_id (thread_0) hoặc index (0).",
                    "curl_example": f'curl -X POST {base_url}/v1/threads/switch -H "Content-Type: application/json" -d \'{{"thread_id": "thread_1"}}\''
                },
                {
                    "method": "POST",
                    "path": "/v1/threads/new",
                    "description": "Tạo một cuộc trò chuyện mới.",
                    "curl_example": f"curl -X POST {base_url}/v1/threads/new"
                },
                {
                    "method": "GET",
                    "path": "/v1/history",
                    "description": "Lấy toàn bộ lịch sử tin nhắn và media. Hỗ trợ query ?thread_id=thread_1",
                    "curl_example": f"curl {base_url}/v1/history"
                },
                {
                    "method": "POST",
                    "path": "/v1/chat/completions",
                    "description": "Chuẩn OpenAI Chat Completion (tương thích OpenAI SDK / LangChain / Cursor).",
                    "curl_example": f'curl -X POST {base_url}/v1/chat/completions -H "Content-Type: application/json" -d \'{{"model": "muse", "messages": [{{"role": "user", "content": "Xin chào"}}]}}\''
                },
                {
                    "method": "POST",
                    "path": "/v1/batch/chat",
                    "description": "Tạo nhiều video đồng thời qua nhiều worker page song song.",
                    "curl_example": f'curl -X POST {base_url}/v1/batch/chat -H "Content-Type: application/json" -d \'{{"prompts": ["Prompt 1", "Prompt 2"], "concurrency": 2}}\''
                },
                {
                    "method": "POST",
                    "path": "/v1/batch/async",
                    "description": "Đưa danh sách prompt vào hàng đợi nền và nhận batch_id ngay lập tức.",
                    "curl_example": f'curl -X POST {base_url}/v1/batch/async -H "Content-Type: application/json" -d \'{{"prompts": ["Prompt 1", "Prompt 2"], "concurrency": 2}}\''
                },
                {
                    "method": "GET",
                    "path": "/v1/batch/status",
                    "description": "Kiểm tra tiến độ và kết quả của tác vụ batch nền theo batch_id.",
                    "curl_example": f"curl {base_url}/v1/batch/status?id=batch_xxx"
                },
                {
                    "method": "GET",
                    "path": "/media/{filename}",
                    "description": "Phát trực tiếp hoặc tải file Video MP4/Ảnh (hỗ trợ HTTP Range 206 bytes streaming).",
                    "curl_example": f"curl -I {base_url}/media/muse_696d3fd9_0.mp4"
                },
                {
                    "method": "GET",
                    "path": "/v1/status",
                    "description": "Kiểm tra trạng thái kết nối tới Muse.ai session.",
                    "curl_example": f"curl {base_url}/v1/status"
                }
            ]
        }
        return web.json_response(docs)

    async def handle_index(self, request: web.Request) -> web.Response:
        """Serves the Chat Web UI."""
        if os.path.exists(INDEX_HTML_PATH):
            with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
                return web.Response(text=f.read(), content_type="text/html")
        return web.Response(text="<h1>Muse.ai Bridge Chat UI</h1><p>index.html not found.</p>", content_type="text/html")

    async def handle_docs(self, request: web.Request) -> web.Response:
        """Serves the Interactive HTML Documentation & Tailscale Guide."""
        if os.path.exists(DOCS_HTML_PATH):
            with open(DOCS_HTML_PATH, "r", encoding="utf-8") as f:
                return web.Response(text=f.read(), content_type="text/html")
        return web.Response(text="<h1>Documentation not found</h1>", content_type="text/html")

    async def handle_eval(self, request: web.Request) -> web.Response:
        """Evaluates JavaScript on the active Muse.ai page."""
        if not self.page:
            return web.json_response({"ok": False, "error": "Browser not connected"}, status=503)
        try:
            body = await request.json()
            script = body.get("script", "")
            res = await self.page.evaluate(script)
            return web.json_response({"ok": True, "result": res})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    def create_app(self) -> web.Application:
        @web.middleware
        async def logger_middleware(request, handler):
            peer = request.headers.get("X-Forwarded-For") or request.remote or "unknown"
            t0 = time.time()
            try:
                resp = await handler(request)
                dt = (time.time() - t0) * 1000
                print(f"[HTTP] {request.method} {request.rel_url} from {peer} -> {resp.status} ({dt:.0f}ms)")
                return resp
            except Exception as exc:
                dt = (time.time() - t0) * 1000
                print(f"[HTTP] {request.method} {request.rel_url} from {peer} -> EXCEPTION: {exc} ({dt:.0f}ms)")
                raise

        def cors_headers(request) -> Dict[str, str]:
            origin = (request.headers.get("Origin") or "").rstrip("/")
            if origin not in CORS_ORIGINS:
                return {}
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-API-Key, Authorization",
                "Access-Control-Allow-Private-Network": "true",
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            }

        def deny(request, status: int, msg: str) -> web.Response:
            return web.json_response({"ok": False, "error": msg}, status=status, headers=cors_headers(request))

        def is_public(request) -> bool:
            """True nếu request KHÔNG phải kết nối Tailnet trực tiếp => coi là public, siết bảo mật.

            Funnel proxy tới http://127.0.0.1:8770 nên request thật xuất hiện là loopback và
            KHÔNG kèm header `Tailscale-Funnel-Request` (Tailscale không tự thêm header này).
            Client Tailnet nội bộ gọi thẳng 100.126.145.3:8770 -> remote là IP 100.x, không loopback,
            không có X-Forwarded-For. Fail-safe: chỉ cần 1 dấu hiệu "qua proxy" là siết.
            """
            if request.headers.get("Tailscale-Funnel-Request"):
                return True
            if request.headers.get("X-Forwarded-For"):  # Funnel/serve luôn thêm header này
                return True
            remote = (request.remote or "").strip().lower()
            # Loopback = đi qua Funnel proxy (hoặc script chạy ngay trên máy) -> bắt buộc key.
            return remote in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "")

        @web.middleware
        async def security_middleware(request, handler):
            if request.method == "OPTIONS":
                return web.Response(status=204, headers=cors_headers(request))

            if is_public(request):
                path = request.path
                is_media = path.startswith("/media/") and len(path) > len("/media/") and request.method == "GET"
                if not is_media and (request.method, path) not in FUNNEL_ALLOWED:
                    return deny(request, 403, "Endpoint not available via public access")
                if not API_KEY:
                    return deny(request, 403, "Public access disabled (MUSE_API_KEY not set)")
                auth = request.headers.get("Authorization", "")
                given = request.headers.get("X-API-Key") or (auth[7:] if auth.startswith("Bearer ") else "")
                if given != API_KEY:
                    return deny(request, 401, "Invalid or missing API key")
                if path == "/v1/batch/status" and not (request.query.get("id") or request.query.get("batch_id")):
                    return deny(request, 400, "Missing batch id")
                if path == "/v1/batch/async":
                    try:
                        data = await request.json()  # aiohttp cache body, handler đọc lại được
                    except Exception:
                        return deny(request, 400, "Invalid JSON")
                    files = [f for it in (data.get("items") or []) for f in (it.get("files") or [])]
                    raw = data.get("files") or []
                    files += [f for x in raw for f in (x if isinstance(x, list) else [x])]
                    if any(not (isinstance(f, str) and f.startswith("data:")) for f in files):
                        return deny(request, 400, "Only data: URLs are accepted in files via public access")

            resp = await handler(request)
            resp.headers.update(cors_headers(request))
            return resp

        app = web.Application(client_max_size=100 * 1024 * 1024, middlewares=[logger_middleware, security_middleware])
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/docs", self.handle_docs)
        app.router.add_get("/docs.html", self.handle_docs)
        app.router.add_get("/v1/status", self.handle_status)
        app.router.add_get("/v1/threads", self.handle_get_threads)
        app.router.add_post("/v1/threads/switch", self.handle_switch_thread)
        app.router.add_post("/v1/threads/new", self.handle_new_thread)
        app.router.add_get("/v1/history", self.handle_history)
        app.router.add_post("/v1/chat", self.handle_chat)
        app.router.add_post("/v1/chat/completions", self.handle_chat_completions)
        app.router.add_post("/v1/batch/chat", self.handle_batch_chat)
        app.router.add_post("/v1/batch/async", self.handle_batch_async)
        app.router.add_get("/v1/batch/status", self.handle_batch_status)
        app.router.add_post("/v1/upload", self.handle_upload)
        app.router.add_post("/v1/eval", self.handle_eval)
        app.router.add_get("/v1/docs", self.handle_api_docs)
        app.router.add_static("/media", MEDIA_DIR, show_index=True)
        return app

    async def run(self):
        await self.init_browser()
        app = self.create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=None, port=self.port)
        await site.start()
        print(f"\n=======================================================")
        print(f" [MuseBridge] REST API server running at:")
        print(f"   - http://localhost:{self.port}")
        print(f"   - http://127.0.0.1:{self.port}")
        print(f" Endpoints:")
        print(f"   GET  /               - Web Chat UI")
        print(f"   POST /v1/chat        - Send prompt and get response")
        print(f"   GET  /v1/history     - Get conversation messages")
        print(f"   GET  /v1/status      - Check connection status")
        print(f"   POST /v1/threads/new - Start new chat thread")
        print(f"=======================================================\n")
        while True:
            await asyncio.sleep(3600)

def main():
    parser = argparse.ArgumentParser(description="Muse.ai In-Browser RPC Bridge Server")
    parser.add_argument("--port", type=int, default=8765, help="HTTP server port (default: 8765)")
    parser.add_argument("--cdp", type=str, default=None, help="Chrome DevTools Protocol URL (e.g. http://localhost:9222)")
    parser.add_argument("--cookies", type=str, default=None, help="Path to cookies.json")
    parser.add_argument("--headful", action="store_true", help="Launch headful browser instead of headless")
    args = parser.parse_args()

    server = MuseBridgeServer(
        port=args.port,
        cdp_url=args.cdp,
        cookies_path=args.cookies,
        headless=not args.headful
    )
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[Bridge] Stopping server...")

if __name__ == "__main__":
    main()
