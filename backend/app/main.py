from __future__ import annotations

import json
import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.conversations import router as conversations_router
from .api.routes.health import router as health_router
from .api.routes.query import router as query_router
from .core.config import Settings, get_settings
from .services.chat_store import ChatStore
from .services.generation import GenerationService
from .services.rag import RAGService
from .services.retrieval import RetrievalService
from .utils.logging_config import configure_logging


logger = logging.getLogger(__name__)
EXPECTED_CHROMA_COUNT = 447
EXPECTED_EMBEDDING_DIMENSION = 384


@dataclass(slots=True)
class Runtime:
    settings: Settings
    store: ChatStore
    rag: RAGService
    ollama_available: bool
    chroma_count: int
    embedding_model: Any
    chroma_client: Any
    collection: Any
    ollama_client: Any
    chroma_snapshot: Any


def _pipeline_config(settings: Settings) -> dict[str, Any]:
    path = Path(settings.chroma_path) / "pipeline_config.json"
    if not path.is_file():
        raise RuntimeError(f"Missing persisted pipeline configuration: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "collection_name": settings.chroma_collection,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": EXPECTED_EMBEDDING_DIMENSION,
        "embedding_device": "cpu",
        "normalize_embeddings": True,
        "distance_metric": "cosine",
        "chunk_count": EXPECTED_CHROMA_COUNT,
    }
    mismatches = [key for key, value in expected.items() if config.get(key) != value]
    if mismatches:
        raise RuntimeError(f"Persisted pipeline configuration mismatch: {', '.join(mismatches)}")
    return config


def _installed_model_names(client: Any) -> set[str]:
    response = client.list()
    models = getattr(response, "models", None)
    if models is None and isinstance(response, dict):
        models = response.get("models", [])
    names: set[str] = set()
    for model in models or []:
        name = getattr(model, "model", None) or getattr(model, "name", None)
        if name is None and isinstance(model, dict):
            name = model.get("model") or model.get("name")
        if name:
            names.add(str(name))
    return names


def _collection_distance_metric(collection: Any) -> str | None:
    configuration = getattr(collection, "configuration", None)
    if isinstance(configuration, dict):
        hnsw = configuration.get("hnsw") or {}
        if hnsw.get("space"):
            return str(hnsw["space"])
    metadata = getattr(collection, "metadata", None) or {}
    return metadata.get("hnsw:space")


def load_runtime(settings: Settings) -> Runtime:
    import chromadb
    import ollama
    from sentence_transformers import SentenceTransformer

    pipeline = _pipeline_config(settings)
    logger.info("Loading embedding model=%s device=cpu", settings.embedding_model)
    embedding_model = SentenceTransformer(settings.embedding_model, device="cpu", local_files_only=True)
    embedding_model.max_seq_length = int(pipeline.get("embedding_max_seq_length", 452))
    device = getattr(getattr(embedding_model, "device", None), "type", None)
    dimension_method = getattr(embedding_model, "get_embedding_dimension", None)
    dimension = dimension_method() if dimension_method else embedding_model.get_sentence_embedding_dimension()
    if device != "cpu" or int(dimension) != EXPECTED_EMBEDDING_DIMENSION:
        raise RuntimeError("Embedding model must report CPU and 384 dimensions")

    # Chroma 1.5.x writes internal HNSW/SQLite bookkeeping even for read-only opens.
    # Query an ephemeral snapshot so the notebook's frozen store stays byte-for-byte immutable.
    chroma_snapshot = tempfile.TemporaryDirectory(prefix="nist-rag-chroma-")
    snapshot_path = Path(chroma_snapshot.name) / "vector_store"
    shutil.copytree(settings.chroma_path, snapshot_path)
    chroma_client = chromadb.PersistentClient(path=str(snapshot_path))
    collection = chroma_client.get_collection(name=settings.chroma_collection, embedding_function=None)
    chroma_count = collection.count()
    if chroma_count != EXPECTED_CHROMA_COUNT:
        raise RuntimeError(f"Expected 447 Chroma records, found {chroma_count}")
    if _collection_distance_metric(collection) != "cosine":
        raise RuntimeError("Chroma collection must use cosine distance")

    ollama_client = ollama.Client(host=settings.ollama_host, timeout=600)
    ollama_available = False
    try:
        installed = _installed_model_names(ollama_client)
        ollama_available = settings.ollama_model in installed
        if not ollama_available:
            logger.warning("Ollama reachable but model %s is not installed", settings.ollama_model)
    except Exception as exc:
        logger.warning("Ollama unavailable during startup: %s", type(exc).__name__)

    store = ChatStore()
    retriever = RetrievalService(embedding_model, collection, settings.retrieval_top_k)
    generator = GenerationService(
        ollama_client,
        settings.ollama_model,
        settings.ollama_context,
        settings.ollama_temperature,
        settings.ollama_num_predict,
        Lock(),
    )
    rag = RAGService(retriever, generator, store, settings.max_history_exchanges)
    logger.info(
        "Startup ready collection=%s count=%d embedding_device=cpu ollama=%s model=%s",
        settings.chroma_collection,
        chroma_count,
        "available" if ollama_available else "unavailable",
        settings.ollama_model,
    )
    return Runtime(
        settings=settings,
        store=store,
        rag=rag,
        ollama_available=ollama_available,
        chroma_count=chroma_count,
        embedding_model=embedding_model,
        chroma_client=chroma_client,
        collection=collection,
        ollama_client=ollama_client,
        chroma_snapshot=chroma_snapshot,
    )


def create_app(
    settings: Settings | None = None,
    runtime_loader: Callable[[Settings], Any] = load_runtime,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.runtime = runtime_loader(resolved_settings)
        try:
            yield
        finally:
            snapshot = getattr(application.state.runtime, "chroma_snapshot", None)
            if snapshot is not None:
                snapshot.cleanup()

    application = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(query_router)
    application.include_router(conversations_router)
    return application


configure_logging()
app = create_app()
