"""
Builds the searchable document corpus from FHIR bundles + AI summaries.

Each indexed document has the shape:
{
  "text":          str,         # text to embed
  "doc_id":        str,
  "mrn":           str,
  "patient_name":  str,
  "resource_type": str,         # "Patient"|"DocumentReference"|"DiagnosticReport"|"Summary"
  "date":          str,         # YYYY-MM-DD
  "title":         str,
  "summary_snippet": str,       # first 200 chars of text
}
"""
from __future__ import annotations

import base64
from typing import Callable

from app.search.vector_store import VectorStore
from app.summarizer.summarizer import ClinicalSummary


def _decode_attachment(att: dict) -> str:
    data = att.get("data", "")
    if data:
        try:
            return base64.b64decode(data).decode("utf-8")
        except Exception:
            pass
    return att.get("title", "")


def extract_docs_from_bundle(bundle: dict) -> list[dict]:
    """
    Turn a FHIR bundle into a list of indexable text chunks.
    One chunk per DocumentReference + DiagnosticReport.
    """
    entries = bundle.get("entry", [])
    patient_name = "Unknown"
    mrn = "UNKNOWN"

    # First pass: get patient info
    for entry in entries:
        res = entry.get("resource", {})
        if res.get("resourceType") == "Patient":
            for ident in res.get("identifier", []):
                if ident.get("use") == "usual":
                    mrn = ident.get("value", mrn)
            names = res.get("name", [])
            if names:
                n = names[0]
                given = " ".join(n.get("given", []))
                family = n.get("family", "")
                patient_name = f"{given} {family}".strip()

    docs: list[dict] = []

    for entry in entries:
        res = entry.get("resource", {})
        rtype = res.get("resourceType", "")

        if rtype == "DocumentReference":
            doc_date = (res.get("date") or "")[:10]
            title = res.get("description") or "Document"
            content = ""
            for c in res.get("content", []):
                content = _decode_attachment(c.get("attachment", {}))
                if content:
                    break
            text = f"{title}\n{content}".strip()
            docs.append({
                "text": text,
                "doc_id": res.get("id", ""),
                "mrn": mrn,
                "patient_name": patient_name,
                "resource_type": "DocumentReference",
                "date": doc_date,
                "title": title,
                "summary_snippet": text[:200],
            })

        elif rtype == "DiagnosticReport":
            doc_date = (res.get("effectiveDateTime") or res.get("issued") or "")[:10]
            code_text = ""
            for coding in res.get("code", {}).get("coding", []):
                code_text = coding.get("display", "")
            content = ""
            for form in res.get("presentedForm", []):
                content = _decode_attachment(form)
                if content:
                    break
            text = f"{code_text}\n{content}".strip()
            docs.append({
                "text": text,
                "doc_id": res.get("id", ""),
                "mrn": mrn,
                "patient_name": patient_name,
                "resource_type": "DiagnosticReport",
                "date": doc_date,
                "title": code_text or "Diagnostic Report",
                "summary_snippet": text[:200],
            })

    return docs


def index_bundle_with_summary(
    bundle: dict,
    summary: ClinicalSummary,
    store: VectorStore,
    embed_fn: Callable,
) -> int:
    """Index a bundle's documents plus its AI summary. Returns count indexed."""
    docs = extract_docs_from_bundle(bundle)

    # Add AI summary as its own indexable chunk
    summary_text = (
        f"Chief concern: {summary.chief_concern}\n"
        f"Diagnoses: {', '.join(summary.key_diagnoses)}\n"
        f"Anomalies: {', '.join(summary.flagged_anomalies)}"
    )
    docs.append({
        "text": summary_text,
        "doc_id": f"summary-{summary.mrn}",
        "mrn": summary.mrn,
        "patient_name": summary.patient_name,
        "resource_type": "Summary",
        "date": "",
        "title": "AI Clinical Summary",
        "summary_snippet": summary_text[:200],
    })

    return store.index_documents(docs, embed_fn)
