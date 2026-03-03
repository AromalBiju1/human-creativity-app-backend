from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from database.database import get_db
from database.models import User, Conversation, Message, MessageType, ConversationParticipant
from database.schemas import MessageResponse, MessageUpdate
from routers.auth.auth import get_current_user
from routers.chat.dependencies import get_participant_or_403, build_message_payload, get_cloudinary_upload_params, MEDIA_TYPE_MAP
from routers.chat.manager import manager

router = APIRouter()


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(conversation_id: int, limit: int = 50, before_id: int = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_participant_or_403(conversation_id, current_user.id, db)
    query = db.query(Message).options(
        joinedload(Message.sender),
        joinedload(Message.reply_to).joinedload(Message.sender)
    ).filter(Message.conversation_id == conversation_id, Message.is_deleted == False)
    if before_id:
        query = query.filter(Message.id < before_id)
    return list(reversed(query.order_by(Message.created_at.desc()).limit(limit).all()))


@router.post("/{conversation_id}/messages/request-upload")
async def request_upload_url(conversation_id: int, content_type: str, filename: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_participant_or_403(conversation_id, current_user.id, db)
    result = get_cloudinary_upload_params(conversation_id, content_type, filename)
    await manager.set_upload_pending(result["upload_id"], current_user.id, conversation_id)
    return result


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(message_id: int, body: MessageUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages")
    if msg.message_type != MessageType.text:
        raise HTTPException(status_code=400, detail="Only text messages can be edited")
    msg.content = body.content
    msg.edited_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    await manager.publish(build_message_payload("message_edited", msg, current_user), msg.conversation_id)
    return msg


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
    msg.is_deleted = True
    msg.content = None
    db.commit()
    await manager.publish({"event": "message_deleted", "conversation_id": msg.conversation_id, "message_id": msg.id}, msg.conversation_id)


@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_as_read(conversation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    participant = get_participant_or_403(conversation_id, current_user.id, db)
    latest = db.query(Message).filter(Message.conversation_id == conversation_id, Message.is_deleted == False).order_by(Message.id.desc()).first()
    if latest:
        participant.last_read_message_id = latest.id
        db.commit()