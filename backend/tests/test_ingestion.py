"""
Unit tests for the ingestion & cleaning pipeline.
Covers ≥ 3 edge cases as required:
  1. Missing required fields (DOB, MRN)
  2. Inconsistent date formats (12 variants)
  3. Duplicate records (same MRN+DOB)
  4. Conflicting MRN formatting (spaces, dashes, case)
  5. Gender normalization (all code variants)
  6. Document with no content is skipped
  7. CSV ingestion with column-name aliases
"""
from __future__ import annotations

import json
import pytest
from datetime import date

from app.ingestion.cleaner import (
    dedup_records,
    normalize_date,
    normalize_gender,
    normalize_mrn,
)
from app.ingestion.models import GenderCode
from app.ingestion.pipeline import ingest_csv, ingest_json, ingest_text


# ---------------------------------------------------------------------------
# 1. Date normalization — 12 format variants
# ---------------------------------------------------------------------------

class TestNormalizeDate:
    @pytest.mark.parametrize("raw,expected", [
        ("1985-03-14",       date(1985, 3, 14)),
        ("03/14/1985",       date(1985, 3, 14)),
        ("14/03/1985",       date(1985, 3, 14)),
        ("03-14-1985",       date(1985, 3, 14)),
        ("19850314",         date(1985, 3, 14)),
        ("14 Mar 1985",      date(1985, 3, 14)),
        ("14 March 1985",    date(1985, 3, 14)),
        ("Mar 14, 1985",     date(1985, 3, 14)),
        ("March 14, 1985",   date(1985, 3, 14)),
        ("03/14/85",         date(1985, 3, 14)),
        ("14.03.1985",       date(1985, 3, 14)),
    ])
    def test_formats(self, raw, expected):
        result, _ = normalize_date(raw, "dob")
        assert result == expected

    def test_missing_raises(self):
        with pytest.raises(ValueError, match="Missing required date field"):
            normalize_date(None, "dob")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            normalize_date("", "dob")

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            normalize_date("not-a-date-at-all!!", "dob")

    def test_audit_log_populated(self):
        _, audit = normalize_date("03/14/1985", "dob")
        assert len(audit) > 0
        assert audit[0].field == "dob"
        assert audit[0].original == "03/14/1985"


# ---------------------------------------------------------------------------
# 2. Gender normalization
# ---------------------------------------------------------------------------

class TestNormalizeGender:
    @pytest.mark.parametrize("raw,expected", [
        ("male",        GenderCode.MALE),
        ("Male",        GenderCode.MALE),
        ("M",           GenderCode.MALE),
        ("m",           GenderCode.MALE),
        ("MALE",        GenderCode.MALE),
        ("1",           GenderCode.MALE),
        ("female",      GenderCode.FEMALE),
        ("Female",      GenderCode.FEMALE),
        ("F",           GenderCode.FEMALE),
        ("f",           GenderCode.FEMALE),
        ("2",           GenderCode.FEMALE),
        ("other",       GenderCode.OTHER),
        ("non-binary",  GenderCode.OTHER),
        ("unknown",     GenderCode.UNKNOWN),
        ("",            GenderCode.UNKNOWN),
        (None,          GenderCode.UNKNOWN),
    ])
    def test_all_variants(self, raw, expected):
        result, _ = normalize_gender(raw)
        assert result == expected


# ---------------------------------------------------------------------------
# 3. MRN normalization
# ---------------------------------------------------------------------------

class TestNormalizeMRN:
    def test_uppercase(self):
        mrn, _ = normalize_mrn("mrn12345")
        assert mrn == "MRN12345"

    def test_remove_dashes(self):
        mrn, _ = normalize_mrn("MRN-123-45")
        assert mrn == "MRN12345"

    def test_remove_spaces(self):
        mrn, _ = normalize_mrn("MRN 123 45")
        assert mrn == "MRN12345"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_mrn("")

    def test_audit_created_on_change(self):
        _, audit = normalize_mrn("mrn-123")
        assert len(audit) == 1
        assert "MRN123" in audit[0].normalized

    def test_no_audit_when_already_clean(self):
        _, audit = normalize_mrn("MRN123")
        assert len(audit) == 0


