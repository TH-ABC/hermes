# 🚀 Hướng Dẫn Sử Dụng MuseAI Headless Engine (v3.0 - No Browser)

> **Hệ thống tạo Ảnh & Video đa luồng trực tiếp qua giao thức Noise_XX RPC của Meta AI VM.**  
> **Hoàn toàn không cần Chromium / Playwright / Selenium — Tiết kiệm 97% RAM (chỉ tốn ~47MB RAM).**

---

## 📌 Mục Lục
1. [Điểm Nổi Bật & So Sánh Hiệu Năng](#1-điểm-nổi-bật--so-sánh-hiệu-năng)
2. [Cơ Chế Kỹ Thuật (Reverse Engineering)](#2-cơ-chế-kỹ-thuật-reverse-engineering)
3. [Cài Đặt & Chuẩn Bị Cookie](#3-cài-đặt--chuẩn-bị-cookie)
4. [Sử Dụng Trực Tiếp Qua Dòng Lệnh (CLI)](#4-sử-dụng-trực-tiếp-qua-dòng-lệnh-cli)
   - [4.1. Sinh Ảnh & Video Đơn Lẻ (`run.py gen`)](#41-sinh-ảnh--video-đơn-lẻ-runpy-gen)
   - [4.2. Sinh Hàng Loạt Đa Luồng (`run.py batch`)](#42-sinh-hàng-loạt-đa-luồng-runpy-batch)
5. [Khởi Chạy REST API Server 24/7 (`run.py headless`)](#5-khởi-chạy-rest-api-server-247-runpy-headless)
6. [Đặc Tả Chi Tiết REST API](#6-đặc-tả-chi-tiết-rest-api)
   - [6.1. `GET /v1/status`](#61-get-v1status)
   - [6.2. `POST /v1/chat`](#62-post-v1chat)
   - [6.3. `POST /v1/batch/async` & `GET /v1/batch/status`](#63-post-v1batchasync--get-v1batchstatus)
   - [6.4. `POST /v1/chat/completions` (OpenAI format)](#64-post-v1chatcompletions-openai-format)
   - [6.5. `GET /media/{filename}`](#65-get-mediafilename)
7. [Tích Hợp Vào Google Colab / Code Python](#7-tích-hợp-vào-google-colab--code-python)
8. [Khắc Phục Sự Cố (Troubleshooting)](#8-khắc-phục-sự-cố-troubleshooting)

---

## 1. Điểm Nổi Bật & So Sánh Hiệu Năng

| Tiêu chí | 🌐 Phiên bản cũ (Playwright Browser) | ⚡ Phiên bản mới v3.0 (Headless Noise RPC) |
| :--- | :--- | :--- |
| **Trình duyệt** | Bắt buộc mở Chromium (nặng) | **100% Không cần trình duyệt (Pure Python)** |
| **RAM sử dụng** | 1.500 MB – 2.500 MB RAM | **Chỉ ~47.2 MB RAM** *(giảm 97%)* |
| **CPU lúc nghỉ (Idle)** | 10% – 25% (xử lý Canvas, DOM, CSS) | **0% (gần như đứng yên)** |
| **Độ ổn định đa luồng** | Dễ crash tab, timeout, kẹt selector | **Cực kỳ mượt mà, phân luồng socket riêng biệt** |
| **Tốc độ tạo ảnh** | 35 – 55 giây | **18 – 25 giây** |
| **Tốc độ tạo video** | 80 – 120 giây | **45 – 55 giây** |
| **Môi trường chạy** | Cần môi trường đồ họa GUI/Xvfb | **Chạy được mọi nơi (VPS rẻ tiền 1GB RAM, Mac, Docker, Colab)** |

---

## 2. Cơ Chế Kỹ Thuật (Reverse Engineering)

Giao thức v3.0 kết nối trực tiếp vào máy chủ Meta AI VM (`hatch.metaaivm.com`) thông qua các bước mã hóa bảo mật:

```
[Client]                                           [Meta AI Gateway / VM]
   |                                                        |
   |---- 1. POST /api/hatch/vm/wake ----------------------->| (Đánh thức VM tránh lỗi 502)
   |---- 2. POST /api/hatch/token ------------------------->| (Lấy token kết nối)
   |                                                        |
   |---- 3. WSS Connection: wss://hatch.metaaivm.com/v1/noise
   |<--> 4. Noise_XX Handshake (X25519 + AESGCM + HKDF) <-->| (Thiết lập phiên mã hóa E2E)
   |                                                        |
   |---- 5. RPC POST /fs/write (Upload ảnh tham chiếu) ---->| (Nếu có ảnh input)
   |---- 6. RPC POST /chat/stream (Gửi prompt tạo ảnh/video)| (Session cách ly riêng biệt)
   |---- 7. RPC GET /api/session/list (Poll hoàn thành) --->|
   |---- 8. RPC GET /fs/raw/{path} (Tải file nhị phân) ---->| (Tải trực tiếp về scratch/media/)
```

> [!IMPORTANT]
> **Quy tắc Đa Luồng:** Trong giao thức Noise_XX, số thứ tự `nonce` của mã hóa AES-GCM tăng tuần tự sau mỗi frame. Do đó, engine áp dụng mô hình **Dedicated Client per Worker**: mỗi luồng công việc sẽ mở một kết nối socket riêng biệt, vừa đảm bảo tốc độ tối đa, vừa triệt tiêu hoàn toàn lỗi lệch nonce (`InvalidTag`).

---

## 3. Cài Đặt & Chuẩn Bị Cookie

### 3.1. Thư viện yêu cầu
Hệ thống sử dụng các thư viện Python chuẩn:
```bash
pip install cryptography websocket-client aiohttp requests
```

*(Lưu ý trên Mac chip Apple Silicon M1/M2/M3: luôn chạy với tiền tố `arch -arm64 python3` nếu môi trường mặc định bị dính Rosetta x86).*

### 3.2. Cấu hình Cookie tài khoản
Hệ thống hỗ trợ 2 chế độ nạp cookie:
1. **Chế độ 1 tài khoản:** Đặt file `cookies.json` ngay tại thư mục gốc dự án.
2. **Chế độ Pool nhiều tài khoản:** Đặt các file cookie vào thư mục `cookies/`:
   ```
   cookies/
   ├── acc1.json
   ├── acc2.json
   └── acc3.json
   ```
*(Định dạng file cookie: JSON export chuẩn từ extension EditThisCookie / Cookie-Editor trên trình duyệt).*

---

## 4. Sử Dụng Trực Tiếp Qua Dòng Lệnh (CLI)

Bộ điều khiển hợp nhất nằm trong file [`run.py`](file:///Users/thainguyen/Working/AI_Business/3T_Colab/MuseAI/run.py).

### 4.1. Sinh Ảnh & Video Đơn Lẻ (`run.py gen`)

#### Tạo ảnh (Text-to-Image):
```bash
arch -arm64 python3 run.py gen --prompt "Vẽ một chú cá heo tung tăng dưới đại dương trong xanh"
```

#### Tạo video chuyển động (Text-to-Video):
```bash
arch -arm64 python3 run.py gen --prompt "Tạo video một tách cà phê bốc khói nghi ngút trong buổi sáng se lạnh"
```

#### Tạo video từ ảnh có sẵn (Image-to-Video):
```bash
arch -arm64 python3 run.py gen \
  --prompt "Làm chuyển động bức ảnh này thành một video ngắn sống động" \
  --file scratch/test_rose.webp
```

---

### 4.2. Sinh Hàng Loạt Đa Luồng (`run.py batch`)

Tạo file `prompts.json` chứa danh sách câu lệnh:
```json
[
  "Vẽ biểu tượng logo công nghệ AI màu xanh neon phát sáng 3D",
  "Vẽ tách trà sen thơm ngát trên phiến đá rêu phong mùa xuân",
  "Tạo video sóng biển hoàng hôn vỗ vào bờ cát vàng"
]
```

Chạy lệnh đa luồng (ví dụ chạy 3 luồng cùng lúc):
```bash
arch -arm64 python3 run.py batch \
  --input prompts.json \
  --output results.json \
  --concurrency 3
```

Kết quả sẽ được tự động lưu ra file `results.json` với đầy đủ thông tin:
```json
[
  {
    "ok": true,
    "prompt": "Vẽ biểu tượng logo công nghệ AI...",
    "media": ["/media/muse_b4d3cd6c_0.webp"],
    "local_paths": ["/path/to/scratch/media/muse_b4d3cd6c_0.webp"],
    "duration_ms": 27500,
    "status": "completed"
  }
]
```

---

## 5. Khởi Chạy REST API Server 24/7 (`run.py headless`)

Để phục vụ các hệ thống bên ngoài gọi vào (Google Colab, n8n, Webhook, Bot Telegram, TVC Playbook), khởi chạy server headless:

```bash
arch -arm64 python3 run.py headless --port 8770 --concurrency 4
```

Các tham số tùy chọn:
- `--port`: Cổng lắng nghe (mặc định: `8770`).
- `--host`: Địa chỉ bind (mặc định: `0.0.0.0` - có thể gọi qua mạng LAN hoặc IP Tailscale).
- `--concurrency`: Giới hạn tổng số tác vụ xử lý song song trong pool (mặc định: `4`).
- `--cookies`: Đường dẫn thư mục cookie (mặc định: `cookies/`).

> [!TIP]
> Server tiêu thụ chỉ **~47MB RAM**, có thể chạy 24/7 trên máy cá nhân hoặc VPS gói rẻ nhất mà không sợ tốn tài nguyên.

---

## 6. Đặc Tả Chi Tiết REST API

Server hoàn toàn tương thích ngược với chuẩn API trước đây, các client cũ không cần sửa đổi URL hay format dữ liệu.

### 6.1. `GET /v1/status`
Kiểm tra trạng thái máy chủ và các tài khoản sẵn sàng.
```bash
curl http://127.0.0.1:8770/v1/status
```
**Response:**
```json
{
  "ok": true,
  "mode": "headless_noise",
  "browser": false,
  "engine": "Noise_XX (Headless RPC)",
  "uptime_s": 120,
  "accounts_total": 2,
  "accounts": ["acc1", "acc2"],
  "concurrency": 4,
  "media_dir": "/path/to/scratch/media"
}
```

---

### 6.2. `POST /v1/chat`
Tương tác sinh ảnh, video hoặc chat đơn lẻ.

```bash
curl -X POST http://127.0.0.1:8770/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Vẽ quả táo đỏ bóng loáng đặt trên bàn gỗ",
    "timeout_s": 240
  }'
```

Nếu muốn đính kèm ảnh tham chiếu (Image-to-Video hoặc Vision):
```bash
curl -X POST http://127.0.0.1:8770/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Tạo chuyển động video từ ảnh này",
    "files": ["/media/muse_a06401aa_0.webp"]
  }'
```
*(Trường `files` hỗ trợ: đường dẫn file cục bộ, URL web `http(s)://`, đường dẫn `/media/...` hoặc chuỗi base64 `data:image/...;base64,...`).*

---

### 6.3. `POST /v1/batch/async` & `GET /v1/batch/status`
Xử lý hàng loạt ở chế độ chạy nền (Background Async Queue).

#### Bước 1: Gửi danh sách tác vụ vào hàng đợi
```bash
curl -X POST http://127.0.0.1:8770/v1/batch/async \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": [
      "Vẽ chú sóc nâu gặm hạt dẻ trên tuyết",
      "Vẽ chú mèo máy Doraemon ăn bánh rán"
    ],
    "concurrency": 2
  }'
```
**Response trả về ngay tức thì:**
```json
{
  "ok": true,
  "batch_id": "batch_3960dffa",
  "status": "running",
  "total": 2,
  "concurrency": 2,
  "status_url": "/v1/batch/status?id=batch_3960dffa"
}
```

#### Bước 2: Kiểm tra tiến độ và lấy kết quả
```bash
curl "http://127.0.0.1:8770/v1/batch/status?id=batch_3960dffa"
```
**Response khi hoàn thành:**
```json
{
  "ok": true,
  "batch_id": "batch_3960dffa",
  "status": "completed",
  "total": 2,
  "completed": 2,
  "failed": 0,
  "results": [
    {
      "ok": true,
      "prompt": "Vẽ chú sóc nâu...",
      "media": ["/media/muse_ace5d300_0.webp"],
      "duration_ms": 30308,
      "status": "completed"
    },
    {
      "ok": true,
      "prompt": "Vẽ chú mèo máy...",
      "media": ["/media/muse_5f04ccf6_0.webp"],
      "duration_ms": 52299,
      "status": "completed"
    }
  ]
}
```

---

### 6.4. `POST /v1/chat/completions` (OpenAI format)
Hỗ trợ tương thích trực tiếp với các framework dùng SDK OpenAI (LangChain, LlamaIndex, Dify, v.v.):
```bash
curl -X POST http://127.0.0.1:8770/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "muse-ai",
    "messages": [
      {"role": "user", "content": "Vẽ bức tranh sơn dầu phong cảnh vịnh Hạ Long"}
    ]
  }'
```

---

### 6.5. `GET /media/{filename}`
Tải hoặc xem trực tiếp hình ảnh (WebP/PNG) và video (MP4) vừa được tạo:
```bash
curl -O http://127.0.0.1:8770/media/muse_a06401aa_0.webp
```

---

## 7. Tích Hợp Vào Google Colab / Code Python

Đoạn code mẫu gọi trực tiếp tới máy chủ Headless từ Python hoặc Google Colab:

```python
import requests
import time

SERVER_URL = "http://127.0.0.1:8770"  # Hoặc IP Tailscale của bạn

def generate_image_or_video(prompt: str, file_path: str = None):
    payload = {"prompt": prompt}
    if file_path:
        payload["files"] = [file_path]
    
    print(f"[*] Đang gửi prompt: '{prompt}'...")
    res = requests.post(f"{SERVER_URL}/v1/chat", json=payload, timeout=300).json()
    
    if res.get("ok"):
        print("[+] Thành công!")
        for media_url in res.get("media", []):
            full_url = f"{SERVER_URL}{media_url}"
            print(f"    -> Tải file tại: {full_url}")
        return res
    else:
        print(f"[-] Thất bại: {res.get('error')}")
        return None

# Test thử:
generate_image_or_video("Vẽ một chậu hoa lan hồ điệp tím tuyệt đẹp")
```

---

## 8. Khắc Phục Sự Cố (Troubleshooting)

| Vấn đề | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| **`gatewayUrl not found`** | Cookie đã hết hạn hoặc chưa đăng nhập. | Đăng nhập lại trên web Muse.ai, export lại cookie vào `cookies.json`. |
| **Lỗi `incompatible architecture` trên macOS** | Môi trường Python đang chạy dưới x86_64 qua Rosetta. | Chạy lệnh bằng `arch -arm64 python3 ...`. |
| **Thời gian gen video lâu hơn ảnh** | Video cần render nhiều frame hơn. | Bình thường (Ảnh mất ~20s, Video mất ~50s). Đặt `timeout_s` từ 240 trở lên. |
| **Không kết nối được từ xa** | Firewall hoặc chưa bind `0.0.0.0`. | Thêm tham số `--host 0.0.0.0` khi chạy server và mở cổng firewall tương ứng. |

---

*Tài liệu được cập nhật tự động — Phiên bản MuseAI Headless Engine v3.0.*
