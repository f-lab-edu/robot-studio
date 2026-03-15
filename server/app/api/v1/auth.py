from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.infra.database import get_db
from app.services.auth_service import AuthService
from app.core.security import decode_access_token
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.auth import SignupRequest, SignupResponse, TokenResponse, RefreshRequest, LoginRequest, UserResponse, AuthCodeResponse
router = APIRouter(prefix="/auth", tags=["auth"])

security_scheme = HTTPBearer()

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(req: SignupRequest, service: AuthService = Depends(get_auth_service)):
    try:
        user = await service.signup(req.username, req.email, req.password)
        return SignupResponse(username=user.username, email=user.email)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, service: AuthService = Depends(get_auth_service)):
    try:
        access_token, refresh_token = await service.login(req.email, req.password)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, service: AuthService = Depends(get_auth_service)):
    try:
        access_token, refresh_token = await service.refresh(req.refresh_token)
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/issue-code", response_model=AuthCodeResponse)
async def issue_code(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    redis=Depends(get_redis),
):
    code = await service.issue_code(str(current_user.id), redis)
    return {"code": code}

@router.post("/token-exchange")
async def token_exchange(
    code: str,
    service: AuthService = Depends(get_auth_service),
    redis=Depends(get_redis),
):
    try:
        access_token, refresh_token = await service.exchange_code(code, redis)
        return {"access_token": access_token, "refresh_token": refresh_token}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
