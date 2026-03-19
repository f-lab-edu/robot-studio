import uuid
from app.core.security import create_access_token, hash_password
from app.models.user import User

async def make_user(db_session, email="test@example.com") -> User:
    user = User(username="testuser", email=email, password_hash=hash_password("pw"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

async def test_issue_code_returns_code(client, db_session, fake_redis):
    """정상 요청 → code 필드가 있는 응답 반환"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    response = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "code" in response.json()


async def test_issue_code_stores_user_id_in_redis(client, db_session, fake_redis):
    """발급된 code로 Redis를 조회하면 user_id가 저장돼 있어야 한다"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    response = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": f"Bearer {token}"},
    )

    code = response.json()["code"]
    stored = await fake_redis.get(f"auth_code:{code}")
    assert stored == str(user.id)


async def test_issue_code_without_token_rejected(client):
    """인증 헤더 없음 → 4xx 반환"""
    response = await client.post("/api/v1/auth/issue-code")
    assert response.status_code in (401, 403)


async def test_issue_code_with_invalid_token_returns_401(client):
    """유효하지 않은 토큰 → 401"""
    response = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


async def test_issue_code_with_unknown_user_returns_401(client):
    """DB에 없는 유저의 토큰 → 401"""
    token = create_access_token(str(uuid.uuid4()))
    response = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
