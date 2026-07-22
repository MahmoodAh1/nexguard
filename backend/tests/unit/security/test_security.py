"""Unit tests for hashing, JWT, and RBAC."""

from __future__ import annotations

import time

import pytest

from nexguard.domain.entities import User, UserRole
from nexguard.domain.errors import AuthenticationError, AuthorizationError
from nexguard.security.hashing import Argon2PasswordHasher
from nexguard.security.jwt import JwtTokenService
from nexguard.security.rbac import authorize, is_authorized

SECRET = "unit-test-secret-value-that-is-long-enough"


class TestArgon2Hasher:
    def test_hash_is_not_plaintext_and_verifies(self) -> None:
        hasher = Argon2PasswordHasher()
        digest = hasher.hash("s3cr3t-password")
        assert digest != "s3cr3t-password"
        assert digest.startswith("$argon2")
        assert hasher.verify("s3cr3t-password", digest) is True

    def test_wrong_password_fails(self) -> None:
        hasher = Argon2PasswordHasher()
        digest = hasher.hash("correct-horse")
        assert hasher.verify("battery-staple", digest) is False

    def test_malformed_hash_is_rejected_gracefully(self) -> None:
        hasher = Argon2PasswordHasher()
        assert hasher.verify("x", "not-a-real-hash") is False

    def test_empty_password_rejected(self) -> None:
        with pytest.raises(ValueError):
            Argon2PasswordHasher().hash("")


def _user() -> User:
    return User(email="analyst@nexguard.local", password_hash="x", role=UserRole.ANALYST)


class TestJwtTokenService:
    def test_issue_and_decode_round_trip(self) -> None:
        service = JwtTokenService(secret=SECRET)
        user = _user()
        pair = service.issue(user)

        assert pair.token_type == "bearer"
        assert pair.expires_in == 900
        claims = service.decode(pair.access_token)
        assert claims.subject == str(user.id)
        assert claims.email == user.email
        assert claims.role == "analyst"
        assert claims.token_type == "access"

    def test_refresh_token_is_distinguished(self) -> None:
        service = JwtTokenService(secret=SECRET)
        pair = service.issue(_user())
        assert service.decode(pair.refresh_token).token_type == "refresh"

    def test_expired_token_rejected(self) -> None:
        service = JwtTokenService(secret=SECRET, access_ttl_seconds=-1)
        pair = service.issue(_user())
        time.sleep(0.01)
        with pytest.raises(AuthenticationError):
            service.decode(pair.access_token)

    def test_tampered_token_rejected(self) -> None:
        service = JwtTokenService(secret=SECRET)
        pair = service.issue(_user())
        with pytest.raises(AuthenticationError):
            service.decode(pair.access_token + "tamper")

    def test_wrong_secret_rejected(self) -> None:
        pair = JwtTokenService(secret=SECRET).issue(_user())
        with pytest.raises(AuthenticationError):
            JwtTokenService(secret="a-totally-different-secret-value").decode(pair.access_token)


class TestRbac:
    def test_higher_role_authorized(self) -> None:
        authorize(UserRole.ADMIN, UserRole.VIEWER)  # no raise
        authorize(UserRole.ANALYST, UserRole.ANALYST)
        assert is_authorized(UserRole.ADMIN, UserRole.ANALYST)

    def test_insufficient_role_denied(self) -> None:
        with pytest.raises(AuthorizationError):
            authorize(UserRole.VIEWER, UserRole.ANALYST)
        assert not is_authorized(UserRole.ANALYST, UserRole.ADMIN)
