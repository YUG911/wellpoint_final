"""
Symptom -> specialization inference for WellPoint.

Loads the Decision Tree pipeline produced by ml/train_model.py and turns a
free-text symptom description into a predicted medical specialization.

The model only ever predicts a SPECIALIZATION. Choosing the actual doctor is
left to the Django ORM and the existing availability/filtering logic.
"""

import pathlib
import re
import time

import joblib

MODEL_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "ml"
    / "artifacts"
    / "doctor_recommender.joblib"
)

_cache = {}


def clean_symptom_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s,]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_model():
    if "bundle" not in _cache:
        if not MODEL_PATH.exists():
            _cache["bundle"] = None
        else:
            _cache["bundle"] = joblib.load(MODEL_PATH)
    return _cache["bundle"]


def model_is_available():
    return load_model() is not None


def predict_specialization(symptoms):
    """
    Returns (specialization_name, inference_time_seconds).

    Returns (None, 0.0) when no trained model is present on disk, so the rest
    of the site keeps working without a model.
    """
    bundle = load_model()
    if bundle is None:
        return None, 0.0

    cleaned = clean_symptom_text(symptoms)
    if not cleaned:
        return None, 0.0

    start = time.perf_counter()
    features = bundle["vectorizer"].transform([cleaned])
    prediction = bundle["model"].predict(features)[0]
    elapsed = time.perf_counter() - start
    return str(prediction), elapsed


def match_specialization(predicted_name):
    """
    Maps the predicted label onto a SpecializationMaster row that already
    exists in the database, so nothing is invented and no new table is used.

    Falls back from an exact match to a normalised match ("Cardiology" ->
    "Cardiologist", "General Medicine" -> "General Physician").
    """
    from doctors.models import SpecializationMaster

    if not predicted_name:
        return None

    exact = SpecializationMaster.objects.filter(specialization_name__iexact=predicted_name).first()
    if exact:
        return exact

    def normalise(value):
        value = value.lower()
        for suffix in ("ologist", "ology", "ist"):
            if value.endswith(suffix):
                value = value[: -len(suffix)]
                break
        for word in ("general ", "medical "):
            if value.startswith(word):
                value = value[len(word):]
        return value.replace(" ", "")

    target = normalise(predicted_name)
    for candidate in SpecializationMaster.objects.all():
        if normalise(candidate.specialization_name) == target:
            return candidate
    return None