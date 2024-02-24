from redis import asyncio as aioredis
from redis import Redis
from django.conf import settings


async def get_redis() -> Redis:
    redis = await aioredis.from_url(settings.REDIS_URL)
    return redis
