from __future__ import annotations

from threading import Lock
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.services.generation import GenerationService
from backend.app.services.retrieval import RetrievedChunk


class FakeOllamaClient:
    def __init__(self, *, content: str, thinking: str = "") -> None:
        self.response = SimpleNamespace(message=SimpleNamespace(content=content, thinking=thinking))
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


@pytest.fixture
def chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="nist_ai_rmf_1_0-p0021-c000",
        text="The Core is composed of four functions: GOVERN, MAP, MEASURE, and MANAGE.",
        metadata={
            "chunk_id": "nist_ai_rmf_1_0-p0021-c000",
            "document_id": "nist_ai_rmf_1_0",
            "title": "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
            "page": 21,
            "url": "https://example.test/nist-ai-rmf.pdf",
        },
        distance=0.1,
        similarity=0.9,
    )


def make_service(client: Any) -> GenerationService:
    return GenerationService(client, "qwen3:4b", 4096, 0.1, 1024, Lock())


class FakeStreamingOllamaClient:
    def __init__(self, chunks: list[tuple[str, str]]) -> None:
        self.chunks = chunks
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return iter(
            SimpleNamespace(message=SimpleNamespace(thinking=thinking, content=content))
            for thinking, content in self.chunks
        )


def collect_stream(stream):
    deltas = []
    while True:
        try:
            deltas.append(next(stream))
        except StopIteration as completed:
            return deltas, completed.value


@pytest.mark.parametrize(
    "content",
    [
        "<think>Use the supplied framework passage.</think>GOVERN, MAP, MEASURE, and MANAGE.",
        "Use the supplied framework passage.</think>GOVERN, MAP, MEASURE, and MANAGE.",
    ],
)
def test_thinking_enabled_separates_inline_reasoning(content: str, chunk: RetrievedChunk) -> None:
    client = FakeOllamaClient(content=content)

    result = make_service(client).generate("What are the four core functions?", [chunk], [], True)

    assert result.answer == "GOVERN, MAP, MEASURE, and MANAGE."
    assert result.thinking == "Use the supplied framework passage."
    assert client.calls[0]["think"] is True
    assert "/no_think" not in client.calls[0]["messages"][-1]["content"]
    assert "<think>" not in result.answer and "</think>" not in result.answer


def test_thinking_disabled_discards_orphan_tag_reasoning(chunk: RetrievedChunk) -> None:
    client = FakeOllamaClient(
        content="Private reasoning that must not leak.</think>The four functions are GOVERN, MAP, MEASURE, and MANAGE.",
        thinking="Structured private reasoning.",
    )

    result = make_service(client).generate("What are the four core functions?", [chunk], [], False)

    assert result.answer == "The four functions are GOVERN, MAP, MEASURE, and MANAGE."
    assert result.thinking == ""
    assert client.calls[0]["think"] is False
    assert client.calls[0]["messages"][-1]["content"].startswith("/no_think\n\n")
    assert "Private reasoning" not in result.answer
    assert "<think>" not in result.answer and "</think>" not in result.answer


def test_structured_thinking_stays_separate_from_final_content(chunk: RetrievedChunk) -> None:
    client = FakeOllamaClient(
        content="The four functions are GOVERN, MAP, MEASURE, and MANAGE.",
        thinking="I matched the question to the retrieved passage.",
    )

    result = make_service(client).generate("What are the four core functions?", [chunk], [], True)

    assert result.answer == "The four functions are GOVERN, MAP, MEASURE, and MANAGE."
    assert result.thinking == "I matched the question to the retrieved passage."
    assert result.thinking not in result.answer


def test_streaming_structured_thinking_and_answer_are_separate(chunk: RetrievedChunk) -> None:
    client = FakeStreamingOllamaClient(
        [
            ("Inspecting ", ""),
            ("the evidence.", ""),
            ("", "GOVERN, MAP, "),
            ("", "MEASURE, and MANAGE."),
        ]
    )

    deltas, result = collect_stream(
        make_service(client).stream_generate("What are the four core functions?", [chunk], [], True)
    )

    assert "".join(delta.text for delta in deltas if delta.kind == "thinking_delta") == (
        "Inspecting the evidence."
    )
    assert "".join(delta.text for delta in deltas if delta.kind == "answer_delta") == (
        "GOVERN, MAP, MEASURE, and MANAGE."
    )
    assert result.answer == "GOVERN, MAP, MEASURE, and MANAGE."
    assert result.thinking == "Inspecting the evidence."
    assert client.calls[0]["stream"] is True
    assert client.calls[0]["think"] is True


def test_streaming_orphan_close_tag_never_leaks_disabled_reasoning(chunk: RetrievedChunk) -> None:
    client = FakeStreamingOllamaClient(
        [("", "Private reasoning"), ("", "</thi"), ("", "nk>Final answer.")]
    )

    deltas, result = collect_stream(
        make_service(client).stream_generate("What are the four core functions?", [chunk], [], False)
    )

    assert [(delta.kind, delta.text) for delta in deltas] == [("answer_delta", "Final answer.")]
    assert result.answer == "Final answer."
    assert result.thinking == ""
    assert client.calls[0]["think"] is False
    assert client.calls[0]["messages"][-1]["content"].startswith("/no_think\n\n")
