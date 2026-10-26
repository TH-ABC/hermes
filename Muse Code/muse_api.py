import base64
import mimetypes
import os
import time
from typing import Dict, List, Optional

import requests

BASE_URL = os.environ.get("MUSE_BASE_URL", "http://127.0.0.1:8770").rstrip("/")
API_KEY = os.environ.get("MUSE_API_KEY", "")


def _headers() -> Dict[str, str]:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def file_to_data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def status() -> dict:
    return requests.get(f"{BASE_URL}/v1/status", headers=_headers(), timeout=15).json()


def generate(prompt: str, files: Optional[List[str]] = None, timeout_s: int = 240) -> dict:
    """Chat / tạo ảnh / tạo video đơn lẻ. `files` là đường dẫn ảnh trên máy."""
    body = {
        "prompt": prompt,
        "files": [file_to_data_url(p) for p in files or []],
        "timeout_s": timeout_s,
    }
    r = requests.post(f"{BASE_URL}/v1/chat", json=body, headers=_headers(), timeout=timeout_s + 30)
    return r.json()


def batch_async(items: List[dict], concurrency: int = 2) -> str:
    """Mỗi item: {"prompt": str, "files": [đường dẫn ảnh]}. Trả về batch_id."""
    payload = [
        {"prompt": it["prompt"], "files": [file_to_data_url(p) for p in it.get("files", [])]}
        for it in items
    ]
    r = requests.post(
        f"{BASE_URL}/v1/batch/async",
        json={"items": payload, "concurrency": concurrency},
        headers=_headers(),
        timeout=60,
    )
    return r.json()["batch_id"]


def wait_batch(batch_id: str, poll_s: int = 5) -> dict:
    while True:
        job = requests.get(
            f"{BASE_URL}/v1/batch/status", params={"id": batch_id}, headers=_headers(), timeout=15
        ).json()
        if job.get("status") == "completed":
            return job
        time.sleep(poll_s)


def download(media_path: str, out_dir: str = ".") -> str:
    """Tải file từ đường dẫn `/media/...` trong kết quả về máy."""
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(media_path))
    with requests.get(f"{BASE_URL}{media_path}", headers=_headers(), stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return out
