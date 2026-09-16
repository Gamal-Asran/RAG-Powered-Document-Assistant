from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_runtime


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    ollama: str
    ollama_model: str
    embedding_device: str
    chroma_collection: str
    chroma_count: int


@router.get("/health", response_model=HealthResponse)
def health(runtime=Depends(get_runtime)) -> HealthResponse:
    return HealthResponse(
        status="healthy" if runtime.ollama_available else "degraded",
        ollama="available" if runtime.ollama_available else "unavailable",
        ollama_model=runtime.settings.ollama_model,
        embedding_device=runtime.settings.embedding_device,
        chroma_collection=runtime.settings.chroma_collection,
        chroma_count=runtime.chroma_count,
    )
