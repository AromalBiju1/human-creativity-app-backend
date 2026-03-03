import os
from fastapi import APIRouter, HTTPException, UploadFile, Depends, File, Form,status,Response
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


@router.delete("/delete/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    type: str = "post", 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
   
    model = Story if type == "story" else Post
    item_query = db.query(model).filter(model.id == item_id)
    item = item_query.first()

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"{type.capitalize()} with id: {item_id} not found"
        )
    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Not authorized to perform requested action"
        )

    try:
        if item.media_url and "app_uploads" in item.media_url:
            file_name = item.media_url.split("/")[-1].split(".")[0]
            public_id = f"app_uploads/{file_name}"
            cloudinary.uploader.destroy(public_id, resource_type=item.media_type)
            print(f"🗑️ Deleted from Cloudinary: {public_id}")
    except Exception as e:
        print(f"⚠️ Cloudinary deletion failed: {e}")
    item_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
