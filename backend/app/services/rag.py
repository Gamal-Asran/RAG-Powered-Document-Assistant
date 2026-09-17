from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from time import perf_counter
from typing import Any

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

    def _sources(self, chunks) -> list[SourceResponse]:
        return [
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

    @staticmethod
    def _warn_for_invalid_citations(answer: str, sources: list[SourceResponse], conversation_id: str) -> None:
        retrieved_ids = {source.chunk_id for source in sources}
        cited_ids = set(re.findall(r"[A-Za-z0-9_]+-p\d+-c\d+", answer))
        if cited_ids - retrieved_ids:
            logger.warning("Answer contains citations outside retrieved records conversation_id=%s", conversation_id)

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
        sources = self._sources(chunks)
        self._warn_for_invalid_citations(generated.answer, sources, conversation.id)

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

    def stream_query(self, request: QueryRequest) -> Iterator[dict[str, Any]]:
        question = request.question.strip()
        if not question:
            raise ValueError("question must be non-blank")
        conversation = self.store.resolve_or_create(request.conversation_id, question)

        yield {
            "type": "status",
            "phase": "searching",
            "message": "Searching the document collection...",
        }
        started = perf_counter()
        chunks = self.retriever.retrieve(question)
        retrieval_seconds = perf_counter() - started
        if not chunks:
            raise RuntimeError("No NIST context was retrieved")
        logger.info("Streaming retrieval completed conversation_id=%s seconds=%.3f", conversation.id, retrieval_seconds)

        yield {
            "type": "status",
            "phase": "context",
            "message": "Preparing source context...",
        }
        sources = self._sources(chunks)
        yield {"type": "sources", "sources": [source.model_dump(mode="json") for source in sources]}

        history = self.store.completed_history(conversation.id, self.max_history_exchanges)
        yield {
            "type": "status",
            "phase": "model",
            "message": "Waiting for the local model...",
        }
        generation_started = perf_counter()
        stream = self.generator.stream_generate(question, chunks, history, request.thinking_enabled)
        thinking_status_sent = False
        answer_status_sent = False
        while True:
            try:
                delta = next(stream)
            except StopIteration as completed:
                generated = completed.value
                break
            if delta.kind == "thinking_delta":
                if not thinking_status_sent:
                    yield {
                        "type": "status",
                        "phase": "thinking",
                        "message": "Analyzing the evidence...",
                    }
                    thinking_status_sent = True
                yield {"type": "thinking_delta", "delta": delta.text}
            else:
                if not answer_status_sent:
                    yield {
                        "type": "status",
                        "phase": "answer",
                        "message": "Writing the response...",
                    }
                    answer_status_sent = True
                yield {"type": "answer_delta", "delta": delta.text}

        generation_seconds = perf_counter() - generation_started
        yield {
            "type": "status",
            "phase": "citations",
            "message": "Checking citations...",
        }
        self._warn_for_invalid_citations(generated.answer, sources, conversation.id)
        thinking = generated.thinking if request.thinking_enabled else ""
        self.store.append_exchange(conversation.id, question, generated.answer, thinking, sources)
        yield {
            "type": "status",
            "phase": "finalizing",
            "message": "Finalizing the answer...",
        }
        yield {
            "type": "completed",
            "conversation_id": conversation.id,
            "thinking_enabled": request.thinking_enabled,
            "retrieval_seconds": retrieval_seconds,
            "generation_seconds": generation_seconds,
            "fallback_used": generated.fallback_used,
        }