# ---------------------------------------------------------------------------
# 4. Duplicate detection
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_exact_duplicate_removed(self):
        recs = [
            {"mrn": "MRN001", "date_of_birth": "1980-01-01"},
            {"mrn": "MRN001", "date_of_birth": "1980-01-01"},  # duplicate
        ]
        unique, dupes = dedup_records(recs)
        assert len(unique) == 1
        assert len(dupes) == 1

    def test_mrn_format_variants_treated_as_same(self):
        recs = [
            {"mrn": "mrn-001", "date_of_birth": "1980-01-01"},
            {"mrn": "MRN001",  "date_of_birth": "1980-01-01"},  # same after normalization
        ]
        unique, dupes = dedup_records(recs)
        assert len(unique) == 1

    def test_different_mrns_kept(self):
        recs = [
            {"mrn": "MRN001", "date_of_birth": "1980-01-01"},
            {"mrn": "MRN002", "date_of_birth": "1980-01-01"},
        ]
        unique, dupes = dedup_records(recs)
        assert len(unique) == 2
        assert len(dupes) == 0


# ---------------------------------------------------------------------------
# 5. Full pipeline — JSON ingestion
# ---------------------------------------------------------------------------

class TestJSONPipeline:
    def _sample_json(self, overrides: dict = {}) -> str:
        base = {
            "mrn": "MRN99001",
            "given_name": "Test",
            "family_name": "Patient",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "documents": [
                {
                    "doc_id": "d1",
                    "doc_type": "lab_report",
                    "title": "CBC Panel",
                    "content": "WBC 6.5, RBC 4.2 — normal ranges.",
                    "authored_date": "2024-01-10",
                    "author": "Dr. Test",
                }
            ],
        }
        base.update(overrides)
        return json.dumps([base])

    def test_happy_path(self):
        records, errors = ingest_json(self._sample_json())
        assert len(records) == 1
        assert records[0].patient.mrn == "MRN99001"
        assert records[0].patient.gender == GenderCode.FEMALE
        assert len(records[0].documents) == 1

    def test_missing_dob_produces_audit_entry(self):
        records, errors = ingest_json(self._sample_json({"date_of_birth": ""}))
        assert len(records) == 1
        audit_fields = [a.field for a in records[0].patient.audit_log]
        assert "date_of_birth" in audit_fields

    def test_messy_mrn_normalized(self):
        records, _ = ingest_json(self._sample_json({"mrn": "mrn-99 002"}))
        assert records[0].patient.mrn == "MRN99002"

    def test_document_no_content_skipped(self):
        data = json.loads(self._sample_json())
        data[0]["documents"][0]["content"] = ""
        records, errors = ingest_json(json.dumps(data))
        assert len(records[0].documents) == 0
        assert any("no content" in str(e.get("detail", "")).lower() for e in errors)

    def test_duplicate_patients_removed(self):
        data = json.loads(self._sample_json())
        data.append(data[0].copy())  # exact duplicate
        records, errors = ingest_json(json.dumps(data))
        assert len(records) == 1
        assert any(e.get("type") == "duplicate_removed" for e in errors)


# ---------------------------------------------------------------------------
# 6. CSV ingestion
# ---------------------------------------------------------------------------

class TestCSVPipeline:
    CSV = """patient_id,first_name,last_name,dob,sex,document_type,date,content,doctor
MRN50001,Jane,Doe,1992-08-15,female,lab_report,2024-02-01,HbA1c 6.5% borderline.,Dr. Adams
MRN50002,John,Doe,07/22/1988,male,imaging_note,22/07/2024,Chest X-ray clear.,Dr. Baker
"""

    def test_csv_parses_two_patients(self):
        records, _ = ingest_csv(self.CSV)
        mrns = {r.patient.mrn for r in records}
        assert "MRN50001" in mrns
        assert "MRN50002" in mrns

    def test_csv_date_normalization(self):
        records, _ = ingest_csv(self.CSV)
        p2 = next(r for r in records if r.patient.mrn == "MRN50002")
        assert p2.patient.date_of_birth == date(1988, 7, 22)


# ---------------------------------------------------------------------------
# 7. Text ingestion
# ---------------------------------------------------------------------------

class TestTextPipeline:
    NOTE = """MRN: MRN60001
Date: 2024-03-15
Patient presents with acute bronchitis. Prescribed amoxicillin.
"""

    def test_text_extracts_mrn(self):
        records, _ = ingest_text(self.NOTE)
        assert records[0].patient.mrn == "MRN60001"

    def test_text_creates_one_document(self):
        records, _ = ingest_text(self.NOTE)
        assert len(records[0].documents) == 1
        assert "bronchitis" in records[0].documents[0].content
