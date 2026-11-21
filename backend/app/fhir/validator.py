"""
FHIR R4 Bundle validation.

Uses fhir.resources' own Pydantic models as the validation layer.
Produces a human-readable validation report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError


@dataclass
class ValidationReport:
    patient_mrn: str
    bundle_id: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resource_counts: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        lines = [
            f"[{status}] Bundle {self.bundle_id} — Patient MRN: {self.patient_mrn}",
            f"  Resources: {self.resource_counts}",
        ]
        if self.errors:
            lines.append(f"  Errors ({len(self.errors)}):")
            lines.extend(f"    - {e}" for e in self.errors)
        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            lines.extend(f"    - {w}" for w in self.warnings)
        return "\n".join(lines)


def validate_bundle(bundle_dict: dict[str, Any], patient_mrn: str = "") -> ValidationReport:
    """
    Validate a FHIR R4 Bundle dict.
    Re-parses through fhir.resources to catch schema violations.
    """
    from fhir.resources.bundle import Bundle

    bundle_id = bundle_dict.get("id", "unknown")
    errors: list[str] = []
    warnings: list[str] = []
    resource_counts: dict[str, int] = {}

    try:
        bundle = Bundle.model_validate(bundle_dict)
    except ValidationError as exc:
        for err in exc.errors():
            loc = " → ".join(str(x) for x in err["loc"])
            errors.append(f"{loc}: {err['msg']}")
        return ValidationReport(
            patient_mrn=patient_mrn,
            bundle_id=bundle_id,
            is_valid=False,
            errors=errors,
        )

    def _rtype(resource) -> str:
        """Compat helper: fhir.resources v8 uses get_resource_type()."""
        try:
            return resource.get_resource_type()
        except AttributeError:
            return getattr(resource, "resource_type", "")

    # Count resource types in entries
    for entry in (bundle.entry or []):
        if entry.resource:
            rtype = _rtype(entry.resource)
            resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

    # Rule checks
    if "Patient" not in resource_counts:
        errors.append("Bundle must contain at least one Patient resource")

    if not resource_counts.get("DocumentReference") and not resource_counts.get("DiagnosticReport"):
        warnings.append("Bundle has no DocumentReference or DiagnosticReport resources")

    # Verify subject references resolve within the bundle
    patient_ids = set()
    for entry in (bundle.entry or []):
        if entry.resource and _rtype(entry.resource) == "Patient":
            patient_ids.add(f"Patient/{entry.resource.id}")

    for entry in (bundle.entry or []):
        res = entry.resource
        if res and _rtype(res) in ("DocumentReference", "DiagnosticReport"):
            subject = getattr(res, "subject", None)
            if subject and subject.reference:
                ref = subject.reference
                # Allow both "Patient/id" and "urn:uuid:id" forms
                if not any(ref.endswith(pid.split("/")[-1]) for pid in patient_ids):
                    warnings.append(
                        f"{res.resource_type}/{res.id}: subject ref '{ref}' not found in bundle"
                    )

    is_valid = len(errors) == 0
    return ValidationReport(
        patient_mrn=patient_mrn,
        bundle_id=bundle_id,
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        resource_counts=resource_counts,
    )


def validate_bundles(bundles: list[tuple[str, dict]]) -> list[ValidationReport]:
    """Validate a list of (mrn, bundle_dict) pairs and return reports."""
    return [validate_bundle(b, mrn) for mrn, b in bundles]


def print_validation_report(reports: list[ValidationReport]) -> None:
    total = len(reports)
    valid = sum(1 for r in reports if r.is_valid)
    print(f"\n{'='*60}")
    print(f"FHIR Validation Report — {valid}/{total} bundles valid")
    print("=" * 60)
    for r in reports:
        print(r.summary())
    print("=" * 60 + "\n")
