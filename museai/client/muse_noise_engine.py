#!/usr/bin/env python3
"""
Muse.ai Headless Noise Protocol Engine (Browser-Free)
Directly communicates with Meta AI VM (Hatch) via Noise_XX protocol.
Supports single-account and multi-account concurrent image & video generation.
"""

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Dict, List, Optional, Tuple, Any

import websocket
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MEDIA_DIR = os.path.join(ROOT_DIR, "scratch", "media")
os.makedirs(DEFAULT_MEDIA_DIR, exist_ok=True)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
)
APP_ID = "hatch-web"
LB_HOST = "hatch.metaaivm.com"
NOISE_PATH = "/v1/noise"
CHUNK_SIZE = 65489

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


# ---------------------------------------------------------------- Protobuf Helpers
def _varint(n: int) -> bytes:
    n &= (1 << 64) - 1
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _read_varint(buf: bytes, i: int) -> Tuple[int, int]:
    shift = n = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not (b & 0x80):
            return n, i
        shift += 7


def pb_int(field: int, v: int) -> bytes:
    return _varint(field << 3) + _varint(v)


def pb_bytes(field: int, v) -> bytes:
    if isinstance(v, str):
        v = v.encode("utf-8")
    return _varint(field << 3 | 2) + _varint(len(v)) + v


