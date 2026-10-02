from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from accounts.models import (
    CityMaster, Clinic, ClinicStaff, DayMaster, Patient, Role, StateMaster, User
)
from doctors.models import Doctor


class AuthorizationTests(TestCase):
    def setUp(self):
        roles = {name: Role.objects.get(role_name=name) for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin')}
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='City')

        def make(role, number):
            return User.objects.create(
                full_name=f'{role} User',
                email=f'{role.lower().replace(" ", "")}{number}@auth.test',
                phone=9060000000 + number,
                password_hash=make_password('Secret123!'),
                role=roles[role],
            )

        self.patient_user = make('Patient', 1)
        self.patient = Patient.objects.create(user=self.patient_user, date_of_birth='1990-01-01')
        self.doctor_user = make('Doctor', 2)
        self.doctor = Doctor.objects.create(user=self.doctor_user, doctor_name='Auth Doctor', new_patient_fee=500, old_patient_fee=300)
        self.clinic_user = make('Clinic', 3)
        self.clinic = Clinic.objects.create(user=self.clinic_user, clinic_name='Auth Clinic', address='Address', city=city, contact_number=9060000003)
        self.staff_user = make('Clinic Staff', 4)
        self.staff = ClinicStaff.objects.create(user=self.staff_user, clinic=self.clinic)
        self.admin_user = make('Admin', 5)

        self.users = {
            'patient': self.patient_user,
            'doctor': self.doctor_user,
            'clinic': self.clinic_user,
            'clinic staff': self.staff_user,
            'admin': self.admin_user,
        }

    def login_as(self, role):
        session = self.client.session
        session['user_id'] = self.users[role].pk
        session.save()

    def test_anonymous_users_are_redirected_to_login(self):
        for name in ('patient_dashboard', 'doctor_dashboard', 'clinic_dashboard',
                     'staff_dashboard', 'admin_dashboard', 'user_management',
                     'verification_history', 'doctor_profile', 'doctor_availability',
                     'doctor_appointments', 'clinic_profile', 'clinic_hours',
                     'recommend_doctor', 'my_appointments', 'my_records',
                     'my_prescriptions', 'my_reports'):
            response = self.client.get(reverse(name))
            self.assertTrue(
                response.status_code == 302 and reverse('login') in response['Location'],
                f'{name} should redirect an anonymous user to login',
            )

    def test_anonymous_appointment_urls_are_redirected(self):
        for name in ('book_appointment', 'appointment_confirmation',
                     'reschedule_appointment', 'cancel_appointment',
                     'payment_page', 'submit_review'):
            response = self.client.get(reverse(name, args=[self.doctor.pk]))
            self.assertTrue(
                response.status_code == 302 and reverse('login') in response['Location'],
                f'{name} should redirect an anonymous user to login',
            )

    def test_each_role_reaches_only_its_own_pages(self):
        allowed = {
            'patient': ['patient_dashboard', 'my_appointments', 'my_records',
                        'my_prescriptions', 'my_reports', 'recommend_doctor'],
            'doctor': ['doctor_dashboard', 'doctor_profile', 'doctor_availability',
                       'doctor_appointments', 'doctor_patients'],
            'clinic': ['clinic_dashboard', 'clinic_profile', 'clinic_hours',
                       'clinic_appointments'],
            'clinic staff': ['staff_dashboard'],
            'admin': ['admin_dashboard', 'user_management', 'verification_history'],
        }
        shared = {'clinic_appointments': ('clinic', 'clinic staff')}
        for role, pages in allowed.items():
            self.login_as(role)
            for name in pages:
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, f'{role}->{name}')
            for name, roles in shared.items():
                if role in roles:
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200, f'{role}->{name}')
                else:
                    self.assertEqual(self.client.get(reverse(name)).status_code, 302, f'{role}->{name}')
            owned = set(pages) | {name for name, roles in shared.items() if role in roles}
            for other, other_pages in allowed.items():
                if other == role:
                    continue
                for name in other_pages:
                    if name in owned:
                        continue
                    self.assertEqual(self.client.get(reverse(name)).status_code, 302, f'{role}->{name}')

    def test_admin_management_urls_resolve_to_application_views(self):
        for name in ('user_management', 'verification_history'):
            match = resolve(reverse(name))
            self.assertEqual(match.func.__module__, 'accounts.views')

    def test_django_admin_still_serves_its_own_urls(self):
        match = resolve('/admin/')
        self.assertEqual(match.func.__module__, 'django.contrib.admin.sites')

    def test_patient_cannot_read_another_patients_appointment(self):
        self.login_as('doctor')
        response = self.client.get(reverse('doctor_appointments'))
        self.assertEqual(response.status_code, 200)
        other_patient_user = User.objects.create(
            full_name='Other', email='other@auth.test', phone=9060000099,
            password_hash=make_password('Secret123!'),
            role=Role.objects.filter(role_name='Patient').first(),
        )
        other = Patient.objects.create(user=other_patient_user, date_of_birth='1990-01-01')
        appointment = self._appointment(other)
        self.assertEqual(
            self.client.get(reverse('appointment_confirmation', args=[appointment.pk])).status_code,
            302,
        )
        self.assertEqual(
            self.client.get(reverse('reschedule_appointment', args=[appointment.pk])).status_code,
            302,
        )

    def test_profile_is_shared_by_all_roles_but_only_edits_own_record(self):
        for index, (role, user) in enumerate(self.users.items(), start=1):
            self.client.logout()
            session = self.client.session
            session['user_id'] = user.pk
            session.save()
            self.assertEqual(self.client.get(reverse('profile')).status_code, 200, role)
            self.client.post(reverse('profile'), {
                'full_name': f'Edited {role}',
                'phone': 9070000000 + index,
                'address': 'Self edited',
            })
            user.refresh_from_db()
            self.assertEqual(user.full_name, f'Edited {role}')
            for other_role, other in self.users.items():
                if other_role == role:
                    continue
                other.refresh_from_db()
                self.assertNotEqual(other.full_name, f'Edited {role}')

    def _appointment(self, patient):
        from appointments.models import Appointment
        return Appointment.objects.create(
            patient=patient, doctor=self.doctor, clinic=self.clinic,
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time='10:00', status='Confirmed', patient_type='New',
            fee_charged=500,
        )