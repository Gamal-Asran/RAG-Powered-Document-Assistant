from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services.chat_store import ChatStore
from backend.app.services.generation import GenerationDelta, GenerationError, GenerationResult
from backend.app.services.rag import RAGService
from backend.app.services.retrieval import RetrievedChunk


class FakeRetriever:
    def retrieve(self, question: str) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id=f"nist_ai_rmf_1_0-p000{i + 1}-c000",
                text=f"NIST evidence for {question}, source {i + 1}. " * 8,
                metadata={
                    "chunk_id": f"nist_ai_rmf_1_0-p000{i + 1}-c000",
                    "document_id": "nist_ai_rmf_1_0",
                    "title": "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
                    "page": i + 1,
                    "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf",
                },
                distance=0.2 + i * 0.01,
                similarity=0.8 - i * 0.01,
            )
            for i in range(4)
        ]


class FakeGenerator:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def generate(self, question, chunks, history, thinking_enabled):
        if self.fail:
            raise GenerationError("Ollama generation failed; verify local service")
        return GenerationResult(
            answer="The four functions are GOVERN, MAP, MEASURE, and MANAGE.",
            thinking="I used the retrieved framework evidence." if thinking_enabled else "",
        )

    def stream_generate(self, question, chunks, history, thinking_enabled):
        if self.fail:
            raise GenerationError("Ollama generation failed; verify local service")
        if thinking_enabled:
            yield GenerationDelta("thinking_delta", "I used the retrieved framework evidence.")
        yield GenerationDelta("answer_delta", "The four functions are ")
        yield GenerationDelta("answer_delta", "GOVERN, MAP, MEASURE, and MANAGE.")
        return GenerationResult(
            answer="The four functions are GOVERN, MAP, MEASURE, and MANAGE.",
            thinking="I used the retrieved framework evidence." if thinking_enabled else "",
        )


def build_runtime(*, available: bool = True, generation_fails: bool = False):
    settings = Settings()
    store = ChatStore()
    rag = RAGService(FakeRetriever(), FakeGenerator(generation_fails), store, max_history_exchanges=2)
    return SimpleNamespace(
        settings=settings,
        store=store,
        rag=rag,
        ollama_available=available,
        chroma_count=447,
    )


@pytest.fixture
def runtime():
    return build_runtime()


@pytest.fixture
def client(runtime):
    app = create_app(settings=runtime.settings, runtime_loader=lambda _: runtime)
    with TestClient(app) as test_client:
        yield test_client
