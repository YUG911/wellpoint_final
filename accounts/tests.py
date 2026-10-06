from datetime import date

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse

from .models import Admin, CityMaster, Patient, Role, StateMaster, User, VerificationLog


class AccountWorkflowTests(TestCase):
    def setUp(self):
        self.roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin')}
        self.state = StateMaster.objects.create(state_name='Test State')
        self.city = CityMaster.objects.create(state=self.state, city_name='Test City')

    def user(self, role, number, **values):
        return User.objects.create(full_name=values.get('full_name', role + ' User'), email=values.get('email', f'{number}@example.test'), contact_number=str(number), password_hash=make_password('Secret123!'), role=self.roles[role], account_status=values.get('account_status', 'active'))

    def login_as(self, user):
        session = self.client.session
        session['user_id'] = user.user_id
        session.save()

    def test_patient_registration_is_two_step_and_hashes_password(self):
        response = self.client.post(reverse('register'), {'full_name': 'New Patient', 'email': 'new@example.test', 'contact_number': '9000000001', 'password': 'Secret123!', 'confirm_password': 'Secret123!', 'role': self.roles['Patient'].pk, 'address': 'Address', 'terms_accepted': 'on'})
        self.assertRedirects(response, reverse('register_patient'))
        user = User.objects.get(email='new@example.test')
        self.assertTrue(check_password('Secret123!', user.password_hash))
        self.client.post(reverse('register_patient'), {'date_of_birth': '1990-01-01', 'gender': 'Other', 'blood_group': 'O+', 'emergency_contact': '9000000002'})
        self.assertTrue(Patient.objects.filter(user=user).exists())

    def test_registration_rejects_missing_terms_and_duplicate_contact_data(self):
        self.user('Patient', 9000000003, email='taken@example.test')
        response = self.client.post(reverse('register'), {'full_name': 'Taken', 'email': 'taken@example.test', 'contact_number': '9000000003', 'password': 'a', 'confirm_password': 'a', 'role': self.roles['Patient'].pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email='taken@example.test').count(), 1)
        self.assertContains(response, 'must accept')

    def test_login_role_redirect_and_inactive_rejection(self):
        patient_user = self.user('Patient', 9000000004)
        Patient.objects.create(user=patient_user, date_of_birth=date(1990, 1, 1))
        self.assertRedirects(self.client.post(reverse('login'), {'email': patient_user.email, 'password': 'Secret123!'}), reverse('patient_dashboard'))
        blocked = self.user('Patient', 9000000005, account_status='inactive')
        self.assertEqual(self.client.post(reverse('login'), {'email': blocked.email, 'password': 'Secret123!'}).status_code, 200)

    def test_admin_verification_requires_admin_and_writes_audit_log(self):
        target = self.user('Doctor', 9000000006)
        self.assertRedirects(self.client.post(reverse('verify_user'), {'user_id': target.pk, 'action': 'approve'}), reverse('login'))
        admin_user = self.user('Admin', 9000000007)
        Admin.objects.create(user=admin_user, access_level='Super Admin')
        self.login_as(admin_user)
        self.client.post(reverse('verify_user'), {'user_id': target.pk, 'action': 'approve', 'remarks': 'checked'})
        target.refresh_from_db()
        self.assertTrue(target.is_verified)
        self.assertTrue(VerificationLog.objects.filter(user=target, status='Approved').exists())

    def test_profile_edit_and_city_endpoint(self):
        patient_user = self.user('Patient', 9000000008)
        Patient.objects.create(user=patient_user, date_of_birth=date(1990, 1, 1))
        self.login_as(patient_user)
        self.assertRedirects(self.client.post(reverse('profile'), {'full_name': 'Updated', 'contact_number': '9000000009', 'address': 'New Address'}), reverse('profile'))
        patient_user.refresh_from_db()
        self.assertEqual(patient_user.full_name, 'Updated')
        self.assertEqual(self.client.get(reverse('get_cities'), {'state': self.state.state_name}).json()['cities'][0]['city_id'], self.city.pk)
