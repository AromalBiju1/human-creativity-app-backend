from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session,joinedload
from database.database import get_db
from database.models import User
from database.schemas import UserProfileResponse
from routers.auth.auth import get_current_user
import logging
router = APIRouter(tags=["Profile"])
logger = logging.getLogger("uvicorn")

@router.get("/",response_model=UserProfileResponse)
def get_my_profile(current_user:User = Depends(get_current_user),db:Session = Depends(get_db)):
    user = db.query(User).options(joinedload(User.posts)).filter(User.id == current_user.id).first()

    logger.info(user)

    return user