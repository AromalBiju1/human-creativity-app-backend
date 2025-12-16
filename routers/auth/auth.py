from fastapi import APIRouter,HTTPException,Depends,status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database.database import get_db
from database.models import User
from database.schemas import UserCreate,UserLogin,UserResponse,Token
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError ,jwt
from utils.utils import hash_password,verify_password,create_access_token,ALGORITHM,PUBLIC_KEY

router = APIRouter()

jwt_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token:str = Depends(jwt_scheme), db: Session = Depends(get_db)):
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate":"Bearer"},
    )
    try:
        payload = jwt.decode(token,PUBLIC_KEY,algorithms=ALGORITHM)
        username: str = payload.get("sub")
        if username is None:
            return credential_exception
    except JWTError:
        raise credential_exception
    user = db.query(User).filter(User.email == username).first()
    if user is None:
        raise credential_exception
    return user


@router.post("/signup", response_model=UserResponse)
def signup(user:UserCreate,db:Session= Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400,detail="Email Already registered")
    if db.query(User).filter(User.username ==  user.username).first():
        raise HTTPException(status_code=400,detail="Username already taken")

    new_user = User(
        username = user.username,
        email=user.email,
        password_hash=hash_password(user.password)) 
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login",response_model=Token)
def login(user_credentials: UserLogin, db:Session= Depends(get_db)):
    user = db.query(User).filter(
        or_(
            User.email == user_credentials.identifier,
            User.username == user_credentials.identifier
        )
    ).first()  
    if not user or not verify_password(user_credentials.password,user.password_hash) :
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail=" Incorrect username/email or password"
        ) 
    access_token = create_access_token(data={"sub": user.email, "id": user.id})  
    return{"access_token": access_token, "token_type": "bearer"}

@router.get("/me",response_model=UserResponse)                                 
def read_users_me(current_user : User = Depends(get_current_user)):
    return current_user



