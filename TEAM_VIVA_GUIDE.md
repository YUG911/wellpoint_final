# WellPoint - Team Viva / Defense Guide

This document prepares the team for common technical questions during the final project presentation.

## 1. Django Architecture & Core Design

**Q: Why did you choose Django for this project?**
A: Django provides a robust "batteries-included" framework. Its MTV (Model-Template-View) pattern allowed us to quickly separate business logic from the UI. The built-in ORM made it easy to structure our relational MySQL database without writing raw SQL.

**Q: Explain the MTV pattern as used in WellPoint.**
A: 
- **Model**: Defines the schema (e.g., `User`, `Clinic`, `Appointment`) in `models.py`.
- **Template**: The HTML files in the `templates/` folder that render the UI using Django's template language.
- **View**: The Python functions in `views.py` that process requests, query the Models, and return the Templates.

**Q: How did you implement authentication? Did you use Django's default User?**
A: We opted for a custom session-based authentication model to maintain complete control over the schema and roles. We used custom decorators (`@login_required` and `@role_required`) which verify the session ID and the user's role before allowing access to specific views (e.g., Doctor Dashboard).

## 2. Machine Learning Pipeline

**Q: What is the purpose of the ML pipeline in this project?**
A: To reduce friction for patients who know their symptoms but don't know which type of specialist to consult. The model takes a text description of symptoms and predicts a medical specialization (e.g., "Cardiology").

**Q: How is the text data processed before prediction?**
A: The text is converted to lowercase, stripped of punctuation using regex, and then vectorized using Scikit-Learn's `CountVectorizer(binary=True)`. This creates a "bag-of-words" representation indicating the presence or absence of specific symptoms.

**Q: Why did you choose RandomForestClassifier over simpler or more complex models?**
A: Initially, a single `DecisionTreeClassifier` was used, but it proved brittle (overfitting on specific keywords). `RandomForestClassifier` builds multiple decision trees and aggregates their results, providing much higher accuracy (100% on our synthetic dataset) and preventing weird edge-case failures. It is also lightweight enough to run synchronously in a Django view.

## 3. Database & Deployment

**Q: How did you handle database scaling and deployment?**
A: We use an Aiven Cloud MySQL instance for production. We configured Django to use secure TLS connections (`ssl` options) to communicate with Aiven. 

**Q: What is an idempotent script and why did you use one (`seed_demo_data`)?**
A: An idempotent script can be run multiple times without causing duplicate data or errors. We built `seed_demo_data` using `get_or_create` so that reviewers or new developers can instantly populate the database with realistic clinics and doctors without dropping existing production data.

## 4. UI & Frontend

**Q: How does the clinic location feature work?**
A: Instead of forcing clinics to manually type their latitude and longitude, we integrated the HTML5 Browser Geolocation API (`navigator.geolocation`). Upon clicking "Detect Location", the browser asks for permission and automatically populates the form coordinates via JavaScript.
