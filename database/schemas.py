from pydantic import  BaseModel, EmailStr

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
