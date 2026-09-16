"""Typed HTTP client for the local NIST RAG backend."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

try:  # Supports both `streamlit run frontend/app.py` and package imports in tests.
    from .models import CONVERSATION_LIST_ADAPTER, Conversation, ConversationSummary, HealthResponse, QueryResponse
except ImportError:  # pragma: no cover - exercised by the Streamlit script entry point
    from models import CONVERSATION_LIST_ADAPTER, Conversation, ConversationSummary, HealthResponse, QueryResponse


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
