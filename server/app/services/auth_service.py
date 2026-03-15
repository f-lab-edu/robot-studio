import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, create_access_token, verify_password, create_refresh_token
from app.models.user import User, UserToken
from app.repositories.user_repository import UserRepository, UserTokenRepository

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = UserTokenRepository(db)

    def _hash_token(self, token: str) -> str:
        """refresh token을 SHA-256으로 해시"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token()

        user_token = UserToken(
            user_id=user.id,
            token_type="refresh",
            token_hash=self._hash_token(refresh_token),
            expires_at=datetime.now() + timedelta(days=7),
        )
        await self.token_repo.save(user_token)
        await self.db.commit()

        return access_token, refresh_token

    async def signup(self, username: str, email: str, password: str) -> User:
        if await self.user_repo.find_by_email(email):
            raise ValueError("이미 등록된 이메일입니다")

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        await self.user_repo.save(user)
        await self.db.commit()

        return user

    async def login(self, email: str, password: str) -> tuple[str, str]:
        user = await self.user_repo.find_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("이메일 또는 비밀번호가 올바르지 않습니다")

        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        token_hash = self._hash_token(refresh_token)

        stored_token = await self.token_repo.find_by_hash(token_hash, "refresh")
        if not stored_token:
            raise ValueError("유효하지 않은 refresh token입니다")

        if stored_token.expires_at and stored_token.expires_at < datetime.now():
            await self.token_repo.delete(stored_token)
            await self.db.commit()
            raise ValueError("만료된 refresh token입니다")

        await self.token_repo.delete(stored_token)

        user = await self.user_repo.find_by_id(stored_token.user_id)
        if not user:
            raise ValueError("사용자를 찾을 수 없습니다")

        return await self._issue_tokens(user)

    async def issue_code(self, user_id: str, redis) -> str:
        """1회용 코드 발급 — 30초 유효"""
        code = secrets.token_urlsafe(32)
        await redis.setex(f"auth_code:{code}", 30, user_id)
        return code
