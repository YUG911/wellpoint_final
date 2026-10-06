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
        clinic_user = User.objects.create(full_name='Clinic', email='clinic@d.test', contact_number='9020000001', password_hash=make_password('Secret123!'), role=self.clinic_role)
        self.clinic = Clinic.objects.create(user=clinic_user, clinic_name='Care', address='Address', city=city, contact_number=9020000001)
        user = User.objects.create(full_name='Aarav', email='doctor@d.test', contact_number='9020000002', password_hash=make_password('Secret123!'), role=self.doctor_role)
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
