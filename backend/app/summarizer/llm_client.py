"""
Provider-agnostic LLM client.
Supports:  gemini  |  anthropic  |  openai  |  stub (no API key needed)
"""
from __future__ import annotations

import json
import os
import re

from app.config import settings


class LLMError(Exception):
    pass


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _call_gemini(system: str, user: str) -> str:
    from google import genai
    from google.genai import types

    key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise LLMError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=key)

    # Try models in order — newer ones may be unavailable during high demand
    models_to_try = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    ]
    last_error = None
    for model in models_to_try:
        try:
            response = client.models.generate_content(
                model=model,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=600,
                    temperature=0.2,
                ),
            )
            return response.text
        except Exception as e:
            last_error = e
            # 503 = busy, try next model; anything else raise immediately
            if "503" not in str(e) and "UNAVAILABLE" not in str(e):
                raise LLMError(f"Gemini error: {e}") from e
            continue

    raise LLMError(f"All Gemini models unavailable: {last_error}")


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

def _call_anthropic(system: str, user: str) -> str:
    import anthropic
    key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI
    key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise LLMError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=600,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Stub (offline / no key)
# ---------------------------------------------------------------------------

def _call_stub(system: str, user: str) -> str:
    """Deterministic stub — returns valid JSON without hitting any API."""
    mrn_match = re.search(r"Patient MRN:\s*(\S+)", user)
    mrn = mrn_match.group(1) if mrn_match else "UNKNOWN"
    return json.dumps({
        "chief_concern": f"[STUB] No API key configured — stub summary for {mrn}",
        "key_diagnoses": ["Stub diagnosis A", "Stub diagnosis B"],
        "recent_records": [
            {"type": "lab_report", "date": "2024-01-01",
             "summary": "Stub lab result — normal ranges"},
        ],
        "flagged_anomalies": [],
        "word_count": 42,
        "disclaimer": (
            "AI-generated summary (STUB MODE — no real LLM called). "
            "Not validated by a clinician. Do not use for clinical decision-making."
        ),
    })


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def call_llm(system: str, user: str) -> str:
    """Route to configured provider. Auto-falls back to stub if no key is set."""
    provider = (settings.llm_provider or "stub").lower()

    # Auto-fallback: if provider requires a key and none is present → stub
    if provider == "gemini" and not (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")):
        provider = "stub"
    if provider == "anthropic" and not (settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")):
        provider = "stub"
    if provider == "openai" and not (settings.openai_api_key or os.environ.get("OPENAI_API_KEY")):
        provider = "stub"

    if provider == "gemini":
        return _call_gemini(system, user)
    elif provider == "anthropic":
        return _call_anthropic(system, user)
    elif provider == "openai":
        return _call_openai(system, user)
    else:
        return _call_stub(system, user)


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def parse_llm_json(raw: str) -> dict:
    """
    Extract the JSON object from an LLM response.
    Handles markdown code fences and surrounding prose.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise LLMError(f"LLM response contained no JSON object:\n{raw[:300]}")
    return json.loads(match.group(0))
