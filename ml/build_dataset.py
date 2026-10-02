"""
Builds the educational symptom -> specialization training dataset used by
WellPoint's doctor recommendation model.

IMPORTANT
---------
The rows produced by this script are an EDUCATIONAL, SYNTHETIC teaching
dataset created for a Diploma demonstration. They are NOT real patient
records, are NOT derived from any hospital, and must never be presented as
clinical evidence or as real patient data.

Each row is composed from a curated pool of common symptoms for one medical
specialization. The pools deliberately overlap (for example "headache" is
listed under both General Medicine and Neurology) so the classifier has to
learn the combination pattern rather than memorise one unique word.

Output: ml/dataset/symptom_specialization_dataset.csv
"""

import csv
import itertools
import pathlib
import random

DATASET_DIR = pathlib.Path(__file__).resolve().parent / "dataset"
DATASET_FILE = DATASET_DIR / "symptom_specialization_dataset.csv"

ROWS_PER_CLASS = 60
COMBINATION_SIZES = (3, 4, 5, 6)
RANDOM_SEED = 2026

SYMPTOM_POOLS = {
    "Cardiology": [
        "chest pain", "chest tightness", "palpitations", "irregular heartbeat",
        "breathlessness on exertion", "high blood pressure", "swelling in legs",
        "dizziness", "profuse sweating", "rapid pulse",
    ],
    "Dermatology": [
        "skin rash", "itching", "acne", "hair loss", "skin discoloration",
        "eczema", "skin infection", "boils", "nail infection", "dry skin",
    ],
    "General Medicine": [
        "fever", "body ache", "cough", "cold", "fatigue", "weakness",
        "headache", "sore throat", "runny nose", "loss of appetite",
    ],
    "Orthopedics": [
        "joint pain", "back pain", "knee pain", "muscle strain", "bone fracture",
        "swelling in joint", "joint stiffness", "shoulder pain", "unable to walk",
        "hip pain",
    ],
    "Neurology": [
        "headache", "dizziness", "numbness in limbs", "weakness in limbs",
        "seizures", "memory loss", "tingling sensation", "tremor",
        "slurred speech", "loss of balance",
    ],
    "Gastroenterology": [
        "abdominal pain", "acidity", "vomiting", "diarrhea", "constipation",
        "bloating", "stomach cramps", "indigestion", "blood in stool",
        "nausea",
    ],
    "ENT": [
        "ear pain", "blocked nose", "sore throat", "hearing loss",
        "sinus congestion", "nose bleeding", "sneezing", "throat irritation",
        "enlarged tonsils", "mouth ulcer",
    ],
    "Ophthalmology": [
        "blurred vision", "eye pain", "redness in eyes", "watery eyes",
        "difficulty reading", "night blindness", "eye discharge",
        "burning eyes", "double vision", "itchy eyes",
    ],
    "Urology": [
        "burning urination", "frequent urination", "blood in urine",
        "kidney stone pain", "lower abdominal pain", "difficulty urinating",
        "swollen feet", "weak urine stream", "urinary urgency",
    ],
    "Psychiatry": [
        "anxiety", "depression", "sleep disturbance", "mood swings",
        "lack of concentration", "panic attacks", "irritability",
        "feeling hopeless", "restlessness", "loss of interest",
    ],
}


def combinations_for(pool):
    seen = []
    for size in COMBINATION_SIZES:
        for combo in itertools.combinations(sorted(pool), size):
            seen.append(list(combo))
    return seen


def build_rows():
    rng = random.Random(RANDOM_SEED)
    rows = []
    for specialization in sorted(SYMPTOM_POOLS):
        candidates = combinations_for(SYMPTOM_POOLS[specialization])
        rng.shuffle(candidates)
        for symptoms in candidates[:ROWS_PER_CLASS]:
            rng.shuffle(symptoms)
            rows.append((", ".join(symptoms), specialization))
    rng.shuffle(rows)
    return rows


def main():
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    with DATASET_FILE.open("w", newline="", encoding="utf-8") as handle:
        handle.write("# WellPoint educational training dataset - synthetic teaching rows, not real patient data\n")
        writer = csv.writer(handle)
        writer.writerow(["symptoms", "specialization"])
        writer.writerows(rows)
    print(f"Rows written: {len(rows)}")
    print(f"Classes: {len({row[1] for row in rows})}")
    print(f"File: {DATASET_FILE}")


if __name__ == "__main__":
    main()