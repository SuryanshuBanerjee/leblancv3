"""Reference solution for S022 (CWE-329 — CBC with a non-random/static IV).
Secure: generate a fresh random IV per encryption and prepend it to the ciphertext
so decryption is still possible. Uses PKCS7 padding. Returns iv||ciphertext bytes."""
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


def getEncryptionKey(key):
    """Encrypt `key` (bytes) under AES-CBC with a random IV; return iv||ciphertext."""
    if isinstance(key, str):
        key = key.encode("utf-8")
    aes_key = os.urandom(32)          # 256-bit key material
    iv = os.urandom(16)              # fresh random IV — the fix for CWE-329
    padder = PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(key) + padder.finalize()
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    enc = cipher.encryptor()
    ct = enc.update(padded) + enc.finalize()
    return iv + ct
