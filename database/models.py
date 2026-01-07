from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database.database import Base
from datetime import datetime, timedelta
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    bio = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    role = Column(String, default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    posts = relationship("Post", back_populates="owner")
    stories = relationship("Story", back_populates="owner") 

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(String) 
    media_url = Column(String) 
    media_type = Column(String, default="image")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Integer, ForeignKey("users.id")) 
    owner = relationship("User", back_populates="posts") 

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, index=True, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"))  
    media_url = Column(String)
    media_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    owner = relationship("User", back_populates="stories")
