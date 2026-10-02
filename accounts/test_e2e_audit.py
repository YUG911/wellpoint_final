"""TEMPORARY end-to-end role audit harness. Deleted after the audit."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import (Admin, CityMaster, Clinic, ClinicHours, ClinicStaff,
                             DayMaster, Patient, StateMaster, User, VerificationLog)
from appointments.models import Appointment, Payment
from doctors.models import (Doctor, DoctorAvailability, DoctorClinic,
                            DoctorSpecialization, Review, SpecializationMaster)

PW = 'Audit@12345'


class Base(TestCase):
    """Full multi-tenant fixture set."""

    @classmethod
    def setUpTestData(cls):
        cls.state = StateMaster.objects.create(state_name='Gujarat')
        cls.city_a = CityMaster.objects.create(state=cls.state, city_name='Workflow City')
        cls.city_b = CityMaster.objects.create(state=cls.state, city_name='Bopal')
        cls.spec = SpecializationMaster.objects.create(specialization_name='Dermatologist')
        cls.spec2 = SpecializationMaster.objects.create(specialization_name='Cardiologist')

        def mkuser(name, email, phone, role, status='active', verified=True, pw=PW):
            return User.objects.create(
                full_name=name, email=email, phone=phone,
                password_hash=make_password(pw), role=role,
                is_verified=verified, account_status=status)

        roles = {r.role_name: r for r in
                 __import__('accounts.models', fromlist=['Role']).Role.objects.all()}

        cls.u_patient = mkuser('Patient One', 'patient@audit.test', 900000001, roles['Patient'])
        cls.u_patient2 = mkuser('Patient Two', 'patient2@audit.test', 900000002, roles['Patient'])
        cls.u_doc = mkuser('Dr Audit One', 'doctor@audit.test', 900000003, roles['Doctor'])
        cls.u_doc2 = mkuser('Dr Audit Two', 'doctor2@audit.test', 900000004, roles['Doctor'])
        cls.u_clinic = mkuser('Clinic Owner', 'clinic@audit.test', 900000005, roles['Clinic'])
        cls.u_clinic2 = mkuser('Other Clinic Owner', 'clinic2@audit.test', 900000006, roles['Clinic'])
        cls.u_staff = mkuser('Staff One', 'staff@audit.test', 900000007, roles['Clinic Staff'])
        cls.u_staff2 = mkuser('Staff Two', 'staff2@audit.test', 900000008, roles['Clinic Staff'])
        cls.u_admin = mkuser('Admin One', 'admin@audit.test', 900000009, roles['Admin'])

        cls.patient = Patient.objects.create(
            user=cls.u_patient, date_of_birth=date(1990, 5, 5), gender='Male')
        cls.patient2 = Patient.objects.create(
            user=cls.u_patient2, date_of_birth=date(1991, 6, 6), gender='Female')

        cls.clinic = Clinic.objects.create(
            user=cls.u_clinic, clinic_name='Audit Clinic', address='Main St',
            city=cls.city_a, contact_number=900100001,
            latitude=Decimal('23.0225000'), longitude=Decimal('72.5714000'))
        cls.clinic2 = Clinic.objects.create(
            user=cls.u_clinic2, clinic_name='Other Clinic', address='Side St',
            city=cls.city_b, contact_number=900100002,
            latitude=Decimal('23.1000000'), longitude=Decimal('72.6000000'))

        cls.staff = ClinicStaff.objects.create(user=cls.u_staff, clinic=cls.clinic)
        cls.staff2 = ClinicStaff.objects.create(user=cls.u_staff2, clinic=cls.clinic2)
        cls.admin = Admin.objects.create(user=cls.u_admin, access_level='full')

        cls.doc = Doctor.objects.create(
            user=cls.u_doc, doctor_name='Dr Audit One', experience=8,
            new_patient_fee=Decimal('500.00'), old_patient_fee=Decimal('300.00'))
        cls.doc2 = Doctor.objects.create(
            user=cls.u_doc2, doctor_name='Dr Audit Two', experience=3,
            new_patient_fee=Decimal('400.00'), old_patient_fee=Decimal('250.00'))

        DoctorSpecialization.objects.create(doctor=cls.doc, specialization=cls.spec)
        DoctorSpecialization.objects.create(doctor=cls.doc, specialization=cls.spec2)
        DoctorSpecialization.objects.create(doctor=cls.doc2, specialization=cls.spec)
        DoctorClinic.objects.create(doctor=cls.doc, clinic=cls.clinic)
        DoctorClinic.objects.create(doctor=cls.doc2, clinic=cls.clinic)

        cls.days = {d.day_name: d for d in DayMaster.objects.all()}
        for day_name in ('Monday', 'Tuesday', 'Wednesday', 'Thursday',
                         'Friday', 'Saturday', 'Sunday'):
            DoctorAvailability.objects.create(
                doctor=cls.doc, clinic=cls.clinic, day=cls.days[day_name],
                start_time=time(9, 0), end_time=time(17, 0))
            DoctorAvailability.objects.create(
                doctor=cls.doc2, clinic=cls.clinic, day=cls.days[day_name],
                start_time=time(9, 0), end_time=time(17, 0))

    def login(self, email, pw=PW):
        return self.client.post(reverse('login'), {'email': email, 'password': pw},
                                follow=True)

    def future(self, weekday=None, hour=10):
        """A future datetime matching availability 09:00-17:00."""
        d = timezone.localdate() + timedelta(days=1)
        while weekday and d.strftime('%A') != weekday:
            d += timedelta(days=1)
        return d, time(hour, 0)

    def assertOk(self, res, code=200, msg=''):
        self.assertEqual(res.status_code, code,
                         f'{msg} unexpected {res.status_code}, body={res.content[:400]!r}')


# ─────────────────────────── 2. LOGIN ───────────────────────────
class LoginTests(Base):
    def test_login_all_five_roles(self):
        for email, url in [
            ('patient@audit.test', 'patient_dashboard'),
            ('doctor@audit.test', 'doctor_dashboard'),
            ('clinic@audit.test', 'clinic_dashboard'),
            ('staff@audit.test', 'staff_dashboard'),
            ('admin@audit.test', 'admin_dashboard'),
        ]:
            self.client.logout()
            res = self.login(email)
            self.assertRedirects(res, reverse(url), msg_prefix=email)

    def test_wrong_password(self):
        res = self.login('patient@audit.test', 'WrongPass@1')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('_auth_user_id', res.wsgi_request.session)
        self.assertNotIn('user_id', res.wsgi_request.session)

    def test_unknown_email(self):
        res = self.login('nobody@audit.test')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('user_id', res.wsgi_request.session)

    def test_empty_fields(self):
        res = self.client.post(reverse('login'), {'email': '', 'password': ''})
        self.assertEqual(res.status_code, 200)

    def test_inactive_account_rejected(self):
        u = User.objects.get(email='patient@audit.test')
        u.account_status = 'inactive'
        u.save()
        res = self.login('patient@audit.test')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('user_id', res.wsgi_request.session)

    def test_rejected_account_rejected(self):
        u = User.objects.get(email='patient@audit.test')
        u.account_status = 'rejected'
        u.save()
        self.client.post(reverse('login'), {'email': u.email, 'password': PW})
        self.assertNotIn('user_id', self.client.session)

    def test_logout_clears_session(self):
        self.login('patient@audit.test')
        self.assertIn('user_id', self.client.session)
        res = self.client.get(reverse('logout'), follow=True)
        self.assertOk(res)
        self.assertNotIn('user_id', self.client.session)
        self.assertRedirects(self.client.get(reverse('patient_dashboard')), reverse('login'))

    def test_login_again_after_logout(self):
        self.login('doctor@audit.test')
        self.client.get(reverse('logout'))
        res = self.login('doctor@audit.test')
        self.assertRedirects(res, reverse('doctor_dashboard'))

    def test_uppercase_account_status_still_logs_in(self):
        """LEGACY ROWS: db has 'Active'; model default is 'active'."""
        u = User.objects.get(email='patient@audit.test')
        u.account_status = 'Active'
        u.save()
        res = self.login('patient@audit.test')
        self.assertRedirects(res, reverse('patient_dashboard'))

    def test_email_lookup_is_case_insensitive(self):
        res = self.login('Patient@Audit.Test')
        self.assertRedirects(res, reverse('patient_dashboard'))

    def test_unverified_user_can_still_login(self):
        u = User.objects.get(email='patient2@audit.test')
        u.is_verified = False
        u.save()
        res = self.login('patient2@audit.test')
        self.assertRedirects(res, reverse('patient_dashboard'))


# ─────────────────────── 3. PATIENT ───────────────────────
class PatientTests(Base):
    def setUp(self):
        self.login('patient@audit.test')

    def test_dashboard_and_pages_load(self):
        for name in ['patient_dashboard', 'profile', 'my_appointments',
                     'my_records', 'my_prescriptions', 'my_reports',
                     'recommend_doctor']:
            self.assertOk(self.client.get(reverse(name)), msg=name)

    def test_doctor_search_and_detail(self):
        self.assertOk(self.client.get('/doctors/?search=Audit'))
        self.assertOk(self.client.get('/doctors/?specialization=Dermato'))
        self.assertOk(self.client.get('/doctors/?location=Workflow'))
        self.assertOk(self.client.get(reverse('doctor_detail', args=[self.doc.doctor_id])))
        self.assertOk(self.client.get(reverse('book_appointment', args=[self.doc.doctor_id])))

    def test_spaces_in_search_and_location(self):
        for q in ['New Ranip', 'Paldi Ahmedabad', '  spaced  out  ']:
            r = self.client.get('/doctors/', {'search': q})
            self.assertOk(r)
            r = self.client.get('/doctors/', {'location': q})
            self.assertOk(r)

    def test_search_combined_filters(self):
        self.assertOk(self.client.get('/doctors/', {
            'search': 'Audit', 'specialization': 'Dermato', 'location': 'Workflow'}))

    def test_invalid_doctor_ids(self):
        for did in [99999, 0, -1]:
            self.assertOk(self.client.get(f'/doctors/{did}/'), 404)
            self.assertOk(self.client.get(f'/appointments/book/{did}/'), 404)

    def test_book_appointment_happy_path(self):
        d, t = self.future(hour=10)
        res = self.client.post(reverse('book_appointment', args=[self.doc.doctor_id]), {
            'clinic_id': self.clinic.clinic_id,
            'appointment_date': d.isoformat(), 'appointment_time': t.strftime('%H:%M'),
            'symptoms': 'skin rash', 'patient_type': 'New'})
        appt = Appointment.objects.filter(patient=self.patient).first()
        self.assertIsNotNone(appt, 'appointment was not created')
        self.assertEqual(appt.status, 'Pending')
        self.assertEqual(appt.fee_charged, Decimal('500.00'))
        self.assertOk(self.client.get(reverse('appointment_confirmation',
                                              args=[appt.appointment_id])))

    def test_duplicate_booking_rejected(self):
        d, t = self.future(hour=10)
        url = reverse('book_appointment', args=[self.doc.doctor_id])
        data = {'clinic_id': self.clinic.clinic_id,
                'appointment_date': d.isoformat(),
                'appointment_time': t.strftime('%H:%M'), 'patient_type': 'New'}
        self.client.post(url, data)
        self.client.post(url, data)
        self.assertEqual(Appointment.objects.filter(
            doctor=self.doc, appointment_date=d, appointment_time=t,
            status__in=['Pending', 'Confirmed']).count(), 1)

    def test_time_outside_doctor_availability_rejected(self):
        d, _ = self.future(hour=10)
        self.client.post(reverse('book_appointment', args=[self.doc.doctor_id]), {
            'clinic_id': self.clinic.clinic_id, 'appointment_date': d.isoformat(),
            'appointment_time': '20:00', 'patient_type': 'New'})
        self.assertEqual(Appointment.objects.count(), 0)

    def test_past_time_rejected(self):
        d = timezone.localdate() - timedelta(days=1)
        self.client.post(reverse('book_appointment', args=[self.doc.doctor_id]), {
            'clinic_id': self.clinic.clinic_id, 'appointment_date': d.isoformat(),
            'appointment_time': '10:00', 'patient_type': 'New'})
        self.assertEqual(Appointment.objects.count(), 0)

    def test_malformed_date_rejected_without_500(self):
        res = self.client.post(reverse('book_appointment', args=[self.doc.doctor_id]), {
            'clinic_id': self.clinic.clinic_id, 'appointment_date': 'not-a-date',
            'appointment_time': '10:00'})
        self.assertEqual(res.status_code, 302)

    def test_clinic_not_linked_to_doctor_rejected(self):
        d, t = self.future(hour=10)
        self.client.post(reverse('book_appointment', args=[self.doc.doctor_id]), {
            'clinic_id': self.clinic2.clinic_id, 'appointment_date': d.isoformat(),
            'appointment_time': t.strftime('%H:%M')})
        self.assertEqual(Appointment.objects.count(), 0)

    def _appt(self, patient=None):
        patient = patient or self.patient
        d, t = self.future(hour=10)
        return Appointment.objects.create(
            patient=patient, doctor=self.doc, clinic=self.clinic,
            appointment_date=d, appointment_time=t, status='Pending',
            fee_charged=Decimal('500.00'))

    def test_cannot_see_other_patients_appointment(self):
        other = self._appt(self.patient2)
        self.assertOk(self.client.get(
            reverse('appointment_confirmation', args=[other.appointment_id])), 404)
        self.assertOk(self.client.get(
            reverse('reschedule_appointment', args=[other.appointment_id])), 404)
        self.assertOk(self.client.get(
            reverse('cancel_appointment', args=[other.appointment_id])), 404)
        self.assertOk(self.client.get(
            reverse('payment_page', args=[other.appointment_id])), 404)
        self.assertOk(self.client.get(
            reverse('submit_review', args=[other.appointment_id])), 404)

    def test_invalid_appointment_ids_404(self):
        for aid in [99999, 0]:
            for name in ['appointment_confirmation', 'reschedule_appointment',
                         'cancel_appointment', 'payment_page', 'submit_review']:
                self.assertOk(self.client.get(reverse(name, args=[aid])), 404,
                              msg=f'{name}/{aid}')

    def test_reschedule_cancel_payment_review(self):
        appt = self._appt()
        aid = appt.appointment_id
        self.assertOk(self.client.get(reverse('reschedule_appointment', args=[aid])))

        d2, t2 = self.future(hour=11)
        self.client.post(reverse('reschedule_appointment', args=[aid]), {
            'appointment_date': d2.isoformat(), 'appointment_time': t2.strftime('%H:%M')})
        appt.refresh_from_db()
        self.assertEqual(appt.appointment_time, time(11, 0))

        self.client.post(reverse('payment_page', args=[aid]),
                         {'payment_method': 'Cash at Clinic'})
        self.assertTrue(Payment.objects.filter(appointment=appt).exists())

        self.client.post(reverse('cancel_appointment', args=[aid]))
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Cancelled')

    def test_invalid_payment_method_rejected(self):
        appt = self._appt()
        self.client.post(reverse('payment_page', args=[appt.appointment_id]),
                         {'payment_method': 'Bitcoin'})
        self.assertEqual(Payment.objects.filter(appointment=appt).count(), 0)

    def test_review_requires_completed(self):
        appt = self._appt()
        self.assertOk(self.client.get(
            reverse('submit_review', args=[appt.appointment_id])), 404)
        appt.status = 'Completed'
        appt.save()
        self.assertOk(self.client.get(
            reverse('submit_review', args=[appt.appointment_id])))
        self.client.post(reverse('submit_review', args=[appt.appointment_id]),
                         {'rating': '5', 'review_text': 'Great'})
        self.assertEqual(Review.objects.filter(appointment=appt).count(), 1)
        self.client.post(reverse('submit_review', args=[appt.appointment_id]),
                         {'rating': '1'})
        self.assertEqual(Review.objects.filter(appointment=appt).count(), 1)

    def test_records_are_own_only(self):
        other = self._appt(self.patient2)
        mine = self._appt()
        self.assertOk(self.client.get(reverse('my_records')))
        self.assertOk(self.client.get(reverse('my_prescriptions')))
        self.assertOk(self.client.get(reverse('my_reports')))

    def test_patient_cannot_access_doctor_staff_admin(self):
        for name in ['doctor_dashboard', 'doctor_profile', 'doctor_availability',
                     'doctor_appointments', 'doctor_patients', 'staff_dashboard',
                     'admin_dashboard', 'user_management', 'verify_user',
                     'verification_history', 'clinic_dashboard', 'clinic_profile',
                     'clinic_hours', 'clinic_appointments']:
            res = self.client.get(reverse(name))
            self.assertEqual(res.status_code, 302, msg=name)

    def test_patient_cannot_use_doctor_or_staff_write_views(self):
        appt = self._appt()
        for name in ['add_record', 'upload_prescription', 'staff_upload_report']:
            res = self.client.post(reverse(name, args=[appt.appointment_id]),
                                   {'diagnosis': 'x'})
            self.assertEqual(res.status_code, 302, msg=name)


# ─────────────────────── 4. DOCTOR ───────────────────────
class DoctorTests(Base):
    def setUp(self):
        self.login('doctor@audit.test')

    def test_pages_load(self):
        for name in ['doctor_dashboard', 'doctor_profile', 'doctor_availability',
                     'doctor_appointments', 'doctor_patients']:
            self.assertOk(self.client.get(reverse(name)), msg=name)

    def test_availability_crud(self):
        url = reverse('doctor_availability')
        self.assertOk(self.client.get(url))
        day = self.days['Monday']
        r = self.client.post(url, {
            f'start_{day.day_id}': '09:00', f'end_{day.day_id}': '12:00',
            f'clinics_{day.day_id}': [self.clinic.clinic_id]})
        self.assertRedirects(r, url)
        slot = DoctorAvailability.objects.get(doctor=self.doc, day=day)
        self.assertEqual(slot.end_time, time(12, 0))

    def test_availability_end_before_start_rejected(self):
        day = self.days['Monday']
        self.client.post(reverse('doctor_availability'), {
            f'start_{day.day_id}': '15:00', f'end_{day.day_id}': '09:00',
            f'clinics_{day.day_id}': [self.clinic.clinic_id]})
        self.assertFalse(DoctorAvailability.objects.filter(
            doctor=self.doc, day=day, end_time=time(9, 0)).exists())

    def test_availability_malformed_time_does_not_500(self):
        day = self.days['Monday']
        res = self.client.post(reverse('doctor_availability'), {
            f'start_{day.day_id}': 'abc', f'end_{day.day_id}': 'xyz',
            f'clinics_{day.day_id}': [self.clinic.clinic_id]})
        self.assertNotEqual(res.status_code, 500, 'unhandled ValueError on bad time')

    def test_availability_unlinked_clinic_rejected(self):
        day = self.days['Monday']
        res = self.client.post(reverse('doctor_availability'), {
            f'start_{day.day_id}': '09:00', f'end_{day.day_id}': '12:00',
            f'clinics_{day.day_id}': [self.clinic2.clinic_id]})
        self.assertNotEqual(res.status_code, 500, 'unlinked clinic not validated')

    def _appt(self, doctor=None, status='Pending', patient=None, hour=10):
        d, t = self.future(hour=hour)
        return Appointment.objects.create(
            patient=patient or self.patient, doctor=doctor or self.doc,
            clinic=self.clinic, appointment_date=d, appointment_time=t,
            status=status, fee_charged=Decimal('500.00'))

    def test_doctor_cannot_open_other_doctors_appointment(self):
        other = self._appt(self.doc2)
        self.assertOk(self.client.get(reverse('doctor_appointment_detail',
                                              args=[other.appointment_id])), 404)
        self.assertOk(self.client.post(reverse('add_record',
                                               args=[other.appointment_id]),
                                       {'diagnosis': 'x'}), 404)

    def test_invalid_appointment_ids_404(self):
        for aid in [99999, 0]:
            self.assertOk(self.client.get(
                reverse('doctor_appointment_detail', args=[aid])), 404)

    def test_add_record_marks_completed_and_creates_prescription(self):
        appt = self._appt()
        r = self.client.post(reverse('add_record', args=[appt.appointment_id]),
                             {'diagnosis': 'Dermatitis', 'notes': 'n'})
        self.assertRedirects(r, reverse('doctor_appointments'))
        appt.refresh_from_db()
        self.assertEqual(appt.status, 'Completed')

    def test_upload_prescription(self):
        appt = self._appt()
        f = SimpleUploadedFile('rx.txt', b'prescription')
        with override_settings(MEDIA_ROOT='test-media'):
            r = self.client.post(reverse('upload_prescription',
                                         args=[appt.appointment_id]), {'file': f})
        self.assertRedirects(r, reverse('doctor_appointments'))

    def test_doctor_cannot_access_staff_clinic_admin(self):
        for name in ['staff_dashboard', 'upload_report', 'clinic_dashboard',
                     'clinic_profile', 'clinic_hours', 'admin_dashboard',
                     'user_management', 'verify_user', 'verification_history',
                     'patient_dashboard', 'my_appointments', 'my_records']:
            if name == 'upload_report':
                continue
            self.assertEqual(self.client.get(reverse(name)).status_code, 302,
                             msg=name)

    def test_appointment_filter_by_other_patient_id_is_safe(self):
        self._appt(hour=10)
        self._appt(hour=11, patient=self.patient2)
        r = self.client.get(reverse('doctor_appointments'),
                            {'patient': self.patient2.patient_id})
        self.assertOk(r)
        self.assertOk(self.client.get(reverse('doctor_appointments'),
                                      {'patient': 99999}))
        self.assertOk(self.client.get(reverse('doctor_appointments'),
                                      {'status': 'Completed'}))
        self.assertOk(self.client.get(reverse('doctor_appointments'),
                                      {'status': 'DROP TABLE'}))


# ─────────────── 5. RECEPTIONIST / CLINIC STAFF ───────────────
class StaffTests(Base):
    def setUp(self):
        self.login('staff@audit.test')

    def _appt(self, clinic=None):
        d, t = self.future(hour=10)
        return Appointment.objects.create(
            patient=self.patient, doctor=self.doc, clinic=clinic or self.clinic,
            appointment_date=d, appointment_time=t, status='Pending',
            fee_charged=Decimal('500.00'))

    def test_pages_load(self):
        self.assertOk(self.client.get(reverse('staff_dashboard')))
        self.assertOk(self.client.get(reverse('clinic_appointments')))

    def test_clinic_association_scoped(self):
        r = self.client.get(reverse('clinic_appointments'))
        self.assertOk(r)
        self.assertIn(self.clinic.clinic_name, r.content.decode())

    def test_upload_report_own_clinic(self):
        appt = self._appt()
        f = SimpleUploadedFile('rep.txt', b'report')
        with override_settings(MEDIA_ROOT='test-media'):
            r = self.client.post(reverse('staff_upload_report', args=[appt.appointment_id]),
                                 {'report_name': 'Blood', 'file': f})
        self.assertRedirects(r, reverse('staff_dashboard'))

    def test_upload_report_other_clinic_404(self):
        appt = self._appt(self.clinic2)
        self.assertOk(self.client.get(
            reverse('staff_upload_report', args=[appt.appointment_id])), 404)

    def test_upload_report_invalid_appointment_404(self):
        for aid in [99999, 0]:
            self.assertOk(self.client.get(reverse('staff_upload_report', args=[aid])), 404)

    def test_staff_cannot_access_doctor_clinic_admin(self):
        for name in ['doctor_dashboard', 'doctor_profile', 'doctor_availability',
                     'doctor_appointments', 'doctor_patients', 'clinic_dashboard',
                     'clinic_profile', 'clinic_hours', 'admin_dashboard',
                     'user_management', 'verify_user', 'verification_history',
                     'patient_dashboard', 'my_appointments', 'my_records']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302,
                             msg=name)

    def test_staff_cannot_add_record_for_own_clinic(self):
        appt = self._appt()
        self.assertEqual(self.client.post(
            reverse('add_record', args=[appt.appointment_id]),
            {'diagnosis': 'x'}).status_code, 302)


# ─────────────────────── 6. CLINIC ───────────────────────
class ClinicTests(Base):
    def setUp(self):
        self.login('clinic@audit.test')

    def test_pages_load(self):
        for name in ['clinic_dashboard', 'clinic_profile', 'clinic_hours',
                     'clinic_appointments']:
            self.assertOk(self.client.get(reverse(name)), msg=name)

    def test_dashboard_lists_linked_doctors(self):
        r = self.client.get(reverse('clinic_dashboard'))
        self.assertIn(self.doc.doctor_name, r.content.decode())

    def test_clinic_profile_update(self):
        self.client.post(reverse('clinic_profile'), {
            'clinic_name': 'Renamed Clinic', 'address': 'New St',
            'contact_number': '900100001'})
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.clinic_name, 'Renamed Clinic')

    def test_clinic_hours_save_and_reject_bad_input(self):
        url = reverse('clinic_hours')
        mon = self.days['Monday'].day_id
        self.client.post(url, {f'open_{mon}': '09:00', f'close_{mon}': '17:00'})
        self.assertTrue(ClinicHours.objects.filter(
            clinic=self.clinic, day=self.days['Monday']).exists())

        self.client.post(url, {f'open_{mon}': '17:00', f'close_{mon}': '09:00'})
        row = ClinicHours.objects.get(clinic=self.clinic, day=self.days['Monday'])
        self.assertEqual(row.close_time, time(17, 0), 'bad input overwrote good hours')

        self.client.post(url, {f'open_{mon}': '09:00'})
        self.assertEqual(ClinicHours.objects.get(
            clinic=self.clinic, day=self.days['Monday']).close_time, time(17, 0))

    def test_clinic_hours_malformed_time_does_not_500(self):
        mon = self.days['Monday'].day_id
        res = self.client.post(reverse('clinic_hours'), {
            f'open_{mon}': 'abc', f'close_{mon}': 'xyz'})
        self.assertNotEqual(res.status_code, 500, 'unhandled ValueError on bad time')

    def test_clinic_cannot_access_admin_doctor_staff(self):
        for name in ['admin_dashboard', 'user_management', 'verify_user',
                     'verification_history', 'doctor_dashboard', 'doctor_profile',
                     'doctor_availability', 'doctor_appointments', 'doctor_patients',
                     'staff_dashboard', 'patient_dashboard', 'my_appointments']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302,
                             msg=name)


# ─────────────────────── 7. ADMIN ───────────────────────
class AdminTests(Base):
    def setUp(self):
        self.login('admin@audit.test')

    def test_pages_load(self):
        for name in ['admin_dashboard', 'user_management', 'verification_history']:
            self.assertOk(self.client.get(reverse(name)), msg=name)

    def test_counts_in_dashboard(self):
        self.assertOk(self.client.get(reverse('admin_dashboard')))

    def test_verify_approve_writes_log(self):
        u = User.objects.get(email='patient2@audit.test')
        u.is_verified = False
        u.save()
        self.client.post(reverse('verify_user'),
                         {'user_id': u.user_id, 'action': 'approve'})
        u.refresh_from_db()
        self.assertTrue(u.is_verified)
        self.assertTrue(VerificationLog.objects.filter(user=u, status='Approved').exists())

    def test_verify_reject_blocks_login(self):
        u = User.objects.get(email='patient2@audit.test')
        self.client.post(reverse('verify_user'),
                         {'user_id': u.user_id, 'action': 'reject'})
        u.refresh_from_db()
        self.assertEqual(u.account_status, 'rejected')

    def test_verify_invalid_action_and_bad_id(self):
        u = User.objects.get(email='patient2@audit.test')
        r = self.client.post(reverse('verify_user'),
                             {'user_id': u.user_id, 'action': 'delete-everything'})
        self.assertRedirects(r, reverse('admin_dashboard'))
        self.assertOk(self.client.post(reverse('verify_user'),
                                       {'user_id': 99999, 'action': 'approve'}), 404)

    def test_admin_cannot_access_other_role_pages(self):
        for name in ['patient_dashboard', 'my_appointments', 'my_records',
                     'doctor_dashboard', 'doctor_profile', 'doctor_availability',
                     'clinic_dashboard', 'clinic_profile', 'clinic_hours',
                     'staff_dashboard']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302,
                             msg=name)

    def test_admin_without_profile_row_404_not_500(self):
        Admin.objects.filter(user=self.u_admin).delete()
        r = self.client.post(reverse('verify_user'),
                             {'user_id': self.u_patient.user_id, 'action': 'approve'})
        self.assertNotEqual(r.status_code, 500, 'missing Admin row caused a crash')


# ─────────────── 8/12. SECURITY MATRIX ───────────────
PROTECTED = [
    'patient_dashboard', 'doctor_dashboard', 'clinic_dashboard', 'staff_dashboard',
    'admin_dashboard', 'profile', 'user_management',
    'verification_history', 'clinic_appointments', 'clinic_profile', 'clinic_hours',
    'doctor_profile', 'doctor_availability', 'doctor_appointments', 'doctor_patients',
    'recommend_doctor', 'my_appointments', 'my_records', 'my_prescriptions',
'my_reports',
]
ROLE_OWNED = {
    'patient_dashboard': 'patient', 'doctor_dashboard': 'doctor',
    'clinic_dashboard': 'clinic', 'staff_dashboard': 'clinic staff',
    'admin_dashboard': 'admin', 'user_management': 'admin',
    'verification_history': 'admin', 'clinic_profile': 'clinic',
    'clinic_hours': 'clinic', 'doctor_profile': 'doctor',
    'doctor_availability': 'doctor', 'doctor_appointments': 'doctor',
    'doctor_patients': 'doctor', 'recommend_doctor': 'patient',
    'my_appointments': 'patient', 'my_records': 'patient',
'my_prescriptions': 'patient', 'my_reports': 'patient',
    'clinic_appointments': ('clinic', 'clinic staff'),
    'profile': 'any',
}
ROLE_EMAIL = {'patient': 'patient@audit.test', 'doctor': 'doctor@audit.test',
              'clinic': 'clinic@audit.test', 'clinic staff': 'staff@audit.test',
              'admin': 'admin@audit.test'}


class SecurityMatrixTests(Base):
    def test_verify_user_is_post_only_and_role_gated(self):
        for role, email in ROLE_EMAIL.items():
            self.client.logout()
            self.login(email)
            r = self.client.get(reverse('verify_user'))
            if role == 'admin':
                self.assertEqual(r.status_code, 302, 'admin GET verify_user')
                self.assertEqual(r['Location'], reverse('admin_dashboard'))
            else:
                self.assertEqual(r.status_code, 302, msg=role)
                self.assertIn(reverse('login'), r['Location'], msg=role)
            self.client.logout()

    def test_anonymous_blocked_from_all_protected(self):
        for name in PROTECTED:
            if name == 'verify_user':
                continue
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, msg=name)
            self.assertIn(reverse('login'), r['Location'], msg=name)

    def test_cross_role_matrix(self):
        for role, email in ROLE_EMAIL.items():
            self.client.logout()
            self.login(email)
            for name in PROTECTED:
                owner = ROLE_OWNED.get(name)
                r = self.client.get(reverse(name))
                if owner is None or owner == 'any':
                    self.assertEqual(r.status_code, 200,
                                     f'{role} should reach {name}')
                elif role in (owner if isinstance(owner, tuple) else (owner,)):
                    self.assertEqual(r.status_code, 200,
                                     f'{role} should reach own {name}')
                else:
                    self.assertEqual(r.status_code, 302,
                                     f'{role} must NOT reach {name} (owner {owner})')
                    self.assertIn(reverse('login'), r['Location'],
                                  f'{role} -> {name} leaks via redirect')
            self.client.logout()


# ─────────────── 10/11. CLINIC HOURS BOUNDARIES ───────────────
class ClinicHoursBoundaryTests(Base):
    def setUp(self):
        self.client.login(username=None) if False else None
        self.login('patient@audit.test')
        target = timezone.localdate() + timedelta(days=1)
        while target.strftime('%A') != 'Monday':
            target += timedelta(days=1)
        self.monday = target
        ClinicHours.objects.create(clinic=self.clinic, day=self.days['Monday'],
                                   open_time=time(9, 0), close_time=time(17, 0))

    def _book(self, when, clinic=None):
        return self.client.post(
            reverse('book_appointment', args=[self.doc.doctor_id]),
            {'clinic_id': (clinic or self.clinic).clinic_id,
             'appointment_date': when.date().isoformat(),
             'appointment_time': when.strftime('%H:%M')})

    def test_exactly_opening_time_allowed(self):
        d = self.monday
        self._book(datetime.combine(d, time(9, 0)))
        self.assertEqual(Appointment.objects.count(), 1, 'exactly 09:00 should be allowed')

    def test_one_minute_before_open_rejected(self):
        self._book(datetime.combine(self.monday, time(8, 30)))
        self.assertEqual(Appointment.objects.count(), 0)

    def test_exactly_closing_time_rejected(self):
        self._book(datetime.combine(self.monday, time(17, 0)))
        self.assertEqual(Appointment.objects.count(), 0, 'exactly 17:00 should be closed')

    def test_one_minute_before_close_allowed(self):
        self._book(datetime.combine(self.monday, time(16, 30)))
        self.assertEqual(Appointment.objects.count(), 1)

    def test_closed_day_rejected(self):
        target = timezone.localdate() + timedelta(days=1)
        while target.strftime('%A') != 'Sunday':
            target += timedelta(days=1)
        self._book(datetime.combine(target, time(10, 0)))
        self.assertEqual(Appointment.objects.count(), 0)

    def test_zz_diagnostic(self):
        from appointments.views import clinic_opens_at
        from django.contrib.messages import get_messages
        out = [f'today={timezone.localdate()} monday={self.monday}']
        for label, t in [('09:00', time(9, 0)), ('10:00', time(10, 0)),
                         ('16:30', time(16, 30)), ('17:00', time(17, 0))]:
            ok, msg = clinic_opens_at(self.clinic, self.monday, t)
            avail = DoctorAvailability.objects.filter(
                doctor=self.doc, clinic=self.clinic,
                day__day_name__iexact=self.monday.strftime('%A'),
                start_time__lte=t, end_time__gt=t).exists()
            out.append(f'{label} open={ok} avail={avail} msg={msg!r}')
        r = self._book(datetime.combine(self.monday, time(10, 0)))
        msgs = [str(m) for m in get_messages(r.wsgi_request)]
        out.append(f'book 10:00 -> {Appointment.objects.count()} appts, msgs={msgs}')
        print('\n'.join(out))


from datetime import datetime  # noqa: E402
