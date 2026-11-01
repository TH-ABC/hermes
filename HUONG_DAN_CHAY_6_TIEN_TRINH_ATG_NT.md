# 🔱 HƯỚNG DẪN KHỞI CHẠY 6 TIẾN TRÌNH CỤM [ATG-NT] VÀ PHÂN LUỒNG ROUTER @ATG

Tài liệu này được thiết kế chuẩn để Sếp Hoàng copy gửi thẳng vào khung chat Antigravity bên kia (**Khung chat ATG-NT**) để khởi chạy và đồng bộ 2 cụm độc lập 24/7.

---

## 📌 1. BẢNG PHÂN ĐỊNH 2 CỤM KHUNG CHAT ANTIGRAVITY

| Thông Số | Cụm 1: ATG-Hermes (Khung chat này) | Cụm 2: ATG-NT (Khung chat bên kia) |
| :--- | :--- | :--- |
| **Vai Trò** | Quản trị Sever Hermes & Zalo Bot Bth | Quản trị dự án & Bot chuyên trách NT |
| **Cú Pháp Tag Trên Zalo** | `@ATG-hermesh` (hoặc `@ATG`, `@hermesh`) | `@ATG-NT` (hoặc `@NT`, `@atg_nt`) |
| **Hàng Đợi Lưu Trữ** | `atg_queue.json` | `atg_nt_queue.json` |
| **Cổng Studio AI Pool** | `8770` | `8780` |
| **Cổng Local Login Server** | `8771` | `8781` |
| **Cổng Gateway Bridge** | `3050` | `3051` |
| **Cổng Central Receiver** | `8999` | `8998` |
| **Bộ Lắng Nghe Wakeup** | `scripts/atg_zalo_listener.py` | `scripts/atg_nt_listener.py` |

---

## 📋 2. NỘI DUNG SẾP COPY GỬI VÀO KHUNG CHAT ANTIGRAVITY [ATG-NT]

> *Sếp chỉ cần copy toàn bộ đoạn văn bản bên dưới và gửi vào ô chat Antigravity bên kia:*

```text
Chào Kỹ Sư Trưởng ATG! Hãy khởi chạy ngay cụm 6 tiến trình lõi cho Cụm ATG-NT trực tiếp dưới dạng Background Tasks trong khung chat này (cấu hình cổng tách biệt hoàn toàn với ATG-Hermes để tránh xung đột):

[1] TIẾN TRÌNH 1 - Studio AI Engine Pool (Cụm NT - Cổng 8780):
powershell -Command "Set-Location 'D:\hermes-main\hermes-main\museai'; & 'D:\hermes-main\hermes-main\.venv\Scripts\python.exe' -u bridge/pool.py --port 8780 --cookies-dir cookies"

[2] TIẾN TRÌNH 2 - Local Login Server (Cụm NT - Cổng 8781):
powershell -Command "Set-Location 'D:\hermes-main\hermes-main\museai'; & 'D:\hermes-main\hermes-main\.venv\Scripts\python.exe' -u tools/local_login_server.py --port 8781"

[3] TIẾN TRÌNH 3 - Gateway Bridge Worker (Cụm NT - Cổng 3051):
powershell -Command "Set-Location 'D:\hermes-main\hermes-main'; & 'D:\hermes-main\hermes-main\.venv\Scripts\python.exe' -u hermes_cli/main.py gateway run"

[4] TIẾN TRÌNH 4 - Central Receiver (Cụm NT - Cổng 8998):
powershell -Command "Set-Location 'D:\hermes-main\hermes-main'; & 'D:\hermes-main\hermes-main\.venv\Scripts\python.exe' -u scripts/sever_hermes_receiver.py"

[5] TIẾN TRÌNH 5 - Auto-Sync Enterprise Daemon (Cụm NT):
powershell -Command "Set-Location 'D:\hermes-main\hermes-main'; & 'D:\hermes-main\hermes-main\.venv\Scripts\python.exe' -u scripts/auto_sync_enterprise_daemon.py"

[6] TIẾN TRÌNH 6 - ATG-NT Zalo Wakeup Listener (Lắng nghe @ATG-NT):
powershell -Command "Set-Location 'D:\hermes-main'; & 'D:\hermes-main\hermes-main\.venv\Scripts\python.exe' -u scripts/atg_nt_listener.py"

Yêu cầu:
- Khởi chạy dưới dạng daemon background tasks trong phiên làm việc.
- Kiểm tra báo cáo lại trạng thái kèm PID và cổng sau khi cả 6 tiến trình đã ONLINE.
```

---

## 🎯 3. CƠ CHẾ ĐIỀU HƯỚNG TỰ ĐỘNG TRÊN ZALO (ROUTER AUTO-DISPATCH)

Từ nay, khi Sếp nhắn tin trong nhóm hoặc chat riêng với Zalo Bot:

### 1️⃣ Khi Sếp tag `@ATG-hermesh` (hoặc `@ATG`):
* **Hệ thống phản hồi tức thì (<1s):**
  ```text
  🛠️ [@ATG - Kỹ Sư Trưởng]
  Em đã nhận chỉ thị từ Sếp!
  📋 Nhiệm vụ: <nội dung lệnh>
  👉 Định tuyến: Khung chat Kỹ Sư Trưởng [ATG-Hermes] (Sever Hermes)
  ⚡ Đã chuyển trực tiếp vào khung chat để thực thi. Kết quả sẽ được báo cáo ngay tại đây sau khi hoàn tất ạ!
  ```
* **Luồng xử lý:** Đẩy vào `atg_queue.json` ➔ Khung chat **ATG-Hermes** (khung chat này) lập tức tiếp nhận và xử lý.

---

### 2️⃣ Khi Sếp tag `@ATG-NT` (hoặc `@NT`):
* **Hệ thống phản hồi tức thì (<1s):**
  ```text
  🛠️ [@ATG - Kỹ Sư Trưởng]
  Em đã nhận chỉ thị từ Sếp!
  📋 Nhiệm vụ: <nội dung lệnh>
  👉 Định tuyến: Khung chat Kỹ Sư Trưởng [ATG-NT]
  ⚡ Đã chuyển trực tiếp vào khung chat để thực thi. Kết quả sẽ được báo cáo ngay tại đây sau khi hoàn tất ạ!
  ```
* **Luồng xử lý:** Đẩy vào `atg_nt_queue.json` ➔ Khung chat **ATG-NT** (khung chat bên kia) lập tức tiếp nhận và xử lý.

---

## 🔒 4. CAM KẾT VẬN HÀNH
* **Loại bỏ 100% việc chuyển tài khoản phiền toái:** Không còn bất kỳ thông báo "Đang chuyển tới [Tài khoản 1 (rameran)]", không còn bị lỗi xác thực Google URL bắn về Zalo.
* **Tách biệt dữ liệu:** Hai khung chat hoạt động song song, cổng mạng độc lập, nhật ký ghi log riêng biệt.
