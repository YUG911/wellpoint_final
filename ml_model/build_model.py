
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.pipeline import Pipeline
import joblib
import os

data = [
    ('Fever, Headache, Chills', 'General Medicine'),
    ('Severe headache, nausea, sensitivity to light', 'Neurology'),
    ('Fever, Cough, Weakness, Sore throat', 'General Medicine'),
    ('Chest pain, shortness of breath', 'Cardiology'),
    ('Acne, skin rash, itching', 'Dermatology'),
    ('Stomach ache, diarrhea, vomiting', 'General Medicine'),
    ('Anxiety, depression, insomnia, mood swings', 'Psychiatry'),
    ('Joint pain, back pain, muscle stiffness', 'Orthopedics'),
    ('Blurry vision, eye pain, redness', 'Ophthalmology'),
    ('Ear ache, hearing loss, ringing in ears', 'ENT'),
    ('Irregular periods, severe cramps', 'Gynecology'),
    ('Child has fever, coughing, crying', 'Pediatrics'),
    ('High blood pressure, palpitations', 'Cardiology'),
    ('Mole changing color, sunburn', 'Dermatology'),
    ('Feeling sad, loss of interest', 'Psychiatry'),
    ('Frequent urination, excessive thirst', 'General Medicine'),
    ('Seizures, tremors', 'Neurology'),
    ('Fracture, broken bone, sprain', 'Orthopedics'),
    ('Sore throat, runny nose, sneezing', 'General Medicine'),
    ('Difficulty breathing, wheezing', 'General Medicine'),
    ('Severe stomach pain', 'General Medicine'),
    ('Fever, headache', 'General Medicine'), 
] * 10  # duplicate to give more data for split

df = pd.DataFrame(data, columns=['symptoms', 'specialization'])
os.makedirs('ml_model', exist_ok=True)
df.to_csv('ml_model/dataset.csv', index=False)

X = df['symptoms']
y = df['specialization']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

pipeline = Pipeline([
    ('tfidf', TfidfVectorizer(stop_words='english')),
    ('clf', RandomForestClassifier(n_estimators=100, random_state=42))
])

pipeline.fit(X_train, y_train)
y_pred = pipeline.predict(X_test)

acc = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

with open('ml_model/metrics.txt', 'w') as f:
    f.write(f'Accuracy: {acc:.2f}\nPrecision: {precision:.2f}\nRecall: {recall:.2f}\nF1-Score: {f1:.2f}\n')

joblib.dump(pipeline, 'ml_model/symptom_model.joblib')
print('Model saved.')
