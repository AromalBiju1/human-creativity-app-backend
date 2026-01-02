from pydantic import  BaseModel, EmailStr
from typing import Optional
from datetime import datetime
class UserCreate(BaseModel):
    username: str
    email : EmailStr
    password : str


class UserLogin(BaseModel):
    identifier : str
    password : str

class UserResponse(BaseModel):
    id : int
    username : str
    email : EmailStr
    is_verified : bool
    role : str

    class config:
        from_attributes = True

class Token(BaseModel):
    access_token : str
    token_type : str


class TokenData(BaseModel):
    username: str | None = None

# Post Schemas
class PostBase(BaseModel): #shared data
    title:str
    content: Optional[str] = None

class PostResponse(PostBase):
    id:int
    image_url: str
    created_at: datetime
    owner_id: int

    class config:
        from_attributes = True

        




