from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    role: str


class LoginData(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    user: UserInfo
