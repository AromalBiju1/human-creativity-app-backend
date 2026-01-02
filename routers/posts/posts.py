import os
from config.config import supabase_key,supabase_url
from fastapi import APIRouter,HTTPException,UploadFile,Depends,File,Form
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Post,User
from database.schemas import PostResponse
from routers.auth.auth import get_current_user
from supabase import create_client,Client
import uuid
from typing import List

router = APIRouter()
if not supabase_url or not supabase_key:
    print("Error: Couldn't find supabase url or supabase key")


supabase: Client = create_client(supabase_url,supabase_key) # connect to supabase storage


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
    file_content = await file.read() 

    #upload to supabse image bucket
    supabase.storage.from_("images").upload(file_path,file_content,
    {"content-type":file.content_type}) 
    public_url = supabase.storage.from_("images").get_public_url(file_path) 
    # save  to db

    new_post = Post(
        title=title,
        content=content,
        image_url=public_url,
        owner_id=current_user.id

    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post
 except Exception as e:
    print(f"❌ Upload Error: {e}")
    raise HTTPException(status_code=500, detail=str(e))



@router.get("/", response_model=List[PostResponse])
def get_posts(db: Session = Depends(get_db)):
    # Fetch all posts, ordered by newest first
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return posts    



