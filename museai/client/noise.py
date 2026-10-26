"""
Noise Protocol implementation for Muse.ai (Hatch / Abra).
Protocol: Noise_XX_25519_AESGCM_SHA256
"""

import hashlib
import hmac
import struct
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PROTOCOL_NAME = b"Noise_XX_25519_AESGCM_SHA256"

def hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()

def hkdf_extract_and_expand_2(ck: bytes, data: bytes) -> Tuple[bytes, bytes]:
    """HKDF-style key derivation matching p(this.#h, e, 2) in noise.js."""
    prk = hmac_sha256(ck, data)
    t1 = hmac_sha256(prk, b"\x01")
    t2 = hmac_sha256(prk, t1 + b"\x02")
    return t1, t2

def hkdf_extract_and_expand_3(ck: bytes, data: bytes) -> Tuple[bytes, bytes, bytes]:
    """HKDF-style key derivation matching p(this.#h, e, 3) in noise.js."""
    prk = hmac_sha256(ck, data)
    t1 = hmac_sha256(prk, b"\x01")
    t2 = hmac_sha256(prk, t1 + b"\x02")
    t3 = hmac_sha256(prk, t2 + b"\x03")
    return t1, t2, t3

class CipherState:
    """AES-GCM-256 state with 12-byte big-endian sequence nonce."""
    def __init__(self, key: Optional[bytes] = None):
        self.key: Optional[bytes] = None
        self.aes: Optional[AESGCM] = None
        self.nonce_counter: int = 0
        if key:
            self.initialize_key(key)

    def initialize_key(self, key: bytes):
        assert len(key) == 32, "AES-256 key must be 32 bytes"
        self.key = key
        self.aes = AESGCM(key)
        self.nonce_counter = 0

    @property
    def has_key(self) -> bool:
        return self.aes is not None

    def _build_nonce(self) -> bytes:
        # Match function A(e) in noise.js: 12 bytes with 64-bit uint at byte offset 4
        # Offset 0..3: 0x00, Offset 4..11: uint64 big endian
        return b"\x00\x00\x00\x00" + struct.pack(">Q", self.nonce_counter)

    def encrypt_with_ad(self, ad: bytes, plaintext: bytes) -> bytes:
        if not self.has_key:
            return plaintext
        nonce = self._build_nonce()
        self.nonce_counter += 1
        return self.aes.encrypt(nonce, plaintext, ad)

    def decrypt_with_ad(self, ad: bytes, ciphertext: bytes) -> bytes:
        if not self.has_key:
            return ciphertext
        nonce = self._build_nonce()
        self.nonce_counter += 1
        return self.aes.decrypt(nonce, ciphertext, ad)

class SymmetricState:
    """Noise SymmetricState managing handshake hash and chaining key."""
    def __init__(self):
        self.h: bytes = b""
        self.ck: bytes = b""
        self.cipher = CipherState()
        self.initialize()

    def initialize(self):
        # In noise.js:
        # e = "Noise_XX_25519_AESGCM_SHA256"
        # t = new Uint8Array(32); t.set(e);
        # this.#d = t (h); this.#h = t (ck)
        # mixHash(empty)
        init_bytes = PROTOCOL_NAME.ljust(32, b"\x00")
        self.h = init_bytes
        self.ck = init_bytes
        self.mix_hash(b"")

    def mix_hash(self, data: bytes):
        self.h = hashlib.sha256(self.h + data).digest()

    def mix_key(self, input_key_material: bytes):
        self.ck, temp_k = hkdf_extract_and_expand_2(self.ck, input_key_material)
        self.cipher.initialize_key(temp_k)

    def encrypt_and_hash(self, plaintext: bytes) -> bytes:
        ciphertext = self.cipher.encrypt_with_ad(self.h, plaintext)
        self.mix_hash(ciphertext)
        return ciphertext

    def decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        plaintext = self.cipher.decrypt_with_ad(self.h, ciphertext)
        self.mix_hash(ciphertext)
        return plaintext

    def split(self) -> Tuple[CipherState, CipherState]:
        # In noise.js: [e, t] = p(this.#h, new Uint8Array(0), 2)
        k1, k2 = hkdf_extract_and_expand_2(self.ck, b"")
        tx = CipherState(k1)
        rx = CipherState(k2)
        return tx, rx

    def handshake_hash(self) -> bytes:
        return self.h

