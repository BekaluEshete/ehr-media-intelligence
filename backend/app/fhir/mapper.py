"""
Maps CleanedRecord → HL7 FHIR R4 Bundle (Patient + DocumentReference + DiagnosticReport).

Uses fhir.resources v8 for schema validation.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fhir.resources.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.documentreference import DocumentReference, DocumentReferenceContent
from fhir.resources.attachment import Attachment
from fhir.resources.humanname import HumanName
from fhir.resources.identifier import Identifier
from fhir.resources.patient import Patient
from fhir.resources.reference import Reference

from app.ingestion.models import CleanedDocument, CleanedRecord, DocumentType


# ---------------------------------------------------------------------------
# FHIR gender mapping
# ---------------------------------------------------------------------------
_GENDER_MAP = {
    "male": "male",
    "female": "female",
    "other": "other",
    "unknown": "unknown",
}

# ---------------------------------------------------------------------------
# Document type → LOINC code mapping
# ---------------------------------------------------------------------------
_DOC_LOINC: dict[DocumentType, tuple[str, str]] = {
    DocumentType.LAB_REPORT:         ("11502-2", "Laboratory report"),
    DocumentType.IMAGING_NOTE:       ("18748-4", "Diagnostic imaging study"),
    DocumentType.DISCHARGE_SUMMARY:  ("18842-5", "Discharge summary"),
    DocumentType.CLINICAL_NOTE:      ("34109-9", "Clinical note"),
    DocumentType.UNKNOWN:            ("34109-9", "Clinical note"),
}


def _patient_resource(record: CleanedRecord) -> Patient:
    p = record.patient
    patient = Patient(
        id=f"patient-{p.mrn.lower()}",
        identifier=[
            Identifier(
                use="usual",
                type=CodeableConcept(
                    coding=[Coding(system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                   code="MR", display="Medical record number")]
                ),
                system="urn:oid:2.16.840.1.113883.4.1",
                value=p.mrn,
            )
        ],
        name=[HumanName(use="official", family=p.family_name, given=[p.given_name])],
        gender=_GENDER_MAP.get(p.gender.value, "unknown"),
        birthDate=str(p.date_of_birth),
    )
    return patient


def _document_reference(doc: CleanedDocument, patient_id: str) -> DocumentReference:
    loinc_code, loinc_display = _DOC_LOINC[doc.doc_type]
    dr = DocumentReference(
        id=f"docref-{doc.doc_id}",
        status="current",
        type=CodeableConcept(
            coding=[Coding(
                system="http://loinc.org",
                code=loinc_code,
                display=loinc_display,
            )]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        date=datetime.combine(doc.authored_date,
                              datetime.min.time()).isoformat() + "Z",
        author=[Reference(display=doc.author)] if doc.author else [],
        content=[
            DocumentReferenceContent(
                attachment=Attachment(
                    contentType="text/plain",
                    title=doc.title,
                    data=__import__("base64").b64encode(
                        doc.content.encode("utf-8")
                    ).decode("utf-8"),
                )
            )
        ],
        description=doc.title,
    )
    return dr


def _diagnostic_report(doc: CleanedDocument, patient_id: str,
                        doc_ref_id: str) -> DiagnosticReport | None:
    """Only generate a DiagnosticReport for lab/imaging documents."""
    if doc.doc_type not in (DocumentType.LAB_REPORT, DocumentType.IMAGING_NOTE):
        return None

    loinc_code, loinc_display = _DOC_LOINC[doc.doc_type]
    report = DiagnosticReport(
        id=f"diagrpt-{doc.doc_id}",
        status="final",
        code=CodeableConcept(
            coding=[Coding(
                system="http://loinc.org",
                code=loinc_code,
                display=loinc_display,
            )]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        effectiveDateTime=datetime.combine(
            doc.authored_date, datetime.min.time()
        ).isoformat() + "Z",
        issued=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        result=[],
        presentedForm=[
            Attachment(
                contentType="text/plain",
                title=doc.title,
                data=__import__("base64").b64encode(
                    doc.content.encode("utf-8")
                ).decode("utf-8"),
            )
        ],
    )
    return report


def build_bundle(record: CleanedRecord) -> Bundle:
    """Build a FHIR R4 transaction Bundle for one patient."""
    entries: list[BundleEntry] = []
    patient = _patient_resource(record)
    patient_id = patient.id

    entries.append(BundleEntry(
        fullUrl=f"urn:uuid:{patient_id}",
        resource=patient,
        request=BundleEntryRequest(method="PUT",
                                   url=f"Patient/{patient_id}"),
    ))

    for doc in record.documents:
        doc_ref = _document_reference(doc, patient_id)
        entries.append(BundleEntry(
            fullUrl=f"urn:uuid:{doc_ref.id}",
            resource=doc_ref,
            request=BundleEntryRequest(method="PUT",
                                       url=f"DocumentReference/{doc_ref.id}"),
        ))

        diag = _diagnostic_report(doc, patient_id, doc_ref.id)
        if diag:
            entries.append(BundleEntry(
                fullUrl=f"urn:uuid:{diag.id}",
                resource=diag,
                request=BundleEntryRequest(method="PUT",
                                           url=f"DiagnosticReport/{diag.id}"),
            ))

    bundle = Bundle(
        id=str(uuid.uuid4()),
        type="transaction",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        entry=entries,
    )
    return bundle


def bundle_to_dict(bundle: Bundle) -> dict:
    return json.loads(bundle.model_dump_json())
