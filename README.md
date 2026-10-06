# WellPoint Clinic Appointment Booking System

A Django-based healthcare appointment booking platform for a college diploma project.

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/YUG911/wellpoint_final.git
cd wellpoint_final

# Virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (uses local SQLite)
python manage.py migrate

# Seed demo data (optional but recommended)
python manage.py seed_demo

# Start server
python manage.py runserver
# Open http://127.0.0.1:8000/
```

## 🌐 Live Deployment
**Production URL:** https://wellpoint-tau.vercel.app/

Deployed on Vercel with Aiven MySQL. Auto-deploys on push to `main`.

## 👥 Demo Accounts (after running `seed_demo`)

| Role | Email | Password |
|------|-------|----------|
| **Admin** | admin@demo.example.com | Admin@12345 |
| **Patient** | patient1@demo.example.com | Demo@12345 |
| **Doctor** | doctor_aarav_sharma@demo.example.com | Demo@12345 |
| **Clinic** | clinic_wellpoint_test_clinic@demo.example.com | Demo@12345 |
| **Clinic Staff** | (create via Clinic dashboard) | Demo@12345 |

> **Note:** Passwords are NOT stored in the repo. They are shown here only for local demo purposes.

## 🎬 Teacher Demo Script (Step-by-Step)

### 1. Register a Patient
1. Open http://127.0.0.1:8000/register/ (or https://wellpoint-tau.vercel.app/register/)
2. Fill: Name, Email, **Contact Number** (10 digits), Password, Role: "Patient"
3. Click Register → Fill Patient Details (DOB, Gender, Blood Group, Emergency Contact)
4. Auto-redirects to Login → Log in with email/password
5. **Patient Dashboard** shows: Upcoming appointments, prescriptions, reports

### 2. Search Doctors + Use My Location
1. Click "Find a Doctor" on homepage or go to `/doctors/`
2. **Search bar**: Type doctor name or specialization
3. **Filters**: Specialization checkboxes, Location checkboxes, Experience radio
4. **📍 Location button** (red pin):
   - Click → "Use Current Location" → Allow browser permission
   - System finds nearest clinic via Haversine distance
   - Location auto-fills → results filter to nearby doctors
   - Or click city chips (Ranip, Bopal, Satellite, etc.)
5. Click "View Profile" on any doctor card

### 3. Filter by Specialization
1. In sidebar filters, check "Cardiologist" or "Dermatologist"
2. Results update instantly (client-side, no reload)
3. Clear filters with "Clear All" button

### 4. Book an Appointment
1. On doctor card → "Book Appointment"
2. Select date, time slot, clinic
3. Confirm → Appointment created with **Pending** status
4. Go to "My Appointments" → see booking

### 5. Log in as Doctor
1. Logout → Login with `doctor_aarav_sharma@demo.example.com` / `Demo@12345`
2. **Doctor Dashboard**: Today's appointments, patient list, availability
3. Approve/reject pending appointments

### 6. Log in as Clinic / Clinic Staff
1. Login with clinic email (e.g., `clinic_wellpoint_test_clinic@demo.example.com`)
2. **Clinic Dashboard**: Manage hours, view clinic appointments, staff management
3. Add/edit clinic hours for each day

### 7. Admin View
1. Login with `admin@demo.example.com` / `Admin@12345`
2. **Admin Dashboard**: User management, verification logs, platform stats

### 8. Symptom Recommender (AI/ML)
1. As Patient → "Not sure? Describe your symptoms" button on `/doctors/`
2. Enter symptoms: "chest pain, palpitations, sweating"
3. System predicts specialization (e.g., "Cardiology") → shows matching doctors
4. Try: "skin rash, itching" → Dermatologist

## 🔧 Key Features
- **Multi-role auth**: Patient, Doctor, Clinic, Clinic Staff, Admin
- **Real-time search/filter** on `/doctors/` (no page reload)
- **Geolocation**: "Use Current Location" → Haversine distance to nearest clinic
- **Symptom recommender**: Decision Tree ML model (scikit-learn)
- **Appointment lifecycle**: Book → Pending → Confirmed/Cancelled → Completed
- **Prescriptions & Reports**: Upload/view per appointment
- **Reviews & Ratings**: Patient feedback on doctors

## 📁 Project Structure
```
wellpoint_final/
├── accounts/          # Auth, roles, registration, profiles
├── appointments/      # Booking, payments, reviews
├── clinic_booking/    # Django settings, wsgi, urls
├── doctors/           # Doctor profiles, search, ML recommender
├── records/           # Prescriptions, reports, patient records
├── ml/                # Training pipeline + model artifacts
│   ├── train_model.py
│   └── artifacts/doctor_recommender.joblib
├── static/
│   ├── css/           # style.css, doctors.css, form-pages.css
│   └── js/            # main.js (homepage), doctors.js (search page)
├── templates/         # All HTML templates
├── vercel.json        # Vercel serverless config
├── requirements.txt   # Python deps
├── seed_demo.py       # Management command for demo data
└── PROJECT_AUDIT.md   # Full technical audit
```

## 🛠️ Development Commands
```bash
# System check
python manage.py check

# Run tests (use --keepdb for existing SQLite)
python manage.py test accounts.tests --keepdb

# Seed demo data (idempotent)
python manage.py seed_demo

# Create superuser (if needed)
python manage.py createsuperuser
```

## ⚠️ Known Limitations
- **ML integration partial**: Only 3/10 specializations exist in DB; 7 model predictions return "No doctor found"
- **Vercel media uploads fail**: Disk is read-only; use cloud storage for production
- **Bundle size**: numpy+pandas+scipy+sklearn near Vercel 250 MB limit
- **Test DB migration bug**: Fresh test DB fails (historical migration ordering)

## 📄 Documentation
- **PROJECT_AUDIT.md** — Complete technical audit (architecture, flows, DB, errors fixed, remaining issues)
- **Clinic_Booking_Data_Dictionary_Final.pdf** — Data dictionary (needs "phone" → "contact_number" update)

## 🔐 Environment Variables (Production)
Set these in Vercel dashboard → Settings → Environment Variables:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`
- `DJANGO_SECRET_KEY` (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DJANGO_DEBUG` = "False"

## 📝 License
College diploma project — educational use only.