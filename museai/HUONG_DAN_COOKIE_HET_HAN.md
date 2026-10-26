# Muse pool báo `no healthy account available` — hướng dẫn xử lý

**Triệu chứng (bên Flowboard):** `scene_generation_failed: muse_error: no healthy account available`

**Nguyên nhân:** cả 12 account trong pool hết hạn cookie. Log pool ghi từng account:
`Health <tên>: expired — gatewayUrl missing (session cookie expired or logged out)`.
Các file trong `/opt/museai/cookies/` được ghi từ 1–2/10 và chưa được làm mới. Pool chỉ
đánh dấu `expired` (health check mỗi 10 phút) và gửi Telegram "cần export cookie mới",
nó **không tự đăng nhập lại**. Không phải lỗi code Flowboard.

## Nơi code chạy

| | |
|---|---|
| Repo local | `/Users/trieuhoang/Documents/Projects/3TB/MuseAI` (GitHub `3tmerfast-ui/MuseAI`, nhánh `main`) |
| VPS | `163.61.110.171` (ssh host `reclip-vps`), hostname `linux174105` |
| Thư mục chạy | `/opt/museai` — **không phải git repo**, copy tay, `.deployed_rev` = `81511f1` (đã cũ) |
| Service | `musebridge.service` (user `muse`) → `bridge/pool.py --cookies-dir /opt/museai/cookies --port 8770` |
| Cấu hình / key | `/etc/musebridge.env` (`MUSE_API_KEY`) — không commit, không dán ra chat |
| Log | `journalctl -u musebridge -f` |

Flowboard (Docker, `/opt/flowboard`, cổng 8090) gọi pool qua `http://host.docker.internal:8770`
kèm `X-API-Key`.

## Cách 1 — Nạp cookie mới (nhanh nhất)

1. Đăng nhập từng account trên muse.ai bằng Chrome, export cookie (Cookie-Editor → JSON).
   Cookie phải có `hatch_sess`, thiếu thì bị bỏ.
2. Gom file vào `exports/` rồi tạo file account:
   ```bash
   cd /Users/trieuhoang/Documents/Projects/3TB/MuseAI
   python tools/import_cookies.py exports/*.json --out cookies --prefix acc --dry-run   # xem trước
   python tools/import_cookies.py exports/*.json --out cookies --prefix acc
   ```
3. Đưa lên VPS, **ghi đè đúng tên file cũ** (tên = tên account, vd `main.json`,
   `johnellecantrell7202.json`), owner `muse`, chmod 600. Không dùng `--delete`.
   Pool tự nạp trong ~30 giây.
4. Kiểm tra lại:
   ```bash
   curl -s -X POST -H "X-API-Key: $MUSE_API_KEY" http://127.0.0.1:8770/v1/accounts/check
   journalctl -u musebridge -n 30 --no-pager      # phải thấy "ready", hết "expired"
   ```
   Hoặc dùng dashboard pool (đăng nhập qua `/admin` của Flowboard, mục Muse pool)
   để dán cookie cho từng account, endpoint `POST /v1/accounts/bulk`.

## Cách 2 — Tự đăng nhập lại (`auto-extract`)

`bridge/auto_login.py` đăng nhập bằng email + mật khẩu, lấy OTP từ webmail qua refresh token.
Gọi qua dashboard hoặc `POST /v1/accounts/auto-extract {accounts_raw, overwrite:true}`.
Mỗi dòng `accounts_raw` theo dạng:
```
email|password|refreshToken|client_id
```
(các dạng rút gọn: `email|password|refreshToken`, `email|refreshToken`, `email|password`).
Cần chuỗi account của bạn. Không lưu vào git, không dán vào chat.

## ⚠️ Trước khi đẩy code repo lên VPS

- `/opt/museai` hiện **gần khớp** HEAD `f0eaa07` của repo, chỉ khác:
  - `bridge/index.html`: **VPS có `shrinkImage`** (thu nhỏ ảnh > ~1,1MB trước khi upload)
    mà repo **không có** → push repo lên sẽ làm mất. Kéo file từ VPS về repo và commit trước:
    ```bash
    scp reclip-vps:/opt/museai/bridge/index.html bridge/index.html
    git add bridge/index.html && git commit -m "chore: đồng bộ shrinkImage từ VPS"
    ```
  - `bridge/headless_server.py`: có trong repo, chưa có trên VPS (pool không dùng nó).
- Máy `reclip` còn chạy project khác. Chỉ ghi vào `/opt/museai`, **không** rsync `--delete`
  rộng; dry-run `rsync -n -i` trước.
- Có 2 thư mục backup ngày 7/10 trong `/root`: `muse_only_rescue_...`, `musebridge-backup-...`.
- Sau khi đồng bộ xong, ghi lại revision vào `/opt/museai/.deployed_rev`.

## Push repo MuseAI lên GitHub

Xem `GHI_CHU_PUSH.md` (token trong `.env`, dùng header tạm, không ghi token vào remote URL).

## Chống lặp lại

Cookie sống ~7 ngày rồi chết. Lâu dài nên chạy `auto-extract` theo lịch (cron/systemd timer
trên VPS, chuỗi account để trong file chỉ user `muse` đọc được, ngoài git), hoặc ít nhất
theo dõi Telegram alert "hết hạn cookie" để nạp lại sớm.
