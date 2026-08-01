import os
from pathlib import Path

import pytest

from app.security.provider_secrets import (
    ProviderSecretCipher,
    ProviderSecretDecryptionError,
)


def _synthetic_key(*parts: str) -> str:
    return "-".join(parts)


SYNTHETIC_PROVIDER_SECRET = _synthetic_key(
    "synthetic",
    "provider",
    "secret",
)


def _master_key(path: Path) -> Path:
    path.parent.mkdir(mode=0o700)
    path.write_bytes(os.urandom(32))
    path.chmod(0o600)
    return path


def test_provider_secret_round_trip_never_contains_plaintext(tmp_path: Path) -> None:
    cipher = ProviderSecretCipher(_master_key(tmp_path / "secrets" / "master.key"))

    encrypted = cipher.encrypt(
        provider_id="provider-1",
        api_key=SYNTHETIC_PROVIDER_SECRET,
        key_version=1,
    )

    assert len(encrypted.nonce) == 12
    assert SYNTHETIC_PROVIDER_SECRET.encode() not in encrypted.ciphertext
    assert (
        cipher.decrypt(
            provider_id="provider-1",
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            key_version=1,
        )
        == SYNTHETIC_PROVIDER_SECRET
    )


@pytest.mark.parametrize("field", ["ciphertext", "nonce"])
def test_provider_secret_tampering_fails_closed(
    tmp_path: Path,
    field: str,
) -> None:
    cipher = ProviderSecretCipher(_master_key(tmp_path / "secrets" / "master.key"))
    encrypted = cipher.encrypt("provider-1", SYNTHETIC_PROVIDER_SECRET)
    value = bytearray(getattr(encrypted, field))
    value[0] ^= 0x01
    payload = {
        "ciphertext": encrypted.ciphertext,
        "nonce": encrypted.nonce,
    }
    payload[field] = bytes(value)

    with pytest.raises(ProviderSecretDecryptionError, match="could not be decrypted"):
        cipher.decrypt(provider_id="provider-1", key_version=1, **payload)


def test_provider_secret_is_bound_to_provider_and_key_version(tmp_path: Path) -> None:
    cipher = ProviderSecretCipher(_master_key(tmp_path / "secrets" / "master.key"))
    encrypted = cipher.encrypt("provider-1", SYNTHETIC_PROVIDER_SECRET)

    with pytest.raises(ProviderSecretDecryptionError):
        cipher.decrypt(
            provider_id="provider-2",
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            key_version=1,
        )
    with pytest.raises(ProviderSecretDecryptionError):
        cipher.decrypt(
            provider_id="provider-1",
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
            key_version=2,
        )


def test_master_key_permissions_and_length_are_verified(tmp_path: Path) -> None:
    path = _master_key(tmp_path / "secrets" / "master.key")
    path.chmod(0o644)

    with pytest.raises(RuntimeError, match="0600"):
        ProviderSecretCipher(path).encrypt("provider-1", "secret")

    path.chmod(0o600)
    path.write_bytes(b"too-short")
    with pytest.raises(RuntimeError, match="32 bytes"):
        ProviderSecretCipher(path).encrypt("provider-1", "secret")


def test_master_key_and_secret_directory_symlinks_are_rejected(tmp_path: Path) -> None:
    real_key = _master_key(tmp_path / "real-secrets" / "master.key")
    linked_key = tmp_path / "real-secrets" / "linked.key"
    linked_key.symlink_to(real_key)
    with pytest.raises(RuntimeError, match="regular file"):
        ProviderSecretCipher(linked_key).encrypt("provider-1", "secret")

    linked_directory = tmp_path / "linked-secrets"
    linked_directory.symlink_to(real_key.parent, target_is_directory=True)
    with pytest.raises(RuntimeError, match="real directory"):
        ProviderSecretCipher(linked_directory / "master.key").encrypt(
            "provider-1",
            "secret",
        )
