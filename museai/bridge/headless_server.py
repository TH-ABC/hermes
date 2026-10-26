#!/usr/bin/env python3
"""
Muse.ai Headless Noise Protocol Bridge Server (No Browser / Headless RPC)
Runs completely headless without Chromium, Selenium, or Playwright.
Exposes standard REST API compatible with Google Colab, Webhooks, Telegram, and 3T Pipelines.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from typing import Dict, List, Optional, Any
from aiohttp import web

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from client.muse_noise_engine import MuseNoisePool, DEFAULT_MEDIA_DIR

STATE_DIR = os.path.join(ROOT_DIR, "scratch", "pool")
os.makedirs(STATE_DIR, exist_ok=True)


class HeadlessBridgeServer:
    def __init__(
        self,
        cookies_dir: str = os.path.join(ROOT_DIR, "cookies"),
        port: int = 8770,
        host: Optional[str] = None,
        concurrency: int = 4,
        media_dir: str = DEFAULT_MEDIA_DIR,
    ):
        self.cookies_dir = cookies_dir
        self.port = port
        self.host = host or "0.0.0.0"
        self.concurrency = concurrency
        self.media_dir = media_dir
        self.api_key = os.environ.get("MUSE_API_KEY") or None
        self.started_at = time.time()
        self.pool = MuseNoisePool(cookies_dir, media_dir=self.media_dir)
        self.batch_jobs: Dict[str, Dict] = {}
        self.jobs_file = os.path.join(STATE_DIR, "headless_batch_jobs.json")
        self._load_jobs()

    def _load_jobs(self):
        if os.path.exists(self.jobs_file):
            try:
                with open(self.jobs_file, "r", encoding="utf-8") as f:
                    self.batch_jobs = json.load(f)
            except Exception as e:
                print(f"[Headless] Warning: failed to load batch jobs: {e}")

    def _save_jobs(self):
        try:
            recent = dict(list(self.batch_jobs.items())[-200:])
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(recent, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Headless] Warning: failed to save batch jobs: {e}")

    def _parse_batch(self, data: Dict):
        prompts = data.get("prompts", [])
        raw_items = data.get("items", [])
        raw_files = data.get("files", [])
        if raw_items:
            kept = [it for it in raw_items if it.get("prompt")]
            return [{"prompt": it.get("prompt", ""), "files": it.get("files") or []} for it in kept]
        if prompts:
            if isinstance(raw_files, list) and raw_files and isinstance(raw_files[0], list):
                return [{"prompt": p, "files": f} for p, f in zip(prompts, raw_files)]
            if isinstance(raw_files, list) and raw_files:
                return [{"prompt": p, "files": raw_files} for p in prompts]
            return [{"prompt": p, "files": []} for p in prompts]
        return None

    # ---------------------------------------------------------------- HTTP Handlers

    async def handle_status(self, request: web.Request) -> web.Response:
        acc_names = list(self.pool.accounts.keys())
        return web.json_response({
            "ok": bool(acc_names),
            "mode": "headless_noise",
            "browser": False,
            "engine": "Noise_XX (Headless RPC)",
            "uptime_s": round(time.time() - self.started_at),
            "accounts_total": len(acc_names),
            "accounts": acc_names,
            "concurrency": self.concurrency,
            "media_dir": self.media_dir,
        })

    async def handle_accounts(self, request: web.Request) -> web.Response:
        acc_info = []
        for name, client in self.pool.accounts.items():
            acc_info.append({
                "name": name,
                "cookie_path": os.path.basename(client.cookie_path),
                "vm_id": client.vm_id or "idle",
            })
        return web.json_response({"ok": True, "accounts": acc_info})

    async def handle_reload(self, request: web.Request) -> web.Response:
        self.pool._load_accounts(self.cookies_dir)
        return web.json_response({
            "ok": True,
            "accounts": list(self.pool.accounts.keys())
        })

    async def handle_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON: {e}"}, status=400)

        prompt = data.get("prompt", "").strip()
        if not prompt and data.get("messages"):
            last = data["messages"][-1]
            prompt = last.get("content", "") if isinstance(last, dict) else str(last)

        if not prompt:
            return web.json_response({"ok": False, "error": "Prompt is required"}, status=400)

        files = data.get("files") or []
        account = data.get("account")
        timeout_s = int(data.get("timeout_s", 240))

        try:
            res = await asyncio.to_thread(
                self.pool.generate_one,
                prompt=prompt,
                files=files,
                account_name=account,
                timeout_s=timeout_s
            )
            return web.json_response(res, status=200 if res.get("ok") else 500)
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e), "prompt": prompt}, status=500)

    async def handle_chat_completions(self, request: web.Request) -> web.Response:
        """OpenAI-compatible /v1/chat/completions endpoint."""
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"error": {"message": f"Invalid JSON: {e}"}}, status=400)

        messages = data.get("messages", [])
        if not messages:
            return web.json_response({"error": {"message": "messages required"}}, status=400)

        prompt = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
        model = data.get("model", "muse-ai")

        try:
            res = await asyncio.to_thread(self.pool.generate_one, prompt=prompt, timeout_s=240)
            content = res.get("content", "")
            media = res.get("media", [])
            if media:
                content += "\n\n" + "\n".join(media)

            return web.json_response({
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop"
                }],
                "media": media,
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(content.split()),
                    "total_tokens": len(prompt.split()) + len(content.split())
                }
            })
        except Exception as e:
            return web.json_response({"error": {"message": str(e)}}, status=500)

    async def handle_batch_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON: {e}"}, status=400)

        items = self._parse_batch(data)
        if not items:
            return web.json_response({"ok": False, "error": "Either 'items' or 'prompts' array is required"}, status=400)

        concurrency = int(data.get("concurrency") or self.concurrency)
        timeout_s = int(data.get("timeout_s", 300))

        results = await asyncio.to_thread(
            self.pool.generate_batch,
            items=items,
            concurrency=concurrency,
            timeout_s=timeout_s
        )

        completed = sum(1 for r in results if r and r.get("ok"))
        return web.json_response({
            "ok": True,
            "total": len(items),
            "completed": completed,
            "failed": len(items) - completed,
            "concurrency": concurrency,
            "results": results
        })

    async def handle_batch_async(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON: {e}"}, status=400)

        items = self._parse_batch(data)
        if not items:
            return web.json_response({"ok": False, "error": "Either 'items' or 'prompts' array is required"}, status=400)

        concurrency = int(data.get("concurrency") or self.concurrency)
        timeout_s = int(data.get("timeout_s", 300))
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"

        job = {
            "batch_id": batch_id,
            "status": "running",
            "created_at": time.time(),
            "total": len(items),
            "completed": 0,
            "failed": 0,
            "concurrency": concurrency,
            "results": [None] * len(items)
        }
        self.batch_jobs[batch_id] = job
        self._save_jobs()

        def on_prog(idx, res):
            job["results"][idx] = res
            if res.get("ok"):
                job["completed"] += 1
            else:
                job["failed"] += 1
            self._save_jobs()

        async def _run_bg():
            try:
                await asyncio.to_thread(
                    self.pool.generate_batch,
                    items=items,
                    concurrency=concurrency,
                    timeout_s=timeout_s,
                    on_progress=on_prog
                )
            finally:
                job["status"] = "completed"
                job["finished_at"] = time.time()
                self._save_jobs()

        asyncio.create_task(_run_bg())
        return web.json_response({
            "ok": True,
            "batch_id": batch_id,
            "status": "running",
            "total": len(items),
            "concurrency": concurrency,
            "status_url": f"/v1/batch/status?id={batch_id}"
        })

    async def handle_batch_status(self, request: web.Request) -> web.Response:
        batch_id = request.query.get("id") or request.query.get("batch_id")
        if not batch_id:
            recent = list(self.batch_jobs.values())[-20:]
            return web.json_response({
                "ok": True,
                "count": len(self.batch_jobs),
                "recent_jobs": [
                    {k: j.get(k) for k in ("batch_id", "status", "total", "completed", "failed", "created_at", "finished_at")}
                    for j in recent
                ]
            })

        if batch_id not in self.batch_jobs:
            return web.json_response({
                "ok": False,
                "error": f"Batch job '{batch_id}' not found",
                "available_recent": list(self.batch_jobs.keys())[-5:]
            }, status=404)

        return web.json_response({"ok": True, **self.batch_jobs[batch_id]})

    async def handle_media(self, request: web.Request) -> web.Response:
        name = request.match_info.get("name", "")
        # Prevent path traversal
        clean_name = os.path.basename(name)
        target = os.path.join(self.media_dir, clean_name)
        if not os.path.exists(target):
            return web.Response(text="Media not found", status=404)
        return web.FileResponse(target)

    async def handle_index(self, request: web.Request) -> web.Response:
        acc_count = len(self.pool.accounts)
        html = f"""<!DOCTYPE html>
