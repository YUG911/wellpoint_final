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
        self.patient_user = User.objects.create(full_name='Patient', email='patient@example.test', contact_number=9010000001, password_hash=make_password('Secret123!'), role=self.roles['Patient'])
        self.patient = Patient.objects.create(user=self.patient_user, date_of_birth='1990-01-01')
        clinic_user = User.objects.create(full_name='Clinic', email='clinic@example.test', contact_number=9010000002, password_hash=make_password('Secret123!'), role=self.roles['Clinic'])
        self.clinic = Clinic.objects.create(user=clinic_user, clinic_name='Clinic', address='Address', city=city, contact_number=9010000002)
        doctor_user = User.objects.create(full_name='Aarav Sharma', email='doctor@example.test', contact_number=9010000003, password_hash=make_password('Secret123!'), role=self.roles['Doctor'])
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

    def test_review_validation_rejects_invalid_ratings(self):
        self.book()
        appointment = Appointment.objects.get()
        appointment.status = 'Completed'
        appointment.save()

        # Submit valid review
        res = self.client.post(reverse('submit_review', args=[appointment.pk]), {'rating': '4.5', 'review_text': 'Great'})
        self.assertRedirects(res, reverse('my_appointments'))
        from doctors.models import Review
        self.assertTrue(Review.objects.filter(appointment=appointment, rating=4.5).exists())

        # Reset and try invalid rating
        Review.objects.all().delete()
        res = self.client.post(reverse('submit_review', args=[appointment.pk]), {'rating': '10', 'review_text': 'Bad'})
        self.assertRedirects(res, reverse('submit_review', args=[appointment.pk]))
        self.assertFalse(Review.objects.exists())
        
        # Test non-numeric rating
        res = self.client.post(reverse('submit_review', args=[appointment.pk]), {'rating': 'abc', 'review_text': 'Bad'})
        self.assertRedirects(res, reverse('submit_review', args=[appointment.pk]))
        self.assertFalse(Review.objects.exists())

    def test_multiple_availability_shifts(self):
        # Add a second shift on the same day for the same clinic
        DoctorAvailability.objects.create(doctor=self.doctor, clinic=self.clinic, day=self.day, start_time='14:00', end_time='15:00')
        
        response = self.client.get(reverse('book_appointment', args=[self.doctor.pk]))
        available_slots = response.context['available_slots']
        
        date_str = self.day_date.strftime('%Y-%m-%d')
        self.assertIn(date_str, available_slots)
        
        slots = available_slots[date_str]['slots']
        # Expect 10:00, 10:30, 14:00, 14:30
        times = [s['time'] for s in slots]
        self.assertIn('10:00', times)
        self.assertIn('14:30', times)
        self.assertEqual(len(times), 4)
        
        # Test rescheduling multiple shifts logic
        self.book(when='10:00')
        appointment = Appointment.objects.get()
        res_response = self.client.get(reverse('reschedule_appointment', args=[appointment.pk]))
        res_slots = res_response.context['available_slots']
        self.assertIn(date_str, res_slots)
        self.assertIn('14:30', res_slots[date_str]['slots'])

    def test_slots_preserve_clinic_association(self):
        # Add a second clinic
        city = CityMaster.objects.first()
        clinic2_user = User.objects.create(full_name='Clinic2', email='clinic2@example.test', contact_number=9010000004, password_hash=make_password('Secret123!'), role=self.roles['Clinic'])
        clinic2 = Clinic.objects.create(user=clinic2_user, clinic_name='Clinic2', address='Address', city=city, contact_number=9010000004)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=clinic2)
        
        # Add a shift for clinic2 on the same day
        DoctorAvailability.objects.create(doctor=self.doctor, clinic=clinic2, day=self.day, start_time='16:00', end_time='17:00')
        
        response = self.client.get(reverse('book_appointment', args=[self.doctor.pk]))
        slots = response.context['available_slots'][self.day_date.strftime('%Y-%m-%d')]['slots']
        
        # We expect '10:00' with clinic_id 1, and '16:00' with clinic_id 2
        slot_10 = next(s for s in slots if s['time'] == '10:00')
        self.assertEqual(slot_10['clinic_id'], self.clinic.clinic_id)
        
        slot_16 = next(s for s in slots if s['time'] == '16:00')
        self.assertEqual(slot_16['clinic_id'], clinic2.clinic_id)

    def test_already_booked_slots_excluded(self):
        # 10:00 is booked
        self.book(when='10:00')
        
        response = self.client.get(reverse('book_appointment', args=[self.doctor.pk]))
        if self.day_date.strftime('%Y-%m-%d') in response.context['available_slots']:
            slots = response.context['available_slots'][self.day_date.strftime('%Y-%m-%d')]['slots']
            times = [s['time'] for s in slots]
            self.assertNotIn('10:00', times)
            self.assertIn('10:30', times)

    def test_concurrent_double_booking_prevention(self):
        # First booking succeeds
        res1 = self.book(when='10:00')
        self.assertEqual(Appointment.objects.filter(appointment_time='10:00').count(), 1)
        self.assertRedirects(res1, reverse('appointment_confirmation', args=[Appointment.objects.get().pk]))

        # Second booking request for same doctor, date, and slot is rejected
        res2 = self.book(when='10:00')
        self.assertRedirects(res2, reverse('book_appointment', args=[self.doctor.pk]))
        self.assertEqual(Appointment.objects.filter(appointment_time='10:00').count(), 1)

    def test_reschedule_conflict_rejected(self):
        # Create appointment 1 at 10:00
        self.book(when='10:00')
        appt1 = Appointment.objects.get()

        # Create patient 2 and book at 10:30
        patient2_user = User.objects.create(full_name='Patient 2', email='p2@test.test', contact_number=9010000099, password_hash=make_password('Secret123!'), role=self.roles['Patient'])
        patient2 = Patient.objects.create(user=patient2_user, date_of_birth='1992-02-02')
        appt2 = Appointment.objects.create(patient=patient2, doctor=self.doctor, clinic=self.clinic, appointment_date=self.day_date, appointment_time='10:30', status='Pending', patient_type='New', fee_charged=500)

        # Patient 1 attempts to reschedule into 10:30 (already occupied by Patient 2)
        res = self.client.post(reverse('reschedule_appointment', args=[appt1.pk]), {'appointment_date': self.day_date.isoformat(), 'appointment_time': '10:30'})
        self.assertRedirects(res, reverse('reschedule_appointment', args=[appt1.pk]))
        appt1.refresh_from_db()
        self.assertEqual(str(appt1.appointment_time), '10:00:00')

    def test_booking_with_invalid_clinic_id_falls_back(self):
        # Passing invalid or non-numeric clinic_id gracefully falls back to the doctor's clinic
        res = self.client.post(reverse('book_appointment', args=[self.doctor.pk]), {
            'clinic_id': 'invalid_id',
            'appointment_date': self.day_date.isoformat(),
            'appointment_time': '10:00',
            'patient_type': 'New',
            'symptoms': 'Test'
        })
        self.assertEqual(Appointment.objects.count(), 1)
        appt = Appointment.objects.get()
        self.assertRedirects(res, reverse('appointment_confirmation', args=[appt.pk]))
        self.assertEqual(appt.clinic, self.clinic)
