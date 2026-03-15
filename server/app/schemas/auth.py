import uuid

from pydantic import BaseModel

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

class SignupResponse(BaseModel):
    username: str
    email: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str | None
    email: str

    class Config:
        from_attributes = True

class AuthCodeResponse(BaseModel):
    code: str
