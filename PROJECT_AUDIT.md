# WellPoint Clinic Appointment Booking System — Project Audit

## 1. Project Purpose
WellPoint is a Django-based clinic appointment booking system for a college diploma project. It allows Patients to search doctors, book appointments, and manage health records; Doctors to manage schedules and appointments; Clinics to manage hours and staff; and Admins to oversee the platform.

## 2. Technology Stack
| Layer | Technology |
|-------|------------|
| Backend | Python 3.13, Django 6.1 |
| Database | MySQL 8.4 (Aiven) in production; SQLite locally |
| Frontend | HTML, CSS (Bootstrap 5), Vanilla JS |
| ML | scikit-learn 1.9, joblib, numpy, pandas (Decision Tree) |
| Deployment | Vercel (serverless), GitHub Actions auto-deploy |
| Auth | Custom session-based auth (no django.contrib.auth) |

## 3. Django Apps
| App | Purpose |
|-----|---------|
| `accounts` | User auth, roles (Patient/Doctor/Clinic/Staff/Admin), profiles, registration |
| `doctors` | Doctor profiles, specializations, qualifications, availability, recommendations |
| `appointments` | Booking, rescheduling, cancellation, payments, reviews |
| `records` | Prescriptions, reports, patient records |
| `ml` | Training pipeline for symptom→specialization model |

## 4. Important Files
| File | Description |
|------|-------------|
| `clinic_booking/settings.py` | All settings (env vars, DB, static, security) |
| `clinic_booking/wsgi.py` | Vercel entry point |
| `vercel.json` | Vercel function config |
| `requirements.txt` | Python dependencies |
| `accounts/forms.py` | RegisterForm, profile forms |
| `accounts/views.py` | Auth, registration flows, dashboards |
| `doctors/recommendation.py` | ML model loading + prediction |
| `doctors/views.py` | Doctor search, listing, booking, recommendation |
| `static/js/doctors.js` | Client-side filters + geolocation |
| `static/js/main.js` | Homepage geolocation + mobile menu |
| `ml/train_model.py` | Model training script |
| `ml/artifacts/doctor_recommender.joblib` | Trained model (committed) |
| `accounts/management/commands/seed_demo.py` | Demo data seeder |

## 5. User Roles
| Role | Description |
|------|-------------|
| Patient | Books appointments, views records, uses symptom recommender |
| Doctor | Manages schedule, views appointments, sees patients |
| Clinic | Manages hours, staff, clinic profile |
| Clinic Staff | Assists clinic (limited dashboard) |
| Admin | Full platform oversight, user management |

## 6. Main Workflows

### Registration Flow
```
GET /register/ → RegisterForm (contact_number, email, password, role)
    ↓
POST → views.register() → User created with contact_number
    ↓
Redirect to role-specific step:
    Patient → /register/patient/ (DOB, gender, blood group, emergency contact)
    Doctor  → /register/doctor/  (specialization, qualification, experience, fees)
    Clinic  → /register/clinic/  (clinic name, address, city, coordinates)
    Staff   → /register/staff/   (select clinic)
    ↓
Profile created → Redirect to /login/
```

### Login Flow
```
GET /login/ → form
POST → views.login_view() → session created → redirect to role dashboard
```

### Appointment Flow
```
Patient: /doctors/ → filter/search → click doctor → /book/<doctor_id>/
    ↓
Select date/time/clinic → confirm → Appointment created (status=Pending)
    ↓
Doctor/Clinic: approve/reject → status=Confirmed/Cancelled
    ↓
Patient: view in /my-appointments/, cancel/reschedule if needed
```

### Location + Nearest Clinic Flow
```
Homepage or /doctors/ → click red pin button
    ↓
Popup: "Use Current Location" OR manual chips/entry
    ↓
navigator.geolocation.getCurrentPosition()
    ↓
Haversine distance from user → each clinic (from clinic_locations JSON)
    ↓
Nearest clinic city name filled into location input
    ↓
Form submits to /doctors/?location=<city> → filtered results
```

