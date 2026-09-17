import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..dependencies import get_runtime
from ...schemas.query import QueryRequest, QueryResponse
from ...services.chat_store import ConversationNotFoundError
from ...services.generation import GenerationError


logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


def _ndjson(event: dict) -> bytes:
    return (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, runtime=Depends(get_runtime)) -> QueryResponse:
    if not runtime.ollama_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama or qwen3:4b is unavailable. Start Ollama and install the configured model.",
        )
    try:
        return runtime.rag.query(payload)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except GenerationError as exc:
        logger.error("Generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected query failure")
        raise HTTPException(status_code=500, detail="Unexpected internal error") from exc


@router.post("/query/stream")
def query_stream(payload: QueryRequest, runtime=Depends(get_runtime)) -> StreamingResponse:
    if not runtime.ollama_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama or qwen3:4b is unavailable. Start Ollama and install the configured model.",
        )

    def events() -> Iterator[bytes]:
        try:
            for event in runtime.rag.stream_query(payload):
                yield _ndjson(event)
        except ConversationNotFoundError:
            yield _ndjson({"type": "error", "code": "conversation_not_found", "message": "Conversation not found."})
        except GenerationError as exc:
            logger.error("Streaming generation failed: %s", exc)
            yield _ndjson(
                {
                    "type": "error",
                    "code": "generation_failed",
                    "message": "The local model could not complete the response. Try again without thinking mode.",
                }
            )
        except Exception:
            logger.exception("Unexpected streaming query failure")
            yield _ndjson(
                {
                    "type": "error",
                    "code": "internal_error",
                    "message": "The request could not be completed.",
                }
            )

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"},
    )
