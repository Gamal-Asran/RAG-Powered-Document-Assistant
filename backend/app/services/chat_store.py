from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from uuid import UUID, uuid4

from ..schemas.conversation import ConversationResponse, ConversationSummary, MessageResponse
from ..schemas.query import SourceResponse


class ConversationNotFoundError(LookupError):
    pass


class ChatStore:
    """Thread-safe, process-local conversation storage for the prototype."""

    def __init__(self) -> None:
        self._conversations: dict[str, ConversationResponse] = {}
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_id(conversation_id: str) -> str:
        try:
            return str(UUID(conversation_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ConversationNotFoundError("conversation not found") from exc

    def create(self, first_question: str, conversation_id: str | None = None) -> ConversationResponse:
        normalized = self._normalize_id(conversation_id) if conversation_id else str(uuid4())
        now = self._now()
        title = " ".join(first_question.strip().split())[:80] or "New conversation"
        with self._lock:
            existing = self._conversations.get(normalized)
            if existing is not None:
                return existing.model_copy(deep=True)
            conversation = ConversationResponse(
                id=normalized,
                title=title,
                created_at=now,
                updated_at=now,
                message_count=0,
                messages=[],
            )
            self._conversations[normalized] = conversation
            return conversation.model_copy(deep=True)

    def resolve_or_create(self, conversation_id: str | None, first_question: str) -> ConversationResponse:
        if conversation_id is None:
            return self.create(first_question)
        normalized = self._normalize_id(conversation_id)
        with self._lock:
            existing = self._conversations.get(normalized)
        return existing.model_copy(deep=True) if existing else self.create(first_question, normalized)

    def list(self) -> list[ConversationSummary]:
        with self._lock:
            conversations = sorted(self._conversations.values(), key=lambda item: item.updated_at, reverse=True)
            return [
                ConversationSummary(
                    id=item.id,
                    title=item.title,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    message_count=len(item.messages),
                )
                for item in conversations
            ]

    def get(self, conversation_id: str) -> ConversationResponse:
        normalized = self._normalize_id(conversation_id)
        with self._lock:
            conversation = self._conversations.get(normalized)
            if conversation is None:
                raise ConversationNotFoundError("conversation not found")
            return conversation.model_copy(deep=True)

    def append_exchange(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        thinking: str,
        sources: list[SourceResponse],
    ) -> None:
        normalized = self._normalize_id(conversation_id)
        now = self._now()
        with self._lock:
            conversation = self._conversations.get(normalized)
            if conversation is None:
                raise ConversationNotFoundError("conversation not found")
            conversation.messages.extend(
                [
                    MessageResponse(id=str(uuid4()), role="user", content=question, created_at=now),
                    MessageResponse(
                        id=str(uuid4()),
                        role="assistant",
                        content=answer,
                        thinking=thinking,
                        sources=sources,
                        created_at=self._now(),
                    ),
                ]
            )
            conversation.updated_at = self._now()
            conversation.message_count = len(conversation.messages)

    def completed_history(self, conversation_id: str, max_exchanges: int) -> list[MessageResponse]:
        if max_exchanges <= 0:
            return []
        conversation = self.get(conversation_id)
        return conversation.messages[-(max_exchanges * 2) :]

    def delete(self, conversation_id: str) -> None:
        normalized = self._normalize_id(conversation_id)
        with self._lock:
            if self._conversations.pop(normalized, None) is None:
                raise ConversationNotFoundError("conversation not found")
