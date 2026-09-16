"""Validated frontend representations of the backend API contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(APIModel):
    status: Literal["healthy", "degraded"]
    ollama: Literal["available", "unavailable"]
    ollama_model: str
    embedding_device: str
    chroma_collection: str
    chroma_count: int = Field(ge=0)


class Source(APIModel):
    chunk_id: str
    document_id: str
    title: str
    page: int = Field(gt=0)
    url: str
    similarity: float
    text_preview: str


class QueryResponse(APIModel):
    conversation_id: str
    answer: str
    thinking: str
    thinking_enabled: bool
    sources: list[Source]
    status: Literal["completed"]
    retrieval_seconds: float = Field(ge=0)
    generation_seconds: float = Field(ge=0)


class ConversationSummary(APIModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(ge=0)


class Message(APIModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: str = ""
    sources: list[Source] = Field(default_factory=list)
    created_at: datetime
    retrieval_seconds: float | None = Field(default=None, ge=0)
    generation_seconds: float | None = Field(default=None, ge=0)
    thinking_requested: bool | None = None


class StoredMessage(APIModel):
    """Exact message shape returned by GET /conversations/{id}."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    thinking: str = ""
    sources: list[Source] = Field(default_factory=list)
    created_at: datetime

    def for_display(self) -> Message:
        return Message(**self.model_dump(), thinking_requested=bool(self.thinking.strip()))


class Conversation(ConversationSummary):
    messages: list[StoredMessage]


CONVERSATION_LIST_ADAPTER = TypeAdapter(list[ConversationSummary])


def prepare_sources(sources: list[Source]) -> list[Source]:
    """Deduplicate sources by chunk ID while retaining backend rank order."""
    seen: set[str] = set()
    result: list[Source] = []
    for source in sources:
        if source.chunk_id not in seen:
            seen.add(source.chunk_id)
            result.append(source)
    return result
