from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CityMaster, Clinic, DayMaster, Patient, Role, StateMaster, User
from doctors.models import Doctor, DoctorAvailability, DoctorClinic
from .models import Appointment, Payment


class AppointmentWorkflowTests(TestCase):
    def setUp(self):
        self.roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor', 'Clinic')}
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='City')
        self.patient_user = User.objects.create(full_name='Patient', email='patient@example.test', phone=9010000001, password_hash=make_password('Secret123!'), role=self.roles['Patient'])
        self.patient = Patient.objects.create(user=self.patient_user, date_of_birth='1990-01-01')
        clinic_user = User.objects.create(full_name='Clinic', email='clinic@example.test', phone=9010000002, password_hash=make_password('Secret123!'), role=self.roles['Clinic'])
        self.clinic = Clinic.objects.create(user=clinic_user, clinic_name='Clinic', address='Address', city=city, contact_number=9010000002)
        doctor_user = User.objects.create(full_name='Aarav Sharma', email='doctor@example.test', phone=9010000003, password_hash=make_password('Secret123!'), role=self.roles['Doctor'])
        self.doctor = Doctor.objects.create(user=doctor_user, doctor_name='Aarav Sharma', new_patient_fee=500, old_patient_fee=300)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=self.clinic)
        self.day_date = timezone.localdate() + timedelta(days=1)
        self.day, _ = DayMaster.objects.get_or_create(day_name=self.day_date.strftime('%A'))
        DoctorAvailability.objects.create(doctor=self.doctor, clinic=self.clinic, day=self.day, start_time='10:00', end_time='11:00')
        session = self.client.session
        session['user_id'] = self.patient_user.pk
        session.save()

    def book(self, when='10:00', date=None):
        return self.client.post(reverse('book_appointment', args=[self.doctor.pk]), {'clinic_id': self.clinic.pk, 'appointment_date': (date or self.day_date).isoformat(), 'appointment_time': when, 'patient_type': 'New', 'symptoms': 'Test'})

    def test_booking_creates_pending_appointment_with_fee_and_confirmation(self):
        response = self.book()
        appointment = Appointment.objects.get()
        self.assertRedirects(response, reverse('appointment_confirmation', args=[appointment.pk]))
        self.assertEqual((appointment.status, appointment.fee_charged), ('Pending', 500))
        self.assertContains(self.client.get(reverse('appointment_confirmation', args=[appointment.pk])), 'APPOINTMENT REQUEST SUBMITTED')

    def test_booking_rejects_unavailable_or_duplicate_slot(self):
        self.book()
        self.book()
        self.assertEqual(Appointment.objects.count(), 1)
        self.book(when='12:00')
        self.assertEqual(Appointment.objects.count(), 1)

    def test_owner_only_reschedule_cancel_and_payment_preference(self):
        self.book()
        appointment = Appointment.objects.get()
        response = self.client.post(reverse('reschedule_appointment', args=[appointment.pk]), {'appointment_date': self.day_date.isoformat(), 'appointment_time': '10:30'})
        self.assertRedirects(response, reverse('my_appointments'))
        appointment.refresh_from_db()
        self.assertEqual(str(appointment.appointment_time), '10:30:00')
        self.client.post(reverse('payment_page', args=[appointment.pk]), {'payment_method': 'Cash at Clinic'})
        self.assertEqual(Payment.objects.get(appointment=appointment).payment_method, 'Cash at Clinic')
        self.client.post(reverse('cancel_appointment', args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, 'Cancelled')
