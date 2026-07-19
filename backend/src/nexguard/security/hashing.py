"""Password hashing with Argon2id (memory-hard).

Implements the :class:`~nexguard.domain.ports.PasswordHasher` port. Plaintext
passwords are never stored or logged; the hash embeds its own parameters and
salt, so verification is self-describing and upgrade-safe.
"""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class Argon2PasswordHasher:
    """Argon2id-based hasher."""

    def __init__(self) -> None:
        # Defaults follow argon2-cffi's recommended parameters for interactive use.
        self._hasher = _Argon2()

    def hash(self, password: str) -> str:
        if not password:
            raise ValueError("password must not be empty")
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, ValueError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Whether a stored hash uses outdated parameters and should be upgraded."""
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except (InvalidHashError, ValueError):
            return False
