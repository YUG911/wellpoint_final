from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    CityMaster, Clinic, ClinicHours, ClinicStaff, DayMaster, Patient, Role,
    StateMaster, User
)
from doctors.models import Doctor, DoctorAvailability, DoctorClinic
from .models import Appointment


def next_weekday(name):
    target = timezone.localdate()
    while target.strftime('%A') != name:
        target += timedelta(days=1)
    return target


class ClinicHourRuleTests(TestCase):
    def setUp(self):
        roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor', 'Clinic')}
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='City')
        patient_user = User.objects.create(full_name='Patient', email='p@ch.test', contact_number='9050000001', password_hash=make_password('Secret123!'), role=roles['Patient'])
        self.patient = Patient.objects.create(user=patient_user, date_of_birth='1990-01-01')
        doctor_user = User.objects.create(full_name='Doctor', email='d@ch.test', contact_number='9050000002', password_hash=make_password('Secret123!'), role=roles['Doctor'])
        self.doctor = Doctor.objects.create(user=doctor_user, doctor_name='Hours Doctor', new_patient_fee=500, old_patient_fee=300)
        clinic_user = User.objects.create(full_name='Clinic', email='c@ch.test', contact_number='9050000003', password_hash=make_password('Secret123!'), role=roles['Clinic'])
        self.clinic = Clinic.objects.create(user=clinic_user, clinic_name='Hours Clinic', address='Address', city=city, contact_number=9050000003)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=self.clinic)
        self.monday, _ = DayMaster.objects.get_or_create(day_name='Monday')
        self.monday_date = next_weekday('Monday')
        DoctorAvailability.objects.create(doctor=self.doctor, clinic=self.clinic, day=self.monday, start_time='09:00', end_time='17:00')

        session = self.client.session
        session['user_id'] = patient_user.pk
        session.save()

    def set_clinic_hours(self, open_time, close_time, day=None):
        ClinicHours.objects.create(
            clinic=self.clinic,
            day=day or self.monday,
            open_time=open_time,
            close_time=close_time,
        )

    def book(self, when):
        return self.client.post(
            reverse('book_appointment', args=[self.doctor.pk]),
            {
                'clinic_id': self.clinic.pk,
                'appointment_date': self.monday_date.isoformat(),
                'appointment_time': when,
                'patient_type': 'New',
                'symptoms': 'Test',
            },
        )

    def test_booking_allowed_inside_clinic_hours(self):
        self.set_clinic_hours('10:00', '14:00')
        self.book('11:00')
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_rejected_before_clinic_opens(self):
        self.set_clinic_hours('10:00', '14:00')
        self.book('09:30')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_booking_rejected_after_clinic_closes(self):
        self.set_clinic_hours('10:00', '14:00')
        self.book('14:00')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_booking_rejected_on_a_day_the_clinic_is_closed(self):
        self.set_clinic_hours('10:00', '14:00')
        self.book('11:00')
        Appointment.objects.all().delete()
        ClinicHours.objects.all().delete()
        self.set_clinic_hours('10:00', '14:00', day=DayMaster.objects.get_or_create(day_name='Tuesday')[0])
        self.book('11:00')
        self.assertEqual(Appointment.objects.count(), 0)

    def test_clinic_without_configured_hours_still_accepts_booking(self):
        self.book('11:00')
        self.assertEqual(Appointment.objects.count(), 1)

    def test_booking_page_hides_slots_outside_clinic_hours(self):
        self.set_clinic_hours('11:00', '12:00')
        response = self.client.get(reverse('book_appointment', args=[self.doctor.pk]))
        slots = [
            slot
            for data in response.context['available_slots'].values()
            for slot in data['slots']
        ]
        self.assertIn('11:00', slots)
        self.assertNotIn('09:00', slots)
        self.assertNotIn('13:00', slots)


class ClinicHoursManagementTests(TestCase):
    def setUp(self):
        roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor', 'Clinic')}
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='City')
        self.clinic_user = User.objects.create(full_name='Clinic', email='c@chm.test', contact_number='9050000011', password_hash=make_password('Secret123!'), role=roles['Clinic'])
        self.clinic = Clinic.objects.create(user=self.clinic_user, clinic_name='Managed Clinic', address='Address', city=city, contact_number=9050000011)
        self.patient_user = User.objects.create(full_name='Patient', email='p@chm.test', contact_number='9050000012', password_hash=make_password('Secret123!'), role=roles['Patient'])
        Patient.objects.create(user=self.patient_user, date_of_birth='1990-01-01')
        self.doctor_user = User.objects.create(full_name='Doctor', email='d@chm.test', contact_number='9050000013', password_hash=make_password('Secret123!'), role=roles['Doctor'])
        self.monday, _ = DayMaster.objects.get_or_create(day_name='Monday')

    def login(self, user):
        session = self.client.session
        session['user_id'] = user.pk
        session.save()

    def test_clinic_can_save_working_hours(self):
        self.login(self.clinic_user)
        self.assertRedirects(
            self.client.post(reverse('clinic_hours'), {
                f'open_{self.monday.pk}': '09:00',
                f'close_{self.monday.pk}': '17:00',
            }),
            reverse('clinic_hours'),
        )
        record = ClinicHours.objects.get(clinic=self.clinic, day=self.monday)
        self.assertEqual((str(record.open_time), str(record.close_time)), ('09:00:00', '17:00:00'))

    def test_clinic_rejects_close_before_open_without_saving(self):
        self.login(self.clinic_user)
        self.client.post(reverse('clinic_hours'), {
            f'open_{self.monday.pk}': '17:00',
            f'close_{self.monday.pk}': '09:00',
        })
        self.assertFalse(ClinicHours.objects.filter(clinic=self.clinic).exists())

    def test_empty_day_marks_clinic_closed(self):
        self.login(self.clinic_user)
        self.client.post(reverse('clinic_hours'), {
            f'open_{self.monday.pk}': '09:00',
            f'close_{self.monday.pk}': '17:00',
        })
        self.client.post(reverse('clinic_hours'), {})
        self.assertFalse(ClinicHours.objects.filter(clinic=self.clinic).exists())

    def test_non_clinic_roles_cannot_manage_clinic_hours(self):
        for user in (self.patient_user, self.doctor_user):
            self.client.logout()
            session = self.client.session
            session['user_id'] = user.pk
            session.save()
            self.assertRedirects(self.client.get(reverse('clinic_hours')), reverse('login'))
            self.assertRedirects(
                self.client.post(reverse('clinic_hours'), {f'open_{self.monday.pk}': '09:00', f'close_{self.monday.pk}': '17:00'}),
                reverse('login'),
            )
        self.assertFalse(ClinicHours.objects.filter(clinic=self.clinic).exists())