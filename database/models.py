from sqlalchemy import Column,Integer,String,Boolean,DateTime,ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database.database import Base



class User(Base):
    __tablename__ = "users"
    id = Column(Integer,primary_key=True, index=True)
    email= Column(String,unique=True,index=True,nullable=False)
    username= Column(String,unique=True,index=True,nullable=False)
    password_hash = Column(String,nullable=False)
    is_verified = Column(Boolean,default=False)
    role = Column(String,default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    posts = relationship("Post",back_populates="owner")

class Post(Base):
    __tablename__ = "posts"
    id=Column(Integer,primary_key=True,index=True)
    title=Column(String,index=True)
    content=Column(String) #caption
    image_url=Column(String) #link to supabase storage
    created_at=Column(DateTime(timezone=True),server_default=func.now())
    owner_id=Column(Integer,ForeignKey("users.id")) #Fkey
    owner=relationship("User",back_populates="posts") # lets us access user obj from post
    