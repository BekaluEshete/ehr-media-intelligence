"""Canonical Pydantic v2 models for cleaned EHR records."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class GenderCode(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class AuditEntry(BaseModel):
    field: str
    original: Any
    normalized: Any
    reason: str


class CleanedPatient(BaseModel):
    """Canonical patient demographics after cleaning."""
    mrn: str                          # Normalized MRN: uppercase, no spaces/dashes
    given_name: str
    family_name: str
    date_of_birth: date
    gender: GenderCode
    phone: str = ""
    email: str = ""
    address: str = ""
    audit_log: list[AuditEntry] = Field(default_factory=list)
    source_format: str = ""           # "json" | "csv" | "text"
    source_id: str = ""               # original record id before normalization

    @field_validator("mrn")
    @classmethod
    def normalize_mrn(cls, v: str) -> str:
        return v.upper().replace("-", "").replace(" ", "")


class DocumentType(str, Enum):
    LAB_REPORT = "lab_report"
    IMAGING_NOTE = "imaging_note"
    DISCHARGE_SUMMARY = "discharge_summary"
    CLINICAL_NOTE = "clinical_note"
    UNKNOWN = "unknown"


class CleanedDocument(BaseModel):
    """Canonical representation of a clinical document after cleaning."""
    doc_id: str
    patient_mrn: str
    doc_type: DocumentType
    title: str
    content: str
    authored_date: date
    author: str = ""
    encounter_id: str = ""
    audit_log: list[AuditEntry] = Field(default_factory=list)
    source_format: str = ""
    source_id: str = ""


class CleanedRecord(BaseModel):
    """Top-level container: one patient + their documents."""
    patient: CleanedPatient
    documents: list[CleanedDocument] = Field(default_factory=list)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
