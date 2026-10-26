"""
TinProxy Rotating IP & Proxy Manager for Muse.ai / Flowboard.
Ported from DolaAI (app/services/proxy_service.py).
Provides residential rotating IP proxies to avoid single-IP rate-limiting and checkpoints.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urlparse

TINPROXY_API_KEY = os.environ.get("TINPROXY_API_KEY", "a3X3J5XzC2z41nLNNgmR8uqNOBtlTyrF").strip()
TINPROXY_BASE_URL = os.environ.get("TINPROXY_BASE_URL", "https://api.tinproxy.com").rstrip("/")
MUSE_PROXY = os.environ.get("MUSE_PROXY", "").strip()


def normalize_proxy_url(proxy_str: str, default_protocol: str = "http") -> str:
    """Normalizes:
    - host:port:user:pass -> http://user:pass@host:port
    - host:port -> http://host:port
    - http://... or socks5://... -> untouched
    """
    raw = (proxy_str or "").strip()
    if not raw:
        return ""
    if raw.startswith(("http://", "https://", "socks5://", "socks4://")):
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"{default_protocol}://{user}:{password}@{host}:{port}"
    elif len(parts) == 2:
        host, port = parts
        return f"{default_protocol}://{host}:{port}"
    return f"{default_protocol}://{raw}"


def parse_playwright_proxy(proxy_str: str) -> Optional[Dict[str, str]]:
    """Extracts server, username, password dictionary for Playwright launch(proxy=...)."""
    norm = normalize_proxy_url(proxy_str)
    if not norm:
        return None
    p = urlparse(norm)
    if not p.hostname:
        return None
    server = f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")
    res = {"server": server}
    if p.username:
        res["username"] = p.username
    if p.password:
        res["password"] = p.password
    return res


def get_rotating_proxy(
    rotate: bool = True,
    api_key: Optional[str] = None,
    force_wait: bool = False,
    max_wait: int = 30,
) -> Optional[Dict[str, Any]]:
    """Fetches active TinProxy residential rotating proxy.
    If rotate=True: requests new IP if cooldown expired.
    Falls back to current active proxy if in cooldown.
    """
    if MUSE_PROXY:
        pw = parse_playwright_proxy(MUSE_PROXY)
        norm = normalize_proxy_url(MUSE_PROXY)
        return {
            "proxy_url": norm,
            "playwright": pw,
            "server": pw.get("server") if pw else norm,
            "ip": "custom",
            "location": "custom",
            "source": "static",
            "rotated": False,
        }

    key = (api_key or TINPROXY_API_KEY).strip()
    if not key:
        return None

    headers = {"User-Agent": "Mozilla/5.0"}
    data = None
    rotated = False

    if rotate:
        try:
            req = urllib.request.Request(f"{TINPROXY_BASE_URL}/proxy/get-new-proxy?api_key={key}", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_json = json.loads(resp.read().decode())
                if res_json.get("code") == 1:
                    data = res_json.get("data")
                    rotated = True
                elif res_json.get("code") == 0 and force_wait:
                    rem = res_json.get("data", {}).get("next_request", 0)
                    if 0 < rem <= max_wait:
                        time.sleep(rem + 1)
                        req2 = urllib.request.Request(f"{TINPROXY_BASE_URL}/proxy/get-new-proxy?api_key={key}", headers=headers)
                        with urllib.request.urlopen(req2, timeout=10) as resp2:
                            res_json2 = json.loads(resp2.read().decode())
                            if res_json2.get("code") == 1:
                                data = res_json2.get("data")
                                rotated = True
                if not data and res_json.get("data"):
                    data = res_json.get("data")
        except Exception:
            pass

    if not data or not data.get("http_ipv4"):
        try:
            req = urllib.request.Request(f"{TINPROXY_BASE_URL}/proxy/get-current-proxy?api_key={key}", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_json = json.loads(resp.read().decode())
                data = res_json.get("data")
        except Exception:
            pass

    if not data or not data.get("http_ipv4"):
        return None

    auth = data.get("authentication", {})
    u = auth.get("username", "")
    p = auth.get("password", "")
    srv = data.get("http_ipv4", "")
    proxy_url = f"http://{u}:{p}@{srv}" if u and p else f"http://{srv}"
    pw = {"server": f"http://{srv}"}
    if u:
        pw["username"] = u
    if p:
        pw["password"] = p

    return {
        "proxy_url": proxy_url,
        "playwright": pw,
        "server": f"http://{srv}",
        "username": u,
        "password": p,
        "ip": data.get("public_ip"),
        "location": data.get("location"),
        "rotated": rotated,
        "next_request": data.get("next_request", 0),
        "source": "tinproxy",
    }


async def get_rotating_proxy_async(
    rotate: bool = True,
    api_key: Optional[str] = None,
    force_wait: bool = False,
    max_wait: int = 120,
    on_status: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """Async version of get_rotating_proxy. Non-blocking sleep for cooldown."""
    if MUSE_PROXY:
        pw = parse_playwright_proxy(MUSE_PROXY)
        norm = normalize_proxy_url(MUSE_PROXY)
        return {
            "proxy_url": norm,
            "playwright": pw,
            "server": pw.get("server") if pw else norm,
            "ip": "custom",
            "location": "custom",
            "source": "static",
            "rotated": False,
        }

    key = (api_key or TINPROXY_API_KEY).strip()
    if not key:
        return None

    headers = {"User-Agent": "Mozilla/5.0"}
    data = None
    rotated = False

    def _sync_fetch(url: str):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    if rotate:
        try:
            res_json = await asyncio.to_thread(_sync_fetch, f"{TINPROXY_BASE_URL}/proxy/get-new-proxy?api_key={key}")
            if res_json.get("code") == 1:
                data = res_json.get("data")
                rotated = True
            elif res_json.get("code") == 0 and force_wait:
                rem = res_json.get("data", {}).get("next_request", 0)
                if 0 < rem <= max_wait:
                    if on_status:
                        on_status(f"Đang đợi xoay IP mới ({rem}s cooldown)...")
                    for sec in range(rem, 0, -5):
                        if on_status and sec < rem:
                            on_status(f"Đang đợi xoay IP mới (còn {sec}s)...")
                        await asyncio.sleep(min(5, sec))
                    await asyncio.sleep(1)
                    res_json2 = await asyncio.to_thread(_sync_fetch, f"{TINPROXY_BASE_URL}/proxy/get-new-proxy?api_key={key}")
                    if res_json2.get("code") == 1:
                        data = res_json2.get("data")
                        rotated = True
            if not data and res_json.get("data"):
                data = res_json.get("data")
        except Exception:
            pass

    if not data or not data.get("http_ipv4"):
        try:
            res_json = await asyncio.to_thread(_sync_fetch, f"{TINPROXY_BASE_URL}/proxy/get-current-proxy?api_key={key}")
            data = res_json.get("data")
        except Exception:
            pass

    if not data or not data.get("http_ipv4"):
        return None

    auth = data.get("authentication", {})
    u = auth.get("username", "")
    p = auth.get("password", "")
    srv = data.get("http_ipv4", "")
    proxy_url = f"http://{u}:{p}@{srv}" if u and p else f"http://{srv}"
    pw = {"server": f"http://{srv}"}
    if u:
        pw["username"] = u
    if p:
        pw["password"] = p

    return {
        "proxy_url": proxy_url,
        "playwright": pw,
        "server": f"http://{srv}",
        "username": u,
        "password": p,
        "ip": data.get("public_ip"),
        "location": data.get("location"),
        "rotated": rotated,
        "next_request": data.get("next_request", 0),
        "source": "tinproxy",
    }


def test_proxy(proxy_url: str, timeout: int = 8) -> Dict[str, Any]:
    """Tests connectivity through proxy and measures latency."""
    try:
        norm = normalize_proxy_url(proxy_url)
        handler = urllib.request.ProxyHandler({"http": norm, "https": norm})
        opener = urllib.request.build_opener(handler)
        req = urllib.request.Request("https://api.ipify.org?format=json", headers={"User-Agent": "Mozilla/5.0"})
        t0 = time.time()
        with opener.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return {"ok": True, "ip": data.get("ip"), "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
