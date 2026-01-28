import json
import os
import time
from typing import Any, Dict

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional in dev
    redis = None


SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "7200"))


def blank_chat_context() -> Dict[str, Any]:
    return {
        "conversation_history": [],
        "last_product_query": None,
        "last_info_query": None,
        "last_wine_query": None,
        "last_menu_query": False,
        "last_shown_products": [],
        "last_interaction": None,
        "chat_session_id": None,
    }


class SessionStore:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis = None
        if redis and redis_url:
            try:
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self._redis = None
        self._mem: Dict[str, Dict[str, Any]] = {}

    def get(self, session_id: str) -> Dict[str, Any]:
        key = f"session:{session_id}"
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass

        cached = self._mem.get(session_id)
        if cached and cached.get("expires_at", 0) > time.time():
            return cached["data"]

        data = blank_chat_context()
        self._mem[session_id] = {"data": data, "expires_at": time.time() + SESSION_TTL_SECONDS}
        return data

    def set(self, session_id: str, data: Dict[str, Any]) -> None:
        self._mem[session_id] = {"data": data, "expires_at": time.time() + SESSION_TTL_SECONDS}
        if self._redis:
            try:
                self._redis.setex(
                    f"session:{session_id}",
                    SESSION_TTL_SECONDS,
                    json.dumps(data, ensure_ascii=False),
                )
            except Exception:
                pass
