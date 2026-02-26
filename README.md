# Document Q&A AI Assistant

> On-premise, domain-agnostic RAG system. Upload any PDF or TXT — ask questions, get cited answers. No cloud APIs. Everything runs locally.

Works for **any domain**: education, law, medicine, research, corporate manuals, government documents, and more.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)
- [Windows: Installing pgvector](#windows-installing-pgvector)
- [Project Structure](#project-structure)

---

## Features

| | |
|---|---|
| **Domain-agnostic** | Works with legal codes, textbooks, research papers, corporate manuals, anything |
| **On-premise** | All inference is local — no data leaves your machine |
| **Smart chunking** | Auto-detects document structure (Chapters, Sections, Lessons, Clauses, Articles, etc.) |
| **Streaming** | Server-Sent Events endpoint for real-time token-by-token output |
| **Cited answers** | Every response links back to the source document and section |
| **Fast retrieval** | pgvector HNSW index — approximate nearest-neighbour search in PostgreSQL |
| **Strict RAG** | LLM is constrained to answer only from retrieved context |

---

## Architecture

```
                         ┌──────────────────────────────────┐
  UPLOAD                 │         document_processor        │
  PDF / TXT  ──────────► │  extract text → chunk by section  │
                         └───────────────┬──────────────────┘
                                         │ chunks[]
                                         ▼
                         ┌──────────────────────────────────┐
                         │     embedder (SentenceTransf.)    │
                         │  text → float32[384] vectors      │
                         └───────────────┬──────────────────┘
                                         │ vectors
                                         ▼
                         ┌──────────────────────────────────┐
                         │  PostgreSQL + pgvector (HNSW)     │
                         │  documents table + chunks table   │
                         └──────────────┬───────────────────┘
                                        │
  ASK                                   │
  question  ──► embed query ────────────┘
                                        │ cosine similarity search (top-k)
                                        ▼
                         ┌──────────────────────────────────┐
                         │         prompt_builder            │
                         │  system prompt + context block    │
                         └───────────────┬──────────────────┘
                                         │
                                         ▼
                         ┌──────────────────────────────────┐
                         │   LLM (Qwen2.5-7B via llama.cpp) │
                         │   full response OR SSE stream     │
                         └───────────────┬──────────────────┘
                                         │
                                         ▼
                              { answer, citations[] }
```

### Chunking Strategy

The processor tries structural chunking first, then falls back to fixed-size:

1. **Structural** — splits at detected headings: `Article`, `Section`, `Chapter`, `Lesson`, `Unit`, `Module`, `Clause`, `Provision`, `Part`, `Appendix`, numbered outlines (`1.1 Heading`), and more
2. **Fixed-size** — 800-character windows with 150-character overlap (fallback)

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| Database | [PostgreSQL](https://www.postgresql.org/) 16/17/18 + [pgvector](https://github.com/pgvector/pgvector) |
| ORM / validation | [SQLAlchemy](https://www.sqlalchemy.org/) 2 + [Pydantic](https://docs.pydantic.dev/) v2 |
| Embeddings | [SentenceTransformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`, 384-dim) |
| LLM | [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) (GGUF format) |
| PDF extraction | [pdfplumber](https://github.com/jsvine/pdfplumber) |
| Authentication | API key (`X-API-Key` header) |
| Tests | [pytest](https://pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) |

---

## Prerequisites

- **Python 3.11+**
- **PostgreSQL 16, 17, or 18** with the **pgvector** extension
  → See [Windows: Installing pgvector](#windows-installing-pgvector)
- **A GGUF model file** — Qwen2.5-7B-Instruct is recommended
  → [Download from Hugging Face](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF)

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/docqa-ai.git
cd docqa-ai
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Download a GGUF model

```bash
# Using huggingface-hub (pip install huggingface-hub if needed)
huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF \
  qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf \
  qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf \
  --local-dir models/
```

Any GGUF model works — update `MODEL_PATH` in `.env` accordingly.

### 5. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```ini
API_KEY=your-secret-key-here
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/docqa_ai
MODEL_PATH=models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
```

### 6. Create the database and run migrations

```bash
# Create the database in psql first:
psql -U postgres -c "CREATE DATABASE docqa_ai;"

# Then run the migration script:
python migrate.py
```

This creates the `documents` and `chunks` tables and builds the HNSW index.

### 7. Start the server

```bash
python run.py
```

The API is now live at **http://localhost:8000**
Interactive docs: **http://localhost:8000/docs**

---

## Configuration

All configuration is via environment variables (`.env` file).

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(required)* | Secret key for `X-API-Key` header authentication |
| `DATABASE_URL` | `postgresql://postgres:password@localhost:5432/docqa_ai` | PostgreSQL connection string |
| `MODEL_PATH` | `models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` | Path to your GGUF model file |
| `MODEL_N_CTX` | `2048` | LLM context window size (tokens) |
| `MODEL_N_GPU_LAYERS` | `0` | GPU layers to offload (`0` = CPU only) |
| `MODEL_N_THREADS` | `0` | CPU threads (`0` = auto-detect) |
| `MODEL_MAX_TOKENS` | `512` | Max tokens to generate per response |
| `MODEL_TEMPERATURE` | `0.1` | Sampling temperature (lower = more deterministic) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformers model name |
| `UPLOAD_DIR` | `uploads` | Directory where uploaded files are saved |
| `DATA_DIR` | `data` | Directory for runtime data |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

> **GPU acceleration**: Set `MODEL_N_GPU_LAYERS=-1` to offload all layers to GPU (requires a CUDA build of llama-cpp-python).

---

## API Reference

All endpoints except `GET /api/health` require the `X-API-Key` header.

### Upload a document

```http
POST /api/upload-document
X-API-Key: <your-key>
Content-Type: multipart/form-data

file    : <PDF or TXT file>
title   : "Introduction to Python Programming"
year    : 2023
```

**Response `201`**
```json
{
  "data": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "Introduction to Python Programming",
    "year": 2023,
    "chunks_indexed": 42,
    "strategy": "sections"
  }
}
```

---

### List all documents

```http
GET /api/documents
X-API-Key: <your-key>
```

**Response `200`**
```json
{
  "data": [
    {
      "id": "3fa85f64-...",
      "title": "Introduction to Python Programming",
      "year": 2023,
      "section_count": 42,
      "created_at": "2024-01-15T10:30:00"
    }
  ]
}
```

---

### Delete a document

```http
DELETE /api/document/{id}
X-API-Key: <your-key>
```

**Response `204 No Content`** — document and all its chunks are removed.

---

### Ask a question (full response)

```http
POST /api/ask
X-API-Key: <your-key>
Content-Type: application/json

{
  "question": "What are the key concepts in Chapter 3?",
  "top_k": 3
}
```

**Response `200`**
```json
{
  "data": {
    "answer": "Chapter 3 covers functions and variable scope...",
    "citations": [
      { "document": "Introduction to Python Programming", "section": "Chapter 3" }
    ]
  }
}
```

| Field | Description |
|---|---|
| `question` | Your question (5–2000 characters) |
| `top_k` | Number of context chunks to retrieve (1–20, default `3`) |

---

### Ask a question (streaming)

```http
POST /api/ask/stream
X-API-Key: <your-key>
Content-Type: application/json

{
  "question": "Explain the concept of recursion",
  "top_k": 3
}
```

**Response `200` — `text/event-stream`**
```
data: {"token": "Recursion"}
data: {"token": " is"}
data: {"token": " a"}
...
data: {"citations": [{"document": "...", "section": "..."}]}
data: [DONE]
```

---

### Health check

```http
GET /api/health
```

No authentication required.

**Response `200`**
```json
{
  "status": "ok",
  "database": "connected",
  "model_loaded": false,
  "total_chunks": 156,
  "indexed_chunks": 156
}
```

---

## Running Tests

```bash
# Run all tests
pytest

# With verbose output
pytest -v

# Run a specific file
pytest tests/test_ask.py -v
```

All external dependencies (PostgreSQL, LLM, embedder) are mocked — tests run without any real database or model.

---

## Windows: Installing pgvector

pgvector is not bundled with the standard PostgreSQL Windows installer. Two options:

### Option A — Download pre-built binaries (recommended)

1. Go to [pgvector releases](https://github.com/pgvector/pgvector/releases)
2. Download the `.zip` for your PostgreSQL version (e.g., `pgvector-v0.8.0-pg18-windows-x86_64.zip`)
3. Extract to `pgvector_temp/` in the project root so the layout is:
   ```
   pgvector_temp/
     lib/vector.dll
     share/extension/vector.control
     share/extension/vector--*.sql
   ```
4. Run the installer script as Administrator:
   ```powershell
   # Default: PostgreSQL 18
   .\install_pgvector.ps1

   # Or specify your version:
   .\install_pgvector.ps1 -PG_VERSION 17
   ```
5. Restart the PostgreSQL service
6. Run `python migrate.py`

### Option B — Build from source

Follow the [official build guide](https://github.com/pgvector/pgvector#installation) for Windows.

---

## Project Structure

```
docqa-ai/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, router registration
│   ├── config.py                # Pydantic Settings (reads from .env)
│   ├── database.py              # SQLAlchemy engine, get_db() context manager
│   │
│   ├── models/
│   │   ├── document.py          # Document ORM model  (documents table)
│   │   └── chunk.py             # Chunk ORM model     (chunks table + pgvector)
│   │
│   ├── routes/
│   │   ├── ask.py               # POST /api/ask, POST /api/ask/stream
│   │   ├── upload.py            # POST /api/upload-document, GET /api/documents, DELETE /api/document/{id}
│   │   └── health.py            # GET /api/health
│   │
│   ├── services/
│   │   └── document_processor.py  # Text extraction + structural/fixed-size chunking
│   │
│   ├── storage/
│   │   ├── metadata_store.py    # CRUD for documents table
│   │   └── chunk_store.py       # CRUD for chunks table
│   │
│   ├── rag/
│   │   ├── embedder.py          # SentenceTransformers singleton (lazy-load)
│   │   ├── retriever.py         # pgvector HNSW cosine search + embedding writer
│   │   └── prompt_builder.py    # Strict RAG prompt construction + citation extraction
│   │
│   ├── llm/
│   │   └── model.py             # llama-cpp-python singleton (lazy-load, streaming)
│   │
│   └── dependencies/
│       └── api_key.py           # X-API-Key header validation dependency
│
├── tests/
│   ├── conftest.py              # Pytest fixtures (all deps mocked)
│   ├── test_ask.py              # /api/ask + /api/ask/stream tests
│   └── test_upload.py           # Upload, list, delete, health tests
│
├── models/                      # GGUF model files (gitignored)
├── uploads/                     # Uploaded document files (gitignored)
├── data/                        # Runtime data directory (gitignored)
│
├── migrate.py                   # One-time DB setup: tables + HNSW index
├── run.py                       # Entry point: python run.py
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
└── install_pgvector.ps1         # Windows pgvector installer helper
```

---

## Contributing

1. Fork the repo and create a feature branch
2. Follow the existing patterns — read `app/` before adding anything new
3. Add or update tests for any changed behaviour
4. Run `pytest` — all tests must pass
5. Open a pull request with a clear description

---

## License

MIT — see [LICENSE](LICENSE) for details.
