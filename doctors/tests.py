from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from accounts.models import CityMaster, Clinic, DayMaster, Role, StateMaster, User
from .models import Doctor, DoctorAvailability, DoctorClinic, DoctorSpecialization, SpecializationMaster


class DoctorWorkflowTests(TestCase):
    def setUp(self):
        self.doctor_role = Role.objects.create(role_name='Doctor')
        self.clinic_role = Role.objects.create(role_name='Clinic')
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='Mumbai')
        clinic_user = User.objects.create(full_name='Clinic', email='clinic@d.test', contact_number=9020000001, password_hash=make_password('Secret123!'), role=self.clinic_role)
        self.clinic = Clinic.objects.create(user=clinic_user, clinic_name='Care', address='Address', city=city, contact_number=9020000001)
        user = User.objects.create(full_name='Aarav', email='doctor@d.test', contact_number=9020000002, password_hash=make_password('Secret123!'), role=self.doctor_role)
        self.doctor = Doctor.objects.create(user=user, doctor_name='Aarav Sharma', experience=8, new_patient_fee=500, old_patient_fee=300)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=self.clinic)
        self.spec = SpecializationMaster.objects.create(specialization_name='Cardiology')
        DoctorSpecialization.objects.create(doctor=self.doctor, specialization=self.spec)
        self.day = DayMaster.objects.create(day_name='Monday')

    def login_doctor(self):
        session = self.client.session
        session['user_id'] = self.doctor.user_id
        session.save()

    def test_database_search_filters_by_name_specialization_and_location(self):
        for query in ({'search': 'Aarav'}, {'specialization': 'Cardiology'}, {'location': 'Mumbai'}):
            self.assertContains(self.client.get(reverse('doctor_list'), query), 'Aarav Sharma')
        self.assertNotContains(self.client.get(reverse('doctor_list'), {'search': 'Nobody'}), 'Aarav Sharma')

    def test_specialization_exact_matching_ent_does_not_match_dentist(self):
        ent_spec = SpecializationMaster.objects.create(specialization_name='ENT')
        dentist_spec = SpecializationMaster.objects.create(specialization_name='Dentist')

        ent_user = User.objects.create(
            full_name='Dr. ENT Specialist', email='ent@d.test', contact_number=9020000010,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        ent_doctor = Doctor.objects.create(
            user=ent_user, doctor_name='Dr. Ear Throat', experience=5, new_patient_fee=400, old_patient_fee=250
        )
        DoctorSpecialization.objects.create(doctor=ent_doctor, specialization=ent_spec)
        DoctorClinic.objects.create(doctor=ent_doctor, clinic=self.clinic)

        dentist_user = User.objects.create(
            full_name='Dr. Dental Care', email='dentist@d.test', contact_number=9020000011,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        dentist_doctor = Doctor.objects.create(
            user=dentist_user, doctor_name='Dr. Tooth Smile', experience=6, new_patient_fee=450, old_patient_fee=300
        )
        DoctorSpecialization.objects.create(doctor=dentist_doctor, specialization=dentist_spec)
        DoctorClinic.objects.create(doctor=dentist_doctor, clinic=self.clinic)

        # 1. ENT query matches ENT doctor, not Dentist or Cardiology
        response_ent = self.client.get(reverse('doctor_list'), {'specialization': 'ENT'})
        self.assertContains(response_ent, 'Dr. Ear Throat')
        self.assertNotContains(response_ent, 'Dr. Tooth Smile')
        self.assertNotContains(response_ent, 'Aarav Sharma')

        # 2. Whitespace and case-insensitive normalization: '  ent  '
        response_ent_norm = self.client.get(reverse('doctor_list'), {'specialization': '  ent  '})
        self.assertContains(response_ent_norm, 'Dr. Ear Throat')
        self.assertNotContains(response_ent_norm, 'Dr. Tooth Smile')

        # 3. Dentist query matches Dentist doctor, not ENT
        response_dentist = self.client.get(reverse('doctor_list'), {'specialization': 'Dentist'})
        self.assertContains(response_dentist, 'Dr. Tooth Smile')
        self.assertNotContains(response_dentist, 'Dr. Ear Throat')

        # 4. Other exact match (Cardiology) still works
        response_cardio = self.client.get(reverse('doctor_list'), {'specialization': 'Cardiology'})
        self.assertContains(response_cardio, 'Aarav Sharma')
        self.assertNotContains(response_cardio, 'Dr. Ear Throat')
        self.assertNotContains(response_cardio, 'Dr. Tooth Smile')

        # 5. Symptom query that predicts ENT does not match Dentist doctor
        response_symptoms = self.client.get(reverse('doctor_list'), {'symptoms': 'Ear ache, hearing loss, ringing in ears'})
        self.assertContains(response_symptoms, 'Dr. Ear Throat')
        self.assertNotContains(response_symptoms, 'Dr. Tooth Smile')

    def test_doctor_profile_and_availability_require_doctor_role(self):
        self.assertRedirects(self.client.get(reverse('doctor_profile')), reverse('login'))
        self.login_doctor()
        self.assertContains(self.client.get(reverse('doctor_profile')), 'Aarav Sharma')
        response = self.client.post(reverse('doctor_availability'), {f'start_{self.day.pk}': '09:00', f'end_{self.day.pk}': '12:00', f'clinics_{self.day.pk}': self.clinic.pk})
        self.assertRedirects(response, reverse('doctor_availability'))
        self.assertTrue(DoctorAvailability.objects.filter(doctor=self.doctor, clinic=self.clinic).exists())

    def test_invalid_availability_does_not_replace_existing_slots(self):
        existing = DoctorAvailability.objects.create(doctor=self.doctor, clinic=self.clinic, day=self.day, start_time='09:00', end_time='10:00')
        self.login_doctor()
        self.client.post(reverse('doctor_availability'), {f'start_{self.day.pk}': '12:00', f'end_{self.day.pk}': '09:00', f'clinics_{self.day.pk}': self.clinic.pk})
        self.assertTrue(DoctorAvailability.objects.filter(pk=existing.pk).exists())

    def test_adding_availability_preserves_unrelated_existing_slots(self):
        existing = DoctorAvailability.objects.create(doctor=self.doctor, clinic=self.clinic, day=self.day, start_time='09:00', end_time='10:00')
        self.login_doctor()
        self.client.post(reverse('doctor_availability'), {f'start_{self.day.pk}': '14:00', f'end_{self.day.pk}': '15:00', f'clinics_{self.day.pk}': self.clinic.pk})
        self.assertTrue(DoctorAvailability.objects.filter(pk=existing.pk).exists())
        self.assertTrue(DoctorAvailability.objects.filter(doctor=self.doctor, start_time='14:00', end_time='15:00').exists())

    def test_geolocation_orders_doctors_by_proximity(self):
        # Set clinic coordinates for Mumbai (self.clinic)
        self.clinic.latitude = 19.0760
        self.clinic.longitude = 72.8777
        self.clinic.save()

        # Create a second clinic in Pune (~120km away) and doctor
        pune_city = CityMaster.objects.create(state=self.clinic.city.state, city_name='Pune')
        pune_user = User.objects.create(
            full_name='Pune Clinic', email='pune_clinic@d.test', contact_number=9020000088,
            password_hash=make_password('Secret123!'), role=self.clinic_role
        )
        pune_clinic = Clinic.objects.create(
            user=pune_user, clinic_name='Pune Health Center', address='Pune Camp',
            city=pune_city, contact_number=9020000088, latitude=18.5204, longitude=73.8567
        )
        pune_doc_user = User.objects.create(
            full_name='Dr. Pune Doctor', email='pune_doc@d.test', contact_number=9020000089,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        pune_doctor = Doctor.objects.create(
            user=pune_doc_user, doctor_name='Dr. Pune Cardiologist', experience=10,
            new_patient_fee=600, old_patient_fee=400
        )
        DoctorClinic.objects.create(doctor=pune_doctor, clinic=pune_clinic)
        DoctorSpecialization.objects.create(doctor=pune_doctor, specialization=self.spec)

        # Patient searches from near Mumbai (19.0770, 72.8780)
        res = self.client.get(reverse('doctor_list'), {
            'user_lat': '19.0770',
            'user_lng': '72.8780',
            'location': 'Current Location'
        })
        self.assertEqual(res.status_code, 200)
        doctors_in_context = list(res.context['doctors'])

        # Doctor in Mumbai should be first (closest, < 1 km)
        self.assertEqual(doctors_in_context[0].doctor_id, self.doctor.doctor_id)
        self.assertIsNotNone(doctors_in_context[0].distance_km)
        self.assertLess(doctors_in_context[0].distance_km, 5.0)

        # Doctor in Pune should be second (~120 km)
        self.assertEqual(doctors_in_context[1].doctor_id, pune_doctor.doctor_id)
        self.assertGreater(doctors_in_context[1].distance_km, 50.0)

        # Proximity banner and distance badge appear in HTML
        self.assertContains(res, 'Showing eligible doctors ordered by proximity')
        self.assertContains(res, 'km away')

    def test_invalid_geolocation_handled_gracefully(self):
        # Coordinates out of bounds or non-numeric should safely fall back
        res = self.client.get(reverse('doctor_list'), {
            'user_lat': '999.0',
            'user_lng': 'invalid_lng'
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['has_user_location'])
        self.assertContains(res, 'Aarav Sharma')
