from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session, selectinload
from database.database import get_db
from database.models import User
from database.schemas import FollowResponse, UserSearchResult
from routers.auth.auth import get_current_user
from typing import List

router = APIRouter(tags=["Follow"])

@router.post("/follow/{user_id}",response_model=FollowResponse)

def follow_user(user_id:int,current_user:User = Depends(get_current_user),db:Session = Depends(get_db)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400,detail="You cannot follow yourself")
    
    me = db.query(User).options(selectinload(User.following)).filter(User.id == current_user.id).first()
    target = db.query(User).options(selectinload(User.followers)).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    already_following = any(u.id == user_id for u in me.following)
    if already_following:
        raise HTTPException(status_code=400, detail="Already following this user")

    me.following.append(target)
    db.commit()

    return {
        "message": f"You are now following {target.username}",
        "followers_count": len(target.followers) + 1
    }

@router.delete("/unfollow/{user_id}", response_model=FollowResponse)
def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot unfollow yourself")

    me = db.query(User).options(selectinload(User.following)).filter(User.id == current_user.id).first()
    target = db.query(User).options(selectinload(User.followers)).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    is_following = any(u.id == user_id for u in me.following)
    if not is_following:
        raise HTTPException(status_code=400, detail="You are not following this user")

    me.following.remove(target)
    db.commit()

    return {
        "message": f"You unfollowed {target.username}",
        "followers_count": len(target.followers) - 1
    }


@router.get("/search", response_model=List[UserSearchResult])
def search_users(
    query: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    me = db.query(User).options(selectinload(User.following)).filter(User.id == current_user.id).first()
    following_ids = {u.id for u in me.following}

    users = db.query(User).options(selectinload(User.followers)).filter(
        User.username.ilike(f"%{query}%"),
        User.id != current_user.id
    ).limit(20).all()

    return [
        UserSearchResult(
            id=u.id,
            username=u.username,
            followers_count=len(u.followers),
            is_following=u.id in following_ids
        )
        for u in users
    ]


# ⚠️ /my/followers MUST come before /{user_id}/followers
@router.get("/my/followers", response_model=List[UserSearchResult])
def get_my_followers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    me = db.query(User).options(
        selectinload(User.followers).selectinload(User.followers),
        selectinload(User.following)
    ).filter(User.id == current_user.id).first()

    following_ids = {u.id for u in me.following}

    return [
        UserSearchResult(
            id=u.id,
            username=u.username,
            followers_count=len(u.followers),
            is_following=u.id in following_ids  # do you follow them back?
        )
        for u in me.followers
    ]


# ⚠️ /my/following MUST come before /{user_id}/following
@router.get("/my/following", response_model=List[UserSearchResult])
def get_my_following(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    me = db.query(User).options(
        selectinload(User.following).selectinload(User.followers)
    ).filter(User.id == current_user.id).first()

    return [
        UserSearchResult(
            id=u.id,
            username=u.username,
            followers_count=len(u.followers),
            is_following=True
        )
        for u in me.following
    ]


@router.get("/profile/{user_id}")
def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    me = db.query(User).options(selectinload(User.following)).filter(User.id == current_user.id).first()
    following_ids = {u.id for u in me.following}

    user = db.query(User).options(
        selectinload(User.posts),
        selectinload(User.followers),
        selectinload(User.following)
    ).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "bio": user.bio,
        "profile_pic": user.profile_pic,
        "posts_count": len(user.posts),
        "followers_count": len(user.followers),
        "following_count": len(user.following),
        "is_following": user_id in following_ids
    }


@router.get("/{user_id}/followers", response_model=List[UserSearchResult])
def get_user_followers(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    me = db.query(User).options(selectinload(User.following)).filter(User.id == current_user.id).first()
    following_ids = {u.id for u in me.following}

    target = db.query(User).options(
        selectinload(User.followers).selectinload(User.followers)
    ).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    return [
        UserSearchResult(
            id=u.id,
            username=u.username,
            followers_count=len(u.followers),
            is_following=u.id in following_ids
        )
        for u in target.followers
    ]


@router.get("/{user_id}/following", response_model=List[UserSearchResult])
def get_user_following(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    me = db.query(User).options(selectinload(User.following)).filter(User.id == current_user.id).first()
    following_ids = {u.id for u in me.following}

    target = db.query(User).options(
        selectinload(User.following).selectinload(User.followers)
    ).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    return [
        UserSearchResult(
            id=u.id,
            username=u.username,
            followers_count=len(u.followers),
            is_following=u.id in following_ids
        )
        for u in target.following
    ]