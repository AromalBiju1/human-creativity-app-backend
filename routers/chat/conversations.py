from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from database.database import get_db
from database.models import User, Conversation, ConversationParticipant, Message, ConversationType, ParticipantRole
from database.schemas import ConversationCreate, ConversationUpdate, ConversationResponse, ConversationListResponse
from routers.auth.auth import get_current_user
from routers.chat.dependencies import get_participant_or_403

router = APIRouter()


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if body.type == ConversationType.direct:
        if len(body.participant_ids) != 1:
            raise HTTPException(status_code=400, detail="DM requires exactly one other user")
        other_id = body.participant_ids[0]
        if other_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot DM yourself")
        # Return existing DM if already exists
        for convo in db.query(Conversation).join(ConversationParticipant).filter(
            Conversation.type == ConversationType.direct,
            ConversationParticipant.user_id == current_user.id,
            ConversationParticipant.is_active == True
        ).all():
            if [p.user_id for p in convo.participants if p.user_id != current_user.id] == [other_id]:
                return convo

    if body.type == ConversationType.group and not body.name:
        raise HTTPException(status_code=400, detail="Group chats require a name")

    convo = Conversation(type=body.type, name=body.name)
    db.add(convo)
    db.flush()
    db.add(ConversationParticipant(conversation_id=convo.id, user_id=current_user.id, role=ParticipantRole.admin))
    for uid in body.participant_ids:
        if uid == current_user.id:
            continue
        if not db.query(User).filter(User.id == uid).first():
            raise HTTPException(status_code=404, detail=f"User {uid} not found")
        db.add(ConversationParticipant(conversation_id=convo.id, user_id=uid, role=ParticipantRole.member))

    db.commit()
    db.refresh(convo)
    return convo


@router.get("/", response_model=List[ConversationListResponse])
def get_my_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    participations = db.query(ConversationParticipant).filter(
        ConversationParticipant.user_id == current_user.id,
        ConversationParticipant.is_active == True
    ).options(
        joinedload(ConversationParticipant.conversation).joinedload(Conversation.participants).joinedload(ConversationParticipant.user),
        joinedload(ConversationParticipant.conversation).joinedload(Conversation.last_message).joinedload(Message.sender)
    ).all()

    result = []
    for p in participations:
        convo = p.conversation
        unread_count = db.query(Message).filter(
            Message.conversation_id == convo.id,
            Message.id > p.last_read_message_id if p.last_read_message_id else True,
            Message.sender_id != current_user.id,
            Message.is_deleted == False
        ).count()
        result.append(ConversationListResponse(
            id=convo.id, type=convo.type, name=convo.name,
            group_pic=convo.group_pic, updated_at=convo.updated_at,
            last_message=convo.last_message, unread_count=unread_count,
            participants=convo.participants
        ))
    return result


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_participant_or_403(conversation_id, current_user.id, db)
    convo = db.query(Conversation).options(
        joinedload(Conversation.participants).joinedload(ConversationParticipant.user),
        joinedload(Conversation.last_message).joinedload(Message.sender)
    ).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: int, body: ConversationUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    participant = get_participant_or_403(conversation_id, current_user.id, db)
    if participant.role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can update the group")
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if body.name is not None: convo.name = body.name
    if body.group_pic is not None: convo.group_pic = body.group_pic
    db.commit()
    db.refresh(convo)
    return convo