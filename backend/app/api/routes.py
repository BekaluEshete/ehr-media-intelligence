"""
FastAPI routes:

  POST /ingest          — ingest JSON or CSV EHR data
  GET  /patients        — list all ingested patient MRNs
  GET  /patients/{mrn}  — get FHIR bundle + summary for a patient
  POST /search          — semantic search across all records
  POST /pipeline/run    — run the full pipeline on sample data
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.db.store import get_bundle, get_summary_cache, list_mrns, upsert_bundle, init_db
from app.fhir.mapper import build_bundle, bundle_to_dict
from app.fhir.validator import validate_bundle
from app.ingestion.pipeline import ingest_csv, ingest_json, ingest_text
from app.search.embedder import embed_query, embed_texts
from app.search.indexer import index_bundle_with_summary
from app.search.vector_store import VectorStore
from app.summarizer.summarizer import summarize_bundle

router = APIRouter()
_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

class IngestResponse(BaseModel):
    ingested: int
    errors: list[dict]
    validation_issues: list[dict]


@router.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(
    file: UploadFile = File(...),
    format: str = Form(default="json"),  # "json" | "csv" | "text"
):
    init_db()
    content = await file.read()

    if format == "json":
        records, errors = ingest_json(content)
    elif format == "csv":
        records, errors = ingest_csv(content)
    else:
        records, errors = ingest_text(content)

    validation_issues: list[dict] = []
    store = get_store()

    for record in records:
        bundle = build_bundle(record)
        bundle_dict = bundle_to_dict(bundle)

        report = validate_bundle(bundle_dict, record.patient.mrn)
        if not report.is_valid:
            validation_issues.append({
                "mrn": record.patient.mrn,
                "errors": report.errors,
            })

        upsert_bundle(record.patient.mrn, bundle_dict)

        # Summarize and index
        summary = summarize_bundle(bundle_dict)
        index_bundle_with_summary(bundle_dict, summary, store, embed_texts)

    return IngestResponse(
        ingested=len(records),
        errors=errors,
        validation_issues=validation_issues,
    )


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

@router.get("/patients")
async def list_patients():
    init_db()
    return {"mrns": list_mrns()}


@router.get("/patients/{mrn}")
async def get_patient(mrn: str):
    init_db()
    mrn = mrn.upper()
    bundle = get_bundle(mrn)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Patient {mrn} not found")

    # Fetch cached summary if available
    from app.summarizer.summarizer import _bundle_to_text, _cache_key
    _, _, _, _, _ = _bundle_to_text(bundle)
    key = _cache_key(mrn, bundle)
    cached = get_summary_cache(key)

    return {
        "mrn": mrn,
        "bundle": bundle,
        "summary": cached,
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    resource_type: str | None = None   # "DocumentReference"|"DiagnosticReport"|"Summary"
    date_from: str | None = None       # "YYYY-MM-DD"
    date_to: str | None = None


class SearchResult(BaseModel):
    doc_id: str
    mrn: str
    patient_name: str
    resource_type: str
    date: str
    title: str
    summary_snippet: str
    score: float


class SearchResponse(BaseModel):
    query: str
    total: int
    elapsed_ms: float
    results: list[SearchResult]
    data_loaded: bool = True
    embedding_provider: str = "stub"   # "gemini" | "openai" | "stub"


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(req: SearchRequest):
    from app.search.embedder import get_embedding_provider
    t0 = time.perf_counter()
    provider = get_embedding_provider()

    store = get_store()
    if store.count() == 0:
        return SearchResponse(query=req.query, total=0,
                              elapsed_ms=0, results=[],
                              data_loaded=False,
                              embedding_provider=provider)

    qvec = embed_query(req.query)
    hits = store.search(
        query_vector=qvec,
        top_k=req.top_k,
        resource_type=req.resource_type,
        date_from=req.date_from,
        date_to=req.date_to,
    )

    elapsed = (time.perf_counter() - t0) * 1000
    results = [SearchResult(**h) for h in hits]
    return SearchResponse(
        query=req.query,
        total=len(results),
        elapsed_ms=round(elapsed, 2),
        results=results,
        data_loaded=True,
        embedding_provider=provider,
    )


# ---------------------------------------------------------------------------
# Pipeline runner (convenience endpoint for demo)
# ---------------------------------------------------------------------------

@router.post("/pipeline/run")
async def run_pipeline():
    """
    Ingest sample data, build FHIR bundles, summarize concurrently, and index.
    - If data is already indexed, returns instantly from cache.
    - Gemini is only called for patients with no cached summary.
    - Concurrent calls (4 workers) for speed.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    init_db()
    sample_path = Path(__file__).parent.parent.parent / "data" / "raw" / "sample_patients.json"
    if not sample_path.exists():
        raise HTTPException(status_code=404,
                            detail="Sample data not found. Run: python scripts/generate_sample_data.py")

    records, errors = ingest_json(sample_path.read_text())

    # Build FHIR bundles and store them
    bundles: list[tuple[str, dict]] = []
    for record in records:
        bundle = build_bundle(record)
        bd = bundle_to_dict(bundle)
        upsert_bundle(record.patient.mrn, bd)
        bundles.append((record.patient.mrn, bd))

    # Check if FAISS already has data — if so, skip full re-index
    store = get_store()
    already_indexed = store.count() > 0

    if already_indexed:
        # Just make sure all summaries are cached — no Gemini calls for cached ones
        summaries_built = 0
        def _summarize_one(bd):
            return summarize_bundle(bd)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=4) as executor:
            tasks = [loop.run_in_executor(executor, _summarize_one, bd) for _, bd in bundles]
            summaries = await asyncio.gather(*tasks, return_exceptions=True)

        for (mrn, _), summary in zip(bundles, summaries):
            if not isinstance(summary, Exception):
                summaries_built += 1

        return {
            "patients_processed": len(records),
            "summaries_built": summaries_built,
            "errors": errors,
            "indexed_docs": store.count(),
        }

    # First run — clear and build full index
    store.clear()

    def _summarize_one(bd):
        return summarize_bundle(bd)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = [loop.run_in_executor(executor, _summarize_one, bd) for _, bd in bundles]
        summaries = await asyncio.gather(*tasks, return_exceptions=True)

    summaries_built = 0
    for (mrn, bd), summary in zip(bundles, summaries):
        if isinstance(summary, Exception):
            errors.append({"type": "summary_error", "mrn": mrn, "detail": str(summary)})
            continue
        index_bundle_with_summary(bd, summary, store, embed_texts)
        summaries_built += 1

    return {
        "patients_processed": len(records),
        "summaries_built": summaries_built,
        "errors": errors,
        "indexed_docs": store.count(),
    }
