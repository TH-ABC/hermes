#!/usr/bin/env python3
"""
Nạp cookie tài khoản vào Pool (cổng 8770) và lưu trữ cục bộ
"""

import sys
import os
import json
import urllib.request
from pathlib import Path

COOKIES_DIR = Path("D:/hermes-main/hermes-main/museai/cookies")
STORAGE_POOL_FILE = Path("D:/hermes-main/storage/pool_accounts.json")


def import_cookie(name: str, raw_cookies, overwrite: bool = True):
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    target_file = COOKIES_DIR / f"{name}.json"

    parsed = []
    if isinstance(raw_cookies, str):
        raw_cookies = raw_cookies.strip()
        try:
            parsed = json.loads(raw_cookies)
        except Exception:
            # parse header "name=val; name2=val2"
            jar = []
            for part in raw_cookies.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    jar.append({
                        "name": k.strip(),
                        "value": v.strip(),
                        "domain": ".muse.ai",
                        "path": "/",
                        "secure": True
                    })
            parsed = jar
    elif isinstance(raw_cookies, list):
        parsed = raw_cookies

    # Normalize cookies
    normalized = []
    for c in parsed:
        if isinstance(c, dict) and "name" in c and "value" in c:
            normalized.append({
                "name": c["name"],
                "value": str(c["value"]),
                "domain": c.get("domain", ".muse.ai"),
                "path": c.get("path", "/"),
                "secure": bool(c.get("secure", True)),
                "httpOnly": bool(c.get("httpOnly", False))
            })

    if not normalized:
        return {"ok": False, "error": "Không tìm thấy cookie hợp lệ"}

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)

    # Reload port 8770
    try:
        req = urllib.request.Request("http://127.0.0.1:8770/v1/reload", headers={"User-Agent": "HermesBridge"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass
    except Exception:
        pass

    return {"ok": True, "cookies_count": len(normalized), "file": str(target_file)}


if __name__ == "__main__":
    if len(sys.argv) > 2:
        res = import_cookie(sys.argv[1], sys.argv[2])
        print(json.dumps(res, ensure_ascii=False))
    else:
        print("Usage: import_pool_cookie.py <name> <json_or_header>")
