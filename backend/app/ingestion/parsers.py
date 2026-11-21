"""
Parsers for the two required input formats:
  - JSON  (simulated EHR export — list of patient objects)
  - CSV / plain text  (lab results, scanned notes)

Each parser returns a list of raw dicts normalised to a loose common schema
before the cleaner runs.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def parse_json(source: str | Path | bytes) -> list[dict[str, Any]]:
    """
    Accept a JSON file path, raw JSON string, or bytes.
    Expected top-level shape: list of patient-record objects.
    Also handles {"patients": [...]} envelope.
    """
    if isinstance(source, Path):
        raw = source.read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        raw = source.decode("utf-8")
    else:
        raw = source

    data = json.loads(raw)

    if isinstance(data, dict):
        # unwrap common envelopes
        for key in ("patients", "records", "data", "entries"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            data = [data]

    if not isinstance(data, list):
        raise ValueError("JSON input must be a list of patient records (or an envelope with one)")

    # Stamp source format
    for rec in data:
        rec.setdefault("_source_format", "json")
        rec.setdefault("_source_id", str(rec.get("id") or rec.get("mrn") or uuid.uuid4()))

    return data


# ---------------------------------------------------------------------------
# CSV parser
# ---------------------------------------------------------------------------

_CSV_FIELD_ALIASES: dict[str, str] = {
    # MRN variants
    "patient_id": "mrn", "patientid": "mrn", "patient id": "mrn",
    "medical_record_number": "mrn", "medical record number": "mrn",
    # Name variants
    "first_name": "given_name", "firstname": "given_name", "given": "given_name",
    "last_name": "family_name", "lastname": "family_name", "surname": "family_name",
    "name": "_full_name",
    # DOB variants
    "dob": "date_of_birth", "birth_date": "date_of_birth", "birthdate": "date_of_birth",
    "date_of_birth": "date_of_birth",
    # Gender variants
    "sex": "gender", "gender_code": "gender",
    # Doc variants
    "note": "content", "text": "content", "report": "content",
    "type": "doc_type", "document_type": "doc_type",
    "date": "authored_date", "report_date": "authored_date",
    "document_date": "authored_date",
    "document_id": "doc_id", "id": "doc_id",
    "doctor": "author", "physician": "author",
}


def _remap_keys(row: dict[str, str]) -> dict[str, Any]:
    remapped: dict[str, Any] = {}
    for k, v in row.items():
        canonical = _CSV_FIELD_ALIASES.get(k.lower().strip(), k.lower().strip())
        remapped[canonical] = v.strip() if isinstance(v, str) else v
    # Split full name if present
    if "_full_name" in remapped and "given_name" not in remapped:
        parts = str(remapped.pop("_full_name")).split(None, 1)
        remapped["given_name"] = parts[0] if parts else ""
        remapped["family_name"] = parts[1] if len(parts) > 1 else ""
    return remapped


def parse_csv(source: str | Path | bytes) -> list[dict[str, Any]]:
    """
    Parse a CSV file/string into a list of raw record dicts.
    Rows that look like patient demographics are patient records;
    rows with a 'content' or 'note' field are document records linked by MRN.
    """
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        text = source.decode("utf-8")
    else:
        text = source

    reader = csv.DictReader(io.StringIO(text))
    records: list[dict[str, Any]] = []
    for i, row in enumerate(reader):
        rec = _remap_keys(dict(row))
        rec.setdefault("_source_format", "csv")
        rec.setdefault("_source_id", str(rec.get("doc_id") or rec.get("mrn") or f"csv-{i}"))
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Plain-text parser  (one document per record, minimal structure)
# ---------------------------------------------------------------------------

def parse_text(source: str | Path | bytes, patient_mrn: str = "UNKNOWN") -> list[dict[str, Any]]:
    """
    Treat a plain-text blob as a single clinical document.
    Tries to extract MRN / date hints from the text.
    """
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        text = source.decode("utf-8")
    else:
        text = source

    # Try extracting MRN from header lines like "MRN: 12345"
    mrn_match = __import__("re").search(r"MRN[:\s]+([A-Z0-9\-]+)", text, __import__("re").I)
    if mrn_match:
        patient_mrn = mrn_match.group(1)

    return [{
        "mrn": patient_mrn,
        "content": text.strip(),
        "doc_type": "clinical_note",
        "authored_date": "",
        "title": "Imported plain-text note",
        "_source_format": "text",
        "_source_id": str(uuid.uuid4()),
    }]
