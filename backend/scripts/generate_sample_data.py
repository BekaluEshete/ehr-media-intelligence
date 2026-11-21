#!/usr/bin/env python3
"""
Generate synthetic EHR sample data (no real patient data).
Produces:
  backend/data/raw/sample_patients.json  — 10 synthetic patients (JSON format)
  backend/data/raw/sample_labs.csv       — lab result rows (CSV format)
  backend/data/raw/sample_note.txt       — a plain-text clinical note
"""
from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

OUT = Path(__file__).parent.parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

FIRST_NAMES = ["Alice", "Bob", "Carol", "David", "Elena",
               "Frank", "Grace", "Henry", "Iris", "James"]
LAST_NAMES  = ["Smith", "Johnson", "Williams", "Brown", "Jones",
               "Garcia", "Miller", "Davis", "Wilson", "Martinez"]
GENDERS     = ["male", "female", "M", "F", "m", "f", "MALE", "FEMALE", "other", "unknown"]

# Intentionally messy date formats
RAW_DATES = [
    "1985-03-14", "03/14/1985", "14/03/1985", "1990-11-02",
    "Nov 02, 1990", "02 Nov 1990", "1978-07-29", "07-29-1978",
    "19950615", "June 15, 1995", "1965/04/01", "01.04.1965",
]

DOC_TYPES = ["lab_report", "imaging_note", "discharge_summary", "clinical_note"]

# Varied enough that different queries return different patients
LAB_TEXTS = [
    "CBC: WBC 7.2 k/uL (normal), RBC 4.5 M/uL, Hgb 13.8 g/dL. No abnormalities detected.",
    "HbA1c: 7.8% — elevated, consistent with poorly controlled type 2 diabetes mellitus.",
    "Lipid panel: LDL 142 mg/dL (borderline high), HDL 38 mg/dL (low), TG 210 mg/dL (high).",
    "Urinalysis: Protein 2+, glucose trace. Recommend nephrology follow-up for proteinuria.",
    "Thyroid function: TSH 0.3 mIU/L (low), Free T4 1.9 ng/dL (high). Hyperthyroidism workup needed.",
    "BMP: Sodium 128 mEq/L (low), Potassium 5.9 mEq/L (high). Acute hyponatremia, monitor closely.",
    "PT/INR: INR 3.8 — supratherapeutic on warfarin. Hold dose, recheck in 48 hours.",
    "Troponin I: 2.4 ng/mL (elevated). Repeat in 3 hours. Rule out NSTEMI.",
    "Ferritin 6 ng/mL (low), TIBC elevated. Iron deficiency anemia confirmed.",
    "Creatinine 2.1 mg/dL, eGFR 32 mL/min — stage 3b chronic kidney disease.",
]

IMAGING_TEXTS = [
    "Chest X-ray PA: Mild cardiomegaly. No acute consolidation. Pleural effusions absent.",
    "MRI brain: 3mm focus of FLAIR hyperintensity in periventricular white matter. Nonspecific, clinical correlation recommended.",
    "CT abdomen/pelvis with contrast: No acute intra-abdominal pathology. Incidental 6mm renal cyst noted.",
    "Echocardiogram: EF 45%, mild mitral regurgitation, no significant valvular disease.",
    "CT chest PE protocol: No pulmonary embolism. Bilateral ground-glass opacities, possible viral pneumonitis.",
    "X-ray right knee: Moderate tricompartmental osteoarthritis. No acute fracture.",
    "Ultrasound abdomen: Gallstones present, no wall thickening or pericholecystic fluid. Incidental hepatic steatosis.",
    "MRI lumbar spine: L4-L5 disc herniation with moderate left neural foraminal narrowing.",
]

DISCHARGE_TEXTS = [
    "Patient admitted with chest pain. Ruled out NSTEMI. Discharge diagnosis: musculoskeletal chest pain. Continue aspirin 81mg daily.",
    "Admitted for COPD exacerbation. Treated with nebulizers and systemic steroids. Pulmonology follow-up in 2 weeks.",
    "Hospitalized for DKA management. Blood glucose normalized. Insulin regimen adjusted. Endocrinology follow-up scheduled.",
    "Admitted with right lower lobe pneumonia. Completed IV antibiotics, transitioned to oral azithromycin. Discharge O2 sat 97%.",
    "Hip replacement surgery uneventful. Physical therapy initiated. DVT prophylaxis with enoxaparin. Follow-up orthopaedics 2 weeks.",
    "Admitted with hypertensive urgency, BP 198/112. IV labetalol used. Discharged on amlodipine 10mg. Cardiology referral placed.",
]

CLINICAL_NOTES = [
    "Patient presents with acute bronchitis. Productive cough 5 days. No fever. Prescribed amoxicillin 500mg TID x 7 days.",
    "Annual wellness visit. BMI 28.4. Blood pressure 138/88 — lifestyle counselling provided. Repeat in 3 months.",
    "Follow-up type 2 diabetes. HbA1c improved from 8.2% to 7.1%. Continue metformin 1000mg BID. Podiatry referral.",
    "Migraine with aura. Frequency increased to 3x/month. Topiramate prophylaxis initiated. Neurology referral placed.",
    "Anxiety and insomnia. PHQ-9 score 11 (moderate). Started sertraline 50mg. CBT referral to mental health team.",
]


def make_mrn(i: int, messy: bool = False) -> str:
    base = f"MRN{10000 + i}"
    if messy:
        # Intentionally add formatting quirks
        variants = [base, base.lower(), f"mrn-{10000+i}", f"MRN {10000+i}"]
        return random.choice(variants)
    return base


