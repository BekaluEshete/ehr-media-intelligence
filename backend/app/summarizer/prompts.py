"""Prompt templates for clinical summarization."""

SYSTEM_PROMPT = """You are a clinical documentation assistant. Your task is to generate
concise, structured summaries from FHIR patient bundles for review by licensed clinicians.

IMPORTANT RULES:
- Keep the summary under 200 words
- Be factual and precise; do not infer diagnoses beyond what is documented
- Use plain clinical language (avoid abbreviations unless standard)
- Always include the disclaimer field
- Structure the output as valid JSON only — no prose outside the JSON"""

SUMMARY_PROMPT_TEMPLATE = """Summarize the following patient FHIR bundle.

Patient MRN: {mrn}
Patient Name: {name}
Date of Birth: {dob}

Documents ({doc_count} total):
{doc_summaries}

Return a JSON object with EXACTLY these keys:
{{
  "chief_concern": "...",
  "key_diagnoses": ["...", "..."],
  "recent_records": [
    {{"type": "...", "date": "...", "summary": "..."}}
  ],
  "flagged_anomalies": ["..."],
  "word_count": <integer>,
  "disclaimer": "AI-generated summary. Not validated by a clinician. Do not use for clinical decision-making."
}}
"""


def build_summary_prompt(mrn: str, name: str, dob: str,
                          doc_summaries: str, doc_count: int) -> str:
    return SUMMARY_PROMPT_TEMPLATE.format(
        mrn=mrn, name=name, dob=dob,
        doc_summaries=doc_summaries, doc_count=doc_count,
    )
