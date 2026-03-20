import pytest
from unittest.mock import MagicMock

from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.infra.s3 import get_s3_client
from app.main import app


async def make_user(db_session, email="test@example.com") -> User:
    user = User(username="testuser", email=email, password_hash=hash_password("pw"))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def fake_s3():
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://fake-s3.example.com/upload?sig=abc"
    app.dependency_overrides[get_s3_client] = lambda: s3
    yield s3
    app.dependency_overrides.pop(get_s3_client, None)


async def test_presigned_url_without_token_rejected(client):
    """인증 헤더 없이 요청 → 401/403"""
    response = await client.post(
        "/api/v1/objects/presigned-upload-url",
        json={"object_name": "test.mp4"},
    )
    assert response.status_code in (401, 403)


async def test_presigned_url_with_invalid_token_returns_401(client):
    """유효하지 않은 토큰 → 401"""
    response = await client.post(
        "/api/v1/objects/presigned-upload-url",
        headers={"Authorization": "Bearer invalid.token.value"},
        json={"object_name": "test.mp4"},
    )
    assert response.status_code == 401


async def test_presigned_url_with_unknown_user_returns_401(client):
    """DB에 없는 유저의 토큰 → 401"""
    import uuid
    token = create_access_token(str(uuid.uuid4()))
    response = await client.post(
        "/api/v1/objects/presigned-upload-url",
        headers={"Authorization": f"Bearer {token}"},
        json={"object_name": "test.mp4"},
    )
    assert response.status_code == 401


async def test_presigned_url_returns_url_with_valid_auth(client, db_session, fake_s3):
    """유효한 토큰 + S3 mock → 200과 url 반환"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    response = await client.post(
        "/api/v1/objects/presigned-upload-url",
        headers={"Authorization": f"Bearer {token}"},
        json={"object_name": "test.mp4"},
    )

    assert response.status_code == 200
    assert "url" in response.json()


async def test_presigned_url_calls_s3_with_correct_key(client, db_session, fake_s3):
    """S3 generate_presigned_url가 요청한 object_name으로 호출되는지 검증"""
    user = await make_user(db_session)
    token = create_access_token(str(user.id))

    await client.post(
        "/api/v1/objects/presigned-upload-url",
        headers={"Authorization": f"Bearer {token}"},
        json={"object_name": "episode_001.mp4"},
    )

    call_kwargs = fake_s3.generate_presigned_url.call_args
    assert call_kwargs[1]["Params"]["Key"] == "episode_001.mp4"
