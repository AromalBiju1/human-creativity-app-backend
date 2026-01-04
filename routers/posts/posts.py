import os
from fastapi import APIRouter, HTTPException, UploadFile, Depends, File, Form
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Post, User, Story
from database.schemas import PostResponse, StoryResponse 
from routers.auth.auth import get_current_user
import cloudinary
import cloudinary.uploader
from config.config import cloudinary_api_key, cloudinary_name, cloudinary_secret
import uuid
from typing import List
from datetime import datetime 

router = APIRouter()

if not all([cloudinary_name, cloudinary_secret, cloudinary_api_key]):
    print("Error: Couldn't find cloudinary credentials")

cloudinary.config(
    cloud_name=cloudinary_name,
    api_key=cloudinary_api_key,
    api_secret=cloudinary_secret,
    secure=True
)

@router.post("/upload") 
async def create_upload(
    title: str = Form(None),    
    content: str = Form(None), 
    type: str = Form("post"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ALLOWED_VIDEOS = ["video/mp4", "video/webm", "video/quicktime"]
    ALLOWED_IMAGES = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    
    if file.content_type in ALLOWED_IMAGES:
        media_type = "image"
        resource_type = "image"
    elif file.content_type in ALLOWED_VIDEOS:
        media_type = "video"
        resource_type = "video"
    else:
        raise HTTPException(
            status_code=400, 
            detail="File type not supported. Only JPEG, PNG, WEBP, MP4, WEBM, and MOV are allowed."
        )

    try:
        upload_result = cloudinary.uploader.upload(
            file.file,
            folder="app_uploads",
            resource_type=resource_type
        )
        secure_url = upload_result.get('secure_url')

    except Exception as e:
        print(f"❌ Upload Error: {e}")
        raise HTTPException(status_code=500, detail="upload failed")

    if type == "story":
        new_story = Story(
            media_url=secure_url,
            media_type=media_type,
            owner_id=current_user.id 
        )
        db.add(new_story)
        db.commit()
        return {"status": "Story uploaded", "url": secure_url}

    else:
        if not title:
            raise HTTPException(status_code=400, detail="Title is required for posts")

        new_post = Post(
            title=title,
            content=content,
            media_url=secure_url, 
            media_type=media_type,
            owner_id=current_user.id
        )
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        return new_post
@router.get("/stories", response_model=List[StoryResponse])
def get_stories(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    stories = db.query(Story).filter(Story.expires_at > now).all()
    return stories

@router.get("/", response_model=List[PostResponse])
def get_posts(db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return posts