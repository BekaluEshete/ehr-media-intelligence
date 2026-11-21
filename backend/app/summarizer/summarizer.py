"""
Clinical summarization pipeline.

- Builds a compact text representation of a FHIR bundle
- Calls the LLM via llm_client (auto-stubs if no API key)
- Caches results in SQLite keyed by patient_id + record_hash
- Returns a structured ClinicalSummary
"""
from __future__ import annotations

import base64
import hashlib

from pydantic import BaseModel, Field

from app.db.store import get_summary_cache, set_summary_cache
from app.summarizer.llm_client import LLMError, call_llm, parse_llm_json
from app.summarizer.prompts import SYSTEM_PROMPT, build_summary_prompt


class RecentRecord(BaseModel):
    type: str
    date: str
    summary: str


class ClinicalSummary(BaseModel):
    mrn: str
    patient_name: str
    chief_concern: str
    key_diagnoses: list[str] = Field(default_factory=list)
    recent_records: list[RecentRecord] = Field(default_factory=list)
    flagged_anomalies: list[str] = Field(default_factory=list)
    word_count: int = 0
    disclaimer: str = (
        "AI-generated summary. Not validated by a clinician. "
        "Do not use for clinical decision-making."
    )
    cached: bool = False
    error: str = ""


def _extract_text_from_attachment(attachment: dict) -> str:
    """Decode base64 attachment data if present."""
    data = attachment.get("data", "")
    if data:
        try:
            return base64.b64decode(data).decode("utf-8")
        except Exception:
            pass
    return attachment.get("title", "")


def _bundle_to_text(bundle: dict) -> tuple[str, str, str, str, list[str]]:
    """
    Extract (mrn, name, dob, doc_summaries_text, doc_lines) from a FHIR bundle dict.
    """
    entries = bundle.get("entry", [])
    mrn = "UNKNOWN"
    name = "Unknown Patient"
    dob = "Unknown"
    doc_lines: list[str] = []

    for entry in entries:
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "")

        if rtype == "Patient":
            for ident in resource.get("identifier", []):
                if ident.get("use") == "usual":
                    mrn = ident.get("value", mrn)
            names = resource.get("name", [])
            if names:
                n = names[0]
                given = " ".join(n.get("given", []))
                family = n.get("family", "")
                name = f"{given} {family}".strip()
            dob = resource.get("birthDate", "Unknown")

        elif rtype == "DocumentReference":
            doc_date = resource.get("date", "")[:10] if resource.get("date") else "Unknown"
            doc_type = "Document"
            for coding in resource.get("type", {}).get("coding", []):
                doc_type = coding.get("display", doc_type)

            content_text = ""
            for content_item in resource.get("content", []):
                att = content_item.get("attachment", {})
                content_text = _extract_text_from_attachment(att)
                if content_text:
                    break

            snippet = content_text[:300].replace("\n", " ") if content_text else "(no content)"
            doc_lines.append(f"[{doc_type} | {doc_date}] {snippet}")

        elif rtype == "DiagnosticReport":
            report_date = (resource.get("effectiveDateTime", "")[:10]
                           or resource.get("issued", "")[:10] or "Unknown")
            code_text = ""
            for coding in resource.get("code", {}).get("coding", []):
                code_text = coding.get("display", "")
            forms = resource.get("presentedForm", [])
            content_text = ""
            for form in forms:
                content_text = _extract_text_from_attachment(form)
                if content_text:
                    break
            snippet = content_text[:300].replace("\n", " ") if content_text else "(no content)"
            doc_lines.append(f"[DiagnosticReport:{code_text} | {report_date}] {snippet}")

    doc_summaries = "\n".join(f"  {i+1}. {l}" for i, l in enumerate(doc_lines)) or "  (none)"
    return mrn, name, dob, doc_summaries, doc_lines


def _cache_key(mrn: str, bundle: dict) -> str:
    """
    Stable cache key: hash of MRN + document content only.
    Excludes bundle id/timestamp so the same clinical data always hits the cache.
    """
    entries = bundle.get("entry", [])
    content_parts = [mrn]
    for entry in sorted(entries, key=lambda e: e.get("fullUrl", "")):
        res = entry.get("resource", {})
        rtype = res.get("resourceType", "")
        if rtype == "DocumentReference":
            for c in res.get("content", []):
                content_parts.append(c.get("attachment", {}).get("data", ""))
        elif rtype == "DiagnosticReport":
            for f in res.get("presentedForm", []):
                content_parts.append(f.get("data", ""))
    blob = "|".join(content_parts)
    return hashlib.sha256(blob.encode()).hexdigest()


def summarize_bundle(bundle: dict) -> ClinicalSummary:
    """Generate (or return cached) clinical summary for one FHIR bundle."""
    mrn, name, dob, doc_summaries, doc_lines = _bundle_to_text(bundle)
    key = _cache_key(mrn, bundle)

    # Check cache
    cached = get_summary_cache(key)
    if cached:
        return ClinicalSummary(**{**cached, "cached": True})

    # Build prompt
    prompt = build_summary_prompt(
        mrn=mrn, name=name, dob=dob,
        doc_summaries=doc_summaries, doc_count=len(doc_lines),
    )

    try:
        raw = call_llm(SYSTEM_PROMPT, prompt)
        data = parse_llm_json(raw)
    except (LLMError, Exception) as exc:
        summary = ClinicalSummary(
            mrn=mrn, patient_name=name,
            chief_concern="Summary generation failed",
            error=str(exc),
        )
        return summary

    summary = ClinicalSummary(
        mrn=mrn,
        patient_name=name,
        chief_concern=data.get("chief_concern", ""),
        key_diagnoses=data.get("key_diagnoses", []),
        recent_records=[RecentRecord(**r) for r in data.get("recent_records", [])],
        flagged_anomalies=data.get("flagged_anomalies", []),
        word_count=data.get("word_count", 0),
        disclaimer=data.get("disclaimer", ClinicalSummary.model_fields["disclaimer"].default),
        cached=False,
    )

    set_summary_cache(key, mrn, summary.model_dump())
    return summary
