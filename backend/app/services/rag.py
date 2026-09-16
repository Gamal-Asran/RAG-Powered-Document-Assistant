from __future__ import annotations

import logging
import re
from time import perf_counter

from ..schemas.query import QueryRequest, QueryResponse, SourceResponse
from .chat_store import ChatStore
from .generation import GenerationService
from .retrieval import RetrievalService


logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        retriever: RetrievalService,
        generator: GenerationService,
        store: ChatStore,
        max_history_exchanges: int = 2,
    ) -> None:
        self.retriever = retriever
        self.generator = generator
        self.store = store
        self.max_history_exchanges = max_history_exchanges

    @staticmethod
    def _preview(text: str, limit: int = 280) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        return compact[:limit] + ("…" if len(compact) > limit else "")

    def query(self, request: QueryRequest) -> QueryResponse:
        question = request.question.strip()
        if not question:
            raise ValueError("question must be non-blank")
        conversation = self.store.resolve_or_create(request.conversation_id, question)

        started = perf_counter()
        chunks = self.retriever.retrieve(question)
        retrieval_seconds = perf_counter() - started
        logger.info("Retrieval completed conversation_id=%s seconds=%.3f", conversation.id, retrieval_seconds)
        if not chunks:
            raise RuntimeError("No NIST context was retrieved")

        history = self.store.completed_history(conversation.id, self.max_history_exchanges)
        started = perf_counter()
        generated = self.generator.generate(question, chunks, history, request.thinking_enabled)
        generation_seconds = perf_counter() - started
        logger.info(
            "Generation completed conversation_id=%s thinking=%s fallback=%s seconds=%.3f",
            conversation.id,
            request.thinking_enabled,
            generated.fallback_used,
            generation_seconds,
        )
        sources = [
            SourceResponse(
                chunk_id=chunk.chunk_id,
                document_id=str(chunk.metadata["document_id"]),
                title=str(chunk.metadata["title"]),
                page=int(chunk.metadata["page"]),
                url=str(chunk.metadata["url"]),
                similarity=chunk.similarity,
                text_preview=self._preview(chunk.text),
            )
            for chunk in chunks
        ]
        retrieved_ids = {source.chunk_id for source in sources}
        cited_ids = set(re.findall(r"[A-Za-z0-9_]+-p\d+-c\d+", generated.answer))
        invalid_ids = cited_ids - retrieved_ids
        if invalid_ids:
            logger.warning("Answer contains citations outside retrieved records conversation_id=%s", conversation.id)

        thinking = generated.thinking if request.thinking_enabled else ""
        self.store.append_exchange(conversation.id, question, generated.answer, thinking, sources)
        return QueryResponse(
            conversation_id=conversation.id,
            answer=generated.answer,
            thinking=thinking,
            thinking_enabled=request.thinking_enabled,
            sources=sources,
            retrieval_seconds=retrieval_seconds,
            generation_seconds=generation_seconds,
        )
