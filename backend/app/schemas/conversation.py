from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .query import SourceResponse


class MessageResponse(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: str = ""
    sources: list[SourceResponse] = Field(default_factory=list)
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationResponse(ConversationSummary):
    messages: list[MessageResponse]
