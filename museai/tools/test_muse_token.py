#!/usr/bin/env python3
"""Test: can Muse be reached with cookies only (no browser)?
Steps: GET muse.ai home -> parse gatewayUrl -> POST /api/hatch/token.
Prints only status codes, key names and value lengths; never prints cookie/token values.
Usage: python3 tools/test_muse_token.py [cookies.json]"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "cookies.json")
cookies = json.load(open(path))
cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if "muse.ai" in c.get("domain", "muse.ai"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


BASE_HEADERS = {"Cookie": cookie_header, "User-Agent": UA, "Content-Type": "application/json",
                "Origin": "https://muse.ai", "Referer": "https://muse.ai/"}
# Headers Chrome adds to a same-origin fetch(); the server may check them (CSRF guard).
BROWSER_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "sec-ch-ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}


def call(method, url, body=None, extra=None, drop=()):
    headers = {**BASE_HEADERS, **(extra or {})}
    for k in drop:
        headers.pop(k, None)
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers=headers)
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


print(f"cookies: {len(cookies)} ({', '.join(sorted(c['name'] for c in cookies))})")

status, html = call("GET", "https://muse.ai/")
html = html.decode("utf-8", "ignore")
m = re.search(r'gatewayUrl\\?":\\?"(wss://[^"\\]+)', html)
print(f"[1] GET muse.ai/ -> {status}; gatewayUrl {'FOUND' if m else 'NOT FOUND (cookie expired / not logged in?)'}")
if not m:
    sys.exit(1)
gateway = m.group(1)

VARIANTS = [
    ("A basic", {"vmAddress": gateway}, {}, ()),
    ("B +browser headers", {"vmAddress": gateway}, BROWSER_HEADERS, ()),
    ("C +browser, no Referer", {"vmAddress": gateway}, BROWSER_HEADERS, ("Referer",)),
    ("D +browser, empty body", {}, BROWSER_HEADERS, ()),
]
ok = False
for label, payload, extra, drop in VARIANTS:
    status, body = call("POST", "https://muse.ai/api/hatch/token", payload, extra, drop)
    try:
        j = json.loads(body)
    except ValueError:
        j = {}
    if status == 200:
        shape = {k: (len(v) if isinstance(v, str) else type(v).__name__) for k, v in j.items()}
        print(f"[2{label[0]}] {label}: 200 OK; keys/lengths: {shape}")
        ok = True
        break
    print(f"[2{label[0]}] {label}: {status}; error: {j.get('error', body[:80])}")
print("RESULT: cookie-only auth WORKS (token obtainable without a browser)." if ok
      else "RESULT: cookie-only token request FAILED.")
