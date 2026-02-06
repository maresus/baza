from typing import Any, List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class ActionButton(BaseModel):
    label: str
    payload: str


class UIBlock(BaseModel):
    type: str  # "text", "buttons", "list", "image"
    content: Any


class ChatResponse(BaseModel):
    reply: str
    blocks: List[UIBlock] = []
    intent: Optional[str] = None
    session_id: Optional[str] = None
