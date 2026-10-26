#!/usr/bin/env python3
"""Cookie-only Muse client: hatch token -> Noise_XX over WebSocket -> RPC.
Protocol reverse-engineered from research/pretty/noise.js (NoiseXXInitiator, NoiseTransport).
Never prints cookie/token values.

Usage:
  python3 tools/muse_noise_client.py                   # handshake + GET /health
  python3 tools/muse_noise_client.py GET /chat/history
  python3 tools/muse_noise_client.py POST /some/path '{"json": "body"}'
"""
import hashlib
import hmac
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

import websocket  # websocket-client
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
APP_ID = "hatch-web"
LB_HOST = "hatch.metaaivm.com"
NOISE_PATH = "/v1/noise"
CHUNK = 65489
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


# ---------------------------------------------------------------- auth (cookie -> token)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def get_credentials(cookie_path):
    cookies = json.load(open(cookie_path))
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    opener = urllib.request.build_opener(NoRedirect)

    def call(method, url, body=None):
        headers = {"Cookie": cookie_header, "User-Agent": UA, "Origin": "https://muse.ai",
                   "Referer": "https://muse.ai/", "Content-Type": "application/json", **BROWSER_HEADERS}
        req = urllib.request.Request(url, method=method, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with opener.open(req, timeout=20) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    status, html = call("GET", "https://muse.ai/")
    m = re.search(r'gatewayUrl\\?":\\?"(wss://[^"\\]+)', html.decode("utf-8", "ignore"))
    if not m:
        sys.exit(f"[auth] GET muse.ai -> {status}, gatewayUrl not found (cookies expired?)")
    gateway = m.group(1)
    status, body = call("POST", "https://muse.ai/api/hatch/token", {"vmAddress": gateway})
    if status != 200:
        sys.exit(f"[auth] token -> {status}")
    j = json.loads(body)
    host = urllib.parse.urlparse(gateway).hostname
    vm_id = host[: -len(".metaaivm.com")] if host.endswith(".metaaivm.com") else host.split(".")[0]
    print(f"[auth] token OK (len {len(j['token'])}), notary {'yes' if j.get('notary_token') else 'no'}, "
          f"vm_id len {len(vm_id)}")
    return vm_id, j["token"], j.get("notary_token")


# ---------------------------------------------------------------- minimal protobuf
def _varint(n):
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


def pb_int(field, v):
    return _varint(field << 3) + _varint(v)


def pb_bytes(field, v):
    if isinstance(v, str):
        v = v.encode()
    return _varint(field << 3 | 2) + _varint(len(v)) + v


def pb_parse(buf):
    """-> dict field -> list of raw values (int for varint, bytes for len-delimited)."""
    out, i = {}, 0
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


def _read_varint(buf, i):
    shift = n = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def _first(d, f, default=None):
    return d.get(f, [default])[0]


# ---------------------------------------------------------------- Noise_XX_25519_AESGCM_SHA256
def _hmac(k, d):
    return hmac.new(k, d, hashlib.sha256).digest()


def _hkdf2(ck, ikm):
    t = _hmac(ck, ikm)
    a = _hmac(t, b"\x01")
    return a, _hmac(t, a + b"\x02")


def _pub(sk):
    return sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _dh(sk, pub):
    return sk.exchange(X25519PublicKey.from_public_bytes(pub))


class Cipher:
    def __init__(self, key=None):
        self.k, self.n = key, 0

    def _nonce(self):
        nonce = b"\x00" * 4 + struct.pack(">Q", self.n)
        self.n += 1
        return nonce

    def enc(self, ad, pt):
        return AESGCM(self.k).encrypt(self._nonce(), pt, ad) if self.k else pt

    def dec(self, ad, ct):
        return AESGCM(self.k).decrypt(self._nonce(), ct, ad) if self.k else ct


class NoiseXX:
    def __init__(self):
        name = b"Noise_XX_25519_AESGCM_SHA256"
        self.h = name.ljust(32, b"\x00")
        self.ck = self.h
        self.c = Cipher()
        self.mix_hash(b"")  # empty prologue

    def mix_hash(self, d):
        self.h = hashlib.sha256(self.h + d).digest()

    def mix_key(self, ikm):
        self.ck, k = _hkdf2(self.ck, ikm)
        self.c = Cipher(k)

    def enc_hash(self, pt):
        ct = self.c.enc(self.h, pt)
        self.mix_hash(ct)
        return ct

    def dec_hash(self, ct):
        pt = self.c.dec(self.h, ct)
        self.mix_hash(ct)
        return pt

    def msg1(self, payload):
        self.e = X25519PrivateKey.generate()
        ep = _pub(self.e)
        self.mix_hash(ep)
        return ep + self.enc_hash(payload)

    def msg2(self, m):
        self.re = m[:32]
        self.mix_hash(self.re)
        self.mix_key(_dh(self.e, self.re))
        self.rs = self.dec_hash(m[32:80])
        self.mix_key(_dh(self.e, self.rs))
        return self.dec_hash(m[80:])

    def msg3(self, payload):
        s = X25519PrivateKey.generate()  # web client uses a fresh static key per connection
        ct_s = self.enc_hash(_pub(s))
        self.mix_key(_dh(s, self.re))
        return ct_s + self.enc_hash(payload)

    def split(self):
        k1, k2 = _hkdf2(self.ck, b"")
        return Cipher(k1), Cipher(k2)


# ---------------------------------------------------------------- transport
SERVICES = {"daemon": 0, "sentinel": 1, "vault": 2, "authd": 3}


class MuseNoise:
    def __init__(self, cookie_path):
        vm_id, token, notary = get_credentials(cookie_path)
        q = {"vm_id": vm_id, "auth_token": token}
        if notary:
            q["notary_token"] = notary
        q["app_id"] = APP_ID
        q["request_id"] = str(uuid.uuid4())
        url = f"wss://{LB_HOST}{NOISE_PATH}?{urllib.parse.urlencode(q)}"
        self.ws = websocket.create_connection(
            url, timeout=30, header=[f"User-Agent: {UA}"], origin="https://muse.ai")
        print("[ws] connected")
        self._handshake()
        self.stream_id = 1
        self.pending = {}

    def _handshake(self):
        hs = NoiseXX()
        client_nonce = os.urandom(32)
        self.ws.send_binary(hs.msg1(pb_bytes(1, client_nonce)))
        m2 = self.ws.recv()
        if isinstance(m2, str):
            sys.exit(f"[noise] expected binary msg2, got text: {m2[:200]}")
        payload = hs.msg2(m2)
        rv = pb_parse(payload) if payload else {}
        state = _first(rv, 2)
        if state == 2 and len(_first(rv, 3, b"")) == 32 and len(_first(rv, 4, b"")) == 32:
            sys.exit("[noise] VM is CONFIDENTIAL + provisioned: msg3 needs the CVM recovery key "
                     "(stored in the browser, not in cookies). Cookie-only cannot finish this handshake.")
        if state == 1:
            sys.exit("[noise] VM is CONFIDENTIAL + unprovisioned (enrollment required).")
        print(f"[noise] msg2 OK: standard VM, attestation payload {len(payload)} bytes")
        self.ws.send_binary(hs.msg3(b""))
        self.tx, self.rx = hs.split()
        print("[noise] handshake complete")

    def _send_frame(self, service, frame):
        req = pb_int(1, SERVICES[service]) + pb_bytes(2, frame)
        chunk_id = int.from_bytes(os.urandom(8), "little") & ((1 << 63) - 1)
        parts = [req[i:i + CHUNK] for i in range(0, len(req), CHUNK)] or [b""]
        for idx, part in enumerate(parts):
            t = pb_int(1, chunk_id) + pb_int(2, idx) + pb_int(3, len(parts)) + pb_bytes(4, part)
            self.ws.send_binary(self.tx.enc(b"", t))

    def _recv_frame(self):
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

    def request(self, verb, path, body=None, service="daemon", on_chunk=None):
        sid = self.stream_id
        self.stream_id += 1
        headers = [("x-request-id", str(uuid.uuid4())), ("x-app-id", APP_ID), ("Accept-Language", "en-US")]
        payload = b""
        if body is not None:
            payload = json.dumps(body).encode()
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
            if 3 in f:  # response
                r = pb_parse(f[3][0])
                status = _first(r, 1, 0)
                chunk = _first(r, 3, b"")
                out += chunk
                if chunk and on_chunk:
                    on_chunk(chunk)
                if _first(r, 4, 0):
                    break
            elif 4 in f:  # body chunk
                b = pb_parse(f[4][0])
                chunk = _first(b, 1, b"")
                out += chunk
                if chunk and on_chunk:
                    on_chunk(chunk)
                if _first(b, 2, 0):
                    break
            elif 5 in f:  # reset
                r = pb_parse(f[5][0])
                raise RuntimeError(f"stream reset code={_first(r, 1, 0)} reason={_first(r, 2, b'').decode()}")
        return status, bytes(out)

    def close(self):
        self.ws.close()


def main():
    args = sys.argv[1:]
    verb, path = (args[0].upper(), args[1]) if len(args) >= 2 else ("GET", "/health")
    body = json.loads(args[2]) if len(args) >= 3 else None
    client = MuseNoise(os.path.join(ROOT, "cookies.json"))
    try:
        status, data = client.request(verb, path, body)
        print(f"[rpc] {verb} {path} -> {status}, {len(data)} bytes")
        text = data.decode("utf-8", "replace")
        try:
            print(json.dumps(json.loads(text), ensure_ascii=False, indent=1)[:3000])
        except ValueError:
            print(text[:3000])
    finally:
        client.close()


if __name__ == "__main__":
    main()
