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
