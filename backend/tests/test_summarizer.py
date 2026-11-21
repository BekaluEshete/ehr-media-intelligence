"""Tests for the summarizer (using stub LLM — no API key required)."""
from __future__ import annotations

import json

import pytest

from app.summarizer.llm_client import _call_stub, parse_llm_json
from app.summarizer.summarizer import summarize_bundle


@pytest.fixture(autouse=True)
def force_stub_llm(monkeypatch):
    """Force stub LLM for all summarizer tests — no API key needed."""
    import app.config as cfg
    monkeypatch.setattr(cfg.settings, "llm_provider", "stub")
    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "")
    monkeypatch.setattr(cfg.settings, "openai_api_key", "")


def _make_bundle(mrn="TESTMRN") -> dict:
    import base64
    content_b64 = base64.b64encode(b"WBC 6.5 k/uL, normal ranges.").decode()
    return {
        "resourceType": "Bundle",
        "id": "test-bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": f"patient-{mrn.lower()}",
                    "identifier": [{"use": "usual", "value": mrn}],
                    "name": [{"family": "Test", "given": ["Patient"]}],
                    "birthDate": "1985-03-14",
                }
            },
            {
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": "docref-001",
                    "status": "current",
                    "type": {"coding": [{"system": "http://loinc.org",
                                         "code": "11502-2",
                                         "display": "Laboratory report"}]},
                    "subject": {"reference": f"Patient/patient-{mrn.lower()}"},
                    "date": "2024-01-10T00:00:00Z",
                    "content": [{"attachment": {
                        "contentType": "text/plain",
                        "title": "CBC Panel",
                        "data": content_b64,
                    }}],
                }
            }
        ],
    }


class TestStubSummarizer:
    def test_summary_returns_valid_object(self):
        bundle = _make_bundle("STUBMRN01")
        summary = summarize_bundle(bundle)
        assert summary.mrn == "STUBMRN01"
        assert summary.chief_concern != ""
        assert isinstance(summary.key_diagnoses, list)
        assert len(summary.disclaimer) > 10

    def test_summary_cached_on_second_call(self):
        import uuid
        unique_mrn = f"CACHEMRN_{uuid.uuid4().hex[:8].upper()}"
        bundle = _make_bundle(unique_mrn)
        s1 = summarize_bundle(bundle)
        assert s1.cached is False
        s2 = summarize_bundle(bundle)
        assert s2.cached is True

    def test_different_bundles_have_different_mrns(self):
        b1 = _make_bundle("MRN_A")
        b2 = _make_bundle("MRN_B")
        s1 = summarize_bundle(b1)
        s2 = summarize_bundle(b2)
        assert s1.mrn != s2.mrn

    def test_disclaimer_field_present(self):
        bundle = _make_bundle("DISCLAIMERMRN")
        summary = summarize_bundle(bundle)
        assert "AI-generated" in summary.disclaimer or "STUB" in summary.disclaimer


class TestLLMClient:
    def test_stub_returns_valid_json(self):
        raw = _call_stub("system", "Patient MRN: TEST001\nSome documents.")
        data = json.loads(raw)
        assert "chief_concern" in data
        assert "disclaimer" in data

    def test_parse_llm_json_strips_fences(self):
        raw = '```json\n{"chief_concern": "test", "disclaimer": "ai"}\n```'
        data = parse_llm_json(raw)
        assert data["chief_concern"] == "test"

    def test_parse_llm_json_handles_prose_wrapper(self):
        raw = 'Here is the summary:\n{"chief_concern": "chest pain", "disclaimer": "ai"}\nEnd.'
        data = parse_llm_json(raw)
        assert data["chief_concern"] == "chest pain"

    def test_parse_llm_json_raises_on_no_json(self):
        from app.summarizer.llm_client import LLMError
        with pytest.raises(LLMError):
            parse_llm_json("This response has no JSON object at all.")