def make_patient(i: int) -> dict:
    given = FIRST_NAMES[i % len(FIRST_NAMES)]
    family = LAST_NAMES[i % len(LAST_NAMES)]
    gender = GENDERS[i % len(GENDERS)]
    dob = RAW_DATES[i % len(RAW_DATES)]
    mrn = make_mrn(i, messy=(i % 3 == 0))

    # Give each patient their own unique document content
    docs = []
    # Every patient gets one lab report unique to them
    docs.append({
        "doc_id": f"doc-{i}-lab",
        "doc_type": "lab_report",
        "title": f"Lab Report — {given} {family}",
        "content": LAB_TEXTS[i % len(LAB_TEXTS)],
        "authored_date": "2024-01-15",
        "author": f"Dr. {LAST_NAMES[(i + 1) % len(LAST_NAMES)]}",
        "encounter_id": f"enc-{i}-0",
    })
    # Every even patient also gets an imaging note
    if i % 2 == 0:
        docs.append({
            "doc_id": f"doc-{i}-img",
            "doc_type": "imaging_note",
            "title": f"Imaging Note — {given} {family}",
            "content": IMAGING_TEXTS[i % len(IMAGING_TEXTS)],
            "authored_date": "2024-02-10",
            "author": f"Dr. {LAST_NAMES[(i + 2) % len(LAST_NAMES)]}",
            "encounter_id": f"enc-{i}-1",
        })
    # Every third patient also gets a discharge summary
    if i % 3 == 0:
        docs.append({
            "doc_id": f"doc-{i}-dis",
            "doc_type": "discharge_summary",
            "title": f"Discharge Summary — {given} {family}",
            "content": DISCHARGE_TEXTS[i % len(DISCHARGE_TEXTS)],
            "authored_date": "2024-03-05",
            "author": f"Dr. {LAST_NAMES[(i + 3) % len(LAST_NAMES)]}",
            "encounter_id": f"enc-{i}-2",
        })
    # Every 4th patient gets a clinical note
    if i % 4 == 0:
        docs.append({
            "doc_id": f"doc-{i}-note",
            "doc_type": "clinical_note",
            "title": f"Clinical Note — {given} {family}",
            "content": CLINICAL_NOTES[i % len(CLINICAL_NOTES)],
            "authored_date": "2024-04-01",
            "author": f"Dr. {LAST_NAMES[(i + 4) % len(LAST_NAMES)]}",
            "encounter_id": f"enc-{i}-3",
        })

    return {
        "mrn": mrn,
        "given_name": given,
        "family_name": family,
        "date_of_birth": dob,
        "gender": gender,
        "phone": f"555-{random.randint(1000, 9999)}",
        "email": f"{given.lower()}.{family.lower()}@example.com",
        "address": f"{random.randint(1, 999)} Main St, Springfield",
        "documents": docs,
    }


def main():
    # --- JSON sample (10 patients, includes one intentional duplicate) ---
    patients = [make_patient(i) for i in range(10)]

    # Inject a duplicate (same MRN+DOB as patient 0, different formatting)
    dup = make_patient(0)
    dup["mrn"] = "MRN10000"   # canonical form of patient 0
    patients.append(dup)

    # Inject a patient with a missing DOB (edge-case test — minimal, one doc)
    missing_dob = {
        "mrn": "MRN10099",
        "given_name": "Test",
        "family_name": "NoDob",
        "date_of_birth": "",          # intentionally blank
        "gender": "unknown",
        "documents": [
            {
                "doc_id": "doc-99-0",
                "doc_type": "clinical_note",
                "title": "Clinical Note — Test NoDob",
                "content": "Patient record with missing date of birth. Ingestion edge-case test.",
                "authored_date": "2024-01-01",
                "author": "Dr. Test",
            }
        ],
    }
    patients.append(missing_dob)

    json_path = OUT / "sample_patients.json"
    json_path.write_text(json.dumps(patients, indent=2))
    print(f"Wrote {len(patients)} patients → {json_path}")

    # --- CSV sample (lab rows, some with messy column names) ---
    csv_lines = [
        "patient_id,first_name,last_name,dob,sex,document_type,date,content,doctor",
        f"MRN10000,Alice,Smith,1985-03-14,F,lab_report,2024-01-15,{LAB_TEXTS[0]},Dr. Jones",
        f"mrn-10001,Bob,Johnson,03/14/1985,male,imaging_note,15/01/2024,{IMAGING_TEXTS[0]},Dr. Williams",
        f"MRN10002,Carol,Williams,1990-11-02,,discharge_summary,2024-01-10,{DISCHARGE_TEXTS[0]},",
        # Missing content — should trigger a warning
        "MRN10003,David,Brown,02-Nov-1990,M,lab_report,2024-02-01,,Dr. Garcia",
        # Duplicate of MRN10000 lab row
        f"MRN10000,Alice,Smith,1985-03-14,F,lab_report,2024-01-15,{LAB_TEXTS[1]},Dr. Jones",
    ]
    csv_path = OUT / "sample_labs.csv"
    csv_path.write_text("\n".join(csv_lines))
    print(f"Wrote CSV sample → {csv_path}")

    # --- Plain-text note ---
    note = """MRN: MRN10004
Date: 2024-03-01
Author: Dr. Martinez

CLINICAL NOTE

Patient presents with a 3-day history of productive cough, fever 38.9°C, and right-sided
pleuritic chest pain. History of asthma. No recent travel.

Assessment: Community-acquired pneumonia, right lower lobe. 
Plan: Azithromycin 500mg day 1 then 250mg days 2-5. Follow-up in 5 days or sooner if worsening.
Encouraged smoking cessation.
"""
    txt_path = OUT / "sample_note.txt"
    txt_path.write_text(note)
    print(f"Wrote text note → {txt_path}")


if __name__ == "__main__":
    main()
