
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table,Enum,Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime, timedelta, timezone
import enum
followers_table = Table(
    "followers",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("following_id", Integer, ForeignKey("users.id"), primary_key=True)
)



#Enums


class ConversationType(str, enum.Enum):
    direct  = "direct"   # 1-on-1 DM
    group   = "group"    # Group chat


class ParticipantRole(str, enum.Enum):
    admin   = "admin"    # Can rename group, add/remove members
    member  = "member"   # Regular participant


class MessageType(str, enum.Enum):
    text    = "text"
    image   = "image"
    document = "document" 
    video   = "video"
    system  = "system"   # e.g. "John left the group"
 

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    bio = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    role = Column(String, default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    posts = relationship("Post", back_populates="owner")

    stories = relationship("Story", back_populates="owner")
    participations = relationship("ConversationParticipant", back_populates="user")
    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    followers = relationship(
        "User",
        secondary=followers_table,
        primaryjoin=id == followers_table.c.following_id,
        secondaryjoin=id == followers_table.c.follower_id,
        back_populates="following"
    )
    following = relationship(
        "User",
        secondary=followers_table,
        primaryjoin=id == followers_table.c.follower_id,
        secondaryjoin=id == followers_table.c.following_id,
        back_populates="followers"
    )



class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(String)
    media_url = Column(String)
    media_type = Column(String, default="image")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    media_url = Column(String)
    media_type = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    owner = relationship("User", back_populates="stories")

class Conversation(Base):
    __tablename__ = "conversations"
    id           = Column(Integer, primary_key=True, index=True)
    type         = Column(Enum(ConversationType), default=ConversationType.direct, nullable=False)
    name         = Column(String, nullable=True)       # Only used for group chats
    group_pic    = Column(String, nullable=True)       # Group avatar (Cloudinary URL)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), onupdate=func.now())
    last_message_id  = Column(Integer, ForeignKey("messages.id"), nullable=True)
    participants = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        foreign_keys="Message.conversation_id",
        order_by="Message.created_at"
    )
    last_message = relationship(
        "Message",
        foreign_keys=[last_message_id],
        post_update=True   
    )
    

class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"
    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role            = Column(Enum(ParticipantRole), default=ParticipantRole.member, nullable=False)
    joined_at       = Column(DateTime(timezone=True), server_default=func.now())
    left_at         = Column(DateTime(timezone=True), nullable=True)  # NULL = still in group
    is_active       = Column(Boolean, default=True)                   # False = left the group

    # Per-user notification preferences
    is_muted        = Column(Boolean, default=False)
    # Read receipts — tracks how far this user has read
    last_read_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)

    conversation = relationship("Conversation", back_populates="participants")
    user         = relationship("User", back_populates="participations")
    last_read    = relationship("Message", foreign_keys=[last_read_message_id])


class Message(Base):
    __tablename__ = "messages"
    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    content         = Column(Text, nullable=True)             # NULL if media-only message
    message_type    = Column(Enum(MessageType), default=MessageType.text, nullable=False)
    media_url       = Column(String, nullable=True)           # Cloudinary URL for image/video msgs
    # Threading / replies
    reply_to_id     = Column(Integer, ForeignKey("messages.id"), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    edited_at       = Column(DateTime(timezone=True), nullable=True)  # NULL = never edited
    is_deleted      = Column(Boolean, default=False)                  # Soft delete
    conversation = relationship(
        "Conversation",
        back_populates="messages",
        foreign_keys=[conversation_id]
    )
    sender   = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    reply_to = relationship("Message", remote_side="Message.id", foreign_keys=[reply_to_id])
    # ... existing columns ...
    media_filename  = Column(String, nullable=True)
 


