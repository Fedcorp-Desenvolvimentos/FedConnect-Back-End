import base64
import json
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


def decrypt_aes_128_cbc(encrypted_base64: str, aes_key: str) -> Optional[Dict[str, Any]]:
    if not encrypted_base64 or not aes_key:
        return None

    try:
        key = aes_key.encode("utf-8")[:16].ljust(16, b"\0")
        iv = b"\0" * 16

        encrypted_bytes = base64.b64decode(encrypted_base64)

        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted_bytes) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

        return json.loads(decrypted.decode("utf-8"))

    except Exception:
        return None
