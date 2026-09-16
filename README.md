# NIST AI Risk Assistant

A local Retrieval-Augmented Generation (RAG) assistant for the NIST AI Risk
Management Framework, the Generative AI Profile, and the AI RMF Playbook.

The application retrieves passages from a persisted Chroma index, asks a local
`qwen3:4b` model to produce a grounded answer, and displays the answer, sources,
optional thinking, and in-memory conversation history in a Streamlit chat UI.
No cloud model or external inference API is used.
![Chat Screenshot](screenshots/chat.png)


## Quick start (existing prepared checkout)

Use three terminals from the repository root.

### 1. Start Ollama

```bash
ollama serve
```

Skip this command if Ollama is already running as a service. Confirm that the
required model is installed:

```bash
ollama list
ollama show qwen3:4b
```

### 2. Start the backend

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --port 8000
```

Wait for `Application startup complete`, then check:

```bash
curl http://127.0.0.1:8000/health
```

### 3. Start the frontend

```bash
source .venv/bin/activate
streamlit run frontend/app.py --server.port 8501
```

Open **http://localhost:8501** and ask:

> What are the four core functions of the AI RMF?

The first backend startup loads the embedding model and the local vector index,
so it can take several seconds. Generation is non-streaming and may take a few
minutes on CPU or modest local hardware.

## Fresh installation

Prerequisites:

- Python 3.10 or newer
- Git
- Ollama
- Enough memory to run `qwen3:4b`

Clone the project and install both application layers into one virtual environment:

```bash
git clone <repository-url>
cd RAG-Powered-Document-Assistant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Install the local LLM:

```bash
ollama pull qwen3:4b
```

The backend deliberately loads the embedding model in offline-only mode. Cache
it once on a machine with network access before starting the backend:

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

Then follow the three-terminal quick start above. The three NIST PDFs and the
persisted 447-chunk Chroma index are included in this repository; rebuilding the
index is not required for normal use.

### Windows activation

PowerShell users can activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The remaining `uvicorn` and `streamlit` commands are the same.

## Architecture

```text
Browser
  │
  ▼
Streamlit frontend (:8501)
  │  HTTP/JSON
  ▼
FastAPI backend (:8000)
  ├── MiniLM query embedding (CPU)
  ├── persisted Chroma index (447 chunks, top 4)
  ├── in-memory conversation store
  └── Ollama qwen3:4b (:11434)
```

The frontend never imports or connects directly to Ollama, ChromaDB,
SentenceTransformers, or PyTorch.

## Configuration

Backend variables are documented in [`backend/.env.example`](backend/.env.example):

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama service |
| `OLLAMA_MODEL` | `qwen3:4b` | Generation model |
| `OLLAMA_CONTEXT` | `4096` | Model context window |
| `OLLAMA_NUM_PREDICT` | `1024` | Maximum generated tokens |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Query embedding model |
| `CHROMA_PATH` | `backend/data/vector_store` | Persisted vector index |
| `RETRIEVAL_TOP_K` | `4` | Sources returned per answer |
| `MAX_HISTORY_EXCHANGES` | `2` | Recent exchanges added to prompts |

Frontend variables are documented in [`frontend/.env.example`](frontend/.env.example):

| Variable | Default | Purpose |
|---|---|---|
| `API_BASE_URL` | `http://127.0.0.1:8000` | FastAPI base URL |
| `QUERY_TIMEOUT_SECONDS` | `300` | Local generation timeout |

Copy the example files to `.env` before customizing them. Real `.env` files are
ignored by Git.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend, Ollama, embedding, and index status |
| `POST` | `/query` | Retrieve sources and generate an answer |
| `GET` | `/conversations` | List in-memory conversations |
| `GET` | `/conversations/{id}` | Load a complete conversation |
| `DELETE` | `/conversations/{id}` | Delete a conversation |

Example query:

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What are the four core functions of the AI RMF?",
    "conversation_id": null,
    "thinking_enabled": false
  }'
```

Interactive API documentation is available at **http://127.0.0.1:8000/docs**.

## Testing

Tests use mocks and do not start Ollama or load ML models:

```bash
source .venv/bin/activate
python -m pytest backend/tests frontend/tests -q
```

Run the real backend smoke test only while the backend and Ollama are running:

```bash
python backend/scripts/smoke_test.py
```

## Project structure

```text
backend/                 FastAPI API, RAG services, schemas, and tests
  app/
  data/vector_store/     Persisted Chroma collection
  scripts/smoke_test.py
frontend/                Streamlit UI, typed API client, and tests
notebooks/               Source RAG pipeline and evaluation notebook
data/raw/                Three source NIST PDFs
data/metadata/           Source manifest
data/evaluation_*        Saved evaluation questions and results
reports/                 Notebook, backend, and frontend handoffs
```

## Prototype limitations

- Responses and thinking are returned only after generation completes; there is
  no token streaming.
- One Ollama generation runs at a time.
- Thinking mode can be substantially slower and may exceed the 300-second
  frontend timeout.
- Conversation history is process-local and disappears when the backend restarts.
- Retrieval uses the current question, with only limited recent history supplied
  to generation.
- This assistant summarizes NIST guidance and does not provide legal advice.
- This is a demonstration prototype, not a production chat application.

For implementation and verification details, see
[`reports/backend_handoff.txt`](reports/backend_handoff.txt) and
[`reports/frontend_handoff.txt`](reports/frontend_handoff.txt).
