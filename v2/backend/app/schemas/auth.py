from pydantic import BaseModel, Field
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=10, max_length=128)
    role: str = 'member'
