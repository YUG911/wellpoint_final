import pathlib

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    CityMaster, Clinic, ClinicHours, DayMaster, Patient, Role, StateMaster, User
)
from appointments.models import Appointment
from doctors.models import (
    Doctor, DoctorAvailability, DoctorClinic, DoctorSpecialization, Review,
    SpecializationMaster
)
from .recommendation import (
    clean_symptom_text, match_specialization, model_is_available,
    predict_specialization
)

MODEL_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / 'ml' / 'artifacts' / 'doctor_recommender.joblib'
)


class RecommendationInferenceTests(TestCase):
    def test_model_file_exists_and_loads(self):
        self.assertTrue(MODEL_PATH.exists(), 'Run python ml/train_model.py first.')
        self.assertTrue(model_is_available())

    def test_prediction_returns_a_specialization_and_timing(self):
        predicted, elapsed = predict_specialization('chest pain, palpitations, sweating')
        self.assertIsNotNone(predicted)
        self.assertGreaterEqual(elapsed, 0.0)

    def test_symptom_text_is_normalised(self):
        self.assertEqual(clean_symptom_text('  Chest   PAIN, Palpitations!! '), 'chest pain, palpitations')

    def test_empty_symptoms_do_not_predict(self):
        self.assertEqual(predict_specialization('   '), (None, 0.0))

    def test_predicted_label_maps_onto_existing_master_row(self):
        SpecializationMaster.objects.create(specialization_name='Cardiologist')
        self.assertIsNotNone(match_specialization('Cardiology'))

    def test_unknown_specialization_does_not_create_data(self):
        SpecializationMaster.objects.create(specialization_name='Cardiologist')
        before = SpecializationMaster.objects.count()
        self.assertIsNone(match_specialization('Nuclear Medicine'))
        self.assertEqual(SpecializationMaster.objects.count(), before)


class RecommendDoctorViewTests(TestCase):
    def setUp(self):
        roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor')}
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='City')
        patient_user = User.objects.create(full_name='Patient', email='p@rec.test', contact_number='9040000001', password_hash=make_password('Secret123!'), role=roles['Patient'])
        self.patient = Patient.objects.create(user=patient_user, date_of_birth='1990-01-01')
        doctor_user = User.objects.create(full_name='Doctor', email='d@rec.test', contact_number='9040000002', password_hash=make_password('Secret123!'), role=roles['Doctor'])
        self.doctor = Doctor.objects.create(user=doctor_user, doctor_name='Rec Doctor', new_patient_fee=500, old_patient_fee=300)
        spec = SpecializationMaster.objects.create(specialization_name='Dermatologist')
        DoctorSpecialization.objects.create(doctor=self.doctor, specialization=spec)

        clinic_user = User.objects.create(full_name='Clinic', email='c@rec.test', contact_number='9040000003', password_hash=make_password('Secret123!'), role=Role.objects.create(role_name='Clinic'))
        clinic = Clinic.objects.create(user=clinic_user, clinic_name='Clinic', address='Address', city=city, contact_number=9040000003)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=clinic)

        next_day = timezone.localdate()
        day, _ = DayMaster.objects.get_or_create(day_name=next_day.strftime('%A'))
        while next_day.strftime('%A') != 'Monday':
            next_day += timezone.timedelta(days=1)
        monday, _ = DayMaster.objects.get_or_create(day_name='Monday')
        DoctorAvailability.objects.create(doctor=self.doctor, clinic=clinic, day=monday, start_time='09:00', end_time='12:00')

        session = self.client.session
        session['user_id'] = patient_user.pk
        session.save()

    def test_recommendation_requires_patient_login(self):
        self.client.logout()
        session = self.client.session
        session.flush()
        self.assertRedirects(self.client.get(reverse('recommend_doctor')), reverse('login'))

    def test_recommendation_shows_specialization_and_matching_doctor(self):
        response = self.client.post(reverse('recommend_doctor'), {'symptoms': 'skin rash, itching, eczema'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dermatology')
        self.assertContains(response, 'Rec Doctor')

    def test_blank_symptoms_is_rejected(self):
        response = self.client.post(reverse('recommend_doctor'), {'symptoms': '  '})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Rec Doctor')

    def test_doctor_role_cannot_use_recommendation(self):
        self.client.logout()
        session = self.client.session
        session['user_id'] = self.doctor.user_id
        session.save()
        self.assertRedirects(self.client.get(reverse('recommend_doctor')), reverse('login'), fetch_redirect_response=False)

    def test_recommendation_does_not_create_appointments_or_choose_a_doctor_by_model(self):
        self.client.post(reverse('recommend_doctor'), {'symptoms': 'chest pain, palpitations, sweating'})
        self.assertEqual(Appointment.objects.count(), 0)
        self.assertEqual(Review.objects.count(), 0)