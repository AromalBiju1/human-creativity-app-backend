from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload
from database.database import get_db
from database.models import User
from database.schemas import UserProfileResponse
from routers.auth.auth import get_current_user
import logging

router = APIRouter(tags=["Profile"])
logger = logging.getLogger("uvicorn")


@router.get("/", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).options(
        selectinload(User.posts),
        selectinload(User.followers),
        selectinload(User.following)
    ).filter(User.id == current_user.id).first()

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_verified": user.is_verified,
        "bio": user.bio,
        "profile_pic": user.profile_pic,
        "role": user.role,
        "created_at": user.created_at,
<<<<<<< HEAD
        "posts": user.posts,
        "followers": user.followers,
        "following": user.following,
=======
        "posts_count": len(user.posts),
        "followers_count": len(user.followers),
        "following_count": len(user.following),
>>>>>>> ed9e98cbf0d69f02b7a74a8a1f48ee2391470f66
    }