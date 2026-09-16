import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_runtime
from ...schemas.query import QueryRequest, QueryResponse
from ...services.chat_store import ConversationNotFoundError
from ...services.generation import GenerationError


logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])


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
