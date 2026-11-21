# EHR Media Intelligence Platform

An AI-powered pipeline that ingests raw EHR data, normalizes it to HL7 FHIR R4,
generates clinical summaries via LLM, and surfaces a semantic search interface
for clinicians.

---

## Architecture

```
Raw EHR (JSON / CSV / text)
        │
        ▼   1 — Ingestion & Cleaning
┌──────────────────────────────┐
│  Pydantic models + audit log │
│  dedup · date normalize      │
│  MRN / gender canonicalize   │
└──────────────┬───────────────┘
               │  2 — FHIR R4 Mapping
               ▼
┌──────────────────────────────┐
│  FHIR Bundle (per patient)   │
│  Patient · DocumentReference │
│  DiagnosticReport            │
│  → SQLite store              │
└──────┬───────────────────────┘
       │  3            │  4
       ▼                    ▼
┌────────────────┐  ┌───────────────────────┐
│  LLM Summary   │  │  Embed docs+summaries │
│  Claude/gemini │  │  FAISS vector store   │
│  <200 words    │  │  POST /search API     │
│  SQLite cache  │  │  top-5 · filters      │
└────────────────┘  └───────────┬───────────┘
                                │   5
                                ▼
                   ┌────────────────────────┐
                   │  Tailwind + React JS  │
                   │  Search · Cards        │
                   │  Detail drawer         │
                   │  ARIA + keyboard nav   │
                   └────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+ (tested on 3.14)
- An Anthropic or OpenAI API key ( use Gemini api key)

### 1. Clone and set up

```bash
git clone <repo-url>
cd ehr-media-intelligence

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY or OPENAI_API_KEY
# LLM_PROVIDER=stub  means no API call (deterministic output for demos)
```

### 3. Generate sample data

```bash
cd backend
python scripts/generate_sample_data.py
```

### 4. Run the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000 in a browser.

Click **Load Sample Data** to ingest, build FHIR bundles, summarize, and index everything. Then search.

### 5. Run tests

```bash
# From monorepo root
pytest                        # all 79 tests
pytest --cov=app --cov-report=term-missing   # with coverage
```

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/ingest` | Ingest JSON / CSV / text file |
| `GET`  | `/api/v1/patients` | List all patient MRNs |
| `GET`  | `/api/v1/patients/{mrn}` | Get FHIR bundle + AI summary |
| `POST` | `/api/v1/search` | Semantic search (top-5, with filters) |
| `POST` | `/api/v1/pipeline/run` | Full pipeline on sample data |

### POST /api/v1/search

```json
{
  "query": "elevated HbA1c diabetes",
  "top_k": 5,
  "resource_type": "DiagnosticReport",
  "date_from": "2024-01-01",
  "date_to": "2024-12-31"
}
```

---

## Stack

**Backend** — Python 3.11+, FastAPI, Pydantic v2, fhir.resources 8.x,
FAISS (faiss-cpu), aiosqlite, Anthropic/OpenAI SDK, pandas, python-dateutil, pytest

**Frontend** — React js, Tailwind CSS (CDN), Fetch API

**No torch / sentence-transformers** — uses a deterministic SHA-256 stub in absence
of an API key; upgrades to OpenAI `text-embedding-3-small` automatically when
`OPENAI_API_KEY` is set.

---

## Project Layout

```
ehr-media-intelligence/
├── backend/
│   ├── app/
│   │   ├── ingestion/       # Task 1: parsers, cleaner, pipeline, models
│   │   ├── fhir/            # Task 2: mapper, validator
│   │   ├── summarizer/      # Task 3: LLM client, prompts, caching
│   │   ├── search/          # Task 4: embedder, FAISS store, indexer
│   │   ├── api/             # FastAPI routes
│   │   ├── db/              # SQLite store
│   │   ├── config.py
│   │   └── main.py
│   ├── data/
│   │   ├── raw/             # Sample JSON / CSV / text inputs
│   │   ├── fhir_bundles/    # (unused file store — SQLite used instead)
│   │   ├── cache/           # (legacy, cache now in SQLite)
│   │   └── faiss_index/     # Persisted FAISS index + metadata
│   ├── scripts/
│   │   └── generate_sample_data.py
│   └── tests/               # 79 unit tests across all 4 tasks
├── frontend/
│   └── public/
│       ├── index.html       # Task 5: search UI
│       └── app.js
├── .env.example
├── pytest.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Design Decisions & Tradeoffs

**FAISS over chromadb** — chromadb requires grpcio which has no wheel for Python 3.14.
FAISS installs cleanly as `faiss-cpu` and meets the same requirements (top-k ANN search,
filters, persistence). The interface is identical from the application's perspective.

**Stub embeddings without a key** — `sentence-transformers` + torch have no Python 3.14
wheels. Rather than force a Python version change, the embedder falls back to a
deterministic SHA-256 stub and upgrades to OpenAI embeddings automatically when
`OPENAI_API_KEY` is present. For production, upgrade to Python 3.12 and use the local
MiniLM model.

**Synchronous SQLite (not aiosqlite async)** — The store layer uses `sqlite3` directly
for simplicity. For a production system under concurrent load, swap to `aiosqlite` with
async context managers throughout.

**fhir.resources v8** — `resource_type` moved to `get_resource_type()` in v8.
The validator and tests use a compat helper that calls `get_resource_type()`.

**LLM stub mode** — All five tasks run end-to-end with no API key. The stub returns
valid, schema-correct JSON (a consistent fictional summary) so the full pipeline,
caching, search indexing, and frontend all function without hitting any external service.

---

## FHIR Concepts Researched

- **FHIR R4 Bundle** (type=`transaction`) — container that groups resources for
  atomic server submission. Each entry has a `fullUrl` and a `request` with method+URL.
- **DocumentReference** — the right resource for unstructured clinical documents
  (PDFs, scanned notes). Content is base64-encoded in `attachment.data`.
- **DiagnosticReport** — structured result of a diagnostic procedure (lab, imaging).
  Uses `effectiveDateTime` (when the test was done) vs `issued` (when reported).
- **LOINC codes** — standard vocabulary for lab/clinical observations. Used in
  `type.coding` for both DocumentReference and DiagnosticReport.
- **Patient identifiers** — MRN uses identifier `type.coding.code = "MR"` from
  the HL7 v2.0203 codesystem.

---

## AI Summary Quality Validation

1. **Schema validation** — every LLM response is parsed as JSON and validated against
   the `ClinicalSummary` Pydantic model. Malformed output raises an error and returns
   a graceful fallback.
2. **Word count field** — the LLM is instructed to self-report `word_count`; the
   prompt enforces the <200-word constraint.
3. **Mandatory disclaimer** — the disclaimer field is required in every response and
   validated in tests.
4. **Stub parity** — the stub produces the same JSON schema as a real LLM response,
   so the full pipeline exercises the same code paths in CI.

---

## What Would Improve With More Time

- Upgrade to Python 3.12 and add local `all-MiniLM-L6-v2` embeddings (offline, faster)
- Add async SQLite throughout for concurrent ingestion under load
- Proper FHIR Terminology Service validation (SNOMED, LOINC code existence checks)
- Re-ranking (cross-encoder) on top of FAISS ANN for better search quality
- Authentication / role-based access (clinician vs admin)
- Streaming LLM responses to the frontend via SSE
- Docker Compose for one-command setup
- Full OpenAPI schema + Swagger UI for the ingest endpoint
