"""Redis 缓存：连不上时自动降级为不缓存，保证 demo 永远能跑。"""
import hashlib
import json

import redis

from app.config import settings

try:
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    r.ping()
except Exception:
    r = None


def cache_key(question: str) -> str:
    return "rag:chat:" + hashlib.md5(question.encode()).hexdigest()


def get_cached(question: str):
    if r is None:
        return None
    data = r.get(cache_key(question))
    return json.loads(data) if data else None


def set_cached(question: str, answer: str, source: str):
    if r is None:
        return
    r.set(cache_key(question), json.dumps(
        {"answer": answer, "source": source}, ensure_ascii=False),
        ex=settings.cache_ttl)