def pb_parse(buf: bytes) -> Dict[int, list]:
    out: Dict[int, list] = {}
    i = 0
    while i < len(buf):
        key, i = _read_varint(buf, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _read_varint(buf, i)
        elif wt == 2:
            ln, i = _read_varint(buf, i)
            v, i = buf[i:i + ln], i + ln
        elif wt == 1:
            v, i = buf[i:i + 8], i + 8
        elif wt == 5:
            v, i = buf[i:i + 4], i + 4
        else:
            raise ValueError(f"bad wire type {wt}")
        out.setdefault(f, []).append(v)
    return out


def _first(d: dict, f: int, default=None):
    return d.get(f, [default])[0]


# ---------------------------------------------------------------- Noise_XX Cipher
def _hmac(k: bytes, d: bytes) -> bytes:
    return hmac.new(k, d, hashlib.sha256).digest()


def _hkdf2(ck: bytes, ikm: bytes) -> Tuple[bytes, bytes]:
    t = _hmac(ck, ikm)
    a = _hmac(t, b"\x01")
    return a, _hmac(t, a + b"\x02")


def _pub(sk: X25519PrivateKey) -> bytes:
    return sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _dh(sk: X25519PrivateKey, pub: bytes) -> bytes:
    return sk.exchange(X25519PublicKey.from_public_bytes(pub))


class Cipher:
    def __init__(self, key: Optional[bytes] = None):
        self.k = key
        self.n = 0

    def _nonce(self) -> bytes:
        nonce = b"\x00" * 4 + struct.pack(">Q", self.n)
        self.n += 1
        return nonce

    def enc(self, ad: bytes, pt: bytes) -> bytes:
        return AESGCM(self.k).encrypt(self._nonce(), pt, ad) if self.k else pt

    def dec(self, ad: bytes, ct: bytes) -> bytes:
        return AESGCM(self.k).decrypt(self._nonce(), ct, ad) if self.k else ct


class NoiseXX:
    def __init__(self):
        name = b"Noise_XX_25519_AESGCM_SHA256"
        self.h = name.ljust(32, b"\x00")
        self.ck = self.h
        self.c = Cipher()
        self.mix_hash(b"")

    def mix_hash(self, d: bytes):
        self.h = hashlib.sha256(self.h + d).digest()

    def mix_key(self, ikm: bytes):
        self.ck, k = _hkdf2(self.ck, ikm)
        self.c = Cipher(k)

    def enc_hash(self, pt: bytes) -> bytes:
        ct = self.c.enc(self.h, pt)
        self.mix_hash(ct)
        return ct

    def dec_hash(self, ct: bytes) -> bytes:
        pt = self.c.dec(self.h, ct)
        self.mix_hash(ct)
        return pt

    def msg1(self, payload: bytes) -> bytes:
        self.e = X25519PrivateKey.generate()
        ep = _pub(self.e)
        self.mix_hash(ep)
        return ep + self.enc_hash(payload)

    def msg2(self, m: bytes) -> bytes:
        self.re = m[:32]
        self.mix_hash(self.re)
        self.mix_key(_dh(self.e, self.re))
        self.rs = self.dec_hash(m[32:80])
        self.mix_key(_dh(self.e, self.rs))
        return self.dec_hash(m[80:])

    def msg3(self, payload: bytes) -> bytes:
        s = X25519PrivateKey.generate()
        ct_s = self.enc_hash(_pub(s))
        self.mix_key(_dh(s, self.re))
        return ct_s + self.enc_hash(payload)

    def split(self) -> Tuple[Cipher, Cipher]:
        k1, k2 = _hkdf2(self.ck, b"")
        return Cipher(k1), Cipher(k2)


# ---------------------------------------------------------------- Headless Client
SERVICES = {"daemon": 0, "sentinel": 1, "vault": 2, "authd": 3}
TERMINAL_FAIL_STATUSES = ("failed", "error", "interrupted", "cancelled", "canceled")
UPLOAD_CHUNK_BYTES = 512 * 1024


import threading

class MuseNoiseClient:
    """Client for a single Muse.ai session over encrypted Noise_XX WebSocket."""

    def __init__(self, cookie_path: str, media_dir: str = DEFAULT_MEDIA_DIR, account_name: str = "default"):
        self.cookie_path = cookie_path
        self.media_dir = media_dir
        self.account_name = account_name
        self.ws: Optional[websocket.WebSocket] = None
        self.tx: Optional[Cipher] = None
        self.rx: Optional[Cipher] = None
        self.vm_id: Optional[str] = None
        self.stream_id = 1
        self.last_connected_at = 0.0
        self.lock = threading.Lock()

    def _get_cookie_header(self) -> str:
        with open(self.cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if isinstance(cookies, list):
            return "; ".join(f"{c['name']}={c['value']}" for c in cookies if "name" in c and "value" in c)
        elif isinstance(cookies, dict):
            return "; ".join(f"{k}={v}" for k, v in cookies.items())
        return ""

    def _http_call(self, method: str, url: str, body: Optional[dict] = None) -> Tuple[int, bytes]:
        cookie_hdr = self._get_cookie_header()
        headers = {
            "Cookie": cookie_hdr,
            "User-Agent": UA,
            "Origin": "https://muse.ai",
            "Referer": "https://muse.ai/",
            "Content-Type": "application/json",
            **BROWSER_HEADERS,
        }
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def connect(self, attempts: int = 3):
        """connect_once() with a short retry: DNS / TLS hiccups on a VPS are transient."""
        for i in range(attempts):
            try:
                return self.connect_once()
            except (urllib.error.URLError, OSError, websocket.WebSocketException) as e:
                self.close()
                if i + 1 == attempts:
                    raise RuntimeError(f"connect failed after {attempts} tries: {e}") from e
                time.sleep(1.5 * (i + 1))

    def connect_once(self):
        """Discovers gateway, wakes VM, obtains auth token, and completes Noise handshake."""
        # The VM behind a cookie can be re-provisioned between the page load and the token call
        # ("hatch_vm_auth_no_match"): re-discover the gateway and retry before giving up.
        for i in range(3):
            try:
                return self._connect_flow()
            except RuntimeError as e:
                if "hatch_vm_auth_no_match" not in str(e) or i == 2:
                    raise
                time.sleep(3 * (i + 1))

    def _connect_flow(self):
        # 1. GET muse.ai/ to find gatewayUrl
        status, html = self._http_call("GET", "https://muse.ai/")
        if status != 200:
            raise RuntimeError(f"Failed to access muse.ai (status {status}) with cookies: {self.cookie_path}")

        m = re.search(r'gatewayUrl\\?":\\?"(wss://[^"\\]+)', html.decode("utf-8", "ignore"))
        if not m:
            raise RuntimeError("gatewayUrl not found in muse.ai HTML (cookie expired or not logged in)")
        gateway = m.group(1)
        host = urllib.parse.urlparse(gateway).hostname or ""
        vm_id = host[:-len(".metaaivm.com")] if host.endswith(".metaaivm.com") else host.split(".")[0]
        self.vm_id = vm_id

        # 2. Wake VM to avoid 502 Bad Gateway
        wake_status, wake_body = self._http_call(
            "POST",
            "https://muse.ai/api/hatch/vm/wake",
            {"vm_id": vm_id, "retry_count": 0, "connect_attempt_id": str(uuid.uuid4())}
        )
        if wake_status not in (200, 204):
            print(f"[{self.account_name}] Warning: vm/wake status {wake_status}: {wake_body.decode('utf-8', 'ignore')}")

        # 3. Obtain auth token
        tok_status, tok_body = self._http_call(
            "POST",
            "https://muse.ai/api/hatch/token",
            {"vmAddress": gateway}
        )
        if tok_status != 200:
            raise RuntimeError(f"Failed to obtain hatch token: {tok_status} {tok_body.decode('utf-8', 'ignore')}")
        j = json.loads(tok_body.decode("utf-8"))
        token = j["token"]
        notary = j.get("notary_token")

        # 4. WebSocket connection to hatch load balancer
        q = {
            "vm_id": vm_id,
            "auth_token": token,
            "app_id": APP_ID,
            "request_id": str(uuid.uuid4()),
        }
        if notary:
            q["notary_token"] = notary
        url = f"wss://{LB_HOST}{NOISE_PATH}?{urllib.parse.urlencode(q)}"

        self.ws = websocket.create_connection(
            url, timeout=30, header=[f"User-Agent: {UA}"], origin="https://muse.ai"
        )

        # 5. Noise_XX Handshake
        hs = NoiseXX()
        client_nonce = os.urandom(32)
        self.ws.send_binary(hs.msg1(pb_bytes(1, client_nonce)))
        m2 = self.ws.recv()
        if isinstance(m2, str):
            raise RuntimeError(f"Unexpected text frame during Noise handshake: {m2[:100]}")
        payload = hs.msg2(m2)
        rv = pb_parse(payload) if payload else {}
        state = _first(rv, 2)
        if state == 2 and len(_first(rv, 3, b"")) == 32 and len(_first(rv, 4, b"")) == 32:
            raise RuntimeError("Confidential VM requires CVM enrollment key (standard VMs supported).")

        self.ws.send_binary(hs.msg3(b""))
        self.tx, self.rx = hs.split()
        self.last_connected_at = time.time()
        print(f"[{self.account_name}] Noise handshake completed. Connected to VM {vm_id}.")

    def ensure_connected(self):
        if not self.ws or not self.tx or not self.rx:
            self.connect()

    def _send_frame(self, service: str, frame: bytes):
        self.ensure_connected()
        req = pb_int(1, SERVICES[service]) + pb_bytes(2, frame)
        chunk_id = int.from_bytes(os.urandom(8), "little") & ((1 << 63) - 1)
        parts = [req[i:i + CHUNK_SIZE] for i in range(0, len(req), CHUNK_SIZE)] or [b""]
        for idx, part in enumerate(parts):
            t = pb_int(1, chunk_id) + pb_int(2, idx) + pb_int(3, len(parts)) + pb_bytes(4, part)
            self.ws.send_binary(self.tx.enc(b"", t))

    def _recv_frame(self) -> dict:
        assemblies = {}
        while True:
            raw = self.ws.recv()
            if isinstance(raw, str):
                continue
            t = pb_parse(self.rx.dec(b"", raw))
            cid, idx, total = _first(t, 1, 0), _first(t, 2, 0), _first(t, 3, 1)
            a = assemblies.setdefault(cid, {})
            a[idx] = _first(t, 4, b"")
            if len(a) < total:
                continue
            data = b"".join(a[i] for i in range(total))
            del assemblies[cid]
            resp = pb_parse(data)
            return pb_parse(_first(resp, 1, b""))

    def request(self, verb: str, path: str, body: Optional[dict] = None, service: str = "daemon") -> Tuple[int, bytes]:
        """Sends an encrypted RPC request over Noise and returns (status_code, body_bytes)."""
        with self.lock:
            sid = self.stream_id
            self.stream_id += 1
            headers = [
                ("x-request-id", str(uuid.uuid4())),
                ("x-app-id", APP_ID),
                ("Accept-Language", "en-US"),
            ]
            payload = b""
            if body is not None:
                payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
                headers.insert(0, ("Content-Type", "application/json"))

            app = pb_bytes(1, verb) + pb_bytes(2, path)
            for k, v in headers:
                app += pb_bytes(3, pb_bytes(1, k) + pb_bytes(2, v))
            app += pb_bytes(4, payload) + pb_int(5, 1)
            self._send_frame(service, pb_int(1, sid) + pb_bytes(2, app))

            status, out = None, bytearray()
            while True:
                f = self._recv_frame()
                if _first(f, 1, 0) != sid:
                    continue
                if 3 in f:  # Response frame
                    r = pb_parse(f[3][0])
                    status = _first(r, 1, 0)
                    chunk = _first(r, 3, b"")
                    out += chunk
                    if _first(r, 4, 0):
                        break
                elif 4 in f:  # Body chunk
                    b = pb_parse(f[4][0])
                    chunk = _first(b, 1, b"")
                    out += chunk
                    if _first(b, 2, 0):
                        break
                elif 5 in f:  # Reset frame
                    r = pb_parse(f[5][0])
                    reason = _first(r, 2, b"").decode("utf-8", "ignore")
                    raise RuntimeError(f"Stream reset code={_first(r, 1, 0)}: {reason}")
            return status or 0, bytes(out)

    def upload_file(self, data_or_b64: Any, filename: str) -> str:
        """Uploads a file to VM's workspace/uploads/ and returns relative path."""
        if isinstance(data_or_b64, bytes):
            b64_str = base64.b64encode(data_or_b64).decode("utf-8")
        elif isinstance(data_or_b64, str):
            if data_or_b64.startswith(("http://", "https://")):
                req = urllib.request.Request(data_or_b64, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    b64_str = base64.b64encode(r.read()).decode("utf-8")
            elif data_or_b64.startswith(("/media/", "media/")):
                cand = os.path.join(self.media_dir, os.path.basename(data_or_b64))
                if os.path.exists(cand):
                    with open(cand, "rb") as f:
                        b64_str = base64.b64encode(f.read()).decode("utf-8")
                else:
                    raise FileNotFoundError(f"Media file not found: {data_or_b64}")
            elif data_or_b64.startswith("data:"):
                b64_str = data_or_b64.split(",", 1)[-1]
            elif os.path.exists(data_or_b64):
                with open(data_or_b64, "rb") as f:
                    b64_str = base64.b64encode(f.read()).decode("utf-8")
            else:
                b64_str = data_or_b64
        else:
            raise ValueError("Unsupported data format for upload")

        clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.basename(filename))
        remote_rel_path = f"workspace/uploads/{uuid.uuid4().hex[:6]}_{clean_name}"
        # The VM's /fs/write rejects bodies over ~1.5MB raw (413 "length limit exceeded"), so a phone
        # photo goes up in UPLOAD_CHUNK_BYTES slices: the first overwrites, the rest append.
        raw = base64.b64decode(b64_str + "=" * (-len(b64_str) % 4))
        for off in range(0, max(len(raw), 1), UPLOAD_CHUNK_BYTES):
            st, res = self.request("POST", "/fs/write", body={
                "path": remote_rel_path,
                "data_base64": base64.b64encode(raw[off:off + UPLOAD_CHUNK_BYTES]).decode("ascii"),
                "overwrite": off == 0,
                "append": off > 0,
                "create_parent": True,
            })
            if st not in (200, 201):
                raise RuntimeError(f"Failed to upload {filename} to {remote_rel_path}: {st} {res.decode('utf-8', 'ignore')}")
        return remote_rel_path

    def download_file(self, remote_path: str, save_filename: Optional[str] = None) -> Tuple[str, bytes]:
        """Downloads file from VM via GET /fs/raw/{remote_path} and saves locally."""
        clean_path = remote_path.replace("sandbox://", "").lstrip("/")
        st, data = self.request("GET", f"/fs/raw/{clean_path}")
        if st != 200:
            raise RuntimeError(f"Failed to download {clean_path} (status {st})")
        if not save_filename:
            ext = os.path.splitext(clean_path)[-1] or ".bin"
            save_filename = f"muse_{uuid.uuid4().hex[:8]}_0{ext}"
        local_path = os.path.join(self.media_dir, save_filename)
        with open(local_path, "wb") as f:
            f.write(data)
        return local_path, data

    def generate(
        self,
        prompt: str,
        files: Optional[List[Any]] = None,
        timeout_s: int = 240,
        session_id: Optional[str] = None,
        poll_interval_s: float = 2.5
    ) -> Dict[str, Any]:
        """
        Executes a prompt (image, video, or chat) in an isolated side session.
        Returns dict with status, content, media links, and duration.
        """
        self.ensure_connected()
        t0 = time.time()
        resumed = bool(session_id)
        prev_updated = 0
        if resumed:
            prev = self._session_info(session_id)
            if prev is None:
                resumed, session_id = False, None  # gone (or another account's): start fresh
            else:
                prev_updated = prev.get("updated_at_ms") or 0
        session_id = session_id or str(uuid.uuid4())
        node_id = str(uuid.uuid4())

        # Prepare items if files provided
        items = []
        if files:
            for idx, file_item in enumerate(files):
                fname = f"input_{idx}.jpg"
                mime = "image/jpeg"
                if isinstance(file_item, str):
                    if file_item.startswith("data:"):
                        m = re.match(r"data:([^;]+);", file_item)
                        if m:
                            mime = m.group(1)
                        ext = mimetypes.guess_extension(mime) or ".jpg"
                        fname = f"input_{idx}{ext}"
                    elif os.path.exists(file_item):
                        fname = os.path.basename(file_item)
                        mime, _ = mimetypes.guess_type(file_item)
                        mime = mime or "image/jpeg"
                remote_path = self.upload_file(file_item, fname)
                items.append({
                    "type": "file_ref",
                    "path": remote_path,
                    "mime_type": mime
                })
            items.append({"type": "text", "text": prompt})
            body = {
                "items": items,
                "session_id": session_id,
                "node_id": node_id,
                "capabilities": ["chat_cancel", "delta_stream"]
            }
        else:
            body = {
                "message": prompt,
                "session_id": session_id,
                "node_id": node_id,
                "capabilities": ["chat_cancel", "delta_stream"]
            }

        # Dispatch prompt
        ack_status, ack_data = self.request("POST", "/chat/stream", body=body)
        if ack_status != 200:
            err_msg = ack_data.decode("utf-8", "ignore")
            return {
                "ok": False,
                "prompt": prompt,
                "error": f"POST /chat/stream rejected ({ack_status}): {err_msg}",
                "status": "failed",
                "account": self.account_name,
            }

        # Poll session status until completed. A resumed session is already "completed" before this
        # turn starts, so it only counts once it was seen running or its updated_at moved past prev_updated.
        deadline = time.time() + timeout_s
        completed = False
        terminal = ""
        seen_running = not resumed
        while time.time() < deadline:
            time.sleep(poll_interval_s)
            s = self._session_info(session_id)
            if not s:
                continue
            status = s.get("status")
            if status in ("running", "pending", "queued"):
                seen_running = True
            elif status == "completed" and (seen_running or (s.get("updated_at_ms") or 0) > prev_updated):
                completed = True
                break
            elif status in TERMINAL_FAIL_STATUSES and (seen_running or (s.get("updated_at_ms") or 0) > prev_updated):
                terminal = status
                break

        if terminal:
            return {
                "ok": False,
                "prompt": prompt,
                "error": f"Muse session ended as '{terminal}'",
                "status": "failed",
                "session_id": session_id,
                "account": self.account_name,
            }

        if not completed:
            return {
                "ok": False,
                "prompt": prompt,
                "error": f"Generation timed out after {timeout_s}s",
                "status": "timeout",
                "session_id": session_id,
                "account": self.account_name,
            }

        # Retrieve conversation history and media
        st, hist_data = self.request("GET", f"/chat/history?session_id={session_id}")
        if st != 200:
            return {
                "ok": False,
                "prompt": prompt,
                "error": f"Failed to retrieve chat history ({st})",
                "status": "failed",
                "account": self.account_name,
            }

        hj = json.loads(hist_data.decode("utf-8"))
        events = hj.get("result", {}).get("chat_events", [])

        assistant_text = ""
        media_urls = []
        local_files = []

        # Only this turn: a resumed session's history also holds every earlier turn and its media.
        last_user = max((i for i, ev in enumerate(events) if ev.get("event_name") == "message.user"), default=-1)
        for ev in events[last_user + 1:]:
            ename = ev.get("event_name")
            p = ev.get("payload", {})
            if ename == "message.assistant":
                txt = ev.get("display_text") or p.get("content") or ""
                if txt:
                    assistant_text = txt
            elif ename == "delta.presentation":
                pdata = p.get("data", {})
                # Images
                for img in pdata.get("images", []):
                    rpath = img.get("path")
                    if rpath:
                        local_path, _ = self.download_file(rpath)
                        save_name = os.path.basename(local_path)
                        media_urls.append(f"/media/{save_name}")
                        local_files.append(local_path)
                # Videos
                for vid in pdata.get("videos", []):
                    rpath = vid.get("path")
                    if rpath:
                        local_path, _ = self.download_file(rpath)
                        save_name = os.path.basename(local_path)
                        media_urls.append(f"/media/{save_name}")
                        local_files.append(local_path)

        duration_ms = round((time.time() - t0) * 1000)
        return {
            "ok": True,
            "prompt": prompt,
            "content": assistant_text,
            "media": media_urls,
            "local_paths": local_files,
            "session_id": session_id,
            "duration_ms": duration_ms,
            "status": "completed",
            "account": self.account_name,
        }

    def _session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            st, s_data = self.request("GET", "/api/session/list")
            if st != 200:
                return None
            for s in json.loads(s_data.decode("utf-8")).get("result", {}).get("sessions", []):
                if s.get("session_id") == session_id:
                    return s
        except (ValueError, AttributeError):
            pass
        return None

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
            self.tx = None
            self.rx = None


# ---------------------------------------------------------------- Headless Pool
class MuseNoisePool:
    """Manages multiple accounts and executes concurrent batch generation jobs without browser."""

    def __init__(self, cookies_dir_or_file: str, media_dir: str = DEFAULT_MEDIA_DIR):
        self.media_dir = media_dir
        self.accounts: Dict[str, MuseNoiseClient] = {}
        self._load_accounts(cookies_dir_or_file)

    def _load_accounts(self, target: str):
        if os.path.isdir(target):
            for fn in sorted(os.listdir(target)):
                if fn.endswith(".json") and not fn.startswith((".", "_")):
                    name = fn[:-5]
                    self.accounts[name] = MuseNoiseClient(
                        os.path.join(target, fn), media_dir=self.media_dir, account_name=name
                    )
            if not self.accounts:
                cand = os.path.join(ROOT_DIR, "cookies.json")
                if os.path.exists(cand):
                    self.accounts["default"] = MuseNoiseClient(
                        cand, media_dir=self.media_dir, account_name="default"
                    )
        elif os.path.isfile(target):
            self.accounts["default"] = MuseNoiseClient(
                target, media_dir=self.media_dir, account_name="default"
            )

    def pick_account(self) -> MuseNoiseClient:
        # Simple round-robin / first available
        if not self.accounts:
            raise RuntimeError("No cookie accounts found in pool")
        return list(self.accounts.values())[0]

    def generate_one(
        self,
        prompt: str,
        files: Optional[List[Any]] = None,
        account_name: Optional[str] = None,
        timeout_s: int = 240,
    ) -> Dict[str, Any]:
        """Runs a single prompt with a dedicated connection from the pool."""
        if not self.accounts:
            raise RuntimeError("No accounts available in pool")
        if account_name and account_name in self.accounts:
            acc = self.accounts[account_name]
        else:
            acc = list(self.accounts.values())[0]

        client = MuseNoiseClient(acc.cookie_path, media_dir=self.media_dir, account_name=acc.account_name)
        try:
            return client.generate(prompt, files=files, timeout_s=timeout_s)
        finally:
            client.close()

    def generate_batch(
        self,
        items: List[Dict[str, Any]],
        concurrency: int = 2,
        timeout_s: int = 300,
        on_progress=None
    ) -> List[Dict[str, Any]]:
        """Executes a list of items concurrently across accounts via a thread pool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = [None] * len(items)
        account_list = list(self.accounts.values())
        if not account_list:
            raise RuntimeError("No accounts available")

        # Worker function with dedicated connection per task
        def _worker(idx, item, cookie_path, acc_name):
            prompt = item.get("prompt", "")
            files = item.get("files") or []
            print(f"[Pool] Task #{idx+1} started on account '{acc_name}'...")
            client = MuseNoiseClient(cookie_path, media_dir=self.media_dir, account_name=acc_name)
            try:
                res = client.generate(prompt, files=files, timeout_s=timeout_s)
                res["index"] = idx
                return idx, res
            finally:
                client.close()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for idx, item in enumerate(items):
                acc = account_list[idx % len(account_list)]
                f = executor.submit(_worker, idx, item, acc.cookie_path, acc.account_name)
                futures.append(f)

            for future in as_completed(futures):
                idx, res = future.result()
                results[idx] = res
                if on_progress:
                    on_progress(idx, res)

        return results
