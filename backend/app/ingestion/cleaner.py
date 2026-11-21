"""
Data cleaning utilities.

Handles:
- Missing / None fields
- Inconsistent date formats (12 common patterns)
- Duplicate records (same MRN + DOB)
- Conflicting patient identifiers (MRN variants)
- Gender code normalization
- MRN normalization
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from dateutil import parser as dateutil_parser

from .models import AuditEntry, GenderCode

# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y",
    "%d-%m-%Y", "%Y%m%d", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%m/%d/%y", "%d.%m.%Y",
]


def normalize_date(raw: Any, field_name: str) -> tuple[date, list[AuditEntry]]:
    """
    Try to parse *raw* into a date.  Returns (date, audit_entries).
    Raises ValueError if unparseable.
    """
    audit: list[AuditEntry] = []
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"Missing required date field '{field_name}'")

    raw_str = str(raw).strip()

    # Already a date/datetime
    if isinstance(raw, date):
        return raw if isinstance(raw, date) else raw.date(), audit

    # Try each format
    for fmt in _DATE_FORMATS:
        try:
            parsed = date.fromisoformat(raw_str) if fmt == "%Y-%m-%d" else \
                     __import__("datetime").datetime.strptime(raw_str, fmt).date()
            if raw_str != str(parsed):
                audit.append(AuditEntry(
                    field=field_name,
                    original=raw_str,
                    normalized=str(parsed),
                    reason=f"Date normalized from format '{fmt}' to ISO 8601",
                ))
            return parsed, audit
        except (ValueError, TypeError):
            continue

    # Fallback: dateutil fuzzy parsing
    try:
        parsed = dateutil_parser.parse(raw_str, fuzzy=True).date()
        audit.append(AuditEntry(
            field=field_name,
            original=raw_str,
            normalized=str(parsed),
            reason="Date normalized via fuzzy dateutil parsing",
        ))
        return parsed, audit
    except Exception:
        raise ValueError(f"Cannot parse date '{raw_str}' for field '{field_name}'")


# ---------------------------------------------------------------------------
# Gender normalization
# ---------------------------------------------------------------------------

_GENDER_MAP: dict[str, GenderCode] = {
    "m": GenderCode.MALE, "male": GenderCode.MALE,
    "man": GenderCode.MALE, "1": GenderCode.MALE,
    "f": GenderCode.FEMALE, "female": GenderCode.FEMALE,
    "woman": GenderCode.FEMALE, "2": GenderCode.FEMALE,
    "o": GenderCode.OTHER, "other": GenderCode.OTHER,
    "nb": GenderCode.OTHER, "non-binary": GenderCode.OTHER,
    "u": GenderCode.UNKNOWN, "unknown": GenderCode.UNKNOWN,
    "": GenderCode.UNKNOWN,
}


def normalize_gender(raw: Any, field_name: str = "gender") -> tuple[GenderCode, list[AuditEntry]]:
    audit: list[AuditEntry] = []
    if raw is None:
        return GenderCode.UNKNOWN, [AuditEntry(
            field=field_name, original=None,
            normalized=GenderCode.UNKNOWN, reason="Missing gender defaulted to 'unknown'",
        )]
    key = str(raw).strip().lower()
    code = _GENDER_MAP.get(key, GenderCode.UNKNOWN)
    if str(raw).strip() != code.value:
        audit.append(AuditEntry(
            field=field_name, original=raw,
            normalized=code.value,
            reason=f"Gender '{raw}' mapped to canonical code '{code.value}'",
        ))
    return code, audit


# ---------------------------------------------------------------------------
# MRN normalization
# ---------------------------------------------------------------------------

def normalize_mrn(raw: Any) -> tuple[str, list[AuditEntry]]:
    audit: list[AuditEntry] = []
    if not raw:
        raise ValueError("MRN is required and cannot be empty")
    cleaned = re.sub(r"[\s\-_]", "", str(raw)).upper()
    if cleaned != str(raw):
        audit.append(AuditEntry(
            field="mrn", original=raw, normalized=cleaned,
            reason="MRN normalized: removed spaces/dashes, uppercased",
        ))
    return cleaned, audit


# ---------------------------------------------------------------------------
# Name cleaning
# ---------------------------------------------------------------------------

def normalize_name(raw: Any, field_name: str) -> tuple[str, list[AuditEntry]]:
    audit: list[AuditEntry] = []
    if not raw or str(raw).strip() == "":
        raise ValueError(f"Required name field '{field_name}' is missing")
    cleaned = str(raw).strip().title()
    if cleaned != str(raw):
        audit.append(AuditEntry(
            field=field_name, original=raw, normalized=cleaned,
            reason="Name normalized: stripped whitespace, title-cased",
        ))
    return cleaned, audit


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def dedup_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Remove duplicate patient records keyed by (MRN, DOB).
    Returns (unique_records, duplicates_removed).
    """
    seen: dict[tuple, dict] = {}
    duplicates: list[dict] = []
    for rec in records:
        mrn = re.sub(r"[\s\-_]", "", str(rec.get("mrn", ""))).upper()
        dob = str(rec.get("date_of_birth") or rec.get("dob") or "")
        key = (mrn, dob)
        if key in seen:
            duplicates.append(rec)
        else:
            seen[key] = rec
    return list(seen.values()), duplicates
