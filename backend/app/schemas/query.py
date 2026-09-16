from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None
    thinking_enabled: bool = False

    @field_validator("question", mode="before")
    @classmethod
    def strip_question(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if len(value) < 2:
            raise ValueError("question must contain at least 2 non-whitespace characters")
        return value


class SourceResponse(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    page: int = Field(gt=0)
    url: str
    similarity: float
    text_preview: str


class QueryResponse(BaseModel):
    conversation_id: str
    answer: str
    thinking: str
    thinking_enabled: bool
    sources: list[SourceResponse]
    status: str = "completed"
    retrieval_seconds: float = Field(ge=0)
    generation_seconds: float = Field(ge=0)
