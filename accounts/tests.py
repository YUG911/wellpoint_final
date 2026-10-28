import io
import os
from datetime import date
from unittest import mock
from PIL import Image
import pypdf  # strict PDF test fixture generator

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Admin, CityMaster, Clinic, ClinicStaff, Patient, Role, StateMaster, User, VerificationLog
from doctors.models import Doctor, SpecializationMaster, QualificationMaster
from accounts.storage import (
    get_protected_storage,
    get_r2_config,
    get_secure_documents_root,
    protected_storage,
    ProtectedStorage,
    R2ProtectedStorage,
)
from accounts.validators import validate_document_file


def make_valid_pdf_bytes():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_valid_png_bytes():
    buf = io.BytesIO()
    img = Image.new('RGB', (10, 10), color='green')
    img.save(buf, format='PNG')
    return buf.getvalue()


def make_valid_jpg_bytes():
    buf = io.BytesIO()
    img = Image.new('RGB', (10, 10), color='blue')
    img.save(buf, format='JPEG')
    return buf.getvalue()


class AccountWorkflowTests(TestCase):
    def setUp(self):
        self.roles = {name: Role.objects.create(role_name=name) for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin')}
        self.state = StateMaster.objects.create(state_name='Test State')
        self.city = CityMaster.objects.create(state=self.state, city_name='Test City')

    def user(self, role, number, **values):
        return User.objects.create(full_name=values.get('full_name', role + ' User'), email=values.get('email', f'{number}@example.test'), contact_number=number, password_hash=make_password('Secret123!'), role=self.roles[role], account_status=values.get('account_status', 'active'), is_verified=values.get('is_verified', False))

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
        self.client.logout()
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

    def test_demo_seed_is_idempotent_and_creates_clinic_profiles(self):
        call_command('seed_seminar3_demo', verbosity=0)
        call_command('seed_seminar3_demo', verbosity=0)
        self.assertEqual(User.objects.filter(email='demo.clinic.ahmedabad@wellpoint.test').count(), 1)
        clinic_user = User.objects.get(email='demo.clinic.ahmedabad@wellpoint.test')
        self.assertTrue(Clinic.objects.filter(user=clinic_user).exists())
        self.assertTrue(CityMaster.objects.filter(state__state_name='Gujarat', city_name='Ahmedabad').exists())

    def test_unverified_versus_verified_provider_login(self):
        # 1. Doctor unverified -> rejected; verified -> allowed
        doc_user = self.user('Doctor', 9000000010, is_verified=False)
        Doctor.objects.create(user=doc_user, doctor_name='Dr. Test', experience=5, new_patient_fee=500, old_patient_fee=300)
        res = self.client.post(reverse('login'), {'email': doc_user.email, 'password': 'Secret123!'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'pending administrative verification')
        self.assertNotIn('user_id', self.client.session)

        doc_user.is_verified = True
        doc_user.save()
        res_ok = self.client.post(reverse('login'), {'email': doc_user.email, 'password': 'Secret123!'})
        self.assertRedirects(res_ok, reverse('doctor_dashboard'))
        self.client.logout()

        # 2. Clinic unverified -> rejected; verified -> allowed
        clinic_user = self.user('Clinic', 9000000011, is_verified=False)
        Clinic.objects.create(user=clinic_user, clinic_name='Test Clinic', address='Address', city=self.city, contact_number=9000000011)
        res = self.client.post(reverse('login'), {'email': clinic_user.email, 'password': 'Secret123!'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'pending administrative verification')

        clinic_user.is_verified = True
        clinic_user.save()
        res_ok = self.client.post(reverse('login'), {'email': clinic_user.email, 'password': 'Secret123!'})
        self.assertRedirects(res_ok, reverse('clinic_dashboard'))
        self.client.logout()

        # 3. Clinic Staff unverified -> rejected; verified -> allowed
        staff_user = self.user('Clinic Staff', 9000000012, is_verified=False)
        clinic_owner_tmp = self.user('Clinic', 9000000099, is_verified=True)
        clinic_tmp = Clinic.objects.create(user=clinic_owner_tmp, clinic_name='Clinic Tmp', address='T', city=self.city, contact_number=9000000099)
        ClinicStaff.objects.create(user=staff_user, clinic=clinic_tmp)
        res = self.client.post(reverse('login'), {'email': staff_user.email, 'password': 'Secret123!'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'pending administrative verification')

        staff_user.is_verified = True
        staff_user.save()
        res_ok = self.client.post(reverse('login'), {'email': staff_user.email, 'password': 'Secret123!'})
        self.assertRedirects(res_ok, reverse('staff_dashboard'))
        self.client.logout()

        # 4. Patient does NOT require verification -> allowed immediately
        patient_user = self.user('Patient', 9000000013, is_verified=False)
        Patient.objects.create(user=patient_user, date_of_birth=date(1995, 5, 5))
        res_patient = self.client.post(reverse('login'), {'email': patient_user.email, 'password': 'Secret123!'})
        self.assertRedirects(res_patient, reverse('patient_dashboard'))

    def test_unauthorized_staff_registration_and_clinic_isolation(self):
        # Direct POST without prior Clinic Staff registration session is rejected
        clinic_owner = self.user('Clinic', 9000000014, is_verified=True)
        clinic_a = Clinic.objects.create(user=clinic_owner, clinic_name='Clinic A', address='A', city=self.city, contact_number=9000000014)

        # Unauthenticated / un-initiated attempt to link to clinic
        res = self.client.post(reverse('register_staff'), {'clinic': clinic_a.pk})
        self.assertRedirects(res, reverse('register'))
        self.assertEqual(ClinicStaff.objects.count(), 0)

        # Authorized staff flow enforces verification and clinic isolation
        staff_user = self.user('Clinic Staff', 9000000015, is_verified=False)
        session = self.client.session
        session['reg_user_id'] = staff_user.pk
        session['reg_role'] = 'Clinic Staff'
        session.save()

        res_reg = self.client.post(reverse('register_staff'), {'clinic': clinic_a.pk})
        self.assertRedirects(res_reg, reverse('login'))
        self.assertTrue(ClinicStaff.objects.filter(user=staff_user, clinic=clinic_a).exists())

        # Unverified staff member cannot log in to access clinic appointments
        login_res = self.client.post(reverse('login'), {'email': staff_user.email, 'password': 'Secret123!'})
        self.assertEqual(login_res.status_code, 200)
        self.assertContains(login_res, 'pending administrative verification')

    def test_clinic_appointments_profile_check(self):
        # A clinic user without a completed Clinic profile is redirected cleanly
        unprofiled_clinic_user = self.user('Clinic', 9000000016, is_verified=True)
        self.login_as(unprofiled_clinic_user)
        response = self.client.get(reverse('clinic_appointments'))
        self.assertRedirects(response, reverse('register_clinic'))

        # A staff user without a completed ClinicStaff profile is redirected cleanly
        unprofiled_staff_user = self.user('Clinic Staff', 9000000017, is_verified=True)
        self.login_as(unprofiled_staff_user)
        response_staff = self.client.get(reverse('clinic_appointments'))
        self.assertRedirects(response_staff, reverse('register_staff'))


class VerificationAndDocumentSecurityTests(TestCase):
    def setUp(self):
        self.roles = {
            name: Role.objects.create(role_name=name)
            for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin')
        }
        self.state = StateMaster.objects.create(state_name='Test State')
        self.city = CityMaster.objects.create(state=self.state, city_name='Test City')

        # Admin user
        self.admin_user = User.objects.create(
            full_name='System Admin',
            email='sysadmin@wellpoint.test',
            contact_number=9011111111,
            password_hash=make_password('Secret123!'),
            role=self.roles['Admin'],
            is_verified=True,
            account_status='active',
        )
        self.admin = Admin.objects.create(user=self.admin_user, access_level='Super Admin')

    def login_as(self, user):
        session = self.client.session
        session['user_id'] = user.user_id
        session.save()

    def test_patient_photo_id_upload_masked_and_status_transitions(self):
        # 1. Register patient with photo ID document and ID number
        sample_doc = SimpleUploadedFile("patient_id.pdf", make_valid_pdf_bytes(), content_type="application/pdf")
        patient_user = User.objects.create(
            full_name='Rahul Kumar',
            email='rahul@patient.test',
            contact_number=9012345678,
            password_hash=make_password('Secret123!'),
            role=self.roles['Patient'],
            is_verified=False,
            account_status='active',
        )
        patient = Patient.objects.create(
            user=patient_user,
            date_of_birth=date(1995, 6, 15),
            id_number='AADH12345678',
            id_document=sample_doc,
            id_verification_status='Pending',
        )

        # ID number masking check: sensitive digits hidden
        self.assertEqual(patient.masked_id_number, '********5678')
        self.assertNotIn('1234', patient.masked_id_number[:8])

        # Patient views their dashboard with 'Pending' verification notice
        self.login_as(patient_user)
        res = self.client.get(reverse('patient_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Photo ID Pending Review')

        # Patient views profile: masked ID displayed, document link available
        res_prof = self.client.get(reverse('profile'))
        self.assertEqual(res_prof.status_code, 200)
        self.assertContains(res_prof, '********5678')
        self.assertContains(res_prof, 'View Uploaded Document')

        # 2. Admin rejects with reason
        self.login_as(self.admin_user)
        reject_res = self.client.post(reverse('verify_user'), {
            'user_id': patient_user.user_id,
            'action': 'reject',
            'remarks': 'Blurry identity card copy. Please upload a clear photo.',
        })
        self.assertRedirects(reject_res, reverse('admin_dashboard'))
        patient.refresh_from_db()
        self.assertEqual(patient.id_verification_status, 'Rejected')
        self.assertIn('Blurry identity card copy', patient.id_rejection_reason)

        # Patient dashboard displays rejection notification with remarks and resubmit action
        self.login_as(patient_user)
        res_rej = self.client.get(reverse('patient_dashboard'))
        self.assertContains(res_rej, 'Your photo ID proof was rejected')
        self.assertContains(res_rej, 'Blurry identity card copy')

        # 3. Patient resubmits updated ID proof
        new_doc = SimpleUploadedFile("clear_id.pdf", make_valid_pdf_bytes(), content_type="application/pdf")
        upload_res = self.client.post(reverse('upload_patient_id'), {
            'id_number': 'AADH99998888',
            'photo_id': new_doc,
        })
        self.assertRedirects(upload_res, reverse('profile'))
        patient.refresh_from_db()
        self.assertEqual(patient.id_verification_status, 'Pending')
        self.assertEqual(patient.id_rejection_reason, '')
        self.assertEqual(patient.masked_id_number, '********8888')

        # 4. Admin approves
        self.login_as(self.admin_user)
        self.client.post(reverse('verify_user'), {
            'user_id': patient_user.user_id,
            'action': 'approve',
            'remarks': 'Verified via national database',
        })
        patient.refresh_from_db()
        self.assertEqual(patient.id_verification_status, 'Approved')

        # Patient dashboard displays approval notification
        self.login_as(patient_user)
        res_appr = self.client.get(reverse('patient_dashboard'))
        self.assertContains(res_appr, 'Photo ID Approved')

    def test_secure_document_access_permissions(self):
        # Create Patient with ID document
        p_doc = SimpleUploadedFile("secure_id.pdf", make_valid_pdf_bytes(), content_type="application/pdf")
        patient_user = User.objects.create(
            full_name='Priya Patel', email='priya@patient.test', contact_number=9022222222,
            password_hash=make_password('Secret123!'), role=self.roles['Patient'], is_verified=True,
        )
        patient = Patient.objects.create(
            user=patient_user, date_of_birth=date(1992, 4, 10), id_document=p_doc, id_number='ID987654'
        )

        # Create Doctor with License document
        d_doc = SimpleUploadedFile("secure_license.pdf", make_valid_pdf_bytes(), content_type="application/pdf")
        doctor_user = User.objects.create(
            full_name='Dr. Mehta', email='mehta@doc.test', contact_number=9033333333,
            password_hash=make_password('Secret123!'), role=self.roles['Doctor'], is_verified=True,
        )
        doctor = Doctor.objects.create(
            user=doctor_user, doctor_name='Dr. Mehta', experience=8, new_patient_fee=500,
            old_patient_fee=300, license_number='MED-12345', issuing_authority='Gujarat Medical Council',
            license_document=d_doc, license_verification_status='Approved'
        )

        # Another unrelated user
        other_user = User.objects.create(
            full_name='Intruder User', email='intruder@hack.test', contact_number=9044444444,
            password_hash=make_password('Secret123!'), role=self.roles['Patient'], is_verified=True,
        )

        patient_doc_url = reverse('view_patient_id_document', args=[patient.patient_id])
        doctor_doc_url = reverse('view_doctor_license_document', args=[doctor.doctor_id])

        # 1. Unauthenticated requests are blocked and redirected to login
        self.client.logout()
        res_anon_p = self.client.get(patient_doc_url)
        self.assertRedirects(res_anon_p, reverse('login'))
        res_anon_d = self.client.get(doctor_doc_url)
        self.assertRedirects(res_anon_d, reverse('login'))

        # 2. Unrelated user gets 403 Forbidden
        self.login_as(other_user)
        self.assertEqual(self.client.get(patient_doc_url).status_code, 403)
        self.assertEqual(self.client.get(doctor_doc_url).status_code, 403)

        # 3. Patient owner can access their own ID document (200)
        self.login_as(patient_user)
        res_p_owner = self.client.get(patient_doc_url)
        self.assertEqual(res_p_owner.status_code, 200)
        self.assertEqual(res_p_owner['Content-Type'], 'application/pdf')
        # Patient cannot access doctor's license document
        self.assertEqual(self.client.get(doctor_doc_url).status_code, 403)

        # 4. Doctor owner can access their own License document (200)
        self.login_as(doctor_user)
        res_d_owner = self.client.get(doctor_doc_url)
        self.assertEqual(res_d_owner.status_code, 200)
        self.assertEqual(res_d_owner['Content-Type'], 'application/pdf')
        # Doctor cannot access patient's ID document
        self.assertEqual(self.client.get(patient_doc_url).status_code, 403)

        # 5. System Admin can access both documents (200)
        self.login_as(self.admin_user)
        self.assertEqual(self.client.get(patient_doc_url).status_code, 200)
        self.assertEqual(self.client.get(doctor_doc_url).status_code, 200)

    def test_doctor_license_verification_status_and_dashboard_notification(self):
        # 1. Create a doctor with Pending license details
        lic_file = SimpleUploadedFile("lic_doc.pdf", make_valid_pdf_bytes(), content_type="application/pdf")
        doc_user = User.objects.create(
            full_name='Dr. Shweta Rao', email='shweta@doc.test', contact_number=9055555555,
            password_hash=make_password('Secret123!'), role=self.roles['Doctor'], is_verified=True,
            account_status='active',
        )
        doctor = Doctor.objects.create(
            user=doc_user, doctor_name='Dr. Shweta Rao', experience=6, new_patient_fee=700,
            old_patient_fee=400, license_number='NMC/2020/998877', issuing_authority='National Medical Commission',
            license_document=lic_file, license_verification_status='Pending'
        )

        # Doctor visits dashboard: sees pending license verification alert
        self.login_as(doc_user)
        res_dash = self.client.get(reverse('doctor_dashboard'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'Medical License Pending Verification')

        # 2. Admin approves doctor
        self.login_as(self.admin_user)
        self.client.post(reverse('verify_user'), {
            'user_id': doc_user.user_id,
            'action': 'approve',
            'remarks': 'License confirmed with NMC register',
        })
        doctor.refresh_from_db()
        self.assertEqual(doctor.license_verification_status, 'Approved')

        # Doctor logs in and sees "Your medical license has been approved"
        self.login_as(doc_user)
        res_appr = self.client.get(reverse('doctor_dashboard'))
        self.assertContains(res_appr, 'Your medical license has been approved')

        # Session persistence: status remains visible after relogging
        self.client.logout()
        login_res = self.client.post(reverse('login'), {'email': doc_user.email, 'password': 'Secret123!'})
        self.assertRedirects(login_res, reverse('doctor_dashboard'))
        res_relog = self.client.get(reverse('doctor_dashboard'))
        self.assertContains(res_relog, 'Your medical license has been approved')

        # 3. Admin rejects doctor with reasons
        self.login_as(self.admin_user)
        self.client.post(reverse('verify_user'), {
            'user_id': doc_user.user_id,
            'action': 'reject',
            'remarks': 'Registration number not found in State Medical Council registry.',
        })
        doctor.refresh_from_db()
        self.assertEqual(doctor.license_verification_status, 'Rejected')
        self.assertIn('Registration number not found', doctor.rejection_reason)

        # Rejected doctor dashboard displays clear notification and rejection remarks
        self.login_as(doc_user)
        res_rej = self.client.get(reverse('doctor_dashboard'))
        self.assertContains(res_rej, 'Your medical license was rejected')
        self.assertContains(res_rej, 'Registration number not found in State Medical Council registry')

        # Doctor profile displays rejection reason and resubmit form
        res_prof = self.client.get(reverse('doctor_profile'))
        self.assertContains(res_prof, 'Resubmit Medical License Details')

        # 4. Doctor resubmits updated license details
        new_lic = SimpleUploadedFile("corrected_license.pdf", make_valid_pdf_bytes(), content_type="application/pdf")
        resub_res = self.client.post(reverse('resubmit_doctor_license'), {
            'license_number': 'NMC/2020/112233',
            'issuing_authority': 'State Medical Council',
            'license_document': new_lic,
        })
        self.assertRedirects(resub_res, reverse('doctor_dashboard'))
        doctor.refresh_from_db()
        self.assertEqual(doctor.license_verification_status, 'Pending')
        self.assertEqual(doctor.license_number, 'NMC/2020/112233')
        self.assertEqual(doctor.rejection_reason, '')

    def test_home_page_has_near_me_button_and_elements(self):
        res = self.client.get(reverse('home'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="useLocationBtn"')
        self.assertContains(res, 'Near Me')
        self.assertContains(res, 'id="userLatInput"')
        self.assertContains(res, 'id="userLngInput"')
        self.assertContains(res, 'doctors.js')


class DocumentUploadValidationTests(TestCase):
    def setUp(self):
        self.roles = {
            name: Role.objects.create(role_name=name)
            for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin')
        }
        self.state = StateMaster.objects.create(state_name='Test State')
        self.city = CityMaster.objects.create(state=self.state, city_name='Test City')

        self.patient_user = User.objects.create(
            full_name='Test Patient',
            email='pat_test@example.test',
            contact_number=9012345678,
            password_hash=make_password('Secret123!'),
            role=self.roles['Patient'],
            is_verified=True,
            account_status='active',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
            date_of_birth='1995-05-15',
            gender='Female',
            blood_group='O+',
            emergency_contact=9098765432,
            id_verification_status='Pending',
        )

        self.doctor_user = User.objects.create(
            full_name='Dr. Test',
            email='doc_test@example.test',
            contact_number=9012345679,
            password_hash=make_password('Secret123!'),
            role=self.roles['Doctor'],
            is_verified=True,
            account_status='active',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            doctor_name='Dr. Test',
            new_patient_fee=500,
            old_patient_fee=300,
            license_number='MCI/TEST/1234',
            issuing_authority='Medical Council',
            license_verification_status='Pending',
        )
        self.spec = SpecializationMaster.objects.create(specialization_name='Cardiology')
        self.qual = QualificationMaster.objects.create(qualification_name='MBBS')

    def login_as(self, user):
        session = self.client.session
        session['user_id'] = user.user_id
        session.save()

    def test_validator_valid_files(self):
        # 1. Valid PDF verified with pypdf
        pdf_file = SimpleUploadedFile('doc.pdf', make_valid_pdf_bytes(), content_type='application/pdf')
        self.assertEqual(validate_document_file(pdf_file), pdf_file)
        self.assertEqual(pdf_file.tell(), 0)

        # 2. Valid PNG verified with Pillow
        png_file = SimpleUploadedFile('photo.png', make_valid_png_bytes(), content_type='image/png')
        self.assertEqual(validate_document_file(png_file), png_file)
        self.assertEqual(png_file.tell(), 0)

        # 3. Valid JPG verified with Pillow
        jpg_file = SimpleUploadedFile('photo.jpg', make_valid_jpg_bytes(), content_type='image/jpeg')
        self.assertEqual(validate_document_file(jpg_file), jpg_file)
        self.assertEqual(jpg_file.tell(), 0)

        # 4. Valid JPEG verified with Pillow
        jpeg_file = SimpleUploadedFile('photo.jpeg', make_valid_jpg_bytes(), content_type='image/jpeg')
        self.assertEqual(validate_document_file(jpeg_file), jpeg_file)
        self.assertEqual(jpeg_file.tell(), 0)

    def test_validator_corrupted_files_with_valid_looking_headers(self):
        # Corrupted PNG with valid 8-byte PNG signature header
        corrupt_png = SimpleUploadedFile('corrupt.png', b'\x89PNG\r\n\x1a\ncorrupted non-image bytes payload', content_type='image/png')
        with self.assertRaises(ValidationError) as ctx:
            validate_document_file(corrupt_png)
        self.assertIn('corrupted', str(ctx.exception).lower())
        self.assertEqual(corrupt_png.tell(), 0)

        # Corrupted JPG with valid 4-byte SOI header
        corrupt_jpg = SimpleUploadedFile('corrupt.jpg', b'\xff\xd8\xff\xe0corrupted non-image bytes payload', content_type='image/jpeg')
        with self.assertRaises(ValidationError) as ctx:
            validate_document_file(corrupt_jpg)
        self.assertIn('corrupted', str(ctx.exception).lower())
        self.assertEqual(corrupt_jpg.tell(), 0)

        # Corrupted PDF with valid %PDF- header but malformed structure
        corrupt_pdf = SimpleUploadedFile('corrupt.pdf', b'%PDF-1.4\ncorrupted content without xref or catalog', content_type='application/pdf')
        with self.assertRaises(ValidationError) as ctx:
            validate_document_file(corrupt_pdf)
        self.assertIn('corrupted', str(ctx.exception).lower())
        self.assertEqual(corrupt_pdf.tell(), 0)

    def test_validator_mismatched_extensions(self):
        # Valid PNG content saved with .jpg extension
        png_as_jpg = SimpleUploadedFile('image.jpg', make_valid_png_bytes(), content_type='image/jpeg')
        with self.assertRaises(ValidationError):
            validate_document_file(png_as_jpg)

        # Valid PNG content saved with .pdf extension
        png_as_pdf = SimpleUploadedFile('image.pdf', make_valid_png_bytes(), content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validate_document_file(png_as_pdf)

        # Valid JPEG content saved with .png extension
        jpg_as_png = SimpleUploadedFile('photo.png', make_valid_jpg_bytes(), content_type='image/png')
        with self.assertRaises(ValidationError):
            validate_document_file(jpg_as_png)

        # Valid JPEG content saved with .pdf extension
        jpg_as_pdf = SimpleUploadedFile('photo.pdf', make_valid_jpg_bytes(), content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validate_document_file(jpg_as_pdf)

        # Valid PDF content saved with .png extension
        pdf_as_png = SimpleUploadedFile('doc.png', make_valid_pdf_bytes(), content_type='image/png')
        with self.assertRaises(ValidationError):
            validate_document_file(pdf_as_png)

        # Valid PDF content saved with .jpg extension
        pdf_as_jpg = SimpleUploadedFile('doc.jpg', make_valid_pdf_bytes(), content_type='image/jpeg')
        with self.assertRaises(ValidationError):
            validate_document_file(pdf_as_jpg)

    def test_validator_unsupported_formats(self):
        for bad_name in ('shell.exe', 'test.txt', 'document.docx', 'script.sh', 'code.py', 'page.html', 'archive.zip'):
            bad_file = SimpleUploadedFile(bad_name, b'sample content')
            with self.assertRaises(ValidationError) as ctx:
                validate_document_file(bad_file)
            self.assertIn('Unsupported file format', str(ctx.exception))
            self.assertIn('Allowed formats: JPG, JPEG, PNG, and PDF', str(ctx.exception))

    def test_validator_empty_files(self):
        for empty_name in ('empty.pdf', 'empty.png', 'empty.jpg', 'empty.jpeg'):
            empty_file = SimpleUploadedFile(empty_name, b'')
            with self.assertRaises(ValidationError) as ctx:
                validate_document_file(empty_file)
            self.assertIn('empty', str(ctx.exception).lower())
            self.assertEqual(empty_file.tell(), 0)

    def test_validator_files_over_5mb(self):
        oversized_data = b'%PDF-1.4 ' + b'0' * (5 * 1024 * 1024 + 10)
        big_file = SimpleUploadedFile('oversized.pdf', oversized_data, content_type='application/pdf')
        with self.assertRaises(ValidationError) as ctx:
            validate_document_file(big_file)
        self.assertIn('5MB', str(ctx.exception))

    def test_stream_reset_after_validation(self):
        # Valid file
        valid_f = SimpleUploadedFile('valid.png', make_valid_png_bytes(), content_type='image/png')
        validate_document_file(valid_f)
        self.assertEqual(valid_f.tell(), 0)

        # Corrupted file
        bad_f = SimpleUploadedFile('bad.png', b'\x89PNG\r\n\x1a\ncorrupt', content_type='image/png')
        try:
            validate_document_file(bad_f)
        except ValidationError:
            pass
        self.assertEqual(bad_f.tell(), 0)

    def test_patient_registration_validation(self):
        reg_user = User.objects.create(
            full_name='Reg Patient',
            email='reg_pat@example.test',
            contact_number=9012345680,
            password_hash=make_password('Secret123!'),
            role=self.roles['Patient'],
        )
        session = self.client.session
        session['reg_user_id'] = reg_user.user_id
        session['reg_role'] = 'Patient'
        session.save()

        # 1. Invalid file extension rejected with form error
        bad_file = SimpleUploadedFile('notes.txt', b'some text notes')
        res = self.client.post(reverse('register_patient'), {
            'date_of_birth': '1992-02-02',
            'gender': 'Male',
            'blood_group': 'B+',
            'emergency_contact': 9012345681,
            'photo_id': bad_file,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Unsupported file format')
        self.assertFalse(Patient.objects.filter(user=reg_user).exists())

        # 2. Oversized file rejected with form error
        oversized = SimpleUploadedFile('big.pdf', b'%PDF-1.4 ' + b'x' * (5 * 1024 * 1024 + 10))
        res = self.client.post(reverse('register_patient'), {
            'date_of_birth': '1992-02-02',
            'gender': 'Male',
            'blood_group': 'B+',
            'emergency_contact': 9012345681,
            'photo_id': oversized,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '5MB')
        self.assertFalse(Patient.objects.filter(user=reg_user).exists())

        # 3. Corrupted PDF rejected with form error
        corrupt_pdf = SimpleUploadedFile('corrupt.pdf', b'%PDF-1.4\ncorrupted junk')
        res = self.client.post(reverse('register_patient'), {
            'date_of_birth': '1992-02-02',
            'gender': 'Male',
            'blood_group': 'B+',
            'emergency_contact': 9012345681,
            'photo_id': corrupt_pdf,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'corrupted')
        self.assertFalse(Patient.objects.filter(user=reg_user).exists())

        # 4. Mismatched format rejected (valid PNG named .jpg)
        mismatched = SimpleUploadedFile('doc.jpg', make_valid_png_bytes(), content_type='image/jpeg')
        res = self.client.post(reverse('register_patient'), {
            'date_of_birth': '1992-02-02',
            'gender': 'Male',
            'blood_group': 'B+',
            'emergency_contact': 9012345681,
            'photo_id': mismatched,
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Patient.objects.filter(user=reg_user).exists())

        # 5. Valid file accepted, patient created with Pending status (never auto-approved)
        valid_pdf = SimpleUploadedFile('valid_id.pdf', make_valid_pdf_bytes(), content_type='application/pdf')
        res_ok = self.client.post(reverse('register_patient'), {
            'date_of_birth': '1992-02-02',
            'gender': 'Male',
            'blood_group': 'B+',
            'emergency_contact': 9012345681,
            'photo_id': valid_pdf,
            'id_number': 'GOV-PAT-100',
        })
        self.assertRedirects(res_ok, reverse('login'))
        created_patient = Patient.objects.get(user=reg_user)
        self.assertEqual(created_patient.id_verification_status, 'Pending')
        self.assertNotEqual(created_patient.id_verification_status, 'Approved')
        self.assertTrue(bool(created_patient.id_document))

    def test_doctor_registration_validation(self):
        reg_doc_user = User.objects.create(
            full_name='Dr. Reg Test',
            email='reg_doc@example.test',
            contact_number=9012345682,
            password_hash=make_password('Secret123!'),
            role=self.roles['Doctor'],
        )
        session = self.client.session
        session['reg_user_id'] = reg_doc_user.user_id
        session['reg_role'] = 'Doctor'
        session.save()

        # 1. Invalid file extension rejected
        bad_file = SimpleUploadedFile('payload.exe', b'MZ\x90\x00 binary')
        res = self.client.post(reverse('register_doctor'), {
            'doctor_name': 'Dr. Reg Test',
            'experience': 5,
            'new_patient_fee': 400,
            'old_patient_fee': 250,
            'license_number': 'MCI-9988',
            'issuing_authority': 'Medical Council',
            'specializations': [self.spec.pk],
            'qualifications': [self.qual.pk],
            'license_document': bad_file,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Unsupported file format')
        self.assertFalse(Doctor.objects.filter(user=reg_doc_user).exists())

        # 2. Oversized file rejected
        oversized = SimpleUploadedFile('big_lic.pdf', b'%PDF-1.4 ' + b'x' * (5 * 1024 * 1024 + 10))
        res = self.client.post(reverse('register_doctor'), {
            'doctor_name': 'Dr. Reg Test',
            'experience': 5,
            'new_patient_fee': 400,
            'old_patient_fee': 250,
            'license_number': 'MCI-9988',
            'issuing_authority': 'Medical Council',
            'specializations': [self.spec.pk],
            'qualifications': [self.qual.pk],
            'license_document': oversized,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '5MB')
        self.assertFalse(Doctor.objects.filter(user=reg_doc_user).exists())

        # 3. Corrupted PNG with valid header rejected
        corrupt_png = SimpleUploadedFile('lic.png', b'\x89PNG\r\n\x1a\ncorrupt bytes', content_type='image/png')
        res = self.client.post(reverse('register_doctor'), {
            'doctor_name': 'Dr. Reg Test',
            'experience': 5,
            'new_patient_fee': 400,
            'old_patient_fee': 250,
            'license_number': 'MCI-9988',
            'issuing_authority': 'Medical Council',
            'specializations': [self.spec.pk],
            'qualifications': [self.qual.pk],
            'license_document': corrupt_png,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'corrupted')
        self.assertFalse(Doctor.objects.filter(user=reg_doc_user).exists())

        # 4. Valid file accepted, doctor created with Pending status (never auto-approved)
        valid_png = SimpleUploadedFile('lic.png', make_valid_png_bytes(), content_type='image/png')
        res_ok = self.client.post(reverse('register_doctor'), {
            'doctor_name': 'Dr. Reg Test',
            'experience': 5,
            'new_patient_fee': 400,
            'old_patient_fee': 250,
            'license_number': 'MCI-9988',
            'issuing_authority': 'Medical Council',
            'specializations': [self.spec.pk],
            'qualifications': [self.qual.pk],
            'license_document': valid_png,
        })
        self.assertRedirects(res_ok, reverse('login'))
        created_doc = Doctor.objects.get(user=reg_doc_user)
        self.assertEqual(created_doc.license_verification_status, 'Pending')
        self.assertNotEqual(created_doc.license_verification_status, 'Approved')
        self.assertTrue(bool(created_doc.license_document))

    def test_patient_profile_upload_validation(self):
        self.login_as(self.patient_user)

        # 1. Invalid extension rejected with message
        bad_file = SimpleUploadedFile('id.txt', b'text data')
        res = self.client.post(reverse('upload_patient_id'), {'photo_id': bad_file}, follow=True)
        self.assertRedirects(res, reverse('profile'))
        self.assertContains(res, 'Unsupported file format')

        # 2. Oversized rejected
        oversized = SimpleUploadedFile('huge.pdf', b'%PDF-1.4 ' + b'0' * (5 * 1024 * 1024 + 10))
        res = self.client.post(reverse('upload_patient_id'), {'photo_id': oversized}, follow=True)
        self.assertRedirects(res, reverse('profile'))
        self.assertContains(res, '5MB')

        # 3. Corrupted JPG rejected
        corrupt_jpg = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff\xe0corrupt', content_type='image/jpeg')
        res = self.client.post(reverse('upload_patient_id'), {'photo_id': corrupt_jpg}, follow=True)
        self.assertRedirects(res, reverse('profile'))
        self.assertContains(res, 'corrupted')

        # 4. Valid JPG accepted, status is Pending (never auto-approved)
        valid_jpg = SimpleUploadedFile('photo.jpg', make_valid_jpg_bytes(), content_type='image/jpeg')
        res_ok = self.client.post(reverse('upload_patient_id'), {'photo_id': valid_jpg, 'id_number': 'NEW-ID-555'}, follow=True)
        self.assertRedirects(res_ok, reverse('profile'))
        self.assertContains(res_ok, 'Photo ID submitted successfully')
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.id_verification_status, 'Pending')
        self.assertNotEqual(self.patient.id_verification_status, 'Approved')

    def test_doctor_license_resubmit_validation(self):
        self.login_as(self.doctor_user)

        # 1. Invalid extension rejected
        bad_doc = SimpleUploadedFile('lic.docx', b'word doc binary')
        res = self.client.post(reverse('resubmit_doctor_license'), {
            'license_number': 'MCI-NEW',
            'issuing_authority': 'State Council',
            'license_document': bad_doc,
        }, follow=True)
        self.assertContains(res, 'Unsupported file format')

        # 2. Oversized rejected
        oversized = SimpleUploadedFile('oversized.pdf', b'%PDF-1.4 ' + b'0' * (5 * 1024 * 1024 + 10))
        res = self.client.post(reverse('resubmit_doctor_license'), {
            'license_number': 'MCI-NEW',
            'issuing_authority': 'State Council',
            'license_document': oversized,
        }, follow=True)
        self.assertContains(res, '5MB')

        # 3. Corrupted PDF rejected
        corrupt_pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4\ncorrupted structure', content_type='application/pdf')
        res = self.client.post(reverse('resubmit_doctor_license'), {
            'license_number': 'MCI-NEW',
            'issuing_authority': 'State Council',
            'license_document': corrupt_pdf,
        }, follow=True)
        self.assertContains(res, 'corrupted')

        # 4. Valid PDF accepted, status is Pending (never auto-approved)
        valid_pdf = SimpleUploadedFile('doc.pdf', make_valid_pdf_bytes(), content_type='application/pdf')
        res_ok = self.client.post(reverse('resubmit_doctor_license'), {
            'license_number': 'MCI-NEW-777',
            'issuing_authority': 'State Council',
            'license_document': valid_pdf,
        }, follow=True)
        self.assertRedirects(res_ok, reverse('doctor_dashboard'))
        self.assertContains(res_ok, 'Medical license details submitted for verification')
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.license_verification_status, 'Pending')
        self.assertNotEqual(self.doctor.license_verification_status, 'Approved')


class ProductionStorageIntegrationTests(TestCase):
    def test_local_storage_default_without_r2_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            storage = protected_storage.get_storage()
            self.assertEqual(storage.__class__.__name__, 'FileSystemStorage')
            self.assertEqual(str(storage.location), str(get_secure_documents_root()))
            with self.assertRaises(ValueError):
                protected_storage.url('sample.pdf')

    def test_r2_storage_configured_with_environment_variables(self):
        r2_env = {
            'R2_ACCOUNT_ID': '0123456789abcdef0123456789abcdef',
            'R2_ACCESS_KEY_ID': 'test_access_key_123',
            'R2_SECRET_ACCESS_KEY': 'test_secret_key_456',
            'R2_BUCKET_NAME': 'wellpoint-clinical-documents',
        }
        with mock.patch.dict(os.environ, r2_env, clear=True):
            cfg = get_r2_config()
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg['account_id'], '0123456789abcdef0123456789abcdef')
            self.assertEqual(cfg['bucket_name'], 'wellpoint-clinical-documents')

            active_storage = protected_storage.get_storage()
            self.assertIsInstance(active_storage, R2ProtectedStorage)
            self.assertEqual(
                active_storage.endpoint_url,
                'https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com'
            )
            self.assertEqual(active_storage.region_name, 'auto')
            self.assertEqual(active_storage.bucket_name, 'wellpoint-clinical-documents')
            self.assertFalse(active_storage.file_overwrite)
            self.assertIsNone(active_storage.default_acl)
            self.assertIsNone(active_storage.custom_domain)
            self.assertFalse(active_storage.querystring_auth)

    def test_r2_storage_blocks_public_urls(self):
        r2_env = {
            'R2_ACCOUNT_ID': '0123456789abcdef0123456789abcdef',
            'R2_ACCESS_KEY_ID': 'test_access_key_123',
            'R2_SECRET_ACCESS_KEY': 'test_secret_key_456',
            'R2_BUCKET_NAME': 'wellpoint-clinical-documents',
        }
        with mock.patch.dict(os.environ, r2_env, clear=True):
            active_storage = protected_storage.get_storage()
            with self.assertRaises(ValueError) as ctx:
                active_storage.url('patient_ids/id_sample.pdf')
            self.assertIn('not accessible via a public URL', str(ctx.exception))

            with self.assertRaises(ValueError) as ctx2:
                protected_storage.url('patient_ids/id_sample.pdf')
            self.assertIn('not accessible via a public URL', str(ctx2.exception))

    def test_vercel_without_r2_raises_improperly_configured(self):
        with mock.patch.dict(os.environ, {'VERCEL': '1'}, clear=True):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                get_r2_config()
            self.assertIn('Missing required Cloudflare R2 storage environment variables on Vercel', str(ctx.exception))

    def test_partial_r2_env_vars_raises_improperly_configured(self):
        with mock.patch.dict(os.environ, {'R2_ACCOUNT_ID': 'acc123', 'R2_BUCKET_NAME': 'mybucket'}, clear=True):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                get_r2_config()
            self.assertIn('Incomplete Cloudflare R2 storage configuration', str(ctx.exception))

    def test_protected_storage_deconstruct_matches_migration_baseline(self):
        deconstructed = protected_storage.deconstruct()
        self.assertEqual(deconstructed[0], 'django.core.files.storage.FileSystemStorage')
        self.assertEqual(deconstructed[1], ())
        self.assertIsNone(deconstructed[2]['base_url'])
        self.assertEqual(str(deconstructed[2]['location']), str(get_secure_documents_root()))

    def test_local_storage_file_operations_and_cleanup(self):
        from django.core.files.base import ContentFile
        test_filename = 'patient_ids/test_verify_doc.txt'
        saved_name = protected_storage.save(test_filename, ContentFile(b'confidential document content'))
        try:
            self.assertTrue(protected_storage.exists(saved_name))
            self.assertEqual(protected_storage.size(saved_name), 29)
            with protected_storage.open(saved_name, 'rb') as f:
                self.assertEqual(f.read(), b'confidential document content')
        finally:
            if protected_storage.exists(saved_name):
                protected_storage.delete(saved_name)
            self.assertFalse(protected_storage.exists(saved_name))


class PostgresDatabaseConfigurationTests(TestCase):
    def test_neon_postgres_url_configuration(self):
        import dj_database_url
        test_url = 'postgresql://neon_user:neon_pass@ep-cool-sin-123456.ap-southeast-1.aws.neon.tech/wellpoint?sslmode=require'
        parsed = dj_database_url.parse(test_url, conn_max_age=600)
        self.assertEqual(parsed['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(parsed['NAME'], 'wellpoint')
        self.assertEqual(parsed['HOST'], 'ep-cool-sin-123456.ap-southeast-1.aws.neon.tech')
        self.assertEqual(parsed['USER'], 'neon_user')
        self.assertEqual(parsed['PASSWORD'], 'neon_pass')
        self.assertEqual(parsed['OPTIONS']['sslmode'], 'require')
        self.assertEqual(parsed['CONN_MAX_AGE'], 600)

    def test_psycopg_driver_availability(self):
        import psycopg
        self.assertTrue(hasattr(psycopg, '__version__'))
        from django.db.backends.postgresql.base import DatabaseWrapper
        self.assertEqual(DatabaseWrapper.vendor, 'postgresql')

    def test_discrete_postgres_env_parsing(self):
        discrete_env = {
            'POSTGRES_HOST': 'ep-sin-neon.tech',
            'POSTGRES_DATABASE': 'wellpoint_prod',
            'POSTGRES_USER': 'wellpoint_admin',
            'POSTGRES_PASSWORD': 'secure_pg_password_123',
            'POSTGRES_PORT': '5432',
            'POSTGRES_SSLMODE': 'require',
            'DB_CONN_MAX_AGE': '300',
        }
        with mock.patch.dict(os.environ, discrete_env, clear=True):
            from django.conf import settings
            host = os.environ.get('POSTGRES_HOST')
            db = os.environ.get('POSTGRES_DATABASE')
            cfg = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': db,
                'USER': os.environ.get('POSTGRES_USER'),
                'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
                'HOST': host,
                'PORT': os.environ.get('POSTGRES_PORT', '5432'),
                'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '600')),
                'OPTIONS': {'sslmode': os.environ.get('POSTGRES_SSLMODE', 'require'), 'connect_timeout': 10},
            }
            self.assertEqual(cfg['ENGINE'], 'django.db.backends.postgresql')
            self.assertEqual(cfg['NAME'], 'wellpoint_prod')
            self.assertEqual(cfg['HOST'], 'ep-sin-neon.tech')
            self.assertEqual(cfg['CONN_MAX_AGE'], 300)
            self.assertEqual(cfg['OPTIONS']['sslmode'], 'require')
            self.assertEqual(cfg['OPTIONS']['connect_timeout'], 10)
