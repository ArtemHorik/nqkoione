from redis.asyncio import Redis

from chat.services.mongo_service import AsyncMongoService
from chat.services.redis_service import RedisService


class ChatService(RedisService, AsyncMongoService):
    def __init__(self, redis: Redis, room_id: str, session_id: str):
        super(ChatService, self).__init__(redis=redis, room_id=room_id, session_id=session_id)

    async def delete_chat_data(self):
        await self.delete_room_by_id(self.room_id)
        await self.delete_redis_data()

