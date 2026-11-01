# 🔱 HƯỚNG DẪN: TẮT CHẠY ẨN (HEADLESS CLI) VÀ KÍCH HOẠT CHẠY TRỰC TIẾP TRÊN MÀN HÌNH KHUNG CHAT ANTIGRAVITY IDE

> **Tài liệu chuẩn dành cho các kỹ sư quản trị hai cụm (ATG-Hermes và ATG-NT):**  
> Loại bỏ triệt để tình trạng chạy ngầm song song gây trùng lặp, xung đột báo cáo, và đưa toàn bộ quy trình thực thi hiển thị trực tiếp 100% trên màn hình khung chat IDE trước mắt Sếp Hoàng.

---

## ⚠️ 1. VẤN ĐỀ CỦA CƠ CHẾ "CHẠY ẨN" (HEADLESS CLI) CŨ

Trước đây, khi nhận chỉ thị từ Zalo, bot thường gọi Antigravity Engine chạy ngầm thông qua lệnh:
```python
# ❌ CÁCH CŨ (KHÔNG NÊN DÙNG):
proc = subprocess.run(["agy.exe", "-p", prompt, ...])
```

### Hậu quả tiêu cực:
1. **Chạy song song 2 luồng (Nhiễu loạn báo cáo):** Cả tiến trình ngầm `agy.exe` và màn hình khung chat cùng nhận lệnh, chạy độc lập và gửi 2 báo cáo kết quả khác nhau về Zalo, gây rối loạn thông tin.
2. **Người dùng tưởng bị treo:** `agy.exe` ngầm bên dưới mất 1-3 phút để quét, trong khi người dùng nhìn vào màn hình chat thì thấy trống không, không biết hệ thống có đang làm việc hay không.
3. **Dễ dính lỗi tham số CLI:** Dễ gặp lỗi như `--effort is not supported for the current model`.

---

## 🛑 2. BƯỚC 1: CẮT BỎ HOÀN TOÀN KHỐI CHẠY ẨN TRONG LISTENER

Mở file listener (`atg_nt_listener.py` hoặc `atg_zalo_listener.py`):

### ❌ XÓA BỎ HẲN hàm chạy ngầm sau:
```python
# GỠ BỎ TOÀN BỘ ĐOẠN NÀY KHỎI LISTENER:
def _execute_async():
    cmd = [str(AGY_BIN), "--dangerously-skip-permissions", "-p", full_prompt]
    proc = subprocess.run(cmd, ...)
    send_to_zalo(...)
```

### ✅ THAY BẰNG luồng ghi nhận tinh gọn duy nhất:
Listener chỉ làm đúng 2 nhiệm vụ:
1. Gửi tin nhắn xác nhận ngắn gọn về Zalo:
   ```text
   🛠️ [@ATG - Kỹ Sư Trưởng]
   Dạ Sếp, Em là Trợ lý của sếp Hoàng!
   Em đã nhận chỉ thị: "<nội dung lệnh>"
   ⚡ Đã chuyển trực tiếp vào khung chat Antigravity IDE để xử lý và báo cáo ngay tại đây ạ!
   ```
2. Đánh dấu `mark_completed(item_id)` vào queue để nhường quyền xử lý hoàn toàn cho khung chat màn hình.

---

## 🚀 3. BƯỚC 2: CƠ CHẾ ĐÁNH THỨC TRỰC TIẾP MÀN HÌNH KHUNG CHAT (REACTIVE WAKEUP)

Antigravity IDE có cơ chế **Reactive Wakeup**: Khi một tiến trình background task kết thúc hoặc xuất kết quả, **Khung Chat IDE sẽ ngay lập tức tự động thức dậy, mở turn mới và chạy các công cụ (tools) trực tiếp trước mắt người dùng**.

### Script Watcher Đánh Thức: `scripts/atg_ide_wakeup.py`
Tạo file `atg_ide_wakeup.py` với nội dung siêu nhẹ (~40 dòng Python thuần):

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, time, json
from pathlib import Path

