import json
import uuid
import asyncio
from datetime import datetime
from typing import List

from fastapi import (
    APIRouter, WebSocket, WebSocketDisconnect,
    Depends, HTTPException, Query, status, UploadFile, File
)
from sqlalchemy.orm import Session, joinedload
from jose import JWTError, jwt

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from database.database import get_db
from database.models import (
    User, Conversation, ConversationParticipant,
    Message, ConversationType, ParticipantRole, MessageType
)
from database.schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse, ConversationListResponse,
    MessageCreate, MessageUpdate, MessageResponse,
    ParticipantUpdate, ParticipantResponse,
    WSMessageIn, OwnerInfo
)
from routers.auth.auth import get_current_user
from routers.chat.manager import manager
from utils.utils import PUBLIC_KEY, ALGORITHM
from config.config import cloudinary_api_key, cloudinary_name, cloudinary_secret

router = APIRouter(tags=["Chat"])

cloudinary.config(
    cloud_name=cloudinary_name,
    api_key=cloudinary_api_key,
    api_secret=cloudinary_secret,
    secure=True
)

# Allowed MIME types and their MessageType mapping
MEDIA_TYPE_MAP = {
    # Images
    "image/jpeg":       (MessageType.image, "image"),
    "image/png":        (MessageType.image, "image"),
    "image/webp":       (MessageType.image, "image"),
    "image/jpg":        (MessageType.image, "image"),
    "image/gif":        (MessageType.image, "image"),
    # Videos
    "video/mp4":        (MessageType.video, "video"),
    "video/webm":       (MessageType.video, "video"),
    "video/quicktime":  (MessageType.video, "video"),
    # Documents — stored as raw in Cloudinary
    "application/pdf":                                                          (MessageType.document, "raw"),
    "application/msword":                                                       (MessageType.document, "raw"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":  (MessageType.document, "raw"),
    "application/vnd.ms-excel":                                                 (MessageType.document, "raw"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":        (MessageType.document, "raw"),
    "text/plain":                                                               (MessageType.document, "raw"),
}


# ─────────────────────────────────────────────
# WebSocket Auth Helper
# ─────────────────────────────────────────────

def get_user_from_token(token: str, db: Session) -> User:
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


# ─────────────────────────────────────────────
# Shared Guard
# ─────────────────────────────────────────────

def get_participant_or_403(
    conversation_id: int,
    user_id: int,
    db: Session
) -> ConversationParticipant:
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id,
        ConversationParticipant.is_active == True
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="You are not a member of this conversation")
    return participant


# ─────────────────────────────────────────────
# Helper — build broadcast-ready message dict
# ─────────────────────────────────────────────

def build_message_payload(event: str, msg: Message, user: User) -> dict:
    return {
        "event": event,
        "conversation_id": msg.conversation_id,
        "message": {
            "id": msg.id,
            "conversation_id": msg.conversation_id,
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


# ═════════════════════════════════════════════
# REST ENDPOINTS
# ═════════════════════════════════════════════

# ─────────────────────────────────────────────
# 1. Create DM or Group Conversation
# ─────────────────────────────────────────────

@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if body.type == ConversationType.direct:
        if len(body.participant_ids) != 1:
            raise HTTPException(status_code=400, detail="DM requires exactly one other user")
        other_id = body.participant_ids[0]
        if other_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot DM yourself")

        existing = (
            db.query(Conversation)
            .join(ConversationParticipant)
            .filter(
                Conversation.type == ConversationType.direct,
                ConversationParticipant.user_id == current_user.id,
                ConversationParticipant.is_active == True
            ).all()
        )
        for convo in existing:
            other_ids = [p.user_id for p in convo.participants if p.user_id != current_user.id]
            if other_ids == [other_id]:
                return convo

    if body.type == ConversationType.group and not body.name:
        raise HTTPException(status_code=400, detail="Group chats require a name")

    convo = Conversation(type=body.type, name=body.name)
    db.add(convo)
    db.flush()

    db.add(ConversationParticipant(
        conversation_id=convo.id,
        user_id=current_user.id,
        role=ParticipantRole.admin
    ))
    for uid in body.participant_ids:
        if uid == current_user.id:
            continue
        if not db.query(User).filter(User.id == uid).first():
            raise HTTPException(status_code=404, detail=f"User {uid} not found")
        db.add(ConversationParticipant(
            conversation_id=convo.id,
            user_id=uid,
            role=ParticipantRole.member
        ))

    db.commit()
    db.refresh(convo)
    return convo


# ─────────────────────────────────────────────
# 2. Get Inbox
# ─────────────────────────────────────────────

@router.get("/", response_model=List[ConversationListResponse])
def get_my_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    participations = (
        db.query(ConversationParticipant)
        .filter(
            ConversationParticipant.user_id == current_user.id,
            ConversationParticipant.is_active == True
        )
        .options(
            joinedload(ConversationParticipant.conversation)
                .joinedload(Conversation.participants)
                .joinedload(ConversationParticipant.user),
            joinedload(ConversationParticipant.conversation)
                .joinedload(Conversation.last_message)
                .joinedload(Message.sender)
        )
        .all()
    )

    result = []
    for p in participations:
        convo = p.conversation
        if p.last_read_message_id:
            unread_count = db.query(Message).filter(
                Message.conversation_id == convo.id,
                Message.id > p.last_read_message_id,
                Message.is_deleted == False
            ).count()
        else:
            unread_count = db.query(Message).filter(
                Message.conversation_id == convo.id,
                Message.sender_id != current_user.id,
                Message.is_deleted == False
            ).count()

        result.append(ConversationListResponse(
            id=convo.id,
            type=convo.type,
            name=convo.name,
            group_pic=convo.group_pic,
            updated_at=convo.updated_at,
            last_message=convo.last_message,
            unread_count=unread_count,
            participants=convo.participants
        ))
    return result


# ─────────────────────────────────────────────
# 3. Get Single Conversation
# ─────────────────────────────────────────────

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    get_participant_or_403(conversation_id, current_user.id, db)
    convo = (
        db.query(Conversation)
        .options(
            joinedload(Conversation.participants).joinedload(ConversationParticipant.user),
            joinedload(Conversation.last_message).joinedload(Message.sender)
        )
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


# ─────────────────────────────────────────────
# 4. Update Group (admin only)
# ─────────────────────────────────────────────

@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: int,
    body: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    participant = get_participant_or_403(conversation_id, current_user.id, db)
    if participant.role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can update the group")

    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if body.name is not None:
        convo.name = body.name
    if body.group_pic is not None:
        convo.group_pic = body.group_pic

    db.commit()
    db.refresh(convo)
    return convo


# ─────────────────────────────────────────────
# 5. Get Chat History (cursor-based pagination)
# ─────────────────────────────────────────────

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    limit: int = 50,
    before_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    get_participant_or_403(conversation_id, current_user.id, db)

    query = (
        db.query(Message)
        .options(
            joinedload(Message.sender),
            joinedload(Message.reply_to).joinedload(Message.sender)
        )
        .filter(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False
        )
    )
    if before_id:
        query = query.filter(Message.id < before_id)

    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    return list(reversed(messages))


# ─────────────────────────────────────────────
# 6. Request Upload URL
# Client calls this BEFORE uploading a file.
# Server generates a Cloudinary presigned URL and
# tracks the pending upload in Redis.
# ─────────────────────────────────────────────

@router.post("/{conversation_id}/messages/request-upload")
async def request_upload_url(
    conversation_id: int,
    content_type: str,               # e.g. "image/jpeg", "video/mp4", "application/pdf"
    filename: str,                   # Original filename — stored for display in UI
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 1 of media sharing flow.
    Returns a Cloudinary presigned upload URL.
    Client uploads directly to Cloudinary using this URL,
    then sends the resulting media_url over WebSocket.
    """
    get_participant_or_403(conversation_id, current_user.id, db)

    if content_type not in MEDIA_TYPE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. "
                   f"Allowed: images (jpeg/png/webp/gif), videos (mp4/webm/mov), "
                   f"documents (pdf/doc/docx/xls/xlsx/txt)"
        )

    _, resource_type = MEDIA_TYPE_MAP[content_type]

    # Generate a unique upload ID to track this upload in Redis
    upload_id = str(uuid.uuid4())

    # Generate Cloudinary presigned upload params
    # The client uses these to POST directly to Cloudinary
    timestamp = cloudinary.utils.now()
    folder = f"chat_media/{conversation_id}"

    params = {
        "folder": folder,
        "timestamp": timestamp,
        "upload_preset": None,
    }
    signature = cloudinary.utils.api_sign_request(params, cloudinary_secret)

    # Track the pending upload in Redis (10 min TTL)
    await manager.set_upload_pending(
        upload_id=upload_id,
        user_id=current_user.id,
        conversation_id=conversation_id
    )

    return {
        "upload_id": upload_id,          # Client must send this back over WS
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


# ─────────────────────────────────────────────
# 7. Edit a Message
# ─────────────────────────────────────────────

@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def edit_message(
    message_id: int,
    body: MessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    await manager.publish(
        payload=build_message_payload("message_edited", msg, current_user),
        conversation_id=msg.conversation_id
    )
    return msg


# ─────────────────────────────────────────────
# 8. Soft Delete a Message
# ─────────────────────────────────────────────

@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    msg = db.query(Message).filter(Message.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")

    msg.is_deleted = True
    msg.content = None
    db.commit()

    await manager.publish(
        payload={
            "event": "message_deleted",
            "conversation_id": msg.conversation_id,
            "message_id": msg.id
        },
        conversation_id=msg.conversation_id
    )


# ─────────────────────────────────────────────
# 9. Mark Conversation as Read
# ─────────────────────────────────────────────

@router.post("/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_as_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    participant = get_participant_or_403(conversation_id, current_user.id, db)
    latest_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.is_deleted == False)
        .order_by(Message.id.desc())
        .first()
    )
    if latest_msg:
        participant.last_read_message_id = latest_msg.id
        db.commit()


# ─────────────────────────────────────────────
# 10. Add Participant (admin only)
# ─────────────────────────────────────────────

@router.post("/{conversation_id}/participants/{user_id}", status_code=status.HTTP_201_CREATED)
def add_participant(
    conversation_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    requester = get_participant_or_403(conversation_id, current_user.id, db)
    if requester.role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can add members")

    existing = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()

    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="User already in conversation")
        existing.is_active = True
        existing.left_at = None
    else:
        db.add(ConversationParticipant(
            conversation_id=conversation_id,
            user_id=user_id,
            role=ParticipantRole.member
        ))

    db.commit()
    return {"detail": "Participant added"}


# ─────────────────────────────────────────────
# 11. Remove / Leave Conversation
# ─────────────────────────────────────────────

@router.delete("/{conversation_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(
    conversation_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    requester = get_participant_or_403(conversation_id, current_user.id, db)
    if user_id != current_user.id and requester.role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can remove other members")

    target = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Participant not found")

    target.is_active = False
    target.left_at = datetime.utcnow()
    db.commit()


# ─────────────────────────────────────────────
# 12. Update Participant Role (admin only)
# ─────────────────────────────────────────────

@router.patch("/{conversation_id}/participants/{user_id}", response_model=ParticipantResponse)
def update_participant_role(
    conversation_id: int,
    user_id: int,
    body: ParticipantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    requester = get_participant_or_403(conversation_id, current_user.id, db)
    if requester.role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can change roles")

    target = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user_id
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Participant not found")

    target.role = body.role
    db.commit()
    db.refresh(target)
    return target


# ═════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═════════════════════════════════════════════

@router.websocket("/ws/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    # ── 1. Authenticate ──
    try:
        user = get_user_from_token(token, db)
    except HTTPException:
        await websocket.close(code=1008)
        return

    # ── 2. Verify membership ──
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user.id,
        ConversationParticipant.is_active == True
    ).first()
    if not participant:
        await websocket.close(code=1008)
        return

    # ── 3. Connect + mark online ──
    await manager.connect(websocket, conversation_id)
    await manager.set_online(user.id)

    # ── 4. Notify room ──
    await manager.publish(
        payload={"event": "user_online", "user_id": user.id, "username": user.username},
        conversation_id=conversation_id
    )

    # ── 5. Start Redis subscriber as background task ──
    subscribe_task = asyncio.create_task(
        manager.subscribe_and_forward(websocket, conversation_id)
    )

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = WSMessageIn(**json.loads(raw))
            except Exception:
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "detail": "Invalid message format. Expected JSON matching WSMessageIn."
                }))
                continue

            # ── Typing: start ──
            if data.message_type == MessageType.system and data.content == "typing":
                await manager.set_typing(conversation_id, user.id)
                await manager.publish(
                    payload={
                        "event": "user_typing",
                        "conversation_id": conversation_id,
                        "user_id": user.id,
                        "username": user.username
                    },
                    conversation_id=conversation_id
                )
                continue

            # ── Typing: stop ──
            if data.message_type == MessageType.system and data.content == "stop_typing":
                await manager.clear_typing(conversation_id, user.id)
                continue

            # ── Media message (image / video / document) ──
            # Client already uploaded to Cloudinary via presigned URL
            # Now sends the resulting URL over WebSocket with upload_id for validation
            if data.message_type in (MessageType.image, MessageType.video, MessageType.document):
                if not data.media_url or not data.upload_id:
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "detail": "Media messages require both media_url and upload_id"
                    }))
                    continue

                # Validate upload_id exists in Redis and belongs to this user
                upload = await manager.get_upload(data.upload_id)
                if not upload:
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "detail": "Invalid or expired upload_id. Request a new upload URL."
                    }))
                    continue
                if int(upload["user_id"]) != user.id or int(upload["conversation_id"]) != conversation_id:
                    await websocket.send_text(json.dumps({
                        "event": "error",
                        "detail": "upload_id does not belong to you or this conversation"
                    }))
                    continue

                # Persist media message
                msg = Message(
                    conversation_id=conversation_id,
                    sender_id=user.id,
                    message_type=data.message_type,
                    media_url=data.media_url,
                    media_filename=data.media_filename,   # original filename for docs
                    content=data.content,                 # optional caption
                    reply_to_id=data.reply_to_id
                )
                db.add(msg)
                convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                db.flush()
                convo.last_message_id = msg.id
                db.commit()
                db.refresh(msg)

                # Clean up the upload tracking key in Redis
                await manager.clear_upload(data.upload_id)

                # Publish to Redis → all servers broadcast to participants
                await manager.publish(
                    payload=build_message_payload("new_message", msg, user),
                    conversation_id=conversation_id
                )
                continue

            # ── Text message ──
            if not data.content:
                await websocket.send_text(json.dumps({
                    "event": "error",
                    "detail": "Text message cannot be empty"
                }))
                continue

            msg = Message(
                conversation_id=conversation_id,
                sender_id=user.id,
                content=data.content,
                message_type=MessageType.text,
                reply_to_id=data.reply_to_id
            )
            db.add(msg)
            convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            db.flush()
            convo.last_message_id = msg.id
            db.commit()
            db.refresh(msg)

            await manager.publish(
                payload=build_message_payload("new_message", msg, user),
                conversation_id=conversation_id
            )

    except WebSocketDisconnect:
        subscribe_task.cancel()
        manager.disconnect(websocket, conversation_id)
        await manager.set_offline(user.id)
        await manager.clear_typing(conversation_id, user.id)

        await manager.publish(
            payload={"event": "user_offline", "user_id": user.id, "username": user.username},
            conversation_id=conversation_id
        )