from app.core.security import hash_password
from app.models.user import User
from app.services.auth_service import AuthService

async def make_user(db_session, email="test@example.com") -> User:
    user = User(username="testuser", email=email, password_hash=hash_password("pw"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

async def test_issue_code_returns_nonempty_string(db_session, fake_redis):
    """code가 빈 문자열이 아닌 값으로 반환되는지 검증"""
    user = await make_user(db_session)
    service = AuthService(db_session)

    code = await service.issue_code(str(user.id), fake_redis)

    assert isinstance(code, str)
    assert len(code) > 0


async def test_issue_code_stores_user_id_in_redis(db_session, fake_redis):
    """Redis에 auth_code:{code} 키로 user_id가 저장되는지 검증"""
    user = await make_user(db_session)
    service = AuthService(db_session)

    code = await service.issue_code(str(user.id), fake_redis)

    stored = await fake_redis.get(f"auth_code:{code}")
    assert stored == str(user.id)


async def test_issue_code_expires_in_30_seconds(db_session, fake_redis):
    """Redis TTL이 30초로 설정되는지 검증"""
    user = await make_user(db_session)
    service = AuthService(db_session)

    code = await service.issue_code(str(user.id), fake_redis)

    ttl = await fake_redis.ttl(f"auth_code:{code}")
    assert 0 < ttl <= 30


async def test_issue_code_each_call_returns_unique_code(db_session, fake_redis):
    """호출할 때마다 다른 code가 발급되는지 검증"""
    user = await make_user(db_session)
    service = AuthService(db_session)

    code1 = await service.issue_code(str(user.id), fake_redis)
    code2 = await service.issue_code(str(user.id), fake_redis)

    assert code1 != code2

async def test_exchange_code_returns_token_pair(db_session, fake_redis):
    """유효한 code → (access_token, refresh_token) 튜플 반환"""
    user = await make_user(db_session)
    service = AuthService(db_session)
    code = await service.issue_code(str(user.id), fake_redis)

    access_token, refresh_token = await service.exchange_code(code, fake_redis)

    assert isinstance(access_token, str) and len(access_token) > 0
    assert isinstance(refresh_token, str) and len(refresh_token) > 0


async def test_exchange_code_deletes_code_from_redis(db_session, fake_redis):
    """교환 후 Redis에서 code가 삭제되는지 검증"""
    user = await make_user(db_session)
    service = AuthService(db_session)
    code = await service.issue_code(str(user.id), fake_redis)

    await service.exchange_code(code, fake_redis)

    remaining = await fake_redis.get(f"auth_code:{code}")
    assert remaining is None


async def test_exchange_code_is_one_time_use(db_session, fake_redis):
    """같은 code를 두 번 사용하면 두 번째 호출에서 ValueError"""
    user = await make_user(db_session)
    service = AuthService(db_session)
    code = await service.issue_code(str(user.id), fake_redis)

    await service.exchange_code(code, fake_redis)

    try:
        await service.exchange_code(code, fake_redis)
        assert False, "두 번째 exchange_code는 ValueError를 발생시켜야 한다"
    except ValueError:
        pass


async def test_exchange_code_with_invalid_code_raises(db_session, fake_redis):
    """존재하지 않는 code → ValueError"""
    service = AuthService(db_session)

    try:
        await service.exchange_code("nonexistent_code", fake_redis)
        assert False, "ValueError가 발생해야 한다"
    except ValueError:
        pass


# ──────────────────────────────────────────────
# TestSignup
# ──────────────────────────────────────────────

import pytest
from datetime import timedelta
from app.core.security import decode_access_token
from app.models.user import UserToken


class TestSignup:
    async def test_signup_returns_user_with_correct_fields(self, db_session):
        service = AuthService(db_session)
        user = await service.signup("alice", "alice@example.com", "password123")
        assert user.email == "alice@example.com"
        assert user.username == "alice"

    async def test_signup_duplicate_email_raises(self, db_session):
        service = AuthService(db_session)
        await service.signup("alice", "alice@example.com", "password123")
        with pytest.raises(ValueError, match="이미 등록된 이메일"):
            await service.signup("alice2", "alice@example.com", "other")

    async def test_signup_persists_user_in_db(self, db_session):
        from app.repositories.user_repository import UserRepository
        service = AuthService(db_session)
        await service.signup("bob", "bob@example.com", "pw")
        repo = UserRepository(db_session)
        found = await repo.find_by_email("bob@example.com")
        assert found is not None


# ──────────────────────────────────────────────
# TestLogin
# ──────────────────────────────────────────────

class TestLogin:
    async def test_login_returns_token_tuple(self, db_session):
        service = AuthService(db_session)
        await service.signup("carol", "carol@example.com", "mypassword")
        access_token, refresh_token = await service.login("carol@example.com", "mypassword")
        assert isinstance(access_token, str) and len(access_token) > 0
        assert isinstance(refresh_token, str) and len(refresh_token) > 0

    async def test_login_access_token_contains_user_id(self, db_session):
        service = AuthService(db_session)
        user = await service.signup("dave", "dave@example.com", "pw")
        access_token, _ = await service.login("dave@example.com", "pw")
        payload = decode_access_token(access_token)
        assert payload["sub"] == str(user.id)

    async def test_login_refresh_token_saved_in_db(self, db_session):
        from app.repositories.user_repository import UserTokenRepository
        import hashlib
        service = AuthService(db_session)
        await service.signup("eve", "eve@example.com", "pw")
        _, refresh_token = await service.login("eve@example.com", "pw")
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        repo = UserTokenRepository(db_session)
        stored = await repo.find_by_hash(token_hash, "refresh")
        assert stored is not None

    async def test_login_wrong_email_raises(self, db_session):
        service = AuthService(db_session)
        with pytest.raises(ValueError):
            await service.login("nobody@example.com", "pw")

    async def test_login_wrong_password_raises(self, db_session):
        service = AuthService(db_session)
        await service.signup("frank", "frank@example.com", "correct")
        with pytest.raises(ValueError):
            await service.login("frank@example.com", "wrong")


# ──────────────────────────────────────────────
# TestRefresh
# ──────────────────────────────────────────────

class TestRefresh:
    async def _signup_and_login(self, db_session, email="user@example.com"):
        service = AuthService(db_session)
        await service.signup("user", email, "pw")
        access_token, refresh_token = await service.login(email, "pw")
        return service, access_token, refresh_token

    async def test_refresh_returns_new_token_pair(self, db_session):
        service, _, refresh_token = await self._signup_and_login(db_session)
        new_access, new_refresh = await service.refresh(refresh_token)
        assert isinstance(new_access, str) and len(new_access) > 0
        assert isinstance(new_refresh, str) and len(new_refresh) > 0

    async def test_refresh_old_token_deleted(self, db_session):
        import hashlib
        from app.repositories.user_repository import UserTokenRepository
        service, _, refresh_token = await self._signup_and_login(db_session)
        await service.refresh(refresh_token)
        old_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        repo = UserTokenRepository(db_session)
        assert await repo.find_by_hash(old_hash, "refresh") is None

    async def test_refresh_invalid_token_raises(self, db_session):
        service = AuthService(db_session)
        with pytest.raises(ValueError):
            await service.refresh("nonexistent_refresh_token")

    async def test_refresh_expired_token_raises(self, db_session):
        from datetime import datetime
        service, _, refresh_token = await self._signup_and_login(db_session)
        # 저장된 토큰의 expires_at을 과거로 변경
        import hashlib
        from app.repositories.user_repository import UserTokenRepository
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        repo = UserTokenRepository(db_session)
        stored = await repo.find_by_hash(token_hash, "refresh")
        stored.expires_at = datetime.now() - timedelta(seconds=1)
        await db_session.commit()
        with pytest.raises(ValueError, match="만료된 refresh token"):
            await service.refresh(refresh_token)

    async def test_refresh_expired_token_deleted_from_db(self, db_session):
        import hashlib
        from datetime import datetime
        from app.repositories.user_repository import UserTokenRepository
        service, _, refresh_token = await self._signup_and_login(db_session)
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        repo = UserTokenRepository(db_session)
        stored = await repo.find_by_hash(token_hash, "refresh")
        stored.expires_at = datetime.now() - timedelta(seconds=1)
        await db_session.commit()
        try:
            await service.refresh(refresh_token)
        except ValueError:
            pass
        assert await repo.find_by_hash(token_hash, "refresh") is None
