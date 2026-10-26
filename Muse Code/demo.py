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
