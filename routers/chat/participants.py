from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import User, ConversationParticipant, ParticipantRole
from database.schemas import ParticipantResponse, ParticipantUpdate
from routers.auth.auth import get_current_user
from routers.chat.dependencies import get_participant_or_403

router = APIRouter()


@router.post("/{conversation_id}/participants/{user_id}", status_code=status.HTTP_201_CREATED)
def add_participant(conversation_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if get_participant_or_403(conversation_id, current_user.id, db).role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can add members")
    existing = db.query(ConversationParticipant).filter_by(conversation_id=conversation_id, user_id=user_id).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="User already in conversation")
        existing.is_active = True
        existing.left_at = None
    else:
        db.add(ConversationParticipant(conversation_id=conversation_id, user_id=user_id, role=ParticipantRole.member))
    db.commit()
    return {"detail": "Participant added"}


@router.delete("/{conversation_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(conversation_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    requester = get_participant_or_403(conversation_id, current_user.id, db)
    if user_id != current_user.id and requester.role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can remove other members")
    target = db.query(ConversationParticipant).filter_by(conversation_id=conversation_id, user_id=user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Participant not found")
    target.is_active = False
    target.left_at = datetime.utcnow()
    db.commit()


@router.patch("/{conversation_id}/participants/{user_id}", response_model=ParticipantResponse)
def update_participant_role(conversation_id: int, user_id: int, body: ParticipantUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if get_participant_or_403(conversation_id, current_user.id, db).role != ParticipantRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can change roles")
    target = db.query(ConversationParticipant).filter_by(conversation_id=conversation_id, user_id=user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Participant not found")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return target