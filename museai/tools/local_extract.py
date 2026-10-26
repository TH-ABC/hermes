#!/usr/bin/env python3
"""
Lấy cookie Muse ngay trên máy local (IP dân dụng), rồi đẩy lên VPS.
Muse chặn đăng nhập từ IP datacenter (VPS), nên bước login phải chạy ở đây.

  python tools/local_extract.py --file accounts.txt [--sheet URL] [--only name1,name2] [--no-upload]

Dòng tài khoản: email|password|refreshToken|client_id (như dashboard). Cookie ghi vào
cookies_out/<name>.json (600) rồi scp vào VPS_COOKIES_DIR; pool tự nạp trong ~30s.
Cấu hình qua env: VPS_HOST (mặc định reclip-vps), VPS_COOKIES_DIR (mặc định /opt/museai/cookies).
"""
import argparse
import asyncio
import csv
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "cookies_out")
VPS_HOST = os.environ.get("VPS_HOST", "reclip-vps")
VPS_DIR = os.environ.get("VPS_COOKIES_DIR", "/opt/museai/cookies")


def lines_from_sheet(url: str) -> list:
    m = re.search(r"/spreadsheets/d/([\w-]+)", url)
    if not m:
        sys.exit("Link Google Sheet không hợp lệ")
    g = re.search(r"gid=(\d+)", url)
    exp = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={g.group(1) if g else 0}"
    text = urllib.request.urlopen(exp, timeout=30).read().decode("utf-8")
    out = []
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row if c.strip()]
        if cells and "@" in cells[0]:
            out.append("|".join(cells))
    return out


async def main():
    global auto_login

    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--sheet")
    ap.add_argument("--only", help="tên account, cách nhau bằng dấu phẩy")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--headed", action="store_true", help="hiện trình duyệt để debug")
    a = ap.parse_args()
    if a.headed:
        os.environ["MUSE_LOGIN_MANUAL"] = "1"  # must be set before auto_login is imported

    raw = []
    if a.file:
        raw += [l.strip() for l in open(a.file, encoding="utf-8") if l.strip() and not l.startswith("#")]
    if a.sheet:
        raw += lines_from_sheet(a.sheet)
    if not raw:
        sys.exit("Không có tài khoản nào (dùng --file hoặc --sheet)")
    only = set(a.only.split(",")) if a.only else None

    from bridge import auto_login as _al
    auto_login = _al
    from playwright.async_api import async_playwright
    os.makedirs(OUT, mode=0o700, exist_ok=True)
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=not a.headed,
                                       args=["--disable-blink-features=AutomationControlled"])
    ok_files, failed = [], []
    for i, line in enumerate(raw, 1):
        try:
            info = auto_login.parse_account_string(line)
        except Exception as e:
            print(f"[{i}/{len(raw)}] bỏ qua dòng lỗi: {e}")
            continue
        if only and info["name"] not in only:
            continue
        print(f"[{i}/{len(raw)}] {info['email']} ...")
        res = await auto_login.extract_account_cookies(
            browser, line, logger=lambda m, st=None: print("   ", m))
        if res.get("ok"):
            path = os.path.join(OUT, f"{res['name']}.json")
            with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
                json.dump(res["cookies"], f, ensure_ascii=False)
            ok_files.append(path)
            print(f"    ✅ {res['name']}")
        else:
            failed.append((info["email"], res.get("error")))
            print(f"    ❌ {res.get('error')}")
    await browser.close()
    await pw.stop()

    if ok_files and not a.no_upload:
        subprocess.run(["scp", "-q", *ok_files, f"{VPS_HOST}:{VPS_DIR}/"], check=True)
        subprocess.run(["ssh", VPS_HOST,
                        f"chown muse:muse {VPS_DIR}/*.json && chmod 600 {VPS_DIR}/*.json"], check=True)
        print(f"Đã đẩy {len(ok_files)} file lên {VPS_HOST}:{VPS_DIR} — pool tự nạp trong ~30s")
    print(f"Xong: {len(ok_files)} ok, {len(failed)} lỗi")
    for e, err in failed:
        print("  -", e, "|", str(err)[:100])


asyncio.run(main())
