from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from database.models import MessageType,ConversationType,ParticipantRole
class OwnerInfo(BaseModel):
    username: str
    profile_pic: Optional[str] = None
    class Config:
        from_attributes = True

# --- User Schemas ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    identifier: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    bio: Optional[str] = None     
    profile_pic: Optional[str] = None
    is_verified: bool
    role: str

    class Config: 
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

# --- Post Schemas ---
class PostBase(BaseModel): 
    title: str = None 
    content: Optional[str] = None

class PostResponse(PostBase):
    id: int
    media_url: str 
    media_type: str
    created_at: datetime
    owner_id: int
    owner: Optional[OwnerInfo] = None 

    class Config:  
        from_attributes = True


class UserMiniResponse(BaseModel):
    id:int
    username:str

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):

    id: int
    username: str
    email: EmailStr
    is_verified: bool
    bio: Optional[str] = None
    profile_pic: Optional[str] = None
    role: str
    created_at: datetime

    posts: list[PostResponse] = []
    followers: list[UserMiniResponse] = []
    following: list[UserMiniResponse] = []

    class Config:
        from_attributes = True




class StoryResponse(BaseModel):
    id: int
    media_url: str
    media_type: str
    created_at: datetime
    owner_id: int
    owner: Optional[OwnerInfo] = None

    class Config:
        from_attributes = True


class UserSearchResult(BaseModel):
    id: int
    username: str
    followers_count: int
    is_following: bool  # 👈 This tells frontend to show Follow/Unfollow button


# Message Schemas

class MessageCreate(BaseModel):
    """Used when sending a message via REST (not WebSocket)"""
    content: Optional[str] = None
    message_type: MessageType = MessageType.text
    media_url: Optional[str] = None       # Cloudinary URL if image/video
    reply_to_id: Optional[int] = None     # ID of message being replied to


class MessageUpdate(BaseModel):
    """Used for editing a message"""
    content: str                           # Can only edit text content


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: Optional[str] = None
    message_type: MessageType
    media_url: Optional[str] = None
    reply_to_id: Optional[int] = None
    created_at: datetime
    edited_at: Optional[datetime] = None  # None = never edited
    is_deleted: bool
    # Nested sender info — avoids extra API calls on the frontend
    sender: Optional[OwnerInfo] = None
    # Nested reply preview — shows a snippet of the replied-to message
    reply_to: Optional["MessageResponse"] = None
    media_filename: Optional[str] = None   

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Participant Schemas
# ─────────────────────────────────────────────

class ParticipantResponse(BaseModel):
    id: int
    conversation_id: int
    user_id: int
    role: ParticipantRole
    joined_at: datetime
    left_at: Optional[datetime] = None    # None = still active in group
    is_active: bool
    is_muted: bool
    last_read_message_id: Optional[int] = None
    # Nested user info for displaying member list
    user: Optional[OwnerInfo] = None


    class Config:
        from_attributes = True


class FollowResponse(BaseModel):
    message: str
    followers_count: int


class ParticipantUpdate(BaseModel):
    """Used by admins to change a member's role"""
    role: ParticipantRole


# ─────────────────────────────────────────────
# Conversation Schemas
# ─────────────────────────────────────────────

class ConversationCreate(BaseModel):
    """
    For DM:    pass a single user_id in participant_ids
    For group: pass multiple user_ids + a name
    """
    type: ConversationType = ConversationType.direct
    name: Optional[str] = None            # Required for group chats
    participant_ids: list[int]            # User IDs to add (excluding self — added automatically)


class ConversationUpdate(BaseModel):
    """Group chat settings — only admins can update"""
    name: Optional[str] = None
    group_pic: Optional[str] = None       # Cloudinary URL


class ConversationResponse(BaseModel):
    id: int
    type: ConversationType
    name: Optional[str] = None
    group_pic: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    participants: list[ParticipantResponse] = []

    # Last message preview — shown in the inbox/conversation list
    last_message: Optional[MessageResponse] = None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """
    Lightweight version for the inbox/conversation list screen.
    Avoids loading all messages — only shows the last message preview.
    """
    id: int
    type: ConversationType
    name: Optional[str] = None
    group_pic: Optional[str] = None
    updated_at: Optional[datetime] = None
    last_message: Optional[MessageResponse] = None
    # Unread count for this user — computed in the router, not the DB
    unread_count: int = 0
    # Participants needed to show the other person's avatar in a DM
    participants: list[ParticipantResponse] = []

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# WebSocket Schemas
# ─────────────────────────────────────────────

class WSMessageIn(BaseModel):
    """Shape of JSON the client sends over WebSocket"""
    content: Optional[str] = None
    message_type: MessageType = MessageType.text
    media_url: Optional[str] = None
    reply_to_id: Optional[int] = None
    media_filename: Optional[str] = None   # ✅ original filename
    upload_id: Optional[str] = None        # ✅ from request-upload response


class WSMessageOut(BaseModel):
    """Shape of JSON the server broadcasts over WebSocket"""
    event: str                            # "new_message" | "message_edited" | "message_deleted" | "user_typing"
    conversation_id: int
    message: Optional[MessageResponse] = None
    sender: Optional[OwnerInfo] = None    # Used for "user_typing" events (no message needed)
