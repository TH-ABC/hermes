# 📖 Tài liệu REST API Muse.ai (v3.0 Headless Noise & v2.5 In-Browser)

> [!TIP]
> 🚀 **MỚI NHẤT (v3.0 - NO BROWSER):** Đã bổ sung công nghệ **Headless Noise RPC** kết nối trực tiếp backend Meta AI VM qua WebSocket mã hóa Noise_XX. **Không cần mở Chromium, tiết kiệm 97% RAM (chỉ tốn ~47MB)**, hỗ trợ sinh ảnh & video đa luồng song song siêu tốc.  
> 👉 **Xem ngay tài liệu chi tiết tại: [HUONG_DAN_HEADLESS_MULTITHREAD.md](file:///Users/thainguyen/Working/AI_Business/3T_Colab/MuseAI/HUONG_DAN_HEADLESS_MULTITHREAD.md)**

Hệ thống **Muse AI RPC Server** cung cấp chuẩn REST API hoàn chỉnh để điều khiển và khai thác toàn bộ sức mạnh tạo Video TVC, Ảnh và Chat của **Muse.ai (Meta Hatch)**. Hỗ trợ gọi trực tiếp từ xa qua mạng Tailscale, Google Colab, bot Telegram, kịch bản Python hoặc các hệ thống tự động hóa nội bộ (như Flowboard).

---

## 1. Thông tin Kết nối & Mạng

Hệ thống đang hoạt động và lắng nghe trên toàn bộ network interface (`0.0.0.0:8765`):

| Điểm truy cập | URL | Mục đích |
| :--- | :--- | :--- |
| **🖥️ On-Prem Windows 3090 (chính, 24/7)** | `http://100.126.145.3:8770` | Máy `desktop-bpavqpt`, code tại `D:\MuseAI`, task `MuseAI_Bridge` (auto-start khi logon + auto-restart), log `D:\MuseAI\logs\museai.log`. Deploy lại: copy code rồi chạy `deploy\windows\setup.ps1` |
| **Localhost Base URL** | `http://localhost:8765` hoặc `http://127.0.0.1:8765` | Gọi nội bộ trên máy host |
| **Tailscale IP Base URL** | `http://100.95.215.84:8765` | Cắm API từ Google Colab, VPS, laptop, mobile |
| **MagicDNS Hostname** | `http://macbook-pro-2:8765` | Tên miền nội bộ mạng Tailnet |
| **Interactive Docs HTML** | `http://100.95.215.84:8765/docs` | Giao diện tài liệu trực quan có Live API Tester |
| **Chat Web UI** | `http://100.95.215.84:8765/` | Giao diện Web Chat tương tự ChatGPT |

> [!NOTE]
> Giới hạn payload của server đã được nâng lên **100MB** (`client_max_size = 100 * 1024 * 1024`), đảm bảo nhận cùng lúc nhiều ảnh chụp độ phân giải cao dưới dạng Base64 mà không bị lỗi `400 Bad Request`.

---

## 2. Các Nâng Cấp Quan Trọng (v2.5 Changelog)

1. **Hỗ trợ Schema `items` trong Batch**:
   - Cho phép truyền mảng `items: [{ "prompt": "...", "files": ["data:image/jpeg;base64,..."] }]`.
   - Mỗi phần tử có thể mang theo ảnh nhà đất hoặc sản phẩm affiliate riêng biệt.
2. **Khắc phục lỗi ngắt sớm (Early Turn Exit Fix)**:
   - Nhận diện đúng khung chờ video render (`[data-testid*="attachment-presentation-video"]:not(:has(video))`).
   - Kiên nhẫn chờ render xong toàn bộ video MP4 thay vì chốt lượt sớm sau 3s dừng gõ chữ.
3. **Cơ chế Re-Extraction Fallback**:
   - Tự động quét lại DOM trước khi đóng worker page để giải phóng và lưu blob MP4 sang đĩa cứng cục bộ.
4. **Phát hiện lỗi quá tải (503 / Cluster Busy)**:
   - Tự động bắt đúng lỗi 503 khi cụm GPU Meta Hatch quá tải, trả về `"ok": false` và mô tả lỗi rõ ràng để client retry tự động.
5. **Cờ Capabilities trên `/v1/status`**:
   - Trả về `"batch_files": true` để các hệ thống ngoài (Flowboard, Marketing Bot `fdv_mkt`) nhận diện khả năng hỗ trợ file trong batch.

---

## 3. Danh mục Endpoints

| Method | Endpoint | Mô tả |
| :--- | :--- | :--- |
| `GET` | `/v1/status` | Kiểm tra trạng thái máy chủ & cờ `batch_files` |
| `POST` | `/v1/batch/chat` | Sinh video song song (Đồng bộ, chờ trả về kết quả) |
| `POST` | `/v1/batch/async` | Gửi batch vào hàng đợi nền (Bất đồng bộ, nhận `batch_id`) |
| `GET` | `/v1/batch/status?id=...` | Kiểm tra tiến độ và nhận kết quả batch nền |
| `POST` | `/v1/chat` | Tương tác chat & sinh video/ảnh đơn lẻ |
| `POST` | `/v1/chat/completions` | Tương thích chuẩn OpenAI SDK |
| `GET` | `/v1/history` | Lấy lịch sử hội thoại & link video MP4 |
| `GET` | `/v1/threads` | Danh sách các cuộc trò chuyện trên sidebar |
| `POST` | `/v1/threads/switch` | Chuyển đổi thread active |
| `POST` | `/v1/threads/new` | Mở một cuộc trò chuyện trống mới |
| `POST` | `/v1/upload` | Upload & staging file trước khi gửi prompt |
| `GET` | `/media/{filename}` | Stream / Tải video MP4 (HTTP 206 Partial Content) |

---

## 4. Đặc tả Chi tiết Từng Endpoint

### 4.1. `GET /v1/status` — Kiểm tra Trạng thái & Khả năng Máy chủ

* **Phương thức**: `GET`
* **URL**: `/v1/status`
* **Response Mẫu (JSON)**:
  ```json
  {
    "ok": true,
    "url": "https://muse.ai/",
    "title": "Chat — Muse",
    "bridge_ready": true,
    "headless": true,
    "batch_files": true
  }
  ```

---

### 4.2. `POST /v1/batch/chat` — Sinh Video Song Song (Đồng Bộ)

Phân bổ các câu lệnh sinh video tới nhiều tab Playwright worker độc lập, chạy đồng thời và giữ kết nối HTTP cho tới khi hoàn tất.

* **Headers**: `Content-Type: application/json`
* **Tham số Request Body**:
  * `items` *(object[], KHUYÊN DÙNG)*: Mảng item độc lập. Mỗi item gồm:
    * `prompt` *(string, bắt buộc)*: Nội dung câu lệnh sinh video.
    * `files` *(string[], tùy chọn)*: Danh sách ảnh đính kèm. Hỗ trợ Data-URL Base64 (`data:image/jpeg;base64,...`), link HTTP/HTTPS, hoặc raw Base64.
  * `prompts` *(string[], tùy chọn)*: Mảng danh sách prompt văn bản (dùng khi không có ảnh).
  * `files` *(string[][], tùy chọn)*: Mảng file tương ứng khi dùng `prompts`.
  * `concurrency` *(integer, tùy chọn, mặc định: 2)*: Số worker chạy đồng thời (khuyên dùng từ 1 đến 3, tối đa 5).
  * `timeout_ms` *(integer, tùy chọn, mặc định: 180000)*: Thời gian chờ tối đa cho mỗi video (ms).

* **Ví dụ cURL: Tạo 2 Video Bất Động Sản từ Ảnh Căn Nhà**:
  ```bash
  curl -X POST http://100.95.215.84:8765/v1/batch/chat \
    -H "Content-Type: application/json" \
    -d '{
      "items": [
        {
          "prompt": "Tạo video TVC 5s góc máy flycam lướt vào phòng khách căn biệt thự này, ánh sáng ấm cúng",
          "files": ["data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."]
        },
        {
          "prompt": "Tạo video TVC 5s lia máy từ ban công nhìn ra hồ bơi căn penthouse này lúc hoàng hôn",
          "files": ["data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."]
        }
      ],
      "concurrency": 2,
      "timeout_ms": 300000
    }'
  ```

* **Response Thành công (JSON)**:
  ```json
  {
    "ok": true,
    "total": 2,
    "completed": 2,
    "failed": 0,
    "results": [
      {
        "ok": true,
        "prompt": "Tạo video TVC 5s góc máy flycam lướt vào phòng khách...",
        "content": "Xong video rồi. Góc máy flycam lướt vào phòng khách...",
        "media": ["/media/muse_1a094e7c_0.mp4"],
        "files_attached": 1,
        "duration_ms": 78200,
        "status": "completed"
      },
      {
        "ok": true,
        "prompt": "Tạo video TVC 5s lia máy từ ban công...",
        "content": "Video ban công hoàng hôn đã tạo xong...",
        "media": ["/media/muse_85bf5ce6_0.mp4"],
        "files_attached": 1,
        "duration_ms": 81100,
        "status": "completed"
      }
    ]
  }
  ```

* **Response khi Gặp Lỗi Quá Tải (503 / Cluster Busy)**:
  ```json
  {
    "ok": true,
    "total": 1,
    "completed": 0,
    "failed": 1,
    "results": [
      {
        "ok": false,
        "error": "Muse video generation failed or service busy (503)",
        "prompt": "...",
        "content": "Hiện tại mình chưa tạo được video, hệ thống tạo video đang bận...",
        "media": [],
        "files_attached": 1,
        "status": "failed"
      }
    ]
  }
  ```

---

### 4.3. `POST /v1/batch/async` & `GET /v1/batch/status` — Hàng Đợi Nền (Bất Đồng Bộ)

Thích hợp cho kịch bản chạy hàng chục video mà không muốn treo kết nối HTTP.

#### Bước 1: Gửi Job vào hàng đợi
* **Endpoint**: `POST /v1/batch/async`
* **Request**:
  ```bash
  curl -X POST http://100.95.215.84:8765/v1/batch/async \
    -H "Content-Type: application/json" \
    -d '{
      "items": [
        {
          "prompt": "Tạo video TVC 10s máy hàn điện tử mini hoạt động thực tế",
          "files": ["data:image/jpeg;base64,..."]
        },
        {
          "prompt": "Tạo video TVC 10s máy mài góc cầm tay",
          "files": ["data:image/jpeg;base64,..."]
        }
      ],
      "concurrency": 2
    }'
  ```
* **Phản hồi tức thì trong 50ms**:
  ```json
  {
    "ok": true,
    "batch_id": "batch_9f81a7b2",
    "status": "running",
    "total": 2,
    "status_url": "/v1/batch/status?id=batch_9f81a7b2"
  }
  ```

#### Bước 2: Polling kiểm tra tiến độ
* **Endpoint**: `GET /v1/batch/status?id=batch_9f81a7b2`
* **Request**:
  ```bash
  curl "http://100.95.215.84:8765/v1/batch/status?id=batch_9f81a7b2"
  ```
* **Khi hoàn tất**:
  ```json
  {
    "ok": true,
    "batch_id": "batch_9f81a7b2",
    "status": "completed",
    "total": 2,
    "completed": 2,
    "failed": 0,
    "concurrency": 2,
    "created_at": 1790520340.12,
    "finished_at": 1790520416.92,
    "results": [
      {
        "ok": true,
        "prompt": "Tạo video TVC 10s máy hàn điện tử mini...",
        "media": ["/media/muse_xxx_0.mp4"],
        "files_attached": 1,
        "status": "completed"
      },
      {
        "ok": true,
        "prompt": "Tạo video TVC 10s máy mài góc...",
        "media": ["/media/muse_yyy_0.mp4"],
        "files_attached": 1,
        "status": "completed"
      }
    ]
  }
  ```

---

### 4.4. `POST /v1/chat` — Gửi Prompt & Sinh Video/Ảnh (Đơn Lẻ)

**Mặc định mỗi request mở một side chat mới** (`https://muse.ai/thread/new`), không đụng vào main chat.
- Muốn chat tiếp trong một thread có sẵn: truyền `"thread_id": "<id>"`.
- Muốn gửi thẳng vào thread đang mở (như Web Chat UI): truyền `"new_thread": false`.
- Áp dụng giống hệt cho `/v1/chat/completions`; batch (`/v1/batch/*`) thì mỗi prompt luôn chạy trong side chat riêng.

* **Cách 1: Gửi qua JSON**:
  ```bash
  curl -X POST http://100.95.215.84:8765/v1/chat \
    -H "Content-Type: application/json" \
    -d '{
      "prompt": "Tạo video TVC 5s ly cà phê sữa đá nhỏ giọt buổi sáng",
      "timeout_ms": 180000
    }'
  ```

* **Cách 2: Gửi kèm file ảnh local qua Multipart**:
  ```bash
  curl -X POST http://100.95.215.84:8765/v1/chat \
    -F "prompt=Tạo video TVC 5s flycam lướt vào căn phòng này" \
    -F "files=@/path/to/phong_khach.jpg"
  ```

* **Response**:
  ```json
  {
    "ok": true,
    "content": "Video TVC 5s đã xong. Cà phê phin nhỏ giọt...",
    "media": ["/media/muse_81374e00_0.mp4"],
    "duration_ms": 92736,
    "status": "completed"
  }
  ```

---

### 4.5. `POST /v1/chat/completions` — Chuẩn OpenAI Drop-in Replacement

Tương thích 100% với OpenAI SDK, LangChain, Cursor, Cline.

```bash
curl -X POST http://100.95.215.84:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "muse-ai",
    "messages": [
      {"role": "user", "content": "Tạo video 5s chiếc đồng hồ cơ sang trọng"}
    ]
  }'
```

---

### 4.6. `GET /media/{filename}.mp4` — Phát & Tải Video (HTTP Byte-Range)

* Hỗ trợ chuẩn **RFC 7233 (HTTP 206 Partial Content)** với header `Accept-Ranges: bytes`.
* Có thể nhúng trực tiếp vào thẻ `<video>` HTML5, bot Telegram, player web/mobile và tua tới bất kỳ giây nào mà không cần tải hết file.

---

## 5. Code Mẫu Tích Hợp Python Hoàn Chỉnh (Google Colab / Automation)

```python
import base64
import json
import time
import requests
from IPython.display import Video, display

# 1. Địa chỉ Tailscale của máy chủ Muse Bridge
MUSE_API_URL = "http://100.95.215.84:8765"

# 2. Hàm chuyển file ảnh sang chuẩn Data-URL Base64
def image_to_data_url(file_path):
    ext = file_path.split(".")[-1].lower()
    mime = "image/jpeg" if ext in ["jpg", "jpeg"] else ("image/png" if ext == "png" else "image/webp")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"

# 3. Chuẩn bị danh sách các căn nhà / sản phẩm cần tạo video
batch_items = [
    {
        "prompt": "Tạo video TVC 5s góc máy flycam lướt vào phòng khách căn biệt thự này, ánh sáng ấm cúng",
        "files": [image_to_data_url("phong_khach.jpg")]
    },
    {
        "prompt": "Tạo video TVC 5s lia máy chậm từ bàn ăn ra ban công căn hộ cao cấp này lúc hoàng hôn",
        "files": [image_to_data_url("ban_an.jpg")]
    }
]

print("🚀 Đang gửi batch tạo video song song tới Muse AI Bridge...")
start_time = time.time()

# 4. Gửi request batch với concurrency = 2 (tối đa 5)
resp = requests.post(
    f"{MUSE_API_URL}/v1/batch/chat",
    json={
        "items": batch_items,
        "concurrency": 2,
        "timeout_ms": 300000
    },
    headers={"Content-Type": "application/json"},
    timeout=360
)

data = resp.json()
elapsed = time.time() - start_time
print(f"✅ Hoàn tất sau {elapsed:.2f} giây! (Thành công: {data.get('completed')}/{data.get('total')})\n")

# 5. Tải file video MP4 về và phát trực tiếp
for idx, res in enumerate(data.get("results", []), 1):
    if res.get("ok"):
        media_list = res.get("media", [])
        print(f"🎬 [Video #{idx}] {res.get('prompt')}")
        print(f"   - Trạng thái: {res.get('status')}")
        print(f"   - File đính kèm: {res.get('files_attached')}")
        for m_url in media_list:
            full_video_url = f"{MUSE_API_URL}{m_url}"
            local_filename = f"output_clip_{idx}.mp4"
            with open(local_filename, "wb") as f_out:
                f_out.write(requests.get(full_video_url).content)
            print(f"   - Đã tải: {local_filename} ({full_video_url})")
            display(Video(local_filename, embed=True, width=360))
    else:
        print(f"❌ [Video #{idx} Thất bại] Lỗi: {res.get('error')}")
        print(f"   - Chi tiết: {res.get('content')}")
    print("-" * 50)
```

---

## 6. Khuyến nghị Vận hành & Best Practices

1. **Số luồng song song (`concurrency`)**:
   - Khuyên dùng: **2 đến 3 luồng** cho các batch tạo video kèm ảnh nặng.
   - Tránh đẩy quá 5 luồng cùng lúc để không làm nghẽn băng thông session Meta Hatch hoặc gây áp lực GPU client.
2. **Thời gian chờ (`timeout_ms`)**:
   - Text-to-Video: đặt tối thiểu **180,000ms** (3 phút).
   - Image-to-Video (Bất động sản/sản phẩm): đặt tối thiểu **300,000ms** (5 phút) để phòng trường hợp backend Meta Hatch xếp hàng xử lý.
3. **Xử lý Retry**:
   - Nếu nhận `"ok": false` với lỗi `503` hoặc `"service busy"`, cho hệ thống nghỉ 30-60 giây rồi tự động retry lại item đó.

---

## 🔁 Multi-account pool + Ubuntu VPS (v2.6)

**Nạp cookie hàng loạt** → `cookies/<account>.json` (chmod 600, không in giá trị, bỏ trùng, bỏ file thiếu `hatch_sess`):
```bash
python tools/import_cookies.py exports/*.json accounts.txt --out cookies --prefix acc
```
Nhận: JSON của Cookie-Editor/Playwright (1 account/file), dict `{"name":"value"}`, JSON nhiều account `{"acc01":[...],"acc02":{...}}`, hoặc `.txt` mỗi dòng 1 account (`name=value; ...` hoặc `label<TAB>name=value; ...`).

**Chạy pool** (API giống hệt bridge cũ, client không cần sửa):
```bash
python bridge/pool.py --cookies-dir cookies --port 8770 --per-account 2 [--host <tailscale-ip>]
```
- Một Chromium headless, mỗi account một context riêng. Batch chia cho account rảnh nhất; `concurrency` = tổng số luồng (bỏ trống = toàn bộ pool).
- Account trả 503/bận → nghỉ `--cooldown` giây, item chuyển sang account khác (tối đa `--max-attempts`).
- Thả file mới vào `cookies/` → tự nạp trong 30s; xoá file → account bị gỡ. Health check mỗi 10 phút đánh dấu `expired`.
- Chỉ định account: `"account":"acc03"` (JSON body) hoặc `?account=acc03` hoặc header `X-Muse-Account`. Mọi response có header `X-Muse-Account` để gọi tiếp đúng thread.
- Endpoint mới: `GET /v1/accounts`, `POST /v1/accounts/reload`, `POST /v1/accounts/check[?account=]`. Batch nhận thêm `"accounts":["acc01","acc02"]`.
- `MUSE_API_KEY` được set → `/v1/*` và `/media/*` cần header `X-API-Key` hoặc `Authorization: Bearer`.

**Deploy Ubuntu 22.04/24.04:** copy repo + `cookies/` lên VPS rồi `sudo bash deploy/linux/setup.sh` (user `muse`, venv, Chromium + deps, systemd `musebridge`, config `/etc/musebridge.env`, bind Tailscale IP, sinh API key). Log: `journalctl -u musebridge -f`.
