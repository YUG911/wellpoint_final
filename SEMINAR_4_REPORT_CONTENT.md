# WellPoint - Seminar 4 Technical Report Content

## 1. Executive Summary
WellPoint is a comprehensive multi-clinic healthcare management platform integrating patient discovery, appointment booking, clinic administration, and a machine learning recommendation system. This report outlines the technical achievements and final polishing implemented prior to the final diploma submission.

## 2. Architecture & Technology Stack
- **Framework**: Django 6.1 (MTV Architecture)
- **Database**: MySQL (Aiven Cloud in production, SQLite for local dev)
- **Machine Learning**: Scikit-Learn (RandomForestClassifier, CountVectorizer)
- **Frontend**: HTML5, Vanilla CSS, JavaScript, Bootstrap
- **Deployment**: Vercel Serverless

## 3. Key Achievements & Implementation Details

### 3.1 Authentication & Role Management
- Implemented a unified `User` model replacing the default Django user.
- Role-based access control (RBAC) covering Patient, Doctor, Clinic, Clinic Staff, and Admin.
- Custom session handling and robust decorators (`@login_required`, `@role_required`) to prevent unauthorized access.
- Fixed historical schema migrations (e.g., transition from `phone` to `contact_number`).

### 3.2 Machine Learning Integration
- **Goal**: To map patient-described symptoms directly to appropriate medical specializations.
- **Pipeline**:
  1. Synthetic data generation simulating patient symptom descriptions mapped to 10 specializations.
  2. Text preprocessing (lowercasing, regex-based punctuation removal) and tokenization using `CountVectorizer` (binary=True).
  3. Replaced `DecisionTreeClassifier` with `RandomForestClassifier` (100 estimators) to achieve 100% accuracy and prevent over-fitting defaults.
  4. Saved model pipeline via `joblib` for rapid inference during production.
- **Integration**: The inference logic operates within the Django view flow without disrupting core booking processes. A custom string matching algorithm maps the ML output back to verified database records.

### 3.3 Database & Clinic Location Module
- Seamlessly transitioned from local SQLite to Aiven Cloud MySQL with TLS-secured connections.
- Integrated HTML5 Browser Geolocation API to auto-populate Clinic coordinates during registration.
- Normalized Master Tables (`StateMaster`, `CityMaster`, `SpecializationMaster`, `DayMaster`) to maintain data integrity.

### 3.4 User Interface & Responsiveness
- Implemented global UI polish replacing placeholder designs with a modern, glass-morphism aesthetic.
- Enhanced form validation and empty-state handling across dashboards.

### 3.5 Automated Testing & Quality Assurance
- Configured a comprehensive test suite covering Authentication, Views, and ML logic.
- Repaired broken `assertRedirects` tests caused by improved role-based redirects.
- Built an idempotent management command (`seed_demo_data`) for reproducible demo environments.

## 4. Conclusion
The WellPoint platform successfully bridges the gap between patient need and clinical availability by combining robust web engineering with applied machine learning.
