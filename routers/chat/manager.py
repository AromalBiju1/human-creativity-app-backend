import json
from typing import Dict, List
from fastapi import WebSocket
import redis.asyncio as aioredis
from config.config import redis_url


class RedisConnectionManager:
    """
    Hybrid manager:
    - Local dict   → tracks WebSocket objects on THIS server process
    - Redis Pub/Sub → broadcasts across ALL server instances

    Flow:
      send message / media_url
            │
            ▼
      publish to Redis channel "chat:{conversation_id}"
            │
            ▼
      ALL servers subscribed to that channel receive it
            │
            ▼
      each server forwards to its LOCAL WebSocket connections
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: aioredis.Redis = None

        # Local WebSocket connections on THIS server
        # Maps conversation_id -> list of WebSocket
        self.local_connections: Dict[int, List[WebSocket]] = {}


    # Startup / Shutdown (called from main.py lifespan)


    async def startup(self):
        """Call on app startup to create the Redis connection pool"""
        self.redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

    async def shutdown(self):
        """Call on app shutdown to cleanly close Redis"""
        if self.redis:
            await self.redis.aclose()


    # Connection Lifecycle


    async def connect(self, websocket: WebSocket, conversation_id: int):
        await websocket.accept()
        if conversation_id not in self.local_connections:
            self.local_connections[conversation_id] = []
        self.local_connections[conversation_id].append(websocket)

    def disconnect(self, websocket: WebSocket, conversation_id: int):
        if conversation_id in self.local_connections:
            self.local_connections[conversation_id].remove(websocket)
            if not self.local_connections[conversation_id]:
                del self.local_connections[conversation_id]


    # Publishing — write to Redis → fans out to all servers


    async def publish(self, payload: dict, conversation_id: int):
        """
        Publish a message to the Redis channel for this conversation.
        All server instances subscribed to this channel will receive it
        and forward it to their local WebSocket connections.
        """
        channel = f"chat:{conversation_id}"
        await self.redis.publish(channel, json.dumps(payload, default=str))


    # Subscribing — read from Redis → forward to local WebSocket


    async def subscribe_and_forward(self, websocket: WebSocket, conversation_id: int):
        """
        Subscribe to the Redis channel for this conversation and
        forward every message to this specific WebSocket connection.
        Runs as a background asyncio task alongside receive_text().
        """
        channel = f"chat:{conversation_id}"

        # Each subscriber needs its OWN Redis connection
        subscriber = aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        async with subscriber.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            try:
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    await websocket.send_text(message["data"])
            except Exception:
                await pubsub.unsubscribe(channel)
            finally:
                await subscriber.aclose()


    # Typing Indicators — stored in Redis with TTL


    async def set_typing(self, conversation_id: int, user_id: int):
        """Store typing state with 5s TTL — auto-clears if client disconnects"""
        key = f"typing:{conversation_id}:{user_id}"
        await self.redis.set(key, "1", ex=5)

    async def clear_typing(self, conversation_id: int, user_id: int):
        key = f"typing:{conversation_id}:{user_id}"
        await self.redis.delete(key)


    # Online Presence — stored in Redis set


    async def set_online(self, user_id: int):
        await self.redis.sadd("online_users", str(user_id))

    async def set_offline(self, user_id: int):
        await self.redis.srem("online_users", str(user_id))

    async def is_user_online(self, user_id: int) -> bool:
        return await self.redis.sismember("online_users", str(user_id))


    # Upload State Tracking — for presigned uploads


    async def set_upload_pending(self, upload_id: str, user_id: int, conversation_id: int):
        """
        Track a pending upload so we can validate it when the
        client sends the media_url over WebSocket after uploading.
        TTL of 10 minutes — upload must complete within that window.
        """
        key = f"upload:{upload_id}"
        await self.redis.hset(key, mapping={
            "user_id": str(user_id),
            "conversation_id": str(conversation_id),
            "status": "pending"
        })
        await self.redis.expire(key, 600)  # 10 minute TTL

    async def get_upload(self, upload_id: str) -> dict | None:
        key = f"upload:{upload_id}"
        data = await self.redis.hgetall(key)
        return data if data else None

    async def clear_upload(self, upload_id: str):
        await self.redis.delete(f"upload:{upload_id}")


# Single shared instance
manager = RedisConnectionManager(redis_url=redis_url)