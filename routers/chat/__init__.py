from fastapi import APIRouter
from routers.chat import conversations, messages, participants, websocket

# Single router that main.py registers — all sub-routers included here
router = APIRouter()

router.include_router(conversations.router)
router.include_router(messages.router)
router.include_router(participants.router)
router.include_router(websocket.router)