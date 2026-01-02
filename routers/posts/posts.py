import os
from fastapi import APIRouter,HTTPException,UploadFile,Depends,File,Form
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Post,User
from database.schemas import PostResponse
from routers.auth.auth import get_current_user
import cloudinary
import cloudinary.uploader
from config.config import cloudinary_api_key,cloudinary_name,cloudinary_secret
import uuid
from typing import List

router = APIRouter()
if not all([cloudinary_name,cloudinary_secret,cloudinary_api_key]):
    print("Error: Couldn't find cloudinary credentials")


cloudinary.config(
    cloud_name = cloudinary_name,
    api_key = cloudinary_api_key,
    api_secret=cloudinary_secret,
    secure=True

)

@router.post("/upload",response_model=PostResponse)
async def create_post(
    title:str = Form(...),
    content:str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db:Session = Depends(get_db)

):
#validation
 if file.content_type not in ["image/jpeg","image/png","image/webp","image/jpg"]:
    raise HTTPException(status_code=400,detail="only jpeg,jpg,png,webp images are allowed")


#gen unique filename
 file_extension = file.filename.split(".")[-1]
 unique_filename = f"{uuid.uuid4()}.{file_extension}"
 file_path = f"uploads/{unique_filename}"
 try:
    upload_result = cloudinary.uploader.upload(
     file.file,
     folder="app_uploads"
   )
    image_url = upload_result.get('secure_url')


    new_post = Post(
            title=title,
            content=content,
            image_url=image_url,
            owner_id=current_user.id
        )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post
 except Exception as e:
    print(f"❌ Upload Error: {e}")
    raise HTTPException(status_code=500, detail="Image upload failed")



@router.get("/", response_model=List[PostResponse])
def get_posts(db: Session = Depends(get_db)):
    # Fetch all posts, ordered by newest first
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return posts    