class NoiseXXInitiator:
    """
    Noise_XX Handshake Initiator:
    -> e
    <- e, ee, s, es
    -> s, se
    """
    def __init__(self):
        self.state = SymmetricState()
        self.ephemeral_priv: Optional[x25519.X25519PrivateKey] = None
        self.ephemeral_pub_bytes: bytes = b""
        self.remote_ephemeral_pub: bytes = b""
        self.remote_static_pub: bytes = b""
        self.static_priv: Optional[x25519.X25519PrivateKey] = None
        self.static_pub_bytes: bytes = b""
        self.phase = 0

    def write_message_1(self, payload: bytes = b"") -> bytes:
        """
        Message 1: Client sends ephemeral public key + encrypted payload (client nonce).
        Pattern: -> e, payload
        """
        assert self.phase == 0, f"Wrong phase: {self.phase}"
        self.ephemeral_priv = x25519.X25519PrivateKey.generate()
        self.ephemeral_pub_bytes = self.ephemeral_priv.public_key().public_bytes_raw()

        self.state.mix_hash(self.ephemeral_pub_bytes)
        c = self.state.encrypt_and_hash(payload)
        self.phase = 1
        return self.ephemeral_pub_bytes + c

    def read_message_2(self, msg2: bytes) -> bytes:
        """
        Message 2: Server sends remote ephemeral key, remote static key, and payload (attestation/challenge).
        Pattern: <- e, ee, s, es, payload
        """
        assert self.phase == 1, f"Wrong phase: {self.phase}"
        assert len(msg2) >= 96, f"Message 2 too short: {len(msg2)} < 96"

        # 1. Read remote ephemeral (32 bytes)
        self.remote_ephemeral_pub = msg2[:32]
        self.state.mix_hash(self.remote_ephemeral_pub)

        # 2. DH(e, re) -> mixKey
        re_obj = x25519.X25519PublicKey.from_public_bytes(self.remote_ephemeral_pub)
        ee = self.ephemeral_priv.exchange(re_obj)
        self.state.mix_key(ee)

        # 3. Read & decrypt remote static (32 bytes + 16 bytes tag = 48 bytes)
        s_encrypted = msg2[32:80]
        self.remote_static_pub = self.state.decrypt_and_hash(s_encrypted)

        # 4. DH(e, rs) -> mixKey
        rs_obj = x25519.X25519PublicKey.from_public_bytes(self.remote_static_pub)
        es = self.ephemeral_priv.exchange(rs_obj)
        self.state.mix_key(es)

        # 5. Decrypt remote payload (RV challenge / attestation)
        payload_encrypted = msg2[80:]
        payload = self.state.decrypt_and_hash(payload_encrypted)

        self.phase = 2
        return payload

    def write_message_3(self, payload: bytes = b"") -> bytes:
        """
        Message 3: Client sends encrypted static key and encrypted payload (RV proof).
        Pattern: -> s, se, payload
        """
        assert self.phase == 2, f"Wrong phase: {self.phase}"
        self.static_priv = x25519.X25519PrivateKey.generate()
        self.static_pub_bytes = self.static_priv.public_key().public_bytes_raw()

        # 1. Encrypt static pub
        s_encrypted = self.state.encrypt_and_hash(self.static_pub_bytes)

        # 2. DH(s, re) -> mixKey
        re_obj = x25519.X25519PublicKey.from_public_bytes(self.remote_ephemeral_pub)
        se = self.static_priv.exchange(re_obj)
        self.state.mix_key(se)

        # 3. Encrypt payload
        payload_encrypted = self.state.encrypt_and_hash(payload)

        self.phase = 3
        return s_encrypted + payload_encrypted

    def split(self) -> Tuple[CipherState, CipherState]:
        """Completes the handshake and returns (transmit_cipher, receive_cipher)."""
        assert self.phase == 3, f"Wrong phase: {self.phase}"
        self.phase = 4
        return self.state.split()

    def handshake_hash(self) -> bytes:
        return self.state.handshake_hash()