### AI/ML Flow (Symptom Recommender)
```
GET /recommend/ → textarea for symptoms
    ↓
POST → doctors.views.recommend_doctor()
    ↓
doctors.recommendation.predict_specialization(symptoms)
    ↓
joblib.load('ml/artifacts/doctor_recommender.joblib')
    ↓
clean_symptom_text() → vectorizer.transform() → model.predict()
    ↓
Returns (predicted_specialization, inference_time)
    ↓
match_specialization() → SpecializationMaster exact/normalised match
    ↓
If matched: Doctor.objects.filter(specialization=matched) → ranked
    ↓
Render /recommend/ with results
```

## 7. Database Overview
Key tables (Django models):
- `users` — core auth (contact_number PK, role FK)
- `clinics` — clinic profiles, lat/lng (decimal), city FK
- `doctors` — profiles, experience, fees, about
- `doctor_specialization` — M2M doctor↔specialization
- `doctor_qualification` — M2M doctor↔qualification
- `doctor_clinic` — M2M doctor↔clinic
- `doctor_availability` — day, start_time, end_time per clinic
- `appointments` — patient, doctor, clinic, date, time, status, fee
- `payments` — appointment, amount, status, transaction_id
- `patient_records` — patient, doctor, diagnosis, notes
- `prescriptions` — record, medicines, dosage, instructions
- `reports` — record, file, report_type
- `reviews` — patient, doctor, rating, comment
- `specializations`, `qualifications`, `states`, `cities`, `days` — reference

## 8. Important Models
| Model | Key Fields |
|-------|------------|
| `User` | contact_number (PK, CharField 10), email, full_name, password_hash, role, is_verified, account_status |
| `Clinic` | user (OneToOne), clinic_name, address, city, contact_number, latitude, longitude |
| `Doctor` | user (OneToOne), doctor_name, experience, new_patient_fee, old_patient_fee, about |
| `Appointment` | patient, doctor, clinic, appointment_date, start_time, end_time, status, fee_charged |
| `SpecializationMaster` | specialization_name |
| `QualificationMaster` | qualification_name |

## 9. Registration Flow (Detailed)
See Section 6 — Registration Flow. All 4 roles supported end-to-end. Form field is `contact_number` (CharField, 10 digits), validated for uniqueness and format.

## 10. Login Flow (Detailed)
See Section 6 — Login Flow. Custom session auth (no django.contrib.auth). Passwords hashed with PBKDF2 via `make_password`/`check_password`.

## 11. Appointment Flow (Detailed)
See Section 6 — Appointment Flow. Statuses: `Pending`, `Confirmed`, `Cancelled`, `Completed`. Payment integration via `appointments.Payment`.

## 12. Algorithm/ML Flow
See Section 6 — AI/ML Flow.
- **Model**: DecisionTreeClassifier (scikit-learn), 10 classes, 134 features
- **Training**: `ml/train_model.py` on synthetic dataset (600 samples)
- **Integration**: `doctors.recommendation.predict_specialization()` + `match_specialization()`
- **Status**: **Partially integrated** — model predicts 10 classes but only 3 exist in DB (General Physician, Cardiologist, Dermatologist). 7 predictions return "No doctor found".

## 13. Deployment Flow
```
Git push to main (GitHub)
    ↓
Vercel auto-deploy triggered
    ↓
Vercel installs requirements.txt (Django, PyMySQL, sklearn, numpy, pandas, scipy, joblib)
    ↓
Build: python manage.py collectstatic (if configured)
    ↓
Deploy: clinic_booking/wsgi.py as serverless function
    ↓
Runtime: reads MYSQL_* env vars → connects to Aiven MySQL via PyMySQL + TLS
```

## 14. Environment Variables (Names Only)
| Variable | Purpose |
|----------|---------|
| `MYSQL_HOST` | Aiven MySQL host |
| `MYSQL_PORT` | Aiven MySQL port (usually 3306) |
| `MYSQL_DATABASE` | Database name |
| `MYSQL_USER` | Database user |
| `MYSQL_PASSWORD` | Database password |
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | "True"/"False" (default False on Vercel) |
| `VERCEL` | Set by Vercel automatically (used for DEBUG default) |

