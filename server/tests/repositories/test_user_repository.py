import pytest
from datetime import datetime, timedelta

from app.models.user import User, UserToken
from app.repositories.user_repository import UserRepository, UserTokenRepository


class TestUserRepository:
    async def test_find_by_email_returns_user(self, db_session):
        user = User(email="test@example.com", password_hash="hashed", username="testuser")
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        found = await repo.find_by_email("test@example.com")
        assert found is not None
        assert found.email == "test@example.com"

    async def test_find_by_email_returns_none_if_missing(self, db_session):
        repo = UserRepository(db_session)
        found = await repo.find_by_email("notexist@example.com")
        assert found is None

    async def test_find_by_id_returns_user(self, db_session):
        user = User(email="test@example.com", password_hash="hashed", username="testuser")
        db_session.add(user)
        await db_session.commit()

        repo = UserRepository(db_session)
        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.id == user.id

    async def test_find_by_id_returns_none_if_missing(self, db_session):
        import uuid
        repo = UserRepository(db_session)
        found = await repo.find_by_id(uuid.uuid4())
        assert found is None

    async def test_save_persists_user(self, db_session):
        user = User(email="new@example.com", password_hash="hashed", username="newuser")
        repo = UserRepository(db_session)
        await repo.save(user)
        await db_session.commit()

        found = await repo.find_by_email("new@example.com")
        assert found is not None
        assert found.username == "newuser"


class TestUserTokenRepository:
    async def _create_user(self, db_session) -> User:
        user = User(email="tokenuser@example.com", password_hash="hashed", username="tokenuser")
        db_session.add(user)
        await db_session.commit()
        return user

    async def test_find_by_hash_returns_token(self, db_session):
        user = await self._create_user(db_session)
        token = UserToken(
            user_id=user.id,
            token_type="refresh",
            token_hash="abc123hash",
            expires_at=datetime.now() + timedelta(days=7),
        )
        db_session.add(token)
        await db_session.commit()

        repo = UserTokenRepository(db_session)
        found = await repo.find_by_hash("abc123hash", "refresh")
        assert found is not None
        assert found.token_hash == "abc123hash"

    async def test_find_by_hash_returns_none_if_missing(self, db_session):
        repo = UserTokenRepository(db_session)
        found = await repo.find_by_hash("nonexistent", "refresh")
        assert found is None

    async def test_find_by_hash_returns_none_for_wrong_token_type(self, db_session):
        user = await self._create_user(db_session)
        token = UserToken(
            user_id=user.id,
            token_type="refresh",
            token_hash="abc123hash",
            expires_at=datetime.now() + timedelta(days=7),
        )
        db_session.add(token)
        await db_session.commit()

        repo = UserTokenRepository(db_session)
        found = await repo.find_by_hash("abc123hash", "access")
        assert found is None

    async def test_save_persists_token(self, db_session):
        user = await self._create_user(db_session)
        token = UserToken(
            user_id=user.id,
            token_type="refresh",
            token_hash="savehash",
            expires_at=datetime.now() + timedelta(days=7),
        )
        repo = UserTokenRepository(db_session)
        await repo.save(token)
        await db_session.commit()

        found = await repo.find_by_hash("savehash", "refresh")
        assert found is not None

    async def test_delete_removes_token(self, db_session):
        user = await self._create_user(db_session)
        token = UserToken(
            user_id=user.id,
            token_type="refresh",
            token_hash="deletehash",
            expires_at=datetime.now() + timedelta(days=7),
        )
        db_session.add(token)
        await db_session.commit()

        repo = UserTokenRepository(db_session)
        found = await repo.find_by_hash("deletehash", "refresh")
        await repo.delete(found)
        await db_session.commit()

        assert await repo.find_by_hash("deletehash", "refresh") is None
