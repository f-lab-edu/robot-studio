import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_refresh_token,
)
from jose import JWTError


class TestHashPassword:
    def test_returns_nonempty_string(self):
        result = hash_password("mypassword")
        assert isinstance(result, str) and len(result) > 0

    def test_different_calls_produce_different_hashes(self):
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2  # bcrypt은 매번 다른 salt 사용

    def test_verify_correct_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False


class TestAccessToken:
    def test_create_and_decode_roundtrip(self):
        user_id = "test-user-id-123"
        token = create_access_token(user_id)
        payload = decode_access_token(token)
        assert payload["sub"] == user_id

    def test_token_is_string(self):
        token = create_access_token("user-id")
        assert isinstance(token, str)

    def test_invalid_token_raises(self):
        with pytest.raises(JWTError):
            decode_access_token("this.is.invalid")

    def test_tampered_token_raises(self):
        token = create_access_token("user-id")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_access_token(tampered)


class TestRefreshToken:
    def test_returns_nonempty_string(self):
        token = create_refresh_token()
        assert isinstance(token, str) and len(token) > 0

    def test_each_call_returns_unique_token(self):
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2