<html>
<head><title>Muse.ai Headless Noise Engine</title></head>
<body style="font-family: sans-serif; padding: 2rem; max-width: 800px; margin: auto; line-height: 1.6;">
    <h2>🚀 Muse.ai Headless RPC Server (Noise_XX)</h2>
    <p>Running 100% browser-free over encrypted WebSocket RPC.</p>
    <ul>
        <li><strong>Status:</strong> Active (Uptime: {round(time.time() - self.started_at)}s)</li>
        <li><strong>Accounts Loaded:</strong> {acc_count}</li>
        <li><strong>Concurrency:</strong> {self.concurrency}</li>
        <li><strong>Media Storage:</strong> {self.media_dir}</li>
    </ul>
    <h3>API Endpoints:</h3>
    <ul>
        <li><code>GET /v1/status</code> - Service status & loaded accounts</li>
        <li><code>POST /v1/chat</code> - Single generation (Image, Video, Text)</li>
        <li><code>POST /v1/chat/completions</code> - OpenAI-compatible chat API</li>
        <li><code>POST /v1/batch/chat</code> - Synchronous concurrent batch</li>
        <li><code>POST /v1/batch/async</code> - Background asynchronous batch</li>
        <li><code>GET /v1/batch/status?id=...</code> - Query batch job</li>
        <li><code>GET /media/&lt;filename&gt;</code> - Stream generated images/videos</li>
    </ul>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

    # ---------------------------------------------------------------- App Setup

    def create_app(self) -> web.Application:
        api_key = self.api_key

        @web.middleware
        async def auth_and_log(request, handler):
            if api_key and (request.path.startswith("/v1") or request.path.startswith("/media")):
                auth = request.headers.get("Authorization", "")
                given = (request.headers.get("X-API-Key") or (auth[7:] if auth.startswith("Bearer ") else "")
                         or (request.query.get("key", "") if request.path.startswith("/media") else ""))
                if given != api_key:
                    return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

            t0 = time.time()
            resp = await handler(request)
            dur = (time.time() - t0) * 1000
            print(f"[Headless] {request.method} {request.path} -> {resp.status} ({dur:.0f}ms)")
            return resp

        app = web.Application(client_max_size=100 * 1024 * 1024, middlewares=[auth_and_log])
        r = app.router
        r.add_get("/", self.handle_index)
        r.add_get("/v1/status", self.handle_status)
        r.add_get("/v1/accounts", self.handle_accounts)
        r.add_post("/v1/accounts/reload", self.handle_reload)
        r.add_post("/v1/chat", self.handle_chat)
        r.add_post("/v1/chat/completions", self.handle_chat_completions)
        r.add_post("/v1/batch/chat", self.handle_batch_chat)
        r.add_post("/v1/batch/async", self.handle_batch_async)
        r.add_get("/v1/batch/status", self.handle_batch_status)
        r.add_get("/media/{name}", self.handle_media)
        return app

    async def run(self):
        runner = web.AppRunner(self.create_app())
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port)
        await site.start()
        print(f"\n[+] Headless Noise Bridge running on http://{self.host}:{self.port}")
        print(f"[+] Loaded {len(self.pool.accounts)} account(s). Ready for concurrent requests.")
        while True:
            await asyncio.sleep(3600)


def main():
    parser = argparse.ArgumentParser(description="Muse.ai Headless RPC Server (No Browser)")
    parser.add_argument("--cookies", default=os.path.join(ROOT_DIR, "cookies"), help="Path to cookies dir or file")
    parser.add_argument("--port", type=int, default=8770, help="Port to listen on (default 8770)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default 0.0.0.0)")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent tasks")
    args = parser.parse_args()

    server = HeadlessBridgeServer(
        cookies_dir=args.cookies,
        port=args.port,
        host=args.host,
        concurrency=args.concurrency
    )
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\n[+] Headless Server stopped.")


if __name__ == "__main__":
    main()
