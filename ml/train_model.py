"""
WellPoint symptom -> specialization model training.

Runs the full pipeline: load dataset, validate, clean, split, train a
Decision Tree Classifier, evaluate it, save it, and measure real training
and inference times.

Run from the project root:

    python ml/train_model.py

Outputs:
    ml/artifacts/doctor_recommender.joblib   trained pipeline
    ml/artifacts/training_report.json        measured evaluation metrics
"""

import json
import pathlib
import re
import time

import joblib
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

BASE_DIR = pathlib.Path(__file__).resolve().parent
DATASET_FILE = BASE_DIR / "dataset" / "symptom_specialization_dataset.csv"
ARTIFACT_DIR = BASE_DIR / "artifacts"
MODEL_FILE = ARTIFACT_DIR / "doctor_recommender.joblib"
REPORT_FILE = ARTIFACT_DIR / "training_report.json"

REQUIRED_COLUMNS = ("symptoms", "specialization")
TEST_SIZE = 0.2
RANDOM_STATE = 42
MAX_TREE_DEPTH = 16
MIN_SAMPLES_LEAF = 2


def print_header(title):
    print()
    print("=" * 40)
    print(title)
    print("=" * 40)


def load_dataset():
    if not DATASET_FILE.exists():
        raise SystemExit(
            f"Dataset not found at {DATASET_FILE}. Run 'python ml/build_dataset.py' first."
        )
    frame = pd.read_csv(DATASET_FILE, comment="#")
    return frame


def validate_dataset(frame):
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise SystemExit(f"Dataset is missing required column(s): {missing}")

    before = len(frame)
    frame = frame.dropna(subset=list(REQUIRED_COLUMNS))
    frame = frame.drop_duplicates(subset=["symptoms"])
    dropped = before - len(frame)

    frame["symptoms"] = frame["symptoms"].astype(str).str.lower()
    frame["specialization"] = frame["specialization"].astype(str).str.strip()
    frame = frame[frame["symptoms"].str.strip() != ""]
    frame = frame[frame["specialization"] != ""]

    if len(frame) < REQUIRED_ROWS:
        raise SystemExit(f"Only {len(frame)} usable rows found; at least {REQUIRED_ROWS} are required.")
    return frame, dropped


REQUIRED_ROWS = 100


def clean_symptom_text(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s,]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def main():
    total_start = time.perf_counter()

    print_header("WELLPOINT ML TRAINING")

    frame = load_dataset()

    frame, dropped = validate_dataset(frame)
    frame["symptoms"] = frame["symptoms"].map(clean_symptom_text)

    features = frame["symptoms"]
    target = frame["specialization"]
    classes = sorted(target.unique())

    print()
    print("Dataset:")
    print(f"File: {DATASET_FILE}")
    print("NOTE: educational synthetic teaching dataset, not real patient data")
    print(f"Number of samples: {len(frame)}")
    print(f"Rows dropped during cleaning: {dropped}")
    print(f"Number of classes: {len(classes)}")
    print(f"Prediction classes: {', '.join(classes)}")
    print()

    X_train, X_test, y_train, y_test = train_test_split(
        features, target, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=target
    )

    print()
    print("Algorithm:")
    print("Decision Tree Classifier")
    print(f"Max depth: {MAX_TREE_DEPTH}")
    print()
    print(f"Training samples: {len(X_train)}")
    print(f"Testing samples: {len(X_test)}")
    print()

    print("Preprocessing:")
    print("Lowercasing, punctuation cleanup, whitespace normalization")
    print("Bag of symptoms via CountVectorizer (binary presence)")

    vectorizer = CountVectorizer(binary=True, token_pattern=r"[a-z0-9]+")

    print("Training started...")
    fit_start = time.perf_counter()
    X_train_matrix = vectorizer.fit_transform(X_train)
    model = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_STATE,
    )
    model.fit(X_train_matrix, y_train)
    training_time = time.perf_counter() - fit_start
    print("Training completed.")
    print()
    print(f"Number of features after vectorization: {len(vectorizer.vocabulary_)}")
    print()

    print_header("EVALUATION")
    print(f"Training time: {training_time:.4f} seconds")
    print()

    X_test_matrix = vectorizer.transform(X_test)
    predictions = model.predict(X_test_matrix)
    accuracy = accuracy_score(y_test, predictions)

    print()
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print()
    print("Precision / Recall / F1-score (per specialization, weighted average):")
    report = classification_report(y_test, predictions, zero_division=0)
    print(report)
    print("Confusion matrix (rows = actual, columns = predicted):")
    print(confusion_matrix(y_test, predictions, labels=classes))
    print()

    precision = float(_report_metric(report, "weighted avg", "precision"))
    recall = float(_report_metric(report, "weighted avg", "recall"))
    f1 = float(_report_metric(report, "weighted avg", "f1-score"))

    inference_start = time.perf_counter()
    _ = model.predict(vectorizer.transform(["fever, cough, weakness"]))
    inference_time = time.perf_counter() - inference_start

    print_header("PREDICTION")
    print("Prediction:", model.predict(vectorizer.transform(["chest pain, palpitations, sweating"]))[0])
    print("Prediction:", model.predict(vectorizer.transform(["skin rash, itching, eczema"]))[0])
    print()
    print(f"Inference time: {inference_time:.4f} seconds")
    print()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"vectorizer": vectorizer, "model": model}, MODEL_FILE)

    total_time = time.perf_counter() - total_start

    print(f"Model saved to: {MODEL_FILE}")
    print()
    print(f"Total training time: {total_time:.4f} seconds")
    print()

    REPORT_FILE.write_text(
        json.dumps(
            {
                "dataset_file": str(DATASET_FILE.relative_to(BASE_DIR.parent)),
                "dataset_type": "educational synthetic teaching dataset (not real patient data)",
                "algorithm": "RandomForestClassifier",
                "n_estimators": 100,
                "test_size": TEST_SIZE,
                "random_state": RANDOM_STATE,
                "number_of_samples": len(frame),
                "training_samples": len(X_train),
                "testing_samples": len(X_test),
                "number_of_classes": len(classes),
                "classes": classes,
                "number_of_features": int(len(vectorizer.vocabulary_)),
                "accuracy": round(accuracy, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "training_time_seconds": round(training_time, 4),
                "inference_time_seconds": round(inference_time, 6),
                "total_time_seconds": round(total_time, 4),
                "model_file": str(MODEL_FILE.relative_to(BASE_DIR.parent)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Training report saved to: {REPORT_FILE}")


def _report_metric(report, average, metric):
    index = {"precision": 0, "recall": 1, "f1-score": 2}[metric]
    for line in report.splitlines():
        parts = line.split()
        if len(parts) > 2 and parts[:2] == average.split():
            return parts[2 + index]
    return 0.0


if __name__ == "__main__":
    main()