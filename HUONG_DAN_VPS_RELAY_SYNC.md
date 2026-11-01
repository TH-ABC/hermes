# 📡 HƯỚNG DẪN TRIỂN KHAI VPS RELAY SYNC (CLIENT 1 LUỒNG — ZERO HERMES)

Tài liệu này hướng dẫn cách kết nối bất kỳ máy chủ **VPS (Windows hoặc Linux)** vào hệ sinh thái Sever Hermes mà **KHÔNG CẦN CÀI ĐẶT HERMES TRÊN VPS**.

---

## 🌟 1. NGUYÊN LÝ HOẠT ĐỘNG (KIẾN TRÚC 1 LUỒNG SIÊU NHẸ)

```
[Sếp Hoàng nhắn Zalo / Hermes Web]
                │
                ▼
  [Sever Hermes / Central Receiver] (Cổng 8998 / 8999)
                │
     ┌──────────┴──────────┐
     ▼                     ▼
[Chế độ 1: Polling 60s]   [Chế độ 2: Direct Push <1s]
VPS tự động hỏi mỗi 1p    Hermes chủ động ping cổng 8995
     └──────────┬──────────┘
                │
                ▼
      [vps_relay_worker.py] (Trên VPS — 1 file duy nhất)
      • Thực thi lệnh PowerShell / CMD / Bash
      • Gửi kết quả nghiệm thu ngược về Sever Hermes
                │
                ▼
  [Hermes tự động đẩy báo cáo kết quả về Zalo cho Sếp]
```

### Ưu điểm vượt trội:
- **Zero Heavy Dependencies:** Không cần cài đặt Hermes, Node.js hay bất kỳ thư viện pip nào. Chỉ dùng Python 3 có sẵn.
- **Cực kỳ nhẹ:** Tiêu thụ ~10MB RAM, 0% CPU, 0 token khi chờ (Zero-Token Idle).
- **Hỗ trợ cả 2 chế độ:**
  1. *Chế độ Quét (Pull):* Mỗi 60 giây (1 phút) tự động kiểm tra xem Hermes có giao việc gì không.
  2. *Chế độ Bắn Tức Thì (Push):* Khi Hermes có lệnh gấp, Hermes có thể gửi ping trực tiếp qua cổng `8995` của VPS để thực thi ngay lập tức (<1 giây).

---

## 🚀 2. HƯỚNG DẪN CÀI ĐẶT TRÊN VPS (CHỈ 1 BƯỚC)

Sếp chỉ cần copy **1 file duy nhất** sau từ máy chủ sang VPS:
👉 `D:\hermes-main\scripts\vps_relay_worker.py`

Đặt file này vào bất kỳ thư mục nào trên VPS (ví dụ: `C:\vps_agent\vps_relay_worker.py` hoặc `/root/vps_relay_worker.py`).

---

## 💻 3. CÁCH KHỞI CHẠY TRÊN VPS

### 3.1. Chạy Thử Nghiệm Trực Tiếp (Test kết nối)
Mở PowerShell hoặc CMD trên VPS và chạy:
```powershell
python vps_relay_worker.py --server http://<IP_HOẶC_DOMAIN_HERMES>:8998 --vps-id vps-gameserver --interval 60
```
*(Nếu chạy cùng mạng LAN với máy chủ Hermes, IP có thể là `http://192.168.1.112:8998` hoặc IP VPN / Tailscale / Cloudflare Tunnel).*

Khi chạy thành công, console sẽ hiển thị:
```text
[VPS-Worker] 🚀 KHỞI ĐỘNG VPS RELAY WORKER (CLIENT SIÊU NHẸ 24/7)
[VPS-Worker] 📍 Định danh VPS: vps-gameserver
[VPS-Worker] 🌐 Máy chủ Hermes: http://192.168.1.112:8998
[VPS-Worker] ⏱️ Chu kỳ quét lệnh (Polling): Mỗi 60 giây (1 phút)
[VPS-Worker] 📡 Webhook Push Listener sẵn sàng trên cổng 8995
[VPS-Worker] 💓 Nhịp tim OK — Không có lệnh chờ.
```

---

### 3.2. Cấu Hình Chạy Ngầm 24/7 Trên VPS Windows

#### Cách A: Chạy nền bằng file VBS (Không hiện cửa sổ đen)
Tạo file `start_vps_agent.vbs` cạnh file `vps_relay_worker.py`:
```vbscript
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python vps_relay_worker.py --server http://<IP_HERMES>:8998 --vps-id vps-gameserver --interval 60", 0, False
```
Click đúp chuột vào file `.vbs` là tiến trình sẽ chạy ngầm vĩnh viễn 24/7!

#### Cách B: Đăng ký khởi động cùng Windows (Task Scheduler)
1. Mở `Task Scheduler` trên VPS Windows.
2. Tạo task mới: **At system startup** -> **Run whether user is logged on or not**.
3. Action: `Start a program` -> Program: `python.exe`, Arguments: `C:\vps_agent\vps_relay_worker.py --server http://<IP_HERMES>:8998 --vps-id vps-gameserver --interval 60`.

