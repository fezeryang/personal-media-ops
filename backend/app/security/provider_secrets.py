from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MASTER_KEY_BYTES = 32
NONCE_BYTES = 12
CURRENT_KEY_VERSION = 1


class ProviderSecretDecryptionError(RuntimeError):
    pass


@dataclass(frozen=True)
class EncryptedProviderSecret:
    ciphertext: bytes
    nonce: bytes
    key_version: int = CURRENT_KEY_VERSION


class ProviderSecretCipher:
    def __init__(self, master_key_path: Path) -> None:
        self._master_key_path = master_key_path

    @staticmethod
    def _associated_data(provider_id: str, key_version: int) -> bytes:
        return f"mediaops:model-gateway:v1:{key_version}:{provider_id}".encode()

    def _load_key(self) -> bytes:
        try:
            directory_metadata = self._master_key_path.parent.lstat()
            metadata = self._master_key_path.lstat()
        except FileNotFoundError as error:
            raise RuntimeError("Model gateway master key is not configured") from error
        if not stat.S_ISDIR(directory_metadata.st_mode):
            raise RuntimeError(
                "Model gateway secret directory must be a real directory"
            )
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("Model gateway master key must be a regular file")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise RuntimeError("Model gateway master key must use mode 0600")
        directory_mode = stat.S_IMODE(directory_metadata.st_mode)
        if directory_mode != 0o700:
            raise RuntimeError("Model gateway secret directory must use mode 0700")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self._master_key_path, flags)
        except OSError as error:
            raise RuntimeError("Model gateway master key could not be opened") from error
        try:
            opened_metadata = os.fstat(descriptor)
            if not stat.S_ISREG(opened_metadata.st_mode):
                raise RuntimeError("Model gateway master key must be a regular file")
            key = os.read(descriptor, MASTER_KEY_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(key) != MASTER_KEY_BYTES:
            raise RuntimeError("Model gateway master key must be exactly 32 bytes")
        return key

    def encrypt(
        self,
        provider_id: str,
        api_key: str,
        key_version: int = CURRENT_KEY_VERSION,
    ) -> EncryptedProviderSecret:
        if not api_key or not api_key.isprintable():
            raise ValueError("API key must be printable and non-empty")
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(self._load_key()).encrypt(
            nonce,
            api_key.encode(),
            self._associated_data(provider_id, key_version),
        )
        return EncryptedProviderSecret(
            ciphertext=ciphertext,
            nonce=nonce,
            key_version=key_version,
        )

    def decrypt(
        self,
        provider_id: str,
        ciphertext: bytes,
        nonce: bytes,
        key_version: int,
    ) -> str:
        try:
            plaintext = AESGCM(self._load_key()).decrypt(
                nonce,
                ciphertext,
                self._associated_data(provider_id, key_version),
            )
            return plaintext.decode()
        except (InvalidTag, UnicodeDecodeError, ValueError) as error:
            raise ProviderSecretDecryptionError(
                "Provider credential could not be decrypted"
            ) from error