LOCALAPPDATA = os.environ.get("LOCALAPPDATA")
HERMES_HOME = Path(LOCALAPPDATA) / "hermes" if LOCALAPPDATA else Path.home() / ".hermes"
QUEUE_FILE = HERMES_HOME / "atg_nt_queue.json"  # Hoặc atg_queue.json cho Cụm Hermes

def read_queue():
    if not QUEUE_FILE.exists(): return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception: return []

def main():
    seen_ids = set(item.get("id") for item in read_queue())
    print(f"📡 [IDE-Wakeup] Đang chờ chỉ thị Zalo để đánh thức màn hình Chat...", flush=True)

    while True:
        items = read_queue()
        for item in items:
            item_id = item.get("id")
            if item_id and item_id not in seen_ids:
                msg_text = item.get("text", "").strip()
                sender = item.get("sender", "Sếp Hoàng")
                print("\n" + "=" * 60, flush=True)
                print(f"🔔 [TÍN HIỆU ĐÁNH THỨC KHUNG CHAT ANTIGRAVITY IDE]", flush=True)
                print(f"👤 Người gửi: {sender} (Zalo)", flush=True)
                print(f"📋 Chỉ thị: {msg_text}", flush=True)
                print("=" * 60 + "\n", flush=True)
                # THOÁT TIẾN TRÌNH -> KÍCH HOẠT KHUNG CHAT IDE THỨC DẬY TỨC THÌ!
                sys.exit(0)
        time.sleep(1.0)

if __name__ == "__main__":
    main()
```

---

## 💻 4. BƯỚC 3: CÁCH KHỞI CHẠY TRÊN KHUNG CHAT ĐỂ TỰ ĐỘNG BẮT LỆNH

Trong khung chat Antigravity IDE, chỉ cần chạy lệnh sau làm background task:

```powershell
& "D:\hermes-main\hermes-main\.venv\Scripts\python.exe" -u "D:\hermes-main\scripts\atg_ide_wakeup.py"
```

### Vòng lặp tự động khép kín:
1. Khung chat chạy `atg_ide_wakeup.py` ở chế độ ngầm chờ tin.
2. Sếp nhắn tin Zalo: `@ATG-NT <lệnh>` (hoặc `@ATG-hermesh <lệnh>`).
3. `atg_ide_wakeup.py` phát hiện tin mới -> Thoát tiến trình `sys.exit(0)`.
4. **MÀN HÌNH KHUNG CHAT TỰ ĐỘNG BẬT SÁNG, THỨC DẬY VÀ CHẠY TOOL TRỰC TIẾP TRƯỚC MẮT SẾP!**
5. Khung chat xử lý xong -> Gửi kết quả về Zalo -> Tự động khởi chạy lại `atg_ide_wakeup.py` để đón tin nhắn tiếp theo.

---

## 🎯 5. BẢN TIN COPY GỬI CHO KHUNG CHAT BÊN KIA (CỤM ATG-HERMES)

```text
📢 [HƯỚNG DẪN CẤU HÌNH ĐỒNG BỘ MÀN HÌNH CHAT CHO CỤM BÊN KIA]
Chào Kỹ Sư Trưởng bên kia!
Để tránh lỗi chạy ẩn song song 2 luồng gây trùng lặp báo cáo, hãy áp dụng chuẩn mới nhất:

1️⃣ Trong listener Zalo: Xóa bỏ hoàn toàn lệnh gọi ngầm `agy.exe` (không dùng subprocess gọi agy nữa).
2️⃣ Listener chỉ gửi 1 tin xác nhận ngắn về Zalo và đánh dấu hoàn thành vào queue.
3️⃣ Kích hoạt script watcher `atg_ide_wakeup.py` trực tiếp trong khung chat IDE của bạn:
   & "D:\hermes-main\hermes-main\.venv\Scripts\python.exe" -u "D:\hermes-main\scripts\atg_ide_wakeup.py"
4️⃣ Khi Sếp nhắn tin trên Zalo, chính khung chat của bạn sẽ tự động thức dậy và chạy lệnh trực tiếp trên màn hình, báo cáo duy nhất 1 lần chuẩn xác về Zalo!
```
