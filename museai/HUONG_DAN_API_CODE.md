# Hướng dẫn dùng Muse API để code ở thư mục riêng

Tài liệu này đủ để bạn tạo một thư mục mới (ví dụ `C:\muse-app`), copy code mẫu vào và gọi Muse qua REST API. Thư mục project MuseAI chỉ chạy server, bạn không cần sửa gì trong đó.

## 1. Cách hoạt động

```
Code của bạn (thư mục riêng)  --HTTP-->  Muse headless server  --Noise/WebSocket-->  Muse.ai
                                          (đọc cookie trong Pool)
```

- Server dùng cookie đã nạp trong `cookies/` của project MuseAI để đăng nhập Muse.
- Code của bạn chỉ cần gọi HTTP, không cần cookie và không cần cài thư viện của MuseAI.
- Chỉ cần thư viện `requests`: `pip install requests`.

## 2. Chạy server (làm một lần, để cửa sổ cmd này mở)

Mở cmd tại thư mục MuseAI:

```cmd
set MUSE_API_KEY=doi-thanh-key-cua-ban
python run.py headless --port 8770 --concurrency 4
```

- `--cookies <đường dẫn>` để trỏ tới thư mục cookie khác (mặc định `cookies\` trong MuseAI).
- `MUSE_API_KEY` không bắt buộc, nhưng nên đặt nếu server mở ra ngoài localhost. Đã đặt thì mọi lệnh gọi `/v1/*` và `/media/*` phải gửi key.
- Nếu server chạy sẵn ở máy khác (ví dụ máy Windows 24/7 trong README: `http://100.126.145.3:8770`), bạn không cần chạy lại, chỉ cần máy bạn cùng mạng Tailscale.

Kiểm tra server sống:

```cmd
curl http://127.0.0.1:8770/v1/status -H "X-API-Key: doi-thanh-key-cua-ban"
```

## 3. Xác thực

Gửi key bằng một trong hai cách:

- Header `X-API-Key: <key>`
- Header `Authorization: Bearer <key>`

Riêng `/media/...` còn nhận `?key=<key>` trên URL (tiện để mở video trong trình duyệt). Sai key trả về `401 {"ok": false, "error": "unauthorized"}`.

## 4. Danh sách endpoint (server headless)

| Method | Endpoint | Mô tả |
| :--- | :--- | :--- |
| GET | `/v1/status` | Trạng thái server, số tài khoản |
| GET | `/v1/accounts` | Danh sách tài khoản đang nạp |
| POST | `/v1/accounts/reload` | Nạp lại cookie sau khi thêm hoặc đổi file |
| POST | `/v1/chat` | Chat hoặc tạo ảnh/video đơn lẻ |
| POST | `/v1/chat/completions` | Định dạng tương thích OpenAI |
| POST | `/v1/batch/chat` | Nhiều prompt song song, chờ xong mới trả về |
| POST | `/v1/batch/async` | Nhiều prompt chạy nền, trả `batch_id` ngay |
| GET | `/v1/batch/status?id=...` | Xem tiến độ, kết quả của batch nền |
| GET | `/media/{tên_file}` | Tải ảnh/video đã tạo |

### 4.1 `POST /v1/chat`

Request:

```json
{
  "prompt": "Tạo video TVC 5s ly cà phê bốc khói",
  "files": ["data:image/jpeg;base64,..."],
  "account": "tên-tài-khoản (tùy chọn)",
  "timeout_s": 240
}
```

- `prompt` bắt buộc. Có thể thay bằng `messages: [{"role":"user","content":"..."}]`, server lấy tin cuối cùng.
- `files` tùy chọn: ảnh đính kèm dạng data URL, link http(s) hoặc base64 thô.
- `account` tùy chọn: chỉ định tài khoản. Bỏ trống thì Pool tự chọn.
- `timeout_s` mặc định 240 giây.

Response thành công (HTTP 200):

```json
{
  "ok": true,
  "prompt": "...",
  "content": "Xong video rồi...",
  "media": ["/media/muse_1a094e7c_0.mp4"],
  "status": "completed"
}
```

Khi lỗi, HTTP 500 và `"ok": false` kèm `"error"`. Ví dụ hệ thống bận (503): `"error": "Muse video generation failed or service busy (503)"`. Nên retry sau vài chục giây.

### 4.2 `POST /v1/chat/completions` (kiểu OpenAI)

```json
{"model": "muse-ai", "messages": [{"role": "user", "content": "Xin chào"}]}
```

Trả về `choices[0].message.content`, thêm trường `media`. Server chỉ lấy tin nhắn cuối, không nhớ hội thoại. Dùng với OpenAI SDK bằng cách đặt `base_url="http://127.0.0.1:8770/v1"` và `api_key=<key>`.

### 4.3 `POST /v1/batch/chat` (đồng bộ)

```json
{
  "items": [
    {"prompt": "Video 1...", "files": ["data:image/jpeg;base64,..."]},
    {"prompt": "Video 2...", "files": []}
  ],
  "concurrency": 2,
  "timeout_s": 300
}
```

Cũng nhận dạng cũ: `prompts: ["...", "..."]` (kèm `files` tùy chọn). Response:

```json
{"ok": true, "total": 2, "completed": 2, "failed": 0, "concurrency": 2, "results": [ {...}, {...} ]}
```

`results` đúng thứ tự `items`, mỗi phần tử có cấu trúc như response của `/v1/chat`. Kết nối HTTP bị giữ đến khi xong, nên với nhiều video hãy dùng bản async.

### 4.4 `POST /v1/batch/async` và `GET /v1/batch/status`

Gửi cùng body với `/v1/batch/chat`. Server trả ngay:

```json
{"ok": true, "batch_id": "batch_9f81a7b2", "status": "running", "total": 2, "status_url": "/v1/batch/status?id=batch_9f81a7b2"}
```

Hỏi tiến độ bằng `GET /v1/batch/status?id=batch_9f81a7b2`:

```json
{"ok": true, "batch_id": "...", "status": "running", "total": 2, "completed": 1, "failed": 0, "results": [ {...}, null ]}
```

- `status` là `running` hoặc `completed`. Khi `completed` thì `results` đầy đủ.
- Phần tử `null` trong `results` nghĩa là item đó chưa xong.
- Gọi không kèm `id` sẽ liệt kê 20 job gần nhất.

## 5. Client Python dùng được ngay

Tạo `C:\muse-app\muse_api.py` và dán nội dung sau:

```python
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
```

Ví dụ dùng, tạo `C:\muse-app\demo.py`:

```python
import muse_api as muse

# 1. Tạo một video từ ảnh
res = muse.generate("Tạo video TVC 5s ly cà phê bốc khói", files=["anh.jpg"])
if res["ok"]:
    print(res["content"])
    print("Đã tải:", muse.download(res["media"][0], out_dir="out"))
else:
    print("Lỗi:", res.get("error"))

# 2. Nhiều video chạy nền
bid = muse.batch_async([
    {"prompt": "Video 1...", "files": ["a.jpg"]},
    {"prompt": "Video 2...", "files": ["b.jpg"]},
], concurrency=2)
job = muse.wait_batch(bid)
for r in job["results"]:
    if r and r.get("ok"):
        muse.download(r["media"][0], out_dir="out")
```

Chạy trong cmd:

```cmd
cd C:\muse-app
set MUSE_BASE_URL=http://127.0.0.1:8770
set MUSE_API_KEY=doi-thanh-key-cua-ban
python demo.py
```

## 6. Nhờ Muse viết hoặc sửa code từ file

Muse là chat AI, không phải công cụ sửa code chuyên dụng. Có thể dùng `generate()` ở trên, chỉ cần gửi nội dung file vào prompt. Tạo `C:\muse-app\muse_code.py`:

```python
import re
import shutil
import sys

import muse_api

CODE_BLOCK = re.compile(r"```[\w+-]*\n(.*?)```", re.S)


def extract_code(text: str) -> str:
    blocks = CODE_BLOCK.findall(text)
    return max(blocks, key=len).rstrip() + "\n" if blocks else text.strip() + "\n"


def ask(prompt: str) -> str:
    res = muse_api.generate(prompt)
    if not res.get("ok"):
        sys.exit(f"Lỗi: {res.get('error') or res.get('content')}")
    return res["content"]


def edit_file(path: str, instruction: str, inplace: bool = False) -> str:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    prompt = (
        f"### File: {path}\n```\n{src}\n```\n\nYêu cầu: {instruction}\n\n"
        "Trả về TOÀN BỘ nội dung mới của file trong một khối code duy nhất, "
        "không rút gọn, không giải thích bên ngoài khối code."
    )
    new_code = extract_code(ask(prompt))
    out = path
    if inplace:
        shutil.copyfile(path, path + ".bak")
    else:
        out = path + ".muse"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_code)
    return out


if __name__ == "__main__":
    # python muse_code.py main.py "Thêm type hints" [--inplace]
    print("Đã lưu:", edit_file(sys.argv[1], sys.argv[2], "--inplace" in sys.argv))
```

Cách dùng:

```cmd
python muse_code.py main.py "Thêm try/except và type hints"
fc main.py main.py.muse
python muse_code.py main.py "Đổi sang async" --inplace
```

- Không có `--inplace`: bản sửa ghi ra `main.py.muse`, file gốc giữ nguyên.
- Có `--inplace`: ghi đè file gốc và tạo `main.py.bak` để quay lại.
- Viết code mới ra file txt: gọi `ask("Viết hàm ...")` rồi ghi `extract_code(kết_quả)` vào file bạn muốn.

## 7. Lỗi thường gặp

| Hiện tượng | Nguyên nhân và cách xử lý |
| :--- | :--- |
| `401 unauthorized` | Sai hoặc thiếu key. Kiểm tra `MUSE_API_KEY` ở cả server và client |
| `ConnectionError` | Server chưa chạy, sai `MUSE_BASE_URL`, hoặc máy chưa vào mạng Tailscale |
| `/v1/status` có `"ok": false` | Chưa có tài khoản nào nạp. Kiểm tra thư mục `cookies/`, rồi gọi `POST /v1/accounts/reload` |
| Chat được nhưng không ra video | Tài khoản bị hạn chế video (trạng thái `blocked`, chỉ tạo ảnh) hoặc video bận. Thử tài khoản khác bằng trường `account` |
| `503` / "service busy" | Cụm tạo video của Muse đang quá tải. Retry sau vài chục giây |
| Cookie hết hạn | Làm theo `HUONG_DAN_COOKIE_HET_HAN.md` rồi reload |
| Timeout | Tăng `timeout_s`. Video thường cần 60 đến 120 giây |

## 8. Lưu ý

- Server headless dùng `timeout_s` (giây). README cũ ghi `timeout_ms` là của server trình duyệt `bridge/server.py`, không dùng cho headless.
- `/v1/chat/completions` không giữ ngữ cảnh hội thoại, mỗi lần gọi là một yêu cầu độc lập.
- Ảnh gửi dạng base64 nên request có thể lớn. Server nhận tối đa 100MB mỗi request.
- Không commit `MUSE_API_KEY` hoặc file cookie vào git.
