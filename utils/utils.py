import os
from datetime import datetime,timedelta
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt, JWTError
from config.config import private_key,public_key
ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def load_key(filename):
    try:
        with open(filename,"r") as f:
            return f.read()
    except FileNotFoundError:
        return None   


PRIVATE_KEY = load_key(private_key)
PUBLIC_KEY = load_key(public_key)


if not PRIVATE_KEY:
    print("⚠️  WARNING: private.pem not found. Authentication will fail!")


ph = PasswordHasher()


def hash_password(password:str)->str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password:str)-> bool:
    try:
        ph.verify(hashed_password,plain_password)
        return True
    except VerifyMismatchError:
        return False

def create_access_token(data:dict, expires_delta : Optional[timedelta] = None)   :
    if not PRIVATE_KEY:
        raise ValueError("Cannot sign token! private key is missing") 
    to_encode = data.copy()    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta 
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)         
    to_encode.update({'exp': expire})    
    encoded_jwt = jwt.encode(to_encode,PRIVATE_KEY,algorithm=ALGORITHM)    
    return encoded_jwt


    
     






