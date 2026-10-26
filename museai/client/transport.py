"""
Noise Transport Framing & Stream Multiplexing for Muse.ai.
Handles chunking, reassembly, AES-GCM transport encryption, and Protobuf envelope dispatch.
"""

import math
import os
import struct
import random
from typing import List, Dict, Optional, Tuple, AsyncIterator
from client.noise import CipherState
from client.proto.noise_pb2 import (
    NoiseTransportFrame,
    ServiceRequest,
    ServiceResponse,
    ServiceFrame,
    Header,
    ApplicationRequest,
    ApplicationResponse,
    BodyChunk,
    Reset,
    SERVICE_DAEMON
)

MAX_CHUNK_SIZE = 65489

class FrameAssembly:
    def __init__(self, total_chunks: int):
        self.total_chunks = total_chunks
        self.chunks: Dict[int, bytes] = {}

    def add_chunk(self, index: int, data: bytes) -> bool:
        self.chunks[index] = data
        return len(self.chunks) == self.total_chunks

    def reassemble(self) -> bytes:
        return b"".join(self.chunks[i] for i in range(self.total_chunks))

class NoiseTransport:
    def __init__(self, tx_cipher: CipherState, rx_cipher: CipherState):
        self.tx = tx_cipher
        self.rx = rx_cipher
        self._next_stream_id = 1
        self._assemblies: Dict[int, FrameAssembly] = {}

    def encrypt_http_request(
        self,
        verb: str,
        path: str,
        body: bytes = b"",
        headers: Optional[List[Tuple[str, str]]] = None,
        service: int = SERVICE_DAEMON
    ) -> Tuple[int, List[bytes]]:
        """
        Encrypts an ApplicationRequest into one or more AES-GCM encrypted binary frames.
        Returns: (stream_id, list_of_encrypted_frame_bytes)
        """
        stream_id = self._next_stream_id
        self._next_stream_id += 1

        proto_headers = []
        if headers:
            for k, v in headers:
                proto_headers.append(Header(key=k, value=v))

        app_req = ApplicationRequest(
            verb=verb,
            path=path,
            headers=proto_headers,
            body=body,
            end_body=True
        )

        service_frame = ServiceFrame(
            stream_id=stream_id,
            request=app_req
        )

        service_req = ServiceRequest(
            service=service,
            payload=service_frame.SerializeToString()
        )

        payload_bytes = service_req.SerializeToString()
        total_chunks = max(1, math.ceil(len(payload_bytes) / MAX_CHUNK_SIZE))
        chunk_id = random.getrandbits(63)

        encrypted_frames = []
        for i in range(total_chunks):
            start = i * MAX_CHUNK_SIZE
            chunk_slice = payload_bytes[start : start + MAX_CHUNK_SIZE]

            t_frame = NoiseTransportFrame(
                chunk_id=chunk_id,
                chunk_index=i,
                total_chunks=total_chunks,
                payload=chunk_slice
            )
            frame_bytes = t_frame.SerializeToString()
            # In noise.js line 748: await this.#S.encryptWithAd(F=empty, e)
            encrypted = self.tx.encrypt_with_ad(b"", frame_bytes)
            encrypted_frames.append(encrypted)

        return stream_id, encrypted_frames

    def decrypt_frame(self, encrypted_bytes: bytes) -> Optional[ServiceFrame]:
        """
        Decrypts an incoming WebSocket frame and reassembles chunks.
        Returns the parsed ServiceFrame once all chunks for a frame are collected.
        """
        decrypted = self.rx.decrypt_with_ad(b"", encrypted_bytes)
        t_frame = NoiseTransportFrame.FromString(decrypted)

        chunk_id = t_frame.chunk_id
        if chunk_id not in self._assemblies:
            self._assemblies[chunk_id] = FrameAssembly(t_frame.total_chunks)

        assembly = self._assemblies[chunk_id]
        if assembly.add_chunk(t_frame.chunk_index, t_frame.payload):
            full_payload = assembly.reassemble()
            del self._assemblies[chunk_id]

            service_resp = ServiceResponse.FromString(full_payload)
            service_frame = ServiceFrame.FromString(service_resp.payload)
            return service_frame

        return None