---

### 3.3. Cấu Hình Chạy Ngầm 24/7 Trên VPS Linux (systemd)
Tạo file dịch vụ `/etc/systemd/system/vps-relay.service`:
```ini
[Unit]
Description=VPS Relay Worker 24/7
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
ExecStart=/usr/bin/python3 /root/vps_relay_worker.py --server http://<IP_HERMES>:8998 --vps-id vps-linux --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
Kích hoạt dịch vụ:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vps-relay
sudo systemctl start vps-relay
```

---

## 🎯 4. CÁCH SẾP ĐIỀU KHIỂN VPS TRỰC TIẾP TỪ ZALO

Khi Sếp nhắn tin trong nhóm Zalo hoặc chat riêng với Zalo Bot:

### Cú pháp 1: Gửi lệnh thực thi thẳng sang VPS
```text
@ATG vps: Get-Process | Select-Object -First 5
```
hoặc
```text
@ATG-NT vps: dir D:\Ver24-NT\datas
```
hoặc
```text
@ATG vps: netstat -ano | findstr 11241
```

### Luồng xử lý tự động:
1. Bot phản hồi ngay lập tức trên Zalo:
   ```text
   🛠️ [@ATG - Kỹ Sư Trưởng]
   Dạ Sếp, Em là Trợ lý của sếp Hoàng!
   🚀 Đã chuyển lệnh sang VPS: Get-Process | Select-Object -First 5
   📡 Trạng thái: Đã đưa vào hàng đợi VPS (Task ID: vps_task_xxx)
   ⚡ Khi VPS thực thi xong, kết quả sẽ tự động báo về Zalo cho Sếp ngay ạ!
   ```
2. VPS quét lệnh (hoặc nhận Ping tức thì) -> Chạy lệnh trên hệ thống VPS.
3. VPS gửi kết quả về Hermes -> Bot Zalo tự động báo cáo kết quả chi tiết cho Sếp:
   ```text
   🛠️ [@ATG - Báo Cáo Nghiệm Thu VPS]
   Dạ Sếp, lệnh thực thi trên VPS đã có kết quả:
   📋 Lệnh: `Get-Process | Select-Object -First 5`
   ✅ Trạng thái: COMPLETED
   📄 Kết quả trả về:
   Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  SI ProcessName
   -------  ------    -----      -----     ------     --  -- -----------
       120       9     1524       4320       0.03   1024   0 smss
       ...
   ```

---

## 📊 5. CÁC API TRÊN CỔNG SEVER HERMES ĐỂ QUẢN TRỊ VPS

| Phương Thức | Cổng & Đường Dẫn | Mục Đích |
| :---: | :--- | :--- |
| **GET** | `http://127.0.0.1:8998/api/vps/status` | Kiểm tra danh sách các VPS đang online, thời gian nhịp tim cuối, số lệnh đã chạy |
| **GET** | `http://127.0.0.1:8998/api/vps/poll?vps_id=...` | VPS gọi định kỳ để lấy lệnh chờ |
| **POST** | `http://127.0.0.1:8998/api/vps/result` | VPS gửi kết quả thực thi về |
| **POST** | `http://127.0.0.1:8998/api/vps/dispatch` | Đẩy một lệnh mới vào hàng đợi VPS (kèm tính năng Ping trực tiếp nếu có `target_url`) |

---

## 📢 6. BẢN TIN THÔNG BÁO CẬP NHẬT CHO ĐỘI NGŨ / MÁY CHỦ VPS

> **Sếp hoặc Kỹ sư VPS chỉ cần copy đoạn thông báo bên dưới gửi cho bên quản trị VPS:**

```text
📢 [THÔNG BÁO CẬP NHẬT HỆ THỐNG VPS RELAY WORKER]
Gửi đội ngũ kỹ thuật VPS / Quản trị viên máy chủ:

Hệ thống đã triển khai giao thức kết nối siêu nhẹ VPS Relay 1 Luồng (Zero-Hermes).
Vui lòng thực hiện cập nhật theo các bước sau:

1️⃣ Kéo mã nguồn mới nhất:
   cd <thu_muc_hermes>
   git pull origin main

2️⃣ Hoặc copy riêng file worker duy nhất:
   scripts/vps_relay_worker.py

3️⃣ Khởi động worker trên VPS (Windows hoặc Linux):
   python scripts/vps_relay_worker.py --server http://<IP_HOAC_DOMAIN_HERMES>:8998 --vps-id vps-main --interval 60

⚡ Điểm mới trong bản cập nhật này:
- Tự động quét nhận lệnh từ Sever Hermes mỗi 60 giây.
- Hỗ trợ Hermes ping trực tiếp qua cổng 8995 để thực thi tức thì (<1 giây).
- Tự động báo cáo kết quả thực thi lệnh về Zalo cho Sếp Hoàng.
- Tiêu thụ cực nhẹ: ~10MB RAM, 0% CPU, 0 token khi đứng chờ.
```
