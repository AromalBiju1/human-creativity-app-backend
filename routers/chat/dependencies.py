import uuid
from jose import JWTError, jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session

import cloudinary
import cloudinary.utils

from database.models import User, Conversation, ConversationParticipant, Message, MessageType
from utils.utils import PUBLIC_KEY, ALGORITHM
from config.config import cloudinary_api_key, cloudinary_name, cloudinary_secret

# ── Allowed media types ──
MEDIA_TYPE_MAP = {
    "image/jpeg":       (MessageType.image,    "image"),
    "image/png":        (MessageType.image,    "image"),
    "image/webp":       (MessageType.image,    "image"),
    "image/jpg":        (MessageType.image,    "image"),
    "image/gif":        (MessageType.image,    "image"),
    "video/mp4":        (MessageType.video,    "video"),
    "video/webm":       (MessageType.video,    "video"),
    "video/quicktime":  (MessageType.video,    "video"),
    "application/pdf":  (MessageType.document, "raw"),
    "application/msword": (MessageType.document, "raw"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (MessageType.document, "raw"),
    "text/plain":       (MessageType.document, "raw"),
}


def get_user_from_token(token: str, db: Session) -> User:
    """Decode JWT and return the User — used in WebSocket where Depends() isn't available"""
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=ALGORITHM)
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_participant_or_403(conversation_id: int, user_id: int, db: Session) -> ConversationParticipant:
    """Ensure a user is an active participant — raises 403 if not"""
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id,
        ConversationParticipant.is_active == True
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="You are not a member of this conversation")
    return participant


def build_message_payload(event: str, msg: Message, user: User) -> dict:
    """Build a Redis-publishable dict from a Message ORM object"""
    return {
        "event": event,
        "conversation_id": msg.conversation_id,
        "message": {
            "id": msg.id,
            "sender_id": user.id,
            "sender_username": user.username,
            "sender_profile_pic": user.profile_pic,
            "content": msg.content,
            "message_type": msg.message_type,
            "media_url": msg.media_url,
            "media_filename": msg.media_filename,
            "reply_to_id": msg.reply_to_id,
            "created_at": msg.created_at.isoformat(),
            "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
            "is_deleted": msg.is_deleted,
        }
    }


def get_cloudinary_upload_params(conversation_id: int, content_type: str, filename: str) -> dict:
    """Generate Cloudinary presigned upload params for a given file"""
    if content_type not in MEDIA_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}"
        )
    _, resource_type = MEDIA_TYPE_MAP[content_type]
    timestamp = cloudinary.utils.now()
    folder = f"chat_media/{conversation_id}"
    params = {"folder": folder, "timestamp": timestamp}
    signature = cloudinary.utils.api_sign_request(params, cloudinary_secret)

    return {
        "upload_id": str(uuid.uuid4()),
        "filename": filename,
        "content_type": content_type,
        "cloudinary": {
            "upload_url": f"https://api.cloudinary.com/v1_1/{cloudinary_name}/{resource_type}/upload",
            "api_key": cloudinary_api_key,
            "timestamp": timestamp,
            "signature": signature,
            "folder": folder,
        }
    }