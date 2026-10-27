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
        patient_user = User.objects.create(full_name='Patient', email='p@r.test', contact_number=9030000001, password_hash=make_password('Secret123!'), role=roles['Patient'])
        self.patient = Patient.objects.create(user=patient_user, date_of_birth='1990-01-01')
        doctor_user = User.objects.create(full_name='Doctor', email='d@r.test', contact_number=9030000002, password_hash=make_password('Secret123!'), role=roles['Doctor'])
        self.doctor = Doctor.objects.create(user=doctor_user, doctor_name='Doctor', new_patient_fee=500, old_patient_fee=300)
        clinic_user = User.objects.create(full_name='Clinic', email='c@r.test', contact_number=9030000003, password_hash=make_password('Secret123!'), role=roles['Clinic'])
        clinic = Clinic.objects.create(user=clinic_user, clinic_name='Clinic', address='Address', city=city, contact_number=9030000003)
        staff_user = User.objects.create(full_name='Staff', email='s@r.test', contact_number=9030000004, password_hash=make_password('Secret123!'), role=roles['Clinic Staff'])
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

    def test_upload_validation_allowed_formats(self):
        self.session_user(self.doctor.user)
        # 1. Valid PDF
        pdf_file = SimpleUploadedFile('rx.pdf', b'%PDF-1.4 valid medical prescription')
        res_pdf = self.client.post(reverse('upload_prescription', args=[self.appointment.pk]), {'file': pdf_file})
        self.assertRedirects(res_pdf, reverse('doctor_appointments'))

        # 2. Valid PNG
        png_file = SimpleUploadedFile('scan.png', b'\x89PNG\r\n\x1a\n valid png bytes')
        res_png = self.client.post(reverse('upload_prescription', args=[self.appointment.pk]), {'file': png_file})
        self.assertRedirects(res_png, reverse('doctor_appointments'))

        # 3. Valid JPG
        jpg_file = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff valid jpg bytes')
        res_jpg = self.client.post(reverse('upload_prescription', args=[self.appointment.pk]), {'file': jpg_file})
        self.assertRedirects(res_jpg, reverse('doctor_appointments'))

    def test_upload_validation_disallowed_formats(self):
        self.session_user(self.doctor.user)
        for bad_name in ('shell.exe', 'exploit.html', 'script.py', 'test.sh'):
            bad_file = SimpleUploadedFile(bad_name, b'executable or script payload')
            res = self.client.post(reverse('upload_prescription', args=[self.appointment.pk]), {'file': bad_file})
            self.assertEqual(res.status_code, 200)
            self.assertContains(res, 'Unsupported file format')

    def test_upload_validation_oversized_file(self):
        self.session_user(self.doctor.user)
        big_bytes = b'%PDF-' + b'A' * (5 * 1024 * 1024 + 100)
        big_file = SimpleUploadedFile('huge.pdf', big_bytes)
        res = self.client.post(reverse('upload_prescription', args=[self.appointment.pk]), {'file': big_file})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'File exceeds the 5MB size limit')

    def test_upload_validation_invalid_content(self):
        self.session_user(self.doctor.user)
        # Fake PDF extension but non-PDF header
        fake_pdf = SimpleUploadedFile('fake.pdf', b'this is not a pdf file')
        res = self.client.post(reverse('upload_prescription', args=[self.appointment.pk]), {'file': fake_pdf})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Invalid PDF file content')

        # Text file with embedded script tag
        xss_txt = SimpleUploadedFile('notes.txt', b'<script>alert("xss")</script>')
        self.session_user(self.staff.user)
        res_xss = self.client.post(reverse('staff_upload_report', args=[self.appointment.pk]), {'report_name': 'XSS', 'file': xss_txt})
        self.assertEqual(res_xss.status_code, 200)
        self.assertContains(res_xss, 'Invalid text file content')

    def test_upload_report_default_name(self):
        self.session_user(self.staff.user)
        report_file = SimpleUploadedFile('scan.pdf', b'%PDF-1.4 sample diagnostic report')
        # Empty report_name falls back to default
        res = self.client.post(reverse('staff_upload_report', args=[self.appointment.pk]), {'report_name': '   ', 'file': report_file})
        self.assertRedirects(res, reverse('staff_dashboard'))
        report = Report.objects.filter(appointment=self.appointment).latest('report_id')
        self.assertEqual(report.report_name, 'Medical Report')
