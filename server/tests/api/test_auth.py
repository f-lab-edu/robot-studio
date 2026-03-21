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

async def test_token_exchange_returns_tokens(client, db_session):
    """유효한 code → access_token과 refresh_token 반환"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    issue_resp = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": f"Bearer {token}"},
    )
    code = issue_resp.json()["code"]

    response = await client.post(f"/api/v1/auth/token-exchange?code={code}")

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_token_exchange_code_is_one_time_use(client, db_session):
    """같은 code를 두 번 사용하면 두 번째 요청은 401"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    issue_resp = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": f"Bearer {token}"},
    )
    code = issue_resp.json()["code"]

    await client.post(f"/api/v1/auth/token-exchange?code={code}")
    response = await client.post(f"/api/v1/auth/token-exchange?code={code}")

    assert response.status_code == 401


async def test_token_exchange_with_invalid_code_returns_401(client):
    """존재하지 않는 code → 401"""
    response = await client.post("/api/v1/auth/token-exchange?code=nonexistent_code")
    assert response.status_code == 401


async def test_token_exchange_code_deleted_from_redis(client, db_session, fake_redis):
    """교환 후 Redis에서 code가 삭제되는지 검증"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    issue_resp = await client.post(
        "/api/v1/auth/issue-code",
        headers={"Authorization": f"Bearer {token}"},
    )
    code = issue_resp.json()["code"]

    await client.post(f"/api/v1/auth/token-exchange?code={code}")

    remaining = await fake_redis.get(f"auth_code:{code}")
    assert remaining is None


# ──────────────────────────────────────────────
# signup / login / refresh / me
# ──────────────────────────────────────────────

async def test_signup_returns_201_with_user_info(client):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["username"] == "alice"


async def test_signup_duplicate_email_returns_409(client):
    payload = {"username": "alice", "email": "dup@example.com", "password": "secret"}
    await client.post("/api/v1/auth/signup", json=payload)
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 409


async def test_signup_missing_field_returns_422(client):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"username": "alice"},
    )
    assert response.status_code == 422


async def test_login_returns_200_with_tokens(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"username": "bob", "email": "bob@example.com", "password": "pw"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "pw"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_login_wrong_email_returns_401(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "pw"},
    )
    assert response.status_code == 401


async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"username": "carol", "email": "carol@example.com", "password": "correct"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "carol@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


async def test_refresh_returns_200_with_new_tokens(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"username": "dave", "email": "dave@example.com", "password": "pw"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "dave@example.com", "password": "pw"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


async def test_refresh_invalid_token_returns_401(client):
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_token_value"},
    )
    assert response.status_code == 401


async def test_me_returns_200_with_user_info(client):
    await client.post(
        "/api/v1/auth/signup",
        json={"username": "eve", "email": "eve@example.com", "password": "pw"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "eve@example.com", "password": "pw"},
    )
    access_token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "eve@example.com"


async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_invalid_token_returns_401(client):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401
