"""Typed HTTP client for the local NIST RAG backend."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
from pydantic import ValidationError

try:  # Supports both `streamlit run frontend/app.py` and package imports in tests.
    from .models import (
        CONVERSATION_LIST_ADAPTER,
        STREAM_EVENT_ADAPTER,
        CompletedEvent,
        Conversation,
        ConversationSummary,
        ErrorEvent,
        HealthResponse,
        QueryResponse,
        StreamEvent,
    )
except ImportError:  # pragma: no cover - exercised by the Streamlit script entry point
    from models import (
        CONVERSATION_LIST_ADAPTER,
        STREAM_EVENT_ADAPTER,
        CompletedEvent,
        Conversation,
        ConversationSummary,
        ErrorEvent,
        HealthResponse,
        QueryResponse,
        StreamEvent,
    )


class FrontendAPIError(RuntimeError):
    """Base class for errors safe for the frontend to classify."""


class BackendUnavailableError(FrontendAPIError):
    pass


class BackendTimeoutError(FrontendAPIError):
    pass


class BackendValidationError(FrontendAPIError):
    pass


class ConversationNotFoundError(FrontendAPIError):
    pass


class BackendGenerationError(FrontendAPIError):
    pass


class BackendRequestError(FrontendAPIError):
    pass


class BackendClient:
    """Small synchronous client; each request owns and closes its HTTP client."""

    def __init__(
        self,
        base_url: str,
        *,
        query_timeout: float = 300.0,
        short_timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.query_timeout = query_timeout
        self.short_timeout = short_timeout
        self.transport = transport

    def _request(self, method: str, path: str, *, timeout: float, **kwargs: Any) -> httpx.Response:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                transport=self.transport,
            ) as client:
                return client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise BackendTimeoutError("backend request timed out") from exc
        except httpx.RequestError as exc:
            raise BackendUnavailableError("backend is unavailable") from exc

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        try:
            detail = response.json().get("detail", "")
            return str(detail)
        except (ValueError, AttributeError):
            return ""

    def _raise_for_status(self, response: httpx.Response, *, query: bool = False) -> None:
        if response.status_code == 404:
            raise ConversationNotFoundError("conversation not found")
        if response.status_code == 422:
            raise BackendValidationError(self._detail(response) or "request validation failed")
        if query and response.status_code == 503:
            raise BackendGenerationError(self._detail(response) or "generation failed")
        if response.status_code >= 400:
            raise BackendRequestError(self._detail(response) or f"backend returned HTTP {response.status_code}")

    @staticmethod
    def _parse(model: type[Any], response: httpx.Response) -> Any:
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise BackendValidationError("backend returned an invalid response") from exc

    def health(self) -> HealthResponse:
        """Get health, retrying one connection/timeout failure only."""
        last_error: FrontendAPIError | None = None
        for _ in range(2):
            try:
                response = self._request("GET", "/health", timeout=self.short_timeout)
                self._raise_for_status(response)
                return self._parse(HealthResponse, response)
            except (BackendUnavailableError, BackendTimeoutError) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    def query(
        self,
        question: str,
        conversation_id: str | None,
        thinking_enabled: bool,
    ) -> QueryResponse:
        response = self._request(
            "POST",
            "/query",
            timeout=self.query_timeout,
            json={
                "question": question,
                "conversation_id": conversation_id,
                "thinking_enabled": thinking_enabled,
            },
        )
        self._raise_for_status(response, query=True)
        return self._parse(QueryResponse, response)

    def query_stream(
        self,
        question: str,
        conversation_id: str | None,
        thinking_enabled: bool,
    ) -> Iterator[StreamEvent]:
        payload = {
            "question": question,
            "conversation_id": conversation_id,
            "thinking_enabled": thinking_enabled,
        }
        timeout = httpx.Timeout(
            connect=self.short_timeout,
            read=None,
            write=self.short_timeout,
            pool=self.short_timeout,
        )
        sources_seen = False
        answer_seen = False
        completed_seen = False
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=timeout,
                transport=self.transport,
            ) as client:
                with client.stream("POST", "/query/stream", json=payload) as response:
                    if response.status_code >= 400:
                        response.read()
                        self._raise_for_status(response, query=True)
                    for line in response.iter_lines():
                        if not line.strip():
                            continue
                        try:
                            event = STREAM_EVENT_ADAPTER.validate_python(json.loads(line))
                        except (json.JSONDecodeError, ValidationError) as exc:
                            raise BackendValidationError("backend returned a malformed stream event") from exc
                        if completed_seen:
                            raise BackendValidationError("backend returned an event after completion")
                        if isinstance(event, ErrorEvent):
                            raise BackendGenerationError(event.message)
                        if event.type == "sources":
                            if sources_seen or answer_seen:
                                raise BackendValidationError("backend returned stream events out of order")
                            sources_seen = True
                        elif event.type == "thinking_delta":
                            if not sources_seen or answer_seen:
                                raise BackendValidationError("backend returned stream events out of order")
                        elif event.type == "answer_delta":
                            if not sources_seen:
                                raise BackendValidationError("backend returned stream events out of order")
                            answer_seen = True
                        elif isinstance(event, CompletedEvent):
                            if not sources_seen or not answer_seen:
                                raise BackendValidationError("backend completed an incomplete stream")
                            completed_seen = True
                        yield event
        except BackendGenerationError:
            raise
        except BackendValidationError:
            raise
        except httpx.TimeoutException as exc:
            raise BackendTimeoutError("backend stream timed out") from exc
        except httpx.RequestError as exc:
            raise BackendUnavailableError("backend stream was interrupted") from exc
        if not completed_seen:
            raise BackendValidationError("backend stream ended before completion")

    def list_conversations(self) -> list[ConversationSummary]:
        response = self._request("GET", "/conversations", timeout=self.short_timeout)
        self._raise_for_status(response)
        try:
            return CONVERSATION_LIST_ADAPTER.validate_python(response.json())
        except (ValueError, ValidationError) as exc:
            raise BackendValidationError("backend returned an invalid conversation list") from exc

    def get_conversation(self, conversation_id: str) -> Conversation:
        response = self._request(
            "GET", f"/conversations/{conversation_id}", timeout=self.short_timeout
        )
        self._raise_for_status(response)
        return self._parse(Conversation, response)

    def delete_conversation(self, conversation_id: str) -> None:
        response = self._request(
            "DELETE", f"/conversations/{conversation_id}", timeout=self.short_timeout
        )
        self._raise_for_status(response)
