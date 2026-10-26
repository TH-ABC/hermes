"""
CVM (Confidential Virtual Machine) Remote Verification challenge solver for Muse.ai.
Implements the exact cryptographic formulas from noise.js and 18sj5t_gn8_oc.js.
"""

import hmac
import hashlib
from typing import Optional, Tuple
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

L_KEY = b"hatch.noise-auth.key.v1"
C_VM_KEY = b"vm-proof-key"
H_CLIENT_KEY = b"client-proof-key"
D_VM_PROOF = b"hatch.noise-auth.vm-proof.v1"
U_CLIENT_PROOF = b"hatch.noise-auth.client-proof.v1"

def derive_cvm_rv_key(recovery_secret: bytes, vm_id: str) -> bytes:
    """
    Derives 32-byte CVM RV Key (krv) from the Vesta recovery secret and VM ID.
    Formula: HKDF-SHA256(secret, salt=b'', info=f'hatch:rv-luks:v1:{vm_id}', length=32)
    """
    assert len(recovery_secret) == 32, "Recovery secret must be 32 bytes"
    info = f"hatch:rv-luks:v1:{vm_id.strip()}".encode("utf-8")
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"",
        info=info
    )
    return hkdf.derive(recovery_secret)

class RvChallenge:
    def __init__(self, attestation: bytes, state: int, vm_nonce: bytes, vm_proof: Optional[bytes] = None):
        self.attestation = attestation
        self.state = state  # 1: unprovisioned, 2: provisioned
        self.vm_nonce = vm_nonce
        self.vm_proof = vm_proof

    @classmethod
    def decode(cls, data: bytes) -> Optional["RvChallenge"]:
        """Parses protobuf RV challenge returned in Message 2."""
        import io
        stream = io.BytesIO(data)
        attestation = None
        state = None
        vm_nonce = None
        vm_proof = None

        while stream.tell() < len(data):
            tag_byte = stream.read(1)
            if not tag_byte:
                break
            key = ord(tag_byte)
            field_num = key >> 3
            wire_type = key & 7

            if wire_type == 2:  # Length-delimited (bytes/string)
                length = ord(stream.read(1))
                val = stream.read(length)
                if field_num == 1:
                    attestation = val
                elif field_num == 3:
                    vm_nonce = val
                elif field_num == 4:
                    vm_proof = val
            elif wire_type == 0:  # Varint
                val = ord(stream.read(1))
                if field_num == 2:
                    state = val
            else:
                break

        if attestation is None or vm_nonce is None or len(vm_nonce) != 32 or state not in (1, 2):
            return None

        return cls(attestation, state, vm_nonce, vm_proof)

def solve_cvm_challenge(
    challenge: RvChallenge,
    rv_key: bytes,
    notary_token: str,
    transcript_hash_1: bytes,
    transcript_hash_2: bytes,
    client_nonce: bytes
) -> bytes:
    """
    Verifies server's VM proof (if provisioned) and constructs Message 3 payload.
    """
    assert len(rv_key) == 32
    assert len(transcript_hash_1) == 32
    assert len(transcript_hash_2) == 32
    assert len(client_nonce) == 32

    # Helper: HMAC(rvKey, L_KEY + subkey)
    def derive_sub_key(sub_name: bytes) -> bytes:
        return hmac.new(rv_key, L_KEY + sub_name, hashlib.sha256).digest()

    if challenge.state == 1:
        # Unprovisioned: sends fresh rvKey directly
        return _encode_msg3_payload(notary_token, kind="fresh", proof_bytes=rv_key)

    # 1. Verify VM proof from server
    vm_proof_key = derive_sub_key(C_VM_KEY)
    expected_vm_proof = hmac.new(
        vm_proof_key,
        D_VM_PROOF + transcript_hash_1 + client_nonce + challenge.vm_nonce,
        hashlib.sha256
    ).digest()

    if not challenge.vm_proof or not hmac.compare_digest(expected_vm_proof, challenge.vm_proof):
        raise ValueError("CVM remote verification failed: server VM proof rejected")

    # 2. Compute client proof for Message 3
    client_proof_key = derive_sub_key(H_CLIENT_KEY)
    client_proof = hmac.new(
        client_proof_key,
        U_CLIENT_PROOF + transcript_hash_2 + challenge.vm_nonce + client_nonce,
        hashlib.sha256
    ).digest()

    return _encode_msg3_payload(notary_token, kind="proof", proof_bytes=client_proof)

def _encode_msg3_payload(notary_token: str, kind: str, proof_bytes: bytes) -> bytes:
    """Encodes protobuf payload for Message 3: field 1: notary_token, field 2 or 3: bytes."""
    token_bytes = notary_token.strip().encode("utf-8")
    res = bytearray()

    # Field 1 (tag 10 = (1 << 3) | 2): notary_token
    res.append(10)
    res.append(len(token_bytes))
    res.extend(token_bytes)

    # Field 2 (tag 18 = (2 << 3) | 2) for fresh, or Field 3 (tag 26 = (3 << 3) | 2) for proof
    tag = 18 if kind == "fresh" else 26
    res.append(tag)
    res.append(len(proof_bytes))
    res.extend(proof_bytes)

    return bytes(res)
