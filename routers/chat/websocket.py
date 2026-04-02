import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Conversation, ConversationParticipant, Message, MessageType
from database.schemas import WSMessageIn
from routers.chat.dependencies import get_user_from_token, get_participant_or_403, build_message_payload, MEDIA_TYPE_MAP
from routers.chat.manager import manager

router = APIRouter()


@router.websocket("/ws/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    # ── Auth + membership check ──
    try:
        user = get_user_from_token(token, db)
    except Exception:
        await websocket.close(code=1008)
        return

    if not db.query(ConversationParticipant).filter_by(
        conversation_id=conversation_id, user_id=user.id, is_active=True
    ).first():
        await websocket.close(code=1008)
        return

    # ── Connect ──
    await manager.connect(websocket, conversation_id)
    await manager.set_online(user.id)
    await manager.publish({"event": "user_online", "user_id": user.id, "username": user.username}, conversation_id)

    # ── Background task: Redis → this WebSocket ──
    subscribe_task = asyncio.create_task(manager.subscribe_and_forward(websocket, conversation_id))

    try:
        while True:
            try:
                data = WSMessageIn(**json.loads(await websocket.receive_text()))
            except Exception:
                await websocket.send_text(json.dumps({"event": "error", "detail": "Invalid message format"}))
                continue

            # Typing indicators
            if data.message_type == MessageType.system:
                if data.content == "typing":
                    await manager.set_typing(conversation_id, user.id)
                    await manager.publish({"event": "user_typing", "conversation_id": conversation_id, "user_id": user.id, "username": user.username}, conversation_id)
                elif data.content == "stop_typing":
                    await manager.clear_typing(conversation_id, user.id)
                continue

            # Media message — validate upload_id from Redis
            if data.message_type in (MessageType.image, MessageType.video, MessageType.document):
                if not data.media_url or not data.upload_id:
                    await websocket.send_text(json.dumps({"event": "error", "detail": "Media messages require media_url and upload_id"}))
                    continue
                upload = await manager.get_upload(data.upload_id)
                if not upload or int(upload["user_id"]) != user.id or int(upload["conversation_id"]) != conversation_id:
                    await websocket.send_text(json.dumps({"event": "error", "detail": "Invalid or expired upload_id"}))
                    continue
                await manager.clear_upload(data.upload_id)

            # Text message
            elif not data.content:
                await websocket.send_text(json.dumps({"event": "error", "detail": "Message cannot be empty"}))
                continue

            # Persist to DB
            msg = Message(
                conversation_id=conversation_id, sender_id=user.id,
                content=data.content, message_type=data.message_type,
                media_url=data.media_url, media_filename=data.media_filename,
                reply_to_id=data.reply_to_id
            )
            db.add(msg)
            convo = db.query(Conversation).filter_by(id=conversation_id).first()
            db.flush()
            convo.last_message_id = msg.id
            db.commit()
            db.refresh(msg)

            # Publish to Redis → all servers broadcast
            await manager.publish(build_message_payload("new_message", msg, user), conversation_id)

    except WebSocketDisconnect:
        subscribe_task.cancel()
        manager.disconnect(websocket, conversation_id)
        await manager.set_offline(user.id)
        await manager.clear_typing(conversation_id, user.id)
        await manager.publish({"event": "user_offline", "user_id": user.id, "username": user.username}, conversation_id)

    except Exception as e:
        # This catches actual bad data (like malformed JSON)
        # Only try to send an error if the socket is still open
        try:
            await websocket.send_text(json.dumps({"event": "error", "detail": "Invalid message format"}))
        except RuntimeError:
            pass # Socket was already closed, ignore it     