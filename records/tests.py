from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CityMaster, Clinic, ClinicStaff, Patient, Role, StateMaster, User
from appointments.models import Appointment
from doctors.models import Doctor
from .models import PatientRecord, Report


@override_settings(MEDIA_ROOT='test-media')
class RecordWorkflowTests(TestCase):
    def setUp(self):
        roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff')}
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='City')
        patient_user = User.objects.create(full_name='Patient', email='p@r.test', phone=9030000001, password_hash=make_password('Secret123!'), role=roles['Patient'])
        self.patient = Patient.objects.create(user=patient_user, date_of_birth='1990-01-01')
        doctor_user = User.objects.create(full_name='Doctor', email='d@r.test', phone=9030000002, password_hash=make_password('Secret123!'), role=roles['Doctor'])
        self.doctor = Doctor.objects.create(user=doctor_user, doctor_name='Doctor', new_patient_fee=500, old_patient_fee=300)
        clinic_user = User.objects.create(full_name='Clinic', email='c@r.test', phone=9030000003, password_hash=make_password('Secret123!'), role=roles['Clinic'])
        clinic = Clinic.objects.create(user=clinic_user, clinic_name='Clinic', address='Address', city=city, contact_number=9030000003)
        staff_user = User.objects.create(full_name='Staff', email='s@r.test', phone=9030000004, password_hash=make_password('Secret123!'), role=roles['Clinic Staff'])
        self.staff = ClinicStaff.objects.create(user=staff_user, clinic=clinic)
        self.appointment = Appointment.objects.create(patient=self.patient, doctor=self.doctor, clinic=clinic, appointment_date=timezone.localdate() + timedelta(days=1), appointment_time='10:00', status='Confirmed', patient_type='New', fee_charged=500)

    def session_user(self, user):
        session = self.client.session
        session['user_id'] = user.pk
        session.save()

    def test_doctor_completes_own_appointment_record(self):
        self.session_user(self.doctor.user)
        self.client.post(reverse('add_record', args=[self.appointment.pk]), {'diagnosis': 'Diagnosis', 'notes': 'Notes'})
        self.assertTrue(PatientRecord.objects.filter(appointment=self.appointment).exists())
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'Completed')

    def test_staff_can_upload_report_only_for_own_clinic(self):
        self.session_user(self.staff.user)
        response = self.client.post(reverse('staff_upload_report', args=[self.appointment.pk]), {'report_name': 'Blood test', 'file': SimpleUploadedFile('report.txt', b'result')})
        self.assertRedirects(response, reverse('staff_dashboard'))
        self.assertTrue(Report.objects.filter(appointment=self.appointment, uploaded_by=self.staff.user).exists())
