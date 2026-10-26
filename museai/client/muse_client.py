"""
Standalone Python Client for Muse.ai (Meta Hatch/Abra)
Implements end-to-end WebSocket connection over Noise_XX_25519_AESGCM_SHA256,
Protobuf stream multiplexing, and CVM attestation.
"""

import asyncio
import json
import os
import uuid
import datetime
from typing import Optional, AsyncIterator, Dict, Any, List
import requests
import websockets

from client.noise import NoiseXXInitiator
from client.cvm import RvChallenge, solve_cvm_challenge
from client.transport import NoiseTransport
from client.proto.noise_pb2 import ServiceFrame

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

class MuseClient:
    def __init__(
        self,
        cookies: str,
        rv_key_hex: Optional[str] = None,
        base_url: str = "https://muse.ai"
    ):
        self.cookies = cookies
        self.rv_key: Optional[bytes] = bytes.fromhex(rv_key_hex) if rv_key_hex else None
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Cookie": self.cookies,
            "Accept": "application/json",
        })

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.transport: Optional[NoiseTransport] = None
        self.initiator: Optional[NoiseXXInitiator] = None

    def fetch_gateway_token(self, vm_address: str = "wss://gateway.muse.ai/", vm_name: Optional[str] = None) -> Dict[str, Any]:
        """Calls /api/hatch/token to obtain gateway URL, auth token, and notary token."""
        url = f"{self.base_url}/api/hatch/token"
        payload = {"vmAddress": vm_address}
        if vm_name:
            payload["vmName"] = vm_name

        resp = self.session.post(url, json=payload, timeout=15)
        if not resp.ok:
            raise RuntimeError(f"Failed to fetch gateway token: {resp.status_code} {resp.text}")
        return resp.json()

    def fetch_noise_notary_token(self, vm_name: str) -> str:
        """Calls /api/hatch/noise-notary-token to obtain notary token."""
        url = f"{self.base_url}/api/hatch/noise-notary-token"
        resp = self.session.post(url, json={"vmName": vm_name}, timeout=10)
        if not resp.ok:
            raise RuntimeError(f"Failed to fetch noise notary token: {resp.status_code}")
        data = resp.json()
        return data.get("notaryToken", "")

    async def connect(self, vm_id: str, gateway_url: str, auth_token: str, notary_token: Optional[str] = None):
        """
        Connects WebSocket to the gateway and performs the 3-message Noise_XX handshake.
        """
        # Ensure gateway_url has wss:// scheme
        if not gateway_url.startswith("ws://") and not gateway_url.startswith("wss://"):
            gateway_url = f"wss://{gateway_url}"
        if not gateway_url.endswith("/"):
            gateway_url += "/"

        request_id = str(uuid.uuid4())
        ws_endpoint = f"{gateway_url}?vm_id={vm_id}&auth_token={auth_token}&app_id=hatch-web&request_id={request_id}"

        print(f"[MuseClient] Connecting to gateway: {gateway_url} (vm_id: {vm_id})...")
        self.ws = await websockets.connect(
            ws_endpoint,
            extra_headers={"User-Agent": DEFAULT_USER_AGENT},
            max_size=10 * 1024 * 1024
        )

        print("[MuseClient] WebSocket connected. Starting Noise_XX handshake...")
        self.initiator = NoiseXXInitiator()

        # 1. Message 1: -> e, payload (client nonce)
        client_nonce = os.urandom(32)
        # In noise.js: a.default.Writer.create().uint32(10).bytes(e).finish()
        msg1_payload = b"\x0a\x20" + client_nonce
        msg1_bytes = self.initiator.write_message_1(msg1_payload)
        t_hash_1 = self.initiator.handshake_hash()
        await self.ws.send(msg1_bytes)

        # 2. Message 2: <- e, ee, s, es, payload (RV challenge / attestation)
        msg2_bytes = await self.ws.recv()
        if isinstance(msg2_bytes, str):
            msg2_bytes = msg2_bytes.encode("latin1")
        challenge_payload = self.initiator.read_message_2(msg2_bytes)
        t_hash_2 = self.initiator.handshake_hash()
        challenge = RvChallenge.decode(challenge_payload)

        # 3. Message 3: -> s, se, payload (RV proof)
        if challenge:
            print(f"[MuseClient] Received CVM challenge (state={challenge.state}). Solving proof...")
            if not self.rv_key:
                raise ValueError("CVM challenge received but rv_key is not configured. Run extract_keys.js in browser console.")
            if not notary_token:
                notary_token = self.fetch_noise_notary_token(vm_id)

            msg3_payload = solve_cvm_challenge(
                challenge=challenge,
                rv_key=self.rv_key,
                notary_token=notary_token,
                transcript_hash_1=t_hash_1,
                transcript_hash_2=t_hash_2,
                client_nonce=client_nonce
            )
        else:
            print("[MuseClient] Standard VM (no CVM challenge). Sending empty Message 3 payload...")
            msg3_payload = b""

        msg3_bytes = self.initiator.write_message_3(msg3_payload)
        await self.ws.send(msg3_bytes)

        # 4. Split handshake state into transport ciphers
        tx, rx = self.initiator.split()
        self.transport = NoiseTransport(tx, rx)
        print("[MuseClient] Noise_XX handshake successfully completed! Transport ready.")

    async def chat_stream(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Sends chat.stream request over the encrypted NoiseTransport and yields streamed events.
        """
        if not self.transport or not self.ws:
            raise RuntimeError("Client is not connected. Call connect() first.")

        session_id = session_id or str(uuid.uuid4())
        msg_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        req_payload = {
            "id": msg_id,
            "role": "user",
            "content": prompt,
            "session_id": session_id,
            "deliveryStatus": "sending",
            "createdAt": created_at,
            "time_zone": "Asia/Ho_Chi_Minh",
        }
        if model:
            req_payload["model"] = model

        headers = [
            ("Content-Type", "application/json"),
            ("x-app-id", "hatch-web"),
            ("x-request-id", str(uuid.uuid4()))
        ]

        stream_id, frames = self.transport.encrypt_http_request(
            verb="POST",
            path="/chat/stream",
            body=json.dumps(req_payload).encode("utf-8"),
            headers=headers
        )

        for frame in frames:
            await self.ws.send(frame)

        # Listen for incoming frames on this stream
        while True:
            raw_msg = await self.ws.recv()
            if isinstance(raw_msg, str):
                raw_msg = raw_msg.encode("latin1")

            service_frame = self.transport.decrypt_frame(raw_msg)
            if not service_frame:
                continue

            if service_frame.stream_id != stream_id:
                continue

            # Check if ApplicationResponse
            if service_frame.HasField("response"):
                resp = service_frame.response
                if resp.body:
                    try:
                        data = json.loads(resp.body.decode("utf-8"))
                        yield {"type": "response", "data": data, "status": resp.status}
                    except Exception:
                        yield {"type": "raw", "data": resp.body}
                if resp.end_body:
                    break

            # Check if BodyChunk (streaming token or event chunk)
            elif service_frame.HasField("body_chunk"):
                chunk = service_frame.body_chunk
                if chunk.data:
                    try:
                        data = json.loads(chunk.data.decode("utf-8"))
                        yield {"type": "chunk", "data": data}
                    except Exception:
                        yield {"type": "raw_chunk", "data": chunk.data}
                if chunk.end_body:
                    break

            # Check if Reset
            elif service_frame.HasField("reset"):
                yield {"type": "reset", "reason": service_frame.reset.reason}
                break

    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
            self.transport = None
