"""Offload generated images/videos to Google Drive through an Apps Script Web App (same wire as Flowboard spec 28).

Flow: file appears in MEDIA_DIR -> upload to Drive -> verify size -> record file id -> after a grace period delete the
local copy. /media/<name> keeps working: if the local file is gone it is pulled back from Drive into the cache.
Files stay private in the owner's Drive. Disabled (no-op) unless DRIVE_WEBAPP_URL + DRIVE_WEBAPP_SECRET are set.
Never deletes a local file before the Drive copy is verified.
"""
import asyncio
import base64
import json
import mimetypes
import os
import time
from typing import Dict, Optional

import aiohttp
from aiohttp import web

URL = os.environ.get("DRIVE_WEBAPP_URL", "")
SECRET = os.environ.get("DRIVE_WEBAPP_SECRET", "")
FOLDER = os.environ.get("DRIVE_FOLDER_ID", "")
GRACE_S = int(os.environ.get("DRIVE_GRACE_SECONDS", "600"))
MAX_BYTES = 40 * 1024 * 1024  # Apps Script request limit is ~50MB incl. base64
SWEEP_S = 60


def enabled() -> bool:
    return bool(URL and SECRET)


class DriveOffload:
    def __init__(self, media_dir: str):
        self.dir = media_dir
        self.index_path = os.path.join(os.path.dirname(media_dir), "drive_index.json")
        self.index: Dict[str, dict] = {}
        self.errors: Dict[str, str] = {}
        try:
            self.index = json.load(open(self.index_path))
        except Exception:
            pass

    def _save(self):
        tmp = self.index_path + ".tmp"
        json.dump(self.index, open(tmp, "w"))
        os.replace(tmp, self.index_path)

    async def _post(self, payload: dict) -> dict:
        body = {**payload, "secret": SECRET}
        last = "unknown"
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as ses:
                    async with ses.post(URL, json=body, allow_redirects=True) as r:
                        data = await r.json(content_type=None)
                if isinstance(data, dict) and "error" not in data:
                    return data
                last = str((data or {}).get("error", "bad_response")) if isinstance(data, dict) else "bad_response"
                if last == "forbidden":
                    break  # wrong secret never heals by retrying
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
            await asyncio.sleep(3)
        raise RuntimeError(last)

    async def _upload(self, name: str, path: str):
        size = os.path.getsize(path)
        if size > MAX_BYTES:
            self.errors[name] = "file quá lớn (>40MB)"
            return
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        data = base64.b64encode(open(path, "rb").read()).decode()
        res = await self._post({"action": "upload", "name": name, "mime": mime, "data": data, "folderId": FOLDER})
        if int(res.get("size") or 0) != size or not res.get("fileId"):
            raise RuntimeError("size mismatch after upload")
        self.index[name] = {"id": res["fileId"], "size": size, "at": time.time()}
        self.errors.pop(name, None)
        self._save()
        print(f"[Drive] uploaded {name} ({size} bytes)")

    async def sweep_once(self):
        now = time.time()
        for name in os.listdir(self.dir):
            path = os.path.join(self.dir, name)
            if not os.path.isfile(path) or name.endswith(".part"):
                continue
            if now - os.path.getmtime(path) < 5:  # still being written
                continue
            meta = self.index.get(name)
            try:
                if not meta:
                    await self._upload(name, path)
                elif now - meta["at"] > GRACE_S and os.path.getsize(path) == meta["size"] and not meta.get("cached"):
                    os.remove(path)
                    print(f"[Drive] removed local copy of {name}")
            except Exception as e:  # noqa: BLE001
                self.errors[name] = str(e)
                print(f"[Drive] {name}: {e}")

    async def run(self):
        while True:
            try:
                await self.sweep_once()
            except Exception as e:  # noqa: BLE001
                print(f"[Drive] sweep error: {e}")
            await asyncio.sleep(SWEEP_S)

    async def handle_media(self, request: web.Request) -> web.StreamResponse:
        name = request.match_info["name"]
        if "/" in name or name.startswith("."):
            raise web.HTTPNotFound()
        path = os.path.join(self.dir, name)
        if not os.path.isfile(path):
            meta = self.index.get(name)
            if not (meta and enabled()):
                raise web.HTTPNotFound()
            try:
                res = {}
                for attempt in range(3):
                    res = await self._post({"action": "download", "fileId": meta["id"]})
                    if res.get("data"):
                        break
                    await asyncio.sleep(2 * (attempt + 1))
                if not res.get("data"):
                    raise RuntimeError(res.get("error") or "empty response")
                with open(path + ".part", "wb") as f:
                    f.write(base64.b64decode(res["data"]))
                os.replace(path + ".part", path)
                meta["at"] = time.time()  # restart the grace period for the cached copy
                self._save()
            except Exception as e:  # noqa: BLE001
                raise web.HTTPBadGateway(text=f"drive download failed: {e}")
        return web.FileResponse(path)  # FileResponse supports Range requests