## 15. How to Run Locally
```bash
# 1. Clone repo
git clone https://github.com/YUG911/wellpoint_final.git
cd wellpoint_final

# 2. Create venv (optional but recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. Run migrations (uses local SQLite by default)
python manage.py migrate

# 5. (Optional) Seed demo data
python manage.py seed_demo

# 6. Run server
python manage.py runserver
# Open http://127.0.0.1:8000/
```

## 16. How to Test Locally
```bash
# Run Django system check
python manage.py check

# Run tests (uses existing SQLite; fresh test DB fails due to migration ordering)
python manage.py test accounts.tests accounts.test_authorization --keepdb

# Manual smoke test:
# 1. Open http://127.0.0.1:8000/
# 2. Click "Find a Doctor" → /doctors/
# 3. Test search, filters, location button (geolocation)
# 4. Register Patient: /register/ → fill form → /register/patient/ → login
# 5. Book appointment: /doctors/ → click doctor → /book/<id>/
# 6. Login as doctor/clinic/admin → verify dashboards
```

## 17. How to View Vercel Logs
1. Go to Vercel dashboard → Project `wellpoint` → Deployments
2. Click latest deployment → **Build Logs** or **Runtime Logs**
3. For runtime errors: check **Functions** tab → `wsgi.py` logs

## 18. How to Check a Deployment
1. Visit `https://wellpoint-tau.vercel.app/`
2. Verify: Homepage loads, no 500 errors
3. Test `/register/` → form submits without 500
4. Test `/doctors/` → search, filters, location button
5. Test `/recommend/` → symptom input → results
6. Check browser console (F12) for JS errors

## 19. Known Limitations
| Limitation | Details |
|------------|---------|
| **ML integration incomplete** | 7/10 model specializations have no DB match; many predictions default to Psychiatry |
| **Vercel bundle size** | numpy+pandas+scipy+sklearn ≈ 150-200 MB; near 250 MB limit |
| **Media uploads on Vercel** | Disk is read-only; prescriptions/reports upload will fail in production |
| **Test DB migration bug** | Migration 0004 alters `contact_number` before 0005 renames `phone`→`contact_number`; fresh test DB fails |
| **Static files on Vercel** | No whitenoise; collectstatic not in build; CSS/JS served from Vercel CDN (works for now) |
| **Admin password in data.json** | Plain text "Admin@123" — not a valid Django hash |

## 20. Errors Fixed (This Audit)
| Error | Root Cause | Fix |
|-------|------------|-----|
| Registration 500: `FieldError: Cannot resolve keyword 'phone'` | Model field renamed to `contact_number` but code still used `phone` | Updated forms, views, templates, tests to use `contact_number` |
| Form field type mismatch | `IntegerField` for contact number drops leading zeros | Changed to `CharField(max_length=10)` everywhere |
| Homepage location button did nothing | No geolocation JS on homepage | Added full geolocation popup + Haversine logic to `main.js` |
| Search bar cramped on /doctors/ | Flex layout didn't wrap, button wrapped, placeholders cut | Added `flex-wrap`, `min-width`, `flex-shrink:0`, responsive breakpoints |
| Unused files cluttering repo | `verify_tables.py`, `test_e2e_audit.py`, `dictionary.txt` | Deleted (verified no references) |

## 21. Remaining Issues
| Issue | Severity | Recommended Action |
|-------|----------|-------------------|
| 7 ML specializations missing from DB | HIGH | Add SpecializationMaster entries for ENT, Gastro, Neuro, Ophtho, Ortho, Psych, Uro |
| ML model misclassifies common symptoms as Psychiatry | HIGH | Retrain with better dataset or add rule-based fallback |
| Vercel bundle size risk | MEDIUM | Remove pandas/scipy from requirements if not used at runtime (only joblib+sklearn needed) |
| Media uploads fail on Vercel | MEDIUM | Use cloud storage (S3/Cloudinary) or document as known limitation |
| Test DB migration ordering bug | LOW | Don't fix migrations (historical); use `--keepdb` for tests |
| Data dictionary still says "phone" | LOW | Update `Clinic_Booking_Data_Dictionary_Final.pdf` to say `contact_number` |
| Admin password in data.json is plain text | LOW | Regenerate data.json with hashed password |

---
*Generated: 2026-10-06*