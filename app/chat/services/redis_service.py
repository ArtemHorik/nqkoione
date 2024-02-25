from redis.asyncio import Redis


class RedisService:
    def __init__(self, redis, room_id, session_id):
        self.redis: Redis = redis
        self.room_id = room_id
        self.session_id = session_id

    async def get_users_count(self) -> int:
        users_count = await self.redis.get(f'users_count:{self.room_id}')
        return int(users_count) if users_count else 0

    async def decr_users_count(self):
        await self.redis.decr(f'users_count:{self.room_id}', 1)

    async def incr_users_count(self):
        await self.redis.incr(f'users_count:{self.room_id}', 1)

    async def in_session_ids(self) -> bool:
        return bool(await self.redis.sismember(f'sessions:{self.room_id}', self.session_id))

    async def session_ids_append(self) -> None:
        if await self.session_ids_count() < 2:
            await self.redis.sadd(f'sessions:{self.room_id}', self.session_id)
        else:
            raise ValueError('You cannot have more than two sessions.')

    async def session_ids_count(self) -> int:
        return await self.redis.scard(f'sessions:{self.room_id}')

    async def close_redis(self):
        await self.redis.close()
        print(f'REDIS CLOSED FOR SESSION ID {self.session_id}')

    async def delete_redis_data(self):
        await self.redis.delete(f'sessions:{self.room_id}', f'users_count:{self.room_id}')

    async def users_exists(self) -> bool:
        return await self.redis.exists(f'users_count:{self.room_id}')

    async def is_already_connected(self) -> bool:
        return await self.redis.exists(f'session:{self.session_id}:connections')

    async def mark_as_connected(self):
        await self.redis.incr(f'session:{self.session_id}:connections')

    async def unmark_as_connected(self):
        await self.redis.delete(f'session:{self.session_id}:connections')
