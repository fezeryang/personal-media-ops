from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
_dummy_hash = _password_hash.hash("mediaops-dummy-password-not-a-credential")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return _password_hash.verify(password, encoded)


def verify_dummy_password(password: str) -> None:
    _password_hash.verify(password, _dummy_hash)
