from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CityMaster, Clinic, DayMaster, Patient, Role, StateMaster, User
from appointments.models import Appointment
from .models import Doctor, DoctorAvailability, DoctorClinic, DoctorSpecialization, SpecializationMaster


class DoctorWorkflowTests(TestCase):
    def setUp(self):
        self.doctor_role = Role.objects.create(role_name='Doctor')
        self.clinic_role = Role.objects.create(role_name='Clinic')
        state = StateMaster.objects.create(state_name='State')
        city = CityMaster.objects.create(state=state, city_name='Mumbai')
        clinic_user = User.objects.create(full_name='Clinic', email='clinic@d.test', contact_number=9020000001, password_hash=make_password('Secret123!'), role=self.clinic_role)
        self.clinic = Clinic.objects.create(user=clinic_user, clinic_name='Care', address='Address', city=city, contact_number=9020000001)
        user = User.objects.create(full_name='Aarav', email='doctor@d.test', contact_number=9020000002, password_hash=make_password('Secret123!'), role=self.doctor_role)
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

    def test_specialization_exact_matching_ent_does_not_match_dentist(self):
        ent_spec = SpecializationMaster.objects.create(specialization_name='ENT')
        dentist_spec = SpecializationMaster.objects.create(specialization_name='Dentist')

        ent_user = User.objects.create(
            full_name='Dr. ENT Specialist', email='ent@d.test', contact_number=9020000010,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        ent_doctor = Doctor.objects.create(
            user=ent_user, doctor_name='Dr. Ear Throat', experience=5, new_patient_fee=400, old_patient_fee=250
        )
        DoctorSpecialization.objects.create(doctor=ent_doctor, specialization=ent_spec)
        DoctorClinic.objects.create(doctor=ent_doctor, clinic=self.clinic)

        dentist_user = User.objects.create(
            full_name='Dr. Dental Care', email='dentist@d.test', contact_number=9020000011,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        dentist_doctor = Doctor.objects.create(
            user=dentist_user, doctor_name='Dr. Tooth Smile', experience=6, new_patient_fee=450, old_patient_fee=300
        )
        DoctorSpecialization.objects.create(doctor=dentist_doctor, specialization=dentist_spec)
        DoctorClinic.objects.create(doctor=dentist_doctor, clinic=self.clinic)

        # 1. ENT query matches ENT doctor, not Dentist or Cardiology
        response_ent = self.client.get(reverse('doctor_list'), {'specialization': 'ENT'})
        self.assertContains(response_ent, 'Dr. Ear Throat')
        self.assertNotContains(response_ent, 'Dr. Tooth Smile')
        self.assertNotContains(response_ent, 'Aarav Sharma')

        # 2. Whitespace and case-insensitive normalization: '  ent  '
        response_ent_norm = self.client.get(reverse('doctor_list'), {'specialization': '  ent  '})
        self.assertContains(response_ent_norm, 'Dr. Ear Throat')
        self.assertNotContains(response_ent_norm, 'Dr. Tooth Smile')

        # 3. Dentist query matches Dentist doctor, not ENT
        response_dentist = self.client.get(reverse('doctor_list'), {'specialization': 'Dentist'})
        self.assertContains(response_dentist, 'Dr. Tooth Smile')
        self.assertNotContains(response_dentist, 'Dr. Ear Throat')

        # 4. Other exact match (Cardiology) still works
        response_cardio = self.client.get(reverse('doctor_list'), {'specialization': 'Cardiology'})
        self.assertContains(response_cardio, 'Aarav Sharma')
        self.assertNotContains(response_cardio, 'Dr. Ear Throat')
        self.assertNotContains(response_cardio, 'Dr. Tooth Smile')

        # 5. Symptom query that predicts ENT does not match Dentist doctor
        response_symptoms = self.client.get(reverse('doctor_list'), {'symptoms': 'Ear ache, hearing loss, ringing in ears'})
        self.assertContains(response_symptoms, 'Dr. Ear Throat')
        self.assertNotContains(response_symptoms, 'Dr. Tooth Smile')

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

    def test_adding_availability_preserves_unrelated_existing_slots(self):
        existing = DoctorAvailability.objects.create(doctor=self.doctor, clinic=self.clinic, day=self.day, start_time='09:00', end_time='10:00')
        self.login_doctor()
        self.client.post(reverse('doctor_availability'), {f'start_{self.day.pk}': '14:00', f'end_{self.day.pk}': '15:00', f'clinics_{self.day.pk}': self.clinic.pk})
        self.assertTrue(DoctorAvailability.objects.filter(pk=existing.pk).exists())
        self.assertTrue(DoctorAvailability.objects.filter(doctor=self.doctor, start_time='14:00', end_time='15:00').exists())

    def test_geolocation_orders_doctors_by_proximity(self):
        # Set clinic coordinates for Mumbai (self.clinic)
        self.clinic.latitude = 19.0760
        self.clinic.longitude = 72.8777
        self.clinic.save()

        # Create a second clinic in Pune (~120km away) and doctor
        pune_city = CityMaster.objects.create(state=self.clinic.city.state, city_name='Pune')
        pune_user = User.objects.create(
            full_name='Pune Clinic', email='pune_clinic@d.test', contact_number=9020000088,
            password_hash=make_password('Secret123!'), role=self.clinic_role
        )
        pune_clinic = Clinic.objects.create(
            user=pune_user, clinic_name='Pune Health Center', address='Pune Camp',
            city=pune_city, contact_number=9020000088, latitude=18.5204, longitude=73.8567
        )
        pune_doc_user = User.objects.create(
            full_name='Dr. Pune Doctor', email='pune_doc@d.test', contact_number=9020000089,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        pune_doctor = Doctor.objects.create(
            user=pune_doc_user, doctor_name='Dr. Pune Cardiologist', experience=10,
            new_patient_fee=600, old_patient_fee=400
        )
        DoctorClinic.objects.create(doctor=pune_doctor, clinic=pune_clinic)
        DoctorSpecialization.objects.create(doctor=pune_doctor, specialization=self.spec)

        # Patient searches from near Mumbai (19.0770, 72.8780)
        res = self.client.get(reverse('doctor_list'), {
            'user_lat': '19.0770',
            'user_lng': '72.8780',
            'location': 'Current Location'
        })
        self.assertEqual(res.status_code, 200)
        doctors_in_context = list(res.context['doctors'])

        # Doctor in Mumbai should be first (closest, < 1 km)
        self.assertEqual(doctors_in_context[0].doctor_id, self.doctor.doctor_id)
        self.assertIsNotNone(doctors_in_context[0].distance_km)
        self.assertLess(doctors_in_context[0].distance_km, 5.0)

        # Doctor in Pune should be second (~120 km)
        self.assertEqual(doctors_in_context[1].doctor_id, pune_doctor.doctor_id)
        self.assertGreater(doctors_in_context[1].distance_km, 50.0)

        # Proximity banner and distance badge appear in HTML
        self.assertContains(res, 'Showing eligible doctors ordered by proximity')
        self.assertContains(res, 'km away')

    def test_invalid_geolocation_handled_gracefully(self):
        # Coordinates out of bounds or non-numeric should safely fall back
        res = self.client.get(reverse('doctor_list'), {
            'user_lat': '999.0',
            'user_lng': 'invalid_lng'
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['has_user_location'])
        self.assertContains(res, 'Aarav Sharma')

    def test_manual_location_search_by_city_and_locality(self):
        # Update self.clinic with locality in address
        self.clinic.address = 'University Road, Navrangpura'
        self.clinic.save()

        # Create doctor 2 in Satellite, Ahmedabad
        state = self.clinic.city.state
        amd_city = CityMaster.objects.create(state=state, city_name='Ahmedabad')
        clinic2_user = User.objects.create(
            full_name='Satellite Clinic', email='sat_clinic@d.test', contact_number=9020000071,
            password_hash=make_password('Secret123!'), role=self.clinic_role
        )
        clinic2 = Clinic.objects.create(
            user=clinic2_user, clinic_name='Satellite Health Center',
            address='Shivranjani Cross Roads, Satellite', city=amd_city, contact_number=9020000071
        )
        doc2_user = User.objects.create(
            full_name='Dr. Satellite Doc', email='sat_doc@d.test', contact_number=9020000072,
            password_hash=make_password('Secret123!'), role=self.doctor_role
        )
        doc2 = Doctor.objects.create(
            user=doc2_user, doctor_name='Dr. Satellite Specialist', experience=5,
            new_patient_fee=500, old_patient_fee=300
        )
        DoctorClinic.objects.create(doctor=doc2, clinic=clinic2)

        # 1. Search by city name ("Mumbai") -> finds self.doctor
        res_city = self.client.get(reverse('doctor_list'), {'location': 'Mumbai'})
        self.assertEqual(res_city.status_code, 200)
        self.assertContains(res_city, 'Aarav Sharma')
        self.assertNotContains(res_city, 'Dr. Satellite Specialist')

        # 2. Search by locality ("Navrangpura") -> finds self.doctor
        res_nav = self.client.get(reverse('doctor_list'), {'location': 'Navrangpura'})
        self.assertEqual(res_nav.status_code, 200)
        self.assertContains(res_nav, 'Aarav Sharma')
        self.assertNotContains(res_nav, 'Dr. Satellite Specialist')

        # 3. Search by locality ("Satellite") -> finds doc2
        res_sat = self.client.get(reverse('doctor_list'), {'location': 'Satellite'})
        self.assertEqual(res_sat.status_code, 200)
        self.assertContains(res_sat, 'Dr. Satellite Specialist')
        self.assertNotContains(res_sat, 'Aarav Sharma')

    def test_manual_location_search_clears_stale_gps_coordinates(self):
        # When user types a manual location ("Mumbai"), any stale user_lat/lng are ignored
        res = self.client.get(reverse('doctor_list'), {
            'location': 'Mumbai',
            'user_lat': '12.9716',
            'user_lng': '77.5946'
        })
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['has_user_location'])
        self.assertEqual(res.context['user_lat'], '')
        self.assertEqual(res.context['user_lng'], '')
        self.assertContains(res, 'Aarav Sharma')

    def test_doctors_without_coordinates_do_not_cause_errors(self):
        # When clinics have null coordinates, proximity search doesn't crash
        self.clinic.latitude = None
        self.clinic.longitude = None
        self.clinic.save()

        res = self.client.get(reverse('doctor_list'), {
            'user_lat': '19.0760',
            'user_lng': '72.8777',
            'location': 'Current Location'
        })
        self.assertEqual(res.status_code, 200)
        doctors = list(res.context['doctors'])
        self.assertEqual(len(doctors), 1)
        self.assertIsNone(doctors[0].distance_km)
        self.assertContains(res, 'Aarav Sharma')

    def test_no_results_location_search(self):
        res = self.client.get(reverse('doctor_list'), {'location': 'NonExistentPlaceXYZ'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.context['doctors']), 0)
        self.assertContains(res, 'No Doctors Found')

    def test_seed_ahmedabad_demo_doctors_command(self):
        from django.core.management import call_command
        # Execute the seed command in the test database
        call_command('seed_ahmedabad_demo_doctors')

        # Verify exactly 50 demo doctors created
        demo_doctors = Doctor.objects.filter(user__email__startswith='demo.ahmedabad.doctor')
        self.assertEqual(demo_doctors.count(), 50)

        # Verify all 50 have clinic, specialization, and availability
        for doc in demo_doctors:
            self.assertTrue(doc.doctor_clinic.exists())
            self.assertTrue(doc.doctor_specialization.exists())
            self.assertTrue(doc.doctoravailability_set.exists())
            self.assertTrue(doc.doctor_name.startswith('[DEMO]'))

        # Verify clinics across Ahmedabad localities
        demo_clinics = Clinic.objects.filter(user__email__startswith='demo.ahmedabad.clinic')
        self.assertEqual(demo_clinics.count(), 10)
        for cl in demo_clinics:
            self.assertIsNotNone(cl.latitude)
            self.assertIsNotNone(cl.longitude)
            self.assertTrue(cl.clinic_name.startswith('DEMO —'))

        # Idempotence: running a second time does not duplicate records
        call_command('seed_ahmedabad_demo_doctors')
        self.assertEqual(Doctor.objects.filter(user__email__startswith='demo.ahmedabad.doctor').count(), 50)
        self.assertEqual(Clinic.objects.filter(user__email__startswith='demo.ahmedabad.clinic').count(), 10)

        # Clean flag removes all demo records
        call_command('seed_ahmedabad_demo_doctors', clean=True)
        self.assertEqual(Doctor.objects.filter(user__email__startswith='demo.ahmedabad.doctor').count(), 0)
        self.assertEqual(Clinic.objects.filter(user__email__startswith='demo.ahmedabad.clinic').count(), 0)


class MultipleClinicDoctorDiscoveryTests(TestCase):
    """
    Focused tests covering:
    1. Single doctor associated with three distinct clinics.
    2. Different schedules/shifts per clinic on different days/times.
    3. Proximity ordering: Clinic A (~0.5 km) prioritized over Clinic B (~3.9 km) and Clinic C (~7.4 km).
    4. Availability-aware fallback: if nearest clinic has no available slots/shifts, show next eligible clinic.
    5. Booking page clinic list ordering and default clinic selection based on nearest with available slots.
    6. Booking saves selected clinic and specific slot (not merely doctor ID).
    7. Rejection of unavailable/conflicting slots across clinics.
    8. Preserving standard search behavior when coordinates are missing.
    """
    def setUp(self):
        self.doctor_role = Role.objects.create(role_name='Doctor')
        self.clinic_role = Role.objects.create(role_name='Clinic')
        self.patient_role = Role.objects.create(role_name='Patient')

        self.state = StateMaster.objects.create(state_name='Maharashtra')
        self.city = CityMaster.objects.create(state=self.state, city_name='Mumbai')

        # Patient user & profile
        self.patient_user = User.objects.create(
            full_name='Test Patient', email='patient_multi@test.test',
            contact_number=9030000001, password_hash=make_password('Secret123!'),
            role=self.patient_role
        )
        self.patient = Patient.objects.create(user=self.patient_user, date_of_birth='1995-05-15')

        # Doctor user & profile (Approved & Verified)
        self.doc_user = User.objects.create(
            full_name='Dr. Multi Specialist', email='doc_multi@test.test',
            contact_number=9030000002, password_hash=make_password('Secret123!'),
            role=self.doctor_role, is_verified=True
        )
        self.doctor = Doctor.objects.create(
            user=self.doc_user, doctor_name='Dr. Multi Specialist', experience=12,
            new_patient_fee=600, old_patient_fee=400, license_verification_status='Approved'
        )
        self.spec = SpecializationMaster.objects.create(specialization_name='Cardiology')
        DoctorSpecialization.objects.create(doctor=self.doctor, specialization=self.spec)

        # Clinic A (~0.5 km away from patient's reference point 19.0800, 72.8800)
        user_a = User.objects.create(
            full_name='Clinic Alpha User', email='clinic_a@test.test',
            contact_number=9030000011, password_hash=make_password('Secret123!'),
            role=self.clinic_role
        )
        self.clinic_a = Clinic.objects.create(
            user=user_a, clinic_name='Clinic Alpha (Near)',
            address='Bandra West', city=self.city, contact_number=9030000011,
            latitude=19.0760, longitude=72.8777
        )

        # Clinic B (~3.9 km away)
        user_b = User.objects.create(
            full_name='Clinic Beta User', email='clinic_b@test.test',
            contact_number=9030000012, password_hash=make_password('Secret123!'),
            role=self.clinic_role
        )
        self.clinic_b = Clinic.objects.create(
            user=user_b, clinic_name='Clinic Beta (Mid)',
            address='Santacruz East', city=self.city, contact_number=9030000012,
            latitude=19.1100, longitude=72.8900
        )

        # Clinic C (~7.4 km away)
        user_c = User.objects.create(
            full_name='Clinic Gamma User', email='clinic_c@test.test',
            contact_number=9030000013, password_hash=make_password('Secret123!'),
            role=self.clinic_role
        )
        self.clinic_c = Clinic.objects.create(
            user=user_c, clinic_name='Clinic Gamma (Far)',
            address='Andheri East', city=self.city, contact_number=9030000013,
            latitude=19.1400, longitude=72.9100
        )

        # Associate Doctor with all 3 clinics
        DoctorClinic.objects.create(doctor=self.doctor, clinic=self.clinic_a)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=self.clinic_b)
        DoctorClinic.objects.create(doctor=self.doctor, clinic=self.clinic_c)

        # Schedule days
        self.monday, _ = DayMaster.objects.get_or_create(day_name='Monday')
        self.tuesday, _ = DayMaster.objects.get_or_create(day_name='Tuesday')

        # Schedules per clinic:
        # Clinic A: Monday 09:00 - 12:00
        # Clinic B: Monday 13:00 - 16:00
        # Clinic C: Tuesday 17:00 - 19:00
        self.avail_a = DoctorAvailability.objects.create(
            doctor=self.doctor, clinic=self.clinic_a, day=self.monday,
            start_time='09:00:00', end_time='12:00:00'
        )
        self.avail_b = DoctorAvailability.objects.create(
            doctor=self.doctor, clinic=self.clinic_b, day=self.monday,
            start_time='13:00:00', end_time='16:00:00'
        )
        self.avail_c = DoctorAvailability.objects.create(
            doctor=self.doctor, clinic=self.clinic_c, day=self.tuesday,
            start_time='17:00:00', end_time='19:00:00'
        )

        # Patient reference coordinates
        self.patient_lat = '19.0800'
        self.patient_lng = '72.8800'

        # Next future dates for booking tests
        today = timezone.localdate()
        self.booking_monday = None
        self.booking_tuesday = None
        for i in range(1, 14):
            d = today + timedelta(days=i)
            if d.strftime('%A') == 'Monday' and not self.booking_monday:
                self.booking_monday = d
            if d.strftime('%A') == 'Tuesday' and not self.booking_tuesday:
                self.booking_tuesday = d
            if self.booking_monday and self.booking_tuesday:
                break

    def login_patient(self):
        session = self.client.session
        session['user_id'] = self.patient_user.pk
        session.save()

    def test_one_doctor_associated_with_three_clinics_and_distinct_schedules(self):
        # 1. Doctor is linked to 3 clinics
        self.assertEqual(DoctorClinic.objects.filter(doctor=self.doctor).count(), 3)
        clinics = [dc.clinic for dc in DoctorClinic.objects.filter(doctor=self.doctor)]
        self.assertIn(self.clinic_a, clinics)
        self.assertIn(self.clinic_b, clinics)
        self.assertIn(self.clinic_c, clinics)

        # 2. Availabilities link to correct clinic, day, start and end times
        avails = DoctorAvailability.objects.filter(doctor=self.doctor)
        self.assertEqual(avails.count(), 3)

        avail_a = avails.get(clinic=self.clinic_a)
        self.assertEqual(avail_a.day.day_name, 'Monday')
        self.assertEqual(str(avail_a.start_time), '09:00:00')
        self.assertEqual(str(avail_a.end_time), '12:00:00')

        avail_b = avails.get(clinic=self.clinic_b)
        self.assertEqual(avail_b.day.day_name, 'Monday')
        self.assertEqual(str(avail_b.start_time), '13:00:00')
        self.assertEqual(str(avail_b.end_time), '16:00:00')

        avail_c = avails.get(clinic=self.clinic_c)
        self.assertEqual(avail_c.day.day_name, 'Tuesday')
        self.assertEqual(str(avail_c.start_time), '17:00:00')
        self.assertEqual(str(avail_c.end_time), '19:00:00')

    def test_doctor_discovery_prioritizes_nearest_eligible_clinic(self):
        self.login_patient()
        # Patient near Clinic A (~0.5 km away)
        res = self.client.get(reverse('doctor_list'), {
            'user_lat': self.patient_lat,
            'user_lng': self.patient_lng,
            'location': 'Current Location'
        })
        self.assertEqual(res.status_code, 200)

        # Find doctor in results
        doctor = next(d for d in res.context['doctors'] if d.doctor_id == self.doctor.doctor_id)
        # Nearest clinic must be Clinic Alpha (closest eligible clinic with availability)
        self.assertEqual(doctor.nearest_clinic.clinic_id, self.clinic_a.clinic_id)
        self.assertIsNotNone(doctor.distance_km)
        self.assertLess(doctor.distance_km, 2.0)

        # HTML response shows Clinic Alpha and indicates multiple clinics
        self.assertContains(res, 'Clinic Alpha (Near)')
        self.assertContains(res, '+2 more')
        # Booking link points to nearest clinic_id
        self.assertContains(res, f'clinic_id={self.clinic_a.clinic_id}')

    def test_doctor_discovery_falls_back_when_nearest_clinic_has_no_availability(self):
        # Remove availability for Clinic A (doctor still affiliated with Clinic A, but has no active shifts there)
        DoctorAvailability.objects.filter(doctor=self.doctor, clinic=self.clinic_a).delete()

        res = self.client.get(reverse('doctor_list'), {
            'user_lat': self.patient_lat,
            'user_lng': self.patient_lng,
            'location': 'Current Location'
        })
        self.assertEqual(res.status_code, 200)

        doctor = next(d for d in res.context['doctors'] if d.doctor_id == self.doctor.doctor_id)
        # Nearest clinic must now be Clinic Beta (the next closest clinic where doctor actually has availability)
        self.assertEqual(doctor.nearest_clinic.clinic_id, self.clinic_b.clinic_id)
        # Distance should be around ~3.9 km, NOT Clinic A's ~0.5 km
        self.assertGreater(doctor.distance_km, 2.5)
        self.assertLess(doctor.distance_km, 5.0)

    def test_doctor_detail_orders_clinics_nearest_first(self):
        # Access doctor detail with patient coordinates
        res = self.client.get(reverse('doctor_detail', args=[self.doctor.pk]), {
            'user_lat': self.patient_lat,
            'user_lng': self.patient_lng
        })
        self.assertEqual(res.status_code, 200)

        clinics = res.context['clinics']
        self.assertEqual(len(clinics), 3)

        # Ordered nearest first: Clinic A (<2km), Clinic B (~3.9km), Clinic C (~7.4km)
        self.assertEqual(clinics[0].clinic_id, self.clinic_a.clinic_id)
        self.assertEqual(clinics[1].clinic_id, self.clinic_b.clinic_id)
        self.assertEqual(clinics[2].clinic_id, self.clinic_c.clinic_id)

        self.assertLess(clinics[0].distance_km, clinics[1].distance_km)
        self.assertLess(clinics[1].distance_km, clinics[2].distance_km)

        # Distance badges rendered in template
        self.assertContains(res, f'{clinics[0].distance_km} km away')

    def test_booking_page_preselects_nearest_eligible_clinic_with_slots(self):
        self.login_patient()
        res = self.client.get(reverse('book_appointment', args=[self.doctor.pk]), {
            'user_lat': self.patient_lat,
            'user_lng': self.patient_lng
        })
        self.assertEqual(res.status_code, 200)

        clinics = res.context['clinics']
        self.assertEqual(len(clinics), 3)
        # Verify ordering in booking view
        self.assertEqual(clinics[0].clinic.clinic_id, self.clinic_a.clinic_id)
        self.assertEqual(clinics[1].clinic.clinic_id, self.clinic_b.clinic_id)
        self.assertEqual(clinics[2].clinic.clinic_id, self.clinic_c.clinic_id)

        # Default clinic is Clinic A
        self.assertEqual(res.context['default_clinic_id'], self.clinic_a.clinic_id)
        # Clinic Alpha radio input is checked
        self.assertContains(res, f'value="{self.clinic_a.clinic_id}" checked')

    def test_booking_page_falls_back_when_nearest_clinic_has_no_slots(self):
        self.login_patient()
        # Remove shifts for Clinic A
        DoctorAvailability.objects.filter(doctor=self.doctor, clinic=self.clinic_a).delete()

        res = self.client.get(reverse('book_appointment', args=[self.doctor.pk]), {
            'user_lat': self.patient_lat,
            'user_lng': self.patient_lng
        })
        self.assertEqual(res.status_code, 200)

        # Default clinic falls back to Clinic Beta (nearest with available slots)
        self.assertEqual(res.context['default_clinic_id'], self.clinic_b.clinic_id)
        # Clinic Alpha shows no slots available badge
        self.assertContains(res, 'No slots available')

    def test_booking_saves_selected_clinic_and_slot(self):
        self.login_patient()
        # Patient selects Clinic Beta on Monday at 13:00 (when doctor is at Clinic Beta)
        mon_str = self.booking_monday.isoformat()
        res = self.client.post(reverse('book_appointment', args=[self.doctor.pk]), {
            'selected_slot': f'{mon_str}|13:00|{self.clinic_b.clinic_id}',
            'clinic_id': self.clinic_b.clinic_id,
            'appointment_date': mon_str,
            'appointment_time': '13:00',
            'patient_type': 'New',
            'symptoms': 'Heart palpitations'
        })
        self.assertEqual(Appointment.objects.count(), 1)
        appt = Appointment.objects.get()
        self.assertRedirects(res, reverse('appointment_confirmation', args=[appt.pk]))

        # Appointment must be linked to Clinic B and the exact slot
        self.assertEqual(appt.doctor, self.doctor)
        self.assertEqual(appt.clinic, self.clinic_b)
        self.assertNotEqual(appt.clinic, self.clinic_a)
        self.assertEqual(appt.appointment_date, self.booking_monday)
        self.assertEqual(str(appt.appointment_time), '13:00:00')

    def test_booking_rejects_slot_at_wrong_clinic_or_outside_availability(self):
        self.login_patient()
        mon_str = self.booking_monday.isoformat()

        # Doctor is at Clinic B at 13:00, NOT at Clinic A
        # Attempt to book 13:00 at Clinic A must be rejected
        res = self.client.post(reverse('book_appointment', args=[self.doctor.pk]), {
            'selected_slot': f'{mon_str}|13:00|{self.clinic_a.clinic_id}',
            'clinic_id': self.clinic_a.clinic_id,
            'appointment_date': mon_str,
            'appointment_time': '13:00',
            'patient_type': 'New'
        })
        self.assertEqual(Appointment.objects.count(), 0)
        self.assertRedirects(res, reverse('book_appointment', args=[self.doctor.pk]))

        # Attempt to book 09:00 at Clinic B (when doctor is at Clinic A) must also be rejected
        res2 = self.client.post(reverse('book_appointment', args=[self.doctor.pk]), {
            'selected_slot': f'{mon_str}|09:00|{self.clinic_b.clinic_id}',
            'clinic_id': self.clinic_b.clinic_id,
            'appointment_date': mon_str,
            'appointment_time': '09:00',
            'patient_type': 'New'
        })
        self.assertEqual(Appointment.objects.count(), 0)
        self.assertRedirects(res2, reverse('book_appointment', args=[self.doctor.pk]))

    def test_search_without_coordinates_preserves_default_behavior(self):
        # Search without coordinates
        res = self.client.get(reverse('doctor_list'), {'search': 'Dr. Multi Specialist'})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['has_user_location'])

        doctor = next(d for d in res.context['doctors'] if d.doctor_id == self.doctor.doctor_id)
        # No invented distance
        self.assertIsNone(doctor.distance_km)
        self.assertNotContains(res, 'km away')
