"""
Encryption Manager

Provides secure encryption and decryption utilities
for sensitive application data.

Responsibilities
----------------
✓ Encrypt Text
✓ Decrypt Text
✓ Generate Secure Keys
✓ Verify Encryption
✓ Base64 Support
"""

from __future__ import annotations

import base64
import hashlib
import secrets


class EncryptionManager:

    def __init__(self):

        self._secret = secrets.token_bytes(32)

    # --------------------------------------------------

    @staticmethod
    def generate_key(
        length: int = 32,
    ) -> str:

        return secrets.token_hex(length)

    # --------------------------------------------------

    @staticmethod
    def hash_text(
        text: str,
    ) -> str:

        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    # --------------------------------------------------

    def encrypt(
        self,
        plaintext: str,
    ) -> str:

        data = plaintext.encode("utf-8")

        key = self._secret

        encrypted = bytes(

            b ^ key[i % len(key)]

            for i, b in enumerate(data)

        )

        return base64.b64encode(
            encrypted
        ).decode("utf-8")

    # --------------------------------------------------

    def decrypt(
        self,
        ciphertext: str,
    ) -> str:

        encrypted = base64.b64decode(
            ciphertext.encode("utf-8")
        )

        key = self._secret

        decrypted = bytes(

            b ^ key[i % len(key)]

            for i, b in enumerate(encrypted)

        )

        return decrypted.decode("utf-8")

    # --------------------------------------------------

    def verify(
        self,
        plaintext: str,
        ciphertext: str,
    ) -> bool:

        try:

            return (

                self.decrypt(ciphertext)

                == plaintext

            )

        except Exception:

            return False

    # --------------------------------------------------

    @staticmethod
    def encode_base64(
        text: str,
    ) -> str:

        return base64.b64encode(

            text.encode("utf-8")

        ).decode("utf-8")

    # --------------------------------------------------

    @staticmethod
    def decode_base64(
        encoded: str,
    ) -> str:

        return base64.b64decode(

            encoded.encode("utf-8")

        ).decode("utf-8")

    # --------------------------------------------------

    def summary(self):

        return {

            "algorithm": "XOR + Base64",

            "hash_algorithm": "SHA-256",

            "key_size_bytes": len(self._secret),

        }

    # --------------------------------------------------

    def rotate_key(self):

        self._secret = secrets.token_bytes(32)