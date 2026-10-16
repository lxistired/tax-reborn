"""Finite AES-CBC decryptor for a caller-provided PersistenceContainer member key.

This independently written pure-Python primitive represents only observed
AES-CBC/PKCS#7 member decryption. It never contains or derives a vendor key,
never reads a .tax file, and never bypasses activation, licensing, or password
workflows. A real encrypted-container reader remains closed until separately
authorized key material and manifest integration are proven.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
_BLOCK = 16

class CryptoInputError(ValueError):
    """Malformed cryptographic input or invalid PKCS#7 payload."""

def _mul(a: int, b: int) -> int:
    out = 0
    while b:
        if b & 1: out ^= a
        a = ((a << 1) ^ (0x11B if a & 0x80 else 0)) & 0xFF
        b >>= 1
    return out

def _pow(a: int, n: int) -> int:
    out = 1
    while n:
        if n & 1: out = _mul(out, a)
        a = _mul(a, a); n >>= 1
    return out

def _rot8(a: int, n: int) -> int:
    return ((a << n) | (a >> (8 - n))) & 0xFF

def _sbox(a: int) -> int:
    inv = 0 if a == 0 else _pow(a, 254)
    return inv ^ _rot8(inv, 1) ^ _rot8(inv, 2) ^ _rot8(inv, 3) ^ _rot8(inv, 4) ^ 0x63

_SBOX = tuple(_sbox(i) for i in range(256))
_INV_SBOX = tuple(next(i for i, value in enumerate(_SBOX) if value == wanted) for wanted in range(256))

def _expand_key(key: bytes) -> tuple[bytes, ...]:
    if len(key) not in (16, 24, 32):
        raise CryptoInputError("AES key must be exactly 16, 24, or 32 bytes")
    nk, nr = len(key) // 4, len(key) // 4 + 6
    words = [list(key[i:i + 4]) for i in range(0, len(key), 4)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        temp = words[-1][:]
        if i % nk == 0:
            temp = [_SBOX[temp[(j + 1) % 4]] for j in range(4)]
            temp[0] ^= rcon; rcon = _mul(rcon, 2)
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[v] for v in temp]
        words.append([words[i - nk][j] ^ temp[j] for j in range(4)])
    return tuple(bytes(sum(words[i:i + 4], [])) for i in range(0, len(words), 4))

def _add_key(state: list[int], key: bytes) -> None:
    for i, value in enumerate(key): state[i] ^= value

def _inv_shift_rows(state: list[int]) -> None:
    old = state[:]
    for column in range(4):
        for row in range(4):
            state[4 * column + row] = old[4 * ((column - row) % 4) + row]

def _inv_sub_bytes(state: list[int]) -> None:
    for i, value in enumerate(state): state[i] = _INV_SBOX[value]

def _inv_mix_columns(state: list[int]) -> None:
    for column in range(4):
        i = 4 * column; a0, a1, a2, a3 = state[i:i + 4]
        state[i] = _mul(14,a0)^_mul(11,a1)^_mul(13,a2)^_mul(9,a3)
        state[i+1] = _mul(9,a0)^_mul(14,a1)^_mul(11,a2)^_mul(13,a3)
        state[i+2] = _mul(13,a0)^_mul(9,a1)^_mul(14,a2)^_mul(11,a3)
        state[i+3] = _mul(11,a0)^_mul(13,a1)^_mul(9,a2)^_mul(14,a3)

def decrypt_aes_block(block: bytes, key: bytes) -> bytes:
    if len(block) != _BLOCK: raise CryptoInputError("AES block must be exactly 16 bytes")
    rounds = _expand_key(key); state = list(block); _add_key(state, rounds[-1])
    for round_key in reversed(rounds[1:-1]):
        _inv_shift_rows(state); _inv_sub_bytes(state); _add_key(state, round_key); _inv_mix_columns(state)
    _inv_shift_rows(state); _inv_sub_bytes(state); _add_key(state, rounds[0])
    return bytes(state)

def decrypt_aes_cbc_blocks(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(iv) != _BLOCK: raise CryptoInputError("AES-CBC IV must be exactly 16 bytes")
    if not ciphertext or len(ciphertext) % _BLOCK: raise CryptoInputError("ciphertext must contain one or more complete AES blocks")
    previous, out = iv, bytearray()
    for start in range(0, len(ciphertext), _BLOCK):
        block = ciphertext[start:start + _BLOCK]
        out.extend(a ^ b for a, b in zip(decrypt_aes_block(block, key), previous)); previous = block
    return bytes(out)

def decrypt_aes_cbc_pkcs7(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    padded = decrypt_aes_cbc_blocks(ciphertext, key, iv); pad = padded[-1]
    if pad < 1 or pad > _BLOCK or padded[-pad:] != bytes([pad]) * pad:
        raise CryptoInputError("invalid PKCS#7 padding")
    return padded[:-pad]

def decrypt_member_from_base64(ciphertext: bytes, key_b64: str, iv_b64: str) -> bytes:
    try:
        key, iv = base64.b64decode(key_b64, validate=True), base64.b64decode(iv_b64, validate=True)
    except Exception as exc:
        raise CryptoInputError("key and IV must be strict base64") from exc
    return decrypt_aes_cbc_pkcs7(ciphertext, key, iv)

@dataclass(frozen=True)
class CryptoBoundary:
    algorithm: str = "AES-CBC with PKCS#7 padding"
    key_source: str = "caller-provided only"
    key_derivation: str = "not implemented"
    encrypted_tax_container_reader: bool = False
    native_execution: bool = False
