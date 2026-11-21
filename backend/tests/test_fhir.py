"""Tests for FHIR R4 mapping and validation."""
from __future__ import annotations

from datetime import date

from app.ingestion.models import (
    CleanedDocument, CleanedPatient, CleanedRecord, DocumentType, GenderCode
)
from app.fhir.mapper import build_bundle, bundle_to_dict
from app.fhir.validator import validate_bundle


def _make_record(mrn="MRN00001", doc_type=DocumentType.LAB_REPORT) -> CleanedRecord:
    patient = CleanedPatient(
        mrn=mrn,
        given_name="Alice",
        family_name="Smith",
        date_of_birth=date(1985, 3, 14),
        gender=GenderCode.FEMALE,
    )
    doc = CleanedDocument(
        doc_id="doc-001",
        patient_mrn=mrn,
        doc_type=doc_type,
        title="CBC Panel",
        content="WBC 6.5 k/uL, Hgb 13.8 g/dL — normal ranges.",
        authored_date=date(2024, 1, 10),
        author="Dr. Jones",
    )
    return CleanedRecord(patient=patient, documents=[doc])


class TestFHIRMapper:
    def _rtype(self, resource) -> str:
        try:
            return resource.get_resource_type()
        except AttributeError:
            return getattr(resource, "resource_type", "")

    def test_bundle_has_patient(self):
        record = _make_record()
        bundle = build_bundle(record)
        rtypes = [self._rtype(e.resource) for e in bundle.entry]
        assert "Patient" in rtypes

    def test_bundle_has_document_reference(self):
        record = _make_record()
        bundle = build_bundle(record)
        rtypes = [self._rtype(e.resource) for e in bundle.entry]
        assert "DocumentReference" in rtypes

    def test_lab_report_produces_diagnostic_report(self):
        record = _make_record(doc_type=DocumentType.LAB_REPORT)
        bundle = build_bundle(record)
        rtypes = [self._rtype(e.resource) for e in bundle.entry]
        assert "DiagnosticReport" in rtypes

    def test_clinical_note_no_diagnostic_report(self):
        record = _make_record(doc_type=DocumentType.CLINICAL_NOTE)
        bundle = build_bundle(record)
        rtypes = [self._rtype(e.resource) for e in bundle.entry]
        assert "DiagnosticReport" not in rtypes

    def test_patient_mrn_in_identifier(self):
        record = _make_record(mrn="TESTMRN01")
        bundle = build_bundle(record)
        patient = next(e.resource for e in bundle.entry
                       if self._rtype(e.resource) == "Patient")
        mrns = [i.value for i in patient.identifier]
        assert "TESTMRN01" in mrns

    def test_bundle_serializes_to_dict(self):
        record = _make_record()
        bundle = build_bundle(record)
        d = bundle_to_dict(bundle)
        assert d["resourceType"] == "Bundle"
        assert d["type"] == "transaction"
        assert len(d["entry"]) >= 3  # Patient + DocRef + DiagReport

    def test_subject_references_patient(self):
        record = _make_record()
        bundle = build_bundle(record)
        d = bundle_to_dict(bundle)
        patient_id = next(
            e["resource"]["id"] for e in d["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        for entry in d["entry"]:
            res = entry["resource"]
            if res["resourceType"] in ("DocumentReference", "DiagnosticReport"):
                ref = res["subject"]["reference"]
                assert patient_id in ref


class TestFHIRValidator:
    def test_valid_bundle_passes(self):
        record = _make_record()
        bundle_dict = bundle_to_dict(build_bundle(record))
        report = validate_bundle(bundle_dict, "MRN00001")
        assert report.is_valid, report.errors

    def test_missing_patient_fails(self):
        bundle_dict = {
            "resourceType": "Bundle",
            "id": "test",
            "type": "transaction",
            "entry": [],
        }
        report = validate_bundle(bundle_dict, "NONE")
        assert not report.is_valid
        assert any("Patient" in e for e in report.errors)

    def test_resource_counts_correct(self):
        record = _make_record(doc_type=DocumentType.LAB_REPORT)
        bundle_dict = bundle_to_dict(build_bundle(record))
        report = validate_bundle(bundle_dict, "MRN00001")
        assert report.resource_counts.get("Patient") == 1
        assert report.resource_counts.get("DocumentReference") == 1
        assert report.resource_counts.get("DiagnosticReport") == 1

    def test_subject_references_patient(self):
        record = _make_record()
        bundle = build_bundle(record)
        d = bundle_to_dict(bundle)
        patient_id = next(
            e["resource"]["id"] for e in d["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        for entry in d["entry"]:
            res = entry["resource"]
            if res["resourceType"] in ("DocumentReference", "DiagnosticReport"):
                ref = res["subject"]["reference"]
                assert patient_id in ref
