"""GoLogin (Orbita) profiles for the local cookie-extraction login flow.

Uses the `gologin-agent-browser` CLI with the user's GoLogin API token (env GOLOGIN_TOKEN or
~/.gologin-*/config.json). Each login gets a fresh profile (own fingerprint + proxy) that is deleted
afterwards; Orbita is driven through its remote-debugging port.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from typing import Dict, Optional

CONFIG_PATHS = ["~/.gologin-local-agent-browser/config.json", "~/.gologin-agent-browser/config.json"]
CLI_FALLBACKS = ["/usr/local/bin/gologin-agent-browser", "/opt/homebrew/bin/gologin-agent-browser",
                 "~/.npm-global/bin/gologin-agent-browser"]


def token() -> str:
    tok = os.environ.get("GOLOGIN_TOKEN", "").strip()
    if tok:
        return tok
    for p in CONFIG_PATHS:
        try:
            with open(os.path.expanduser(p), encoding="utf-8") as f:
                tok = (json.load(f).get("token") or "").strip()
            if tok and "YOUR_GOLOGIN_API_TOKEN" not in tok:
                return tok
        except Exception:
            pass
    return ""


def cli_bin() -> Optional[str]:
    found = shutil.which("gologin-agent-browser")
    if found:
        return found
    return next((os.path.expanduser(c) for c in CLI_FALLBACKS if os.path.isfile(os.path.expanduser(c))), None)


def available() -> bool:
    """A token and the CLI are both present (never true on the headless VPS)."""
    return bool(token() and cli_bin())


def _cli(args: list, timeout: int = 120) -> str:
    env = dict(os.environ, GOLOGIN_TOKEN=token())
    p = subprocess.run([cli_bin(), "--runtime", "local"] + args, capture_output=True, text=True,
                       timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"gologin {' '.join(args[:2])}: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout.strip()


def _debug_port(profile_id: str) -> Optional[int]:
    out = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f"gologin_profile_{profile_id}" in line:
            m = re.search(r"--remote-debugging-port=(\d+)", line)
            if m:
                return int(m.group(1))
    return None


def _open_sync(name: str, proxy: Optional[Dict]) -> Dict:
    args = ["profile-create", name]
    if proxy and proxy.get("server"):
        u = urllib.parse.urlparse(proxy["server"] if "://" in proxy["server"] else "http://" + proxy["server"])
        mode = {"socks5": "socks5", "socks4": "socks4"}.get(u.scheme, "http")
        args += ["--proxy-mode", mode, "--proxy-host", u.hostname or "", "--proxy-port", str(u.port or 80)]
        if proxy.get("username"):
            args += ["--proxy-user", proxy["username"], "--proxy-pass", proxy.get("password", "")]
    args.append("--json")
    pid = json.loads(_cli(args, timeout=150))["profileId"]
    session = f"muse-{pid[:8]}"
    try:
        _cli(["open", "about:blank", "--profile", pid, "--session", session], timeout=120)
        port = None
        for _ in range(20):
            port = _debug_port(pid)
            if port:
                break
            time.sleep(0.5)
        if not port:
            raise RuntimeError("Orbita không mở cổng debug")
    except Exception:
        _close_sync({"profile_id": pid, "session": session})
        raise
    return {"profile_id": pid, "session": session, "port": port}


def _close_sync(h: Dict):
    pid = h["profile_id"]
    try:
        _cli(["close", "--session", h["session"]], timeout=30)
    except Exception:
        pass
    subprocess.run(["pkill", "-9", "-f", f"gologin_profile_{pid}"], capture_output=True)
    for attempt in range(3):
        try:
            _cli(["profile-delete", pid, "--remote"], timeout=60)
            return
        except Exception as e:
            if attempt == 2:
                print(f"[GoLogin] could not delete profile {pid}: {e}")
            time.sleep(2)


async def open_profile(name: str, proxy: Optional[Dict] = None) -> Dict:
    return await asyncio.to_thread(_open_sync, name, proxy)


async def close_profile(handle: Dict):
    await asyncio.to_thread(_close_sync, handle)
