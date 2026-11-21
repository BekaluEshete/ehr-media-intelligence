"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.db.store import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB and ensure data directories exist."""
    init_db()
    data_root = Path(__file__).parent.parent / "data"
    for sub in ("fhir_bundles", "cache", "faiss_index", "raw"):
        (data_root / sub).mkdir(parents=True, exist_ok=True)
    yield
    # shutdown — nothing to clean up


app = FastAPI(
    title="EHR Media Intelligence API",
    description=(
        "AI-powered EHR ingestion, FHIR R4 normalization, "
        "clinical summarization and semantic search"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# Serve the React build from frontend/public
_frontend = Path(__file__).parent.parent.parent / "frontend" / "public"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
