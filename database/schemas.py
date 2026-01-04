from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class OwnerInfo(BaseModel):
    username: str
    profile_pic: Optional[str] = None
    class Config:
        from_attributes = True

# --- User Schemas ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    identifier: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    bio: Optional[str] = None     
    profile_pic: Optional[str] = None
    is_verified: bool
    role: str

    class Config: 
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

# --- Post Schemas ---
class PostBase(BaseModel): 
    title: str = None 
    content: Optional[str] = None

class PostResponse(PostBase):
    id: int
    media_url: str 
    media_type: str
    created_at: datetime
    owner_id: int
    owner: Optional[OwnerInfo] = None 

    class Config:  
        from_attributes = True


class UserProfileResponse(BaseModel):
    id:int
    username:str
    email:EmailStr
    is_verified:bool
    role:str
    created_at:datetime
    posts : list[PostResponse] = []


    class Config:
        from_attributes = True




class StoryResponse(BaseModel):
    id: int
    media_url: str
    media_type: str
    created_at: datetime
    owner_id: int
    owner: Optional[OwnerInfo] = None

    class Config:
        from_attributes = True