import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from robot_ui.utils.api_client import ApiClient


def make_mock_response(status=200, json_data=None):
    """aiohttp response mock 헬퍼"""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    response.raise_for_status = MagicMock()
    return response


def make_cm(response):
    """aiohttp async context manager mock 헬퍼"""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# 단위 테스트 (HTTP 없음)

def test_set_token_stores_token():
    """set_token 호출 후 _token에 값이 저장되는지 검증"""
    client = ApiClient()
    client.set_token("my.jwt.token")
    assert client._token == "my.jwt.token"


def test_auth_headers_returns_bearer_when_token_set():
    """토큰이 설정된 경우 Authorization 헤더 반환"""
    client = ApiClient()
    client.set_token("my.jwt.token")
    assert client._auth_headers() == {"Authorization": "Bearer my.jwt.token"}


def test_auth_headers_returns_empty_when_no_token():
    """토큰이 없으면 빈 dict 반환"""
    client = ApiClient()
    assert client._auth_headers() == {}


# exchange_code 테스트

async def test_exchange_code_returns_token_dict():
    """유효한 code → access_token, refresh_token 포함된 dict 반환"""
    client = ApiClient()
    token_data = {"access_token": "acc.tok", "refresh_token": "ref.tok"}
    response = make_mock_response(status=200, json_data=token_data)

    with patch.object(client.session, "post", return_value=make_cm(response)):
        result = await client.exchange_code("valid-code-abc")

    assert result["access_token"] == "acc.tok"
    assert result["refresh_token"] == "ref.tok"


async def test_exchange_code_raises_on_401():
    """서버가 401 반환 → ValueError 발생"""
    client = ApiClient()
    response = make_mock_response(status=401)

    with patch.object(client.session, "post", return_value=make_cm(response)):
        with pytest.raises(ValueError):
            await client.exchange_code("expired-code")


async def test_exchange_code_sends_code_as_query_param():
    """code가 query param으로 전달되는지 검증"""
    client = ApiClient()
    response = make_mock_response(status=200, json_data={"access_token": "a", "refresh_token": "b"})
    mock_post = MagicMock(return_value=make_cm(response))

    with patch.object(client.session, "post", mock_post):
        await client.exchange_code("test-code-xyz")

    assert mock_post.call_args[1]["params"] == {"code": "test-code-xyz"}


# get_presigned_url 테스트

async def test_get_presigned_url_returns_url():
    """서버 응답에서 url 값을 반환하는지 검증"""
    client = ApiClient()
    client.set_token("my.jwt.token")
    response = make_mock_response(
        status=200,
        json_data={"url": "https://fake-s3.example.com/upload?sig=abc"},
    )

    with patch.object(client.session, "post", return_value=make_cm(response)):
        url = await client.get_presigned_url("episode_001.mp4")

    assert url == "https://fake-s3.example.com/upload?sig=abc"


async def test_get_presigned_url_sends_auth_header():
    """요청에 Authorization 헤더가 포함되는지 검증"""
    client = ApiClient()
    client.set_token("my.jwt.token")
    response = make_mock_response(
        status=200,
        json_data={"url": "https://fake-s3.example.com/upload?sig=abc"},
    )
    mock_post = MagicMock(return_value=make_cm(response))

    with patch.object(client.session, "post", mock_post):
        await client.get_presigned_url("episode_001.mp4")

    assert mock_post.call_args[1]["headers"] == {"Authorization": "Bearer my.jwt.token"}


async def test_get_presigned_url_without_token_sends_no_auth_header():
    """토큰 없이 요청 시 Authorization 헤더가 없는지 검증"""
    client = ApiClient()
    response = make_mock_response(
        status=200,
        json_data={"url": "https://fake-s3.example.com/upload?sig=abc"},
    )
    mock_post = MagicMock(return_value=make_cm(response))

    with patch.object(client.session, "post", mock_post):
        await client.get_presigned_url("episode_001.mp4")

    assert mock_post.call_args[1]["headers"] == {}
