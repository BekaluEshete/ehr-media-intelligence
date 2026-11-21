"""
Main ingestion pipeline.

Usage:
    from app.ingestion.pipeline import ingest_json, ingest_csv, ingest_text
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from .cleaner import (
    dedup_records,
    normalize_date,
    normalize_gender,
    normalize_mrn,
    normalize_name,
)
from .models import (
    AuditEntry,
    CleanedDocument,
    CleanedPatient,
    CleanedRecord,
    DocumentType,
    GenderCode,
)
from .parsers import parse_csv, parse_json, parse_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DOC_TYPE_MAP: dict[str, DocumentType] = {
    "lab": DocumentType.LAB_REPORT,
    "lab_report": DocumentType.LAB_REPORT,
    "lab report": DocumentType.LAB_REPORT,
    "imaging": DocumentType.IMAGING_NOTE,
    "imaging_note": DocumentType.IMAGING_NOTE,
    "radiology": DocumentType.IMAGING_NOTE,
    "discharge": DocumentType.DISCHARGE_SUMMARY,
    "discharge_summary": DocumentType.DISCHARGE_SUMMARY,
    "clinical_note": DocumentType.CLINICAL_NOTE,
    "clinical": DocumentType.CLINICAL_NOTE,
    "note": DocumentType.CLINICAL_NOTE,
}


def _map_doc_type(raw: Any) -> DocumentType:
    if not raw:
        return DocumentType.UNKNOWN
    return _DOC_TYPE_MAP.get(str(raw).lower().strip(), DocumentType.UNKNOWN)


def _clean_patient(raw: dict[str, Any]) -> tuple[CleanedPatient, list[str]]:
    """
    Clean a single raw patient dict.
    Returns (CleanedPatient, list_of_error_strings).
    Errors are non-fatal; we still return a partial record.
    """
    audit: list[AuditEntry] = []
    errors: list[str] = []

    # MRN
    try:
        mrn, a = normalize_mrn(raw.get("mrn") or raw.get("patient_id") or "")
        audit.extend(a)
    except ValueError as e:
        mrn = f"UNKNOWN-{uuid.uuid4().hex[:6].upper()}"
        errors.append(str(e))

    # Names
    try:
        given, a = normalize_name(raw.get("given_name") or raw.get("first_name") or "", "given_name")
        audit.extend(a)
    except ValueError as e:
        given = "Unknown"
        errors.append(str(e))

    try:
        family, a = normalize_name(raw.get("family_name") or raw.get("last_name") or "", "family_name")
        audit.extend(a)
    except ValueError as e:
        family = "Unknown"
        errors.append(str(e))

    # DOB
    dob_raw = raw.get("date_of_birth") or raw.get("dob") or raw.get("birth_date") or ""
    try:
        dob, a = normalize_date(dob_raw, "date_of_birth")
        audit.extend(a)
    except ValueError as e:
        dob = date(1900, 1, 1)
        errors.append(str(e))
        audit.append(AuditEntry(
            field="date_of_birth", original=dob_raw,
            normalized=str(dob), reason="Unparseable DOB defaulted to 1900-01-01",
        ))

    # Gender
    gender, a = normalize_gender(raw.get("gender") or raw.get("sex"))
    audit.extend(a)

    patient = CleanedPatient(
        mrn=mrn,
        given_name=given,
        family_name=family,
        date_of_birth=dob,
        gender=gender,
        phone=str(raw.get("phone") or ""),
        email=str(raw.get("email") or ""),
        address=str(raw.get("address") or ""),
        audit_log=audit,
        source_format=str(raw.get("_source_format", "")),
        source_id=str(raw.get("_source_id", "")),
    )
    return patient, errors


def _clean_document(raw: dict[str, Any], patient_mrn: str) -> tuple[CleanedDocument | None, list[str]]:
    audit: list[AuditEntry] = []
    errors: list[str] = []

    content = str(raw.get("content") or raw.get("note") or raw.get("text") or "").strip()
    if not content:
        return None, ["Document has no content — skipped"]

    doc_id = str(raw.get("doc_id") or raw.get("id") or uuid.uuid4())
    title = str(raw.get("title") or raw.get("doc_type") or "Untitled Document")

    authored_raw = raw.get("authored_date") or raw.get("date") or raw.get("report_date") or ""
    try:
        authored, a = normalize_date(authored_raw, "authored_date")
        audit.extend(a)
    except ValueError:
        authored = date.today()
        errors.append(f"Missing authored_date for doc '{doc_id}' — defaulted to today")
        audit.append(AuditEntry(
            field="authored_date", original=authored_raw,
            normalized=str(authored), reason="Missing date defaulted to today",
        ))

    doc = CleanedDocument(
        doc_id=doc_id,
        patient_mrn=patient_mrn,
        doc_type=_map_doc_type(raw.get("doc_type") or raw.get("type")),
        title=title,
        content=content,
        authored_date=authored,
        author=str(raw.get("author") or raw.get("doctor") or ""),
        encounter_id=str(raw.get("encounter_id") or ""),
        audit_log=audit,
        source_format=str(raw.get("_source_format", "")),
        source_id=str(raw.get("_source_id", "")),
    )
    return doc, errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

IngestionResult = tuple[list[CleanedRecord], list[dict]]
"""(cleaned_records, error_report_entries)"""


def _process_raw_records(raw_records: list[dict]) -> IngestionResult:
    """Core processing: dedup → clean patients → attach documents."""
    unique, dupes = dedup_records(raw_records)

    error_report: list[dict] = []
    for d in dupes:
        error_report.append({
            "type": "duplicate_removed",
            "mrn": d.get("mrn", "?"),
            "detail": "Duplicate patient record (same MRN+DOB) — removed",
        })

    # Separate patient-level records from document-only records
    patient_recs = [r for r in unique if
                    r.get("given_name") or r.get("first_name") or r.get("family_name")]
    doc_only_recs = [r for r in unique if
                     not (r.get("given_name") or r.get("first_name") or r.get("family_name"))
                     and (r.get("content") or r.get("note"))]

    cleaned: dict[str, CleanedRecord] = {}

    for raw in patient_recs:
        patient, errs = _clean_patient(raw)
        for e in errs:
            error_report.append({"type": "cleaning_error", "mrn": patient.mrn, "detail": e})

        # Inline documents (JSON records may embed a "documents" list)
        docs: list[CleanedDocument] = []
        for raw_doc in (raw.get("documents") or []):
            raw_doc["_source_format"] = raw.get("_source_format", "json")
            raw_doc["_source_id"] = raw_doc.get("_source_id") or str(uuid.uuid4())
            doc, errs2 = _clean_document(raw_doc, patient.mrn)
            if doc:
                docs.append(doc)
            for e in errs2:
                error_report.append({"type": "doc_error", "mrn": patient.mrn, "detail": e})

        cleaned[patient.mrn] = CleanedRecord(
            patient=patient,
            documents=docs,
            ingested_at=datetime.now(timezone.utc),
        )

    # Attach document-only rows to existing patient by MRN
    for raw_doc in doc_only_recs:
        mrn_raw = raw_doc.get("mrn") or raw_doc.get("patient_mrn") or "UNKNOWN"
        from .cleaner import normalize_mrn as _n
        try:
            mrn, _ = _n(mrn_raw)
        except ValueError:
            mrn = "UNKNOWN"

        doc, errs = _clean_document(raw_doc, mrn)
        if doc:
            if mrn in cleaned:
                cleaned[mrn].documents.append(doc)
            else:
                # Create a stub patient record
                stub = CleanedPatient(
                    mrn=mrn, given_name="Unknown", family_name="Unknown",
                    date_of_birth=date(1900, 1, 1), gender=GenderCode.UNKNOWN,
                    audit_log=[AuditEntry(
                        field="patient", original=None, normalized="stub",
                        reason="Document-only row: stub patient created",
                    )],
                    source_format=str(raw_doc.get("_source_format", "")),
                    source_id=str(raw_doc.get("_source_id", "")),
                )
                cleaned[mrn] = CleanedRecord(
                    patient=stub, documents=[doc], ingested_at=datetime.now(timezone.utc)
                )
        for e in errs:
            error_report.append({"type": "doc_error", "mrn": mrn, "detail": e})

    return list(cleaned.values()), error_report


def ingest_json(source: str | bytes) -> IngestionResult:
    raw = parse_json(source)
    return _process_raw_records(raw)


def ingest_csv(source: str | bytes) -> IngestionResult:
    raw = parse_csv(source)
    return _process_raw_records(raw)


def ingest_text(source: str | bytes, patient_mrn: str = "UNKNOWN") -> IngestionResult:
    raw = parse_text(source, patient_mrn)
    return _process_raw_records(raw)
