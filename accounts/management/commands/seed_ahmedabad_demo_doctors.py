"""
Django management command to idempotently create 50 fictional Ahmedabad doctor profiles
for demonstration of nearby doctor search and location filtering.

Usage:
    python manage.py seed_ahmedabad_demo_doctors [--dry-run] [--clean]

NOTE: DO NOT run this command against a shared production database without an isolated
demo environment or explicit filtering.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from django.db import transaction

from accounts.models import User, Role, StateMaster, CityMaster, Clinic, DayMaster
from doctors.models import (
    Doctor, SpecializationMaster, QualificationMaster,
    DoctorSpecialization, DoctorQualification, DoctorClinic, DoctorAvailability
)


class Command(BaseCommand):
    help = "Idempotently create 50 fictional Ahmedabad doctor profiles across 10 localities for location demonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate creation without committing changes to the database.',
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Remove previously seeded Ahmedabad demo doctors and clinics.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        clean = options.get('clean', False)

        if clean:
            self.clean_demo_records()
            return

        self.stdout.write(self.style.NOTICE("Initializing 50 fictional Ahmedabad demo doctors..."))
        if dry_run:
            self.stdout.write(self.style.WARNING("Running in --dry-run mode: no database records will be saved."))

        with transaction.atomic():
            created_clinics, created_docs = self.seed_data(dry_run=dry_run)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed 50 fictional Ahmedabad demo doctors across 10 localities.\n"
                f"Clinics: {created_clinics} processed, Doctors: {created_docs} processed."
            )
        )

    def clean_demo_records(self):
        """Clean up fictional demo doctors and clinics without touching genuine records."""
        emails = [f"demo.ahmedabad.doctor{i:02d}@wellpoint.test" for i in range(1, 51)]
        clinic_emails = [
            f"demo.ahmedabad.clinic.{loc.lower()}@wellpoint.test"
            for loc in [
                "navrangpura", "paldi", "satellite", "vastrapur", "bopal",
                "maninagar", "naranpura", "chandkheda", "gota", "thaltej"
            ]
        ]
        doc_users = User.objects.filter(email__in=emails)
        doc_count = doc_users.count()
        doc_users.delete()

        clinic_users = User.objects.filter(email__in=clinic_emails)
        clinic_count = clinic_users.count()
        clinic_users.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleaned up {doc_count} demo doctor users and {clinic_count} demo clinic users."
            )
        )

    def first_or_create(self, model, defaults=None, **lookup):
        return model.objects.filter(**lookup).first() or model.objects.create(**lookup, **(defaults or {}))

    def seed_data(self, dry_run=False):
        # 1. Fetch or create roles safely
        doctor_role = self.first_or_create(Role, role_name='Doctor')
        clinic_role = self.first_or_create(Role, role_name='Clinic')

        # 2. State & City
        state = self.first_or_create(StateMaster, state_name='Gujarat')
        city = self.first_or_create(CityMaster, state=state, city_name='Ahmedabad')

        # 3. Days of the week
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        days = {name: self.first_or_create(DayMaster, day_name=name) for name in day_names}

        # 4. Specializations
        spec_names = [
            'General Physician', 'Cardiologist', 'Dermatologist', 'Pediatrician',
            'Orthopedic', 'Gynecologist', 'Dentist', 'ENT Specialist',
            'Neurologist', 'Ophthalmologist'
        ]
        specs = {name: self.first_or_create(SpecializationMaster, specialization_name=name) for name in spec_names}

        # 5. Qualifications
        qual_names = ['MBBS', 'MD', 'MS', 'BDS', 'DNB', 'MCh']
        quals = {name: self.first_or_create(QualificationMaster, qualification_name=name) for name in qual_names}

        # 6. 10 Localities in Ahmedabad with realistic coordinates
        localities = [
            {
                'key': 'navrangpura',
                'name': 'DEMO — Navrangpura WellPoint Clinic',
                'address': 'Near University Ground, Navrangpura, Ahmedabad, Gujarat',
                'lat': Decimal('23.0365000'),
                'lng': Decimal('72.5611000'),
                'contact': 9825000001,
            },
            {
                'key': 'paldi',
                'name': 'DEMO — Paldi WellPoint Clinic',
                'address': 'Near Mahalaxmi Cross Roads, Paldi, Ahmedabad, Gujarat',
                'lat': Decimal('23.0125000'),
                'lng': Decimal('72.5629000'),
                'contact': 9825000002,
            },
            {
                'key': 'satellite',
                'name': 'DEMO — Satellite WellPoint Clinic',
                'address': 'Near Shivranjani Cross Roads, Satellite, Ahmedabad, Gujarat',
                'lat': Decimal('23.0304000'),
                'lng': Decimal('72.5178000'),
                'contact': 9825000003,
            },
            {
                'key': 'vastrapur',
                'name': 'DEMO — Vastrapur WellPoint Clinic',
                'address': 'Near Vastrapur Lake, Vastrapur, Ahmedabad, Gujarat',
                'lat': Decimal('23.0350000'),
                'lng': Decimal('72.5293000'),
                'contact': 9825000004,
            },
            {
                'key': 'bopal',
                'name': 'DEMO — Bopal WellPoint Clinic',
                'address': 'South Bopal Ring Road, Bopal, Ahmedabad, Gujarat',
                'lat': Decimal('23.0338000'),
                'lng': Decimal('72.4634000'),
                'contact': 9825000005,
            },
            {
                'key': 'maninagar',
                'name': 'DEMO — Maninagar WellPoint Clinic',
                'address': 'Near Kankaria Lake, Maninagar, Ahmedabad, Gujarat',
                'lat': Decimal('22.9978000'),
                'lng': Decimal('72.6033000'),
                'contact': 9825000006,
            },
            {
                'key': 'naranpura',
                'name': 'DEMO — Naranpura WellPoint Clinic',
                'address': 'Near Ankur Cross Roads, Naranpura, Ahmedabad, Gujarat',
                'lat': Decimal('23.0560000'),
                'lng': Decimal('72.5518000'),
                'contact': 9825000007,
            },
            {
                'key': 'chandkheda',
                'name': 'DEMO — Chandkheda WellPoint Clinic',
                'address': 'Near SP Ring Road, Chandkheda, Ahmedabad, Gujarat',
                'lat': Decimal('23.1118000'),
                'lng': Decimal('72.5722000'),
                'contact': 9825000008,
            },
            {
                'key': 'gota',
                'name': 'DEMO — Gota WellPoint Clinic',
                'address': 'Near SG Highway, Gota, Ahmedabad, Gujarat',
                'lat': Decimal('23.0977000'),
                'lng': Decimal('72.5317000'),
                'contact': 9825000009,
            },
            {
                'key': 'thaltej',
                'name': 'DEMO — Thaltej WellPoint Clinic',
                'address': 'Near Hebatpur Road, Thaltej, Ahmedabad, Gujarat',
                'lat': Decimal('23.0500000'),
                'lng': Decimal('72.5020000'),
                'contact': 9825000010,
            },
        ]

        clinics = []
        for loc in localities:
            clinic_email = f"demo.ahmedabad.clinic.{loc['key']}@wellpoint.test"
            clinic_user = User.objects.filter(email=clinic_email).first()
            if not clinic_user:
                clinic_user = User.objects.create(
                    full_name=loc['name'],
                    email=clinic_email,
                    contact_number=loc['contact'],
                    password_hash=make_password('DemoClinicPass123!'),
                    address=loc['address'],
                    role=clinic_role,
                    is_verified=True,
                    account_status='active',
                )

            clinic = Clinic.objects.filter(user=clinic_user).first()
            if not clinic:
                clinic = Clinic.objects.create(
                    user=clinic_user,
                    clinic_name=loc['name'],
                    address=loc['address'],
                    city=city,
                    contact_number=loc['contact'],
                    latitude=loc['lat'],
                    longitude=loc['lng'],
                )
            else:
                # Keep coordinates and address updated for demo location calculations
                clinic.latitude = loc['lat']
                clinic.longitude = loc['lng']
                clinic.address = loc['address']
                clinic.clinic_name = loc['name']
                clinic.save()

            clinics.append(clinic)

        # 7. Doctor catalog (50 fictional doctors, 5 per clinic)
        doctor_names = [
            ("Aarav Patel", "General Physician", "MBBS", 8, 500, 300),
            ("Diya Shah", "Cardiologist", "MD", 12, 800, 500),
            ("Rohan Mehta", "Dermatologist", "MD", 6, 600, 400),
            ("Priya Joshi", "Pediatrician", "MBBS", 10, 550, 350),
            ("Vikram Trivedi", "Orthopedic", "MS", 15, 900, 600),
            ("Neha Bhatt", "Gynecologist", "MS", 9, 700, 450),
            ("Karan Rathod", "Dentist", "BDS", 7, 400, 250),
            ("Anjali Chauhan", "ENT Specialist", "MS", 11, 650, 400),
            ("Suresh Varma", "Neurologist", "MD", 18, 1100, 700),
            ("Kavita Dave", "Ophthalmologist", "MS", 14, 750, 500),
            ("Ramesh Prajapati", "General Physician", "MBBS", 5, 450, 300),
            ("Sunita Solanki", "Cardiologist", "MD", 16, 950, 600),
            ("Rajesh Rawal", "Dermatologist", "DNB", 8, 600, 400),
            ("Anita Parmar", "Pediatrician", "MD", 13, 650, 400),
            ("Manish Vyas", "Orthopedic", "MS", 10, 800, 500),
            ("Tanvi Makwana", "Gynecologist", "MS", 7, 700, 450),
            ("Chirag Panchal", "Dentist", "BDS", 6, 450, 250),
            ("Bhavna Soni", "ENT Specialist", "MS", 12, 700, 450),
            ("Deepak Barot", "Neurologist", "MD", 20, 1200, 800),
            ("Geeta Modi", "Ophthalmologist", "MS", 9, 650, 400),
            ("Harsh Oza", "General Physician", "MBBS", 4, 400, 250),
            ("Ila Gadhvi", "Cardiologist", "MD", 14, 900, 550),
            ("Jayesh Acharya", "Dermatologist", "MD", 11, 700, 450),
            ("Kinjal Jani", "Pediatrician", "DNB", 8, 550, 350),
            ("Lalit Upadhyay", "Orthopedic", "MS", 17, 950, 650),
            ("Mona Kothari", "Gynecologist", "MS", 10, 750, 500),
            ("Nikhil Pandya", "Dentist", "BDS", 5, 400, 250),
            ("Pallavi Desai", "ENT Specialist", "MS", 13, 750, 500),
            ("Qasim Mansuri", "Neurologist", "MD", 19, 1150, 750),
            ("Rupal Shukla", "Ophthalmologist", "MS", 15, 800, 500),
            ("Sanjay Raval", "General Physician", "MBBS", 9, 500, 350),
            ("Tejal Vora", "Cardiologist", "MD", 12, 850, 550),
            ("Umesh Thakkar", "Dermatologist", "DNB", 7, 600, 400),
            ("Vaishali Dave", "Pediatrician", "MBBS", 11, 600, 400),
            ("Wasim Qureshi", "Orthopedic", "MS", 14, 900, 600),
            ("Yamini Parekh", "Gynecologist", "MS", 8, 700, 450),
            ("Zahir Memon", "Dentist", "BDS", 6, 450, 300),
            ("Ashwin Choksi", "ENT Specialist", "MS", 10, 650, 400),
            ("Bijal Sheth", "Neurologist", "MD", 16, 1100, 700),
            ("Chetan Sanghvi", "Ophthalmologist", "MS", 12, 750, 500),
            ("Dharmesh Gandhi", "General Physician", "MBBS", 6, 450, 300),
            ("Ekta Kapadia", "Cardiologist", "MD", 15, 950, 600),
            ("Falguni Doshi", "Dermatologist", "MD", 9, 650, 450),
            ("Girish Maniar", "Pediatrician", "MD", 14, 700, 450),
            ("Hema Munshi", "Orthopedic", "MS", 18, 1000, 650),
            ("Indrajit Baji", "Gynecologist", "MS", 11, 800, 500),
            ("Jinal Shah", "Dentist", "BDS", 8, 500, 300),
            ("Kamlesh Banker", "ENT Specialist", "MS", 13, 700, 450),
            ("Lopa Mudra", "Neurologist", "MD", 21, 1250, 800),
            ("Mihir Nanavati", "Ophthalmologist", "MS", 10, 700, 450),
        ]

        total_clinics = len(clinics)
        processed_doctors = 0

        for i, (name, spec_name, qual_name, exp, new_fee, old_fee) in enumerate(doctor_names, start=1):
            email = f"demo.ahmedabad.doctor{i:02d}@wellpoint.test"
            contact = 9825000100 + i
            full_name = f"[DEMO] Dr. {name}"

            user = User.objects.filter(email=email).first()
            if not user:
                user = User.objects.create(
                    full_name=full_name,
                    email=email,
                    contact_number=contact,
                    password_hash=make_password('DemoDoctorPass123!'),
                    role=doctor_role,
                    is_verified=True,
                    account_status='active',
                )

            doctor = Doctor.objects.filter(user=user).first()
            if not doctor:
                doctor = Doctor.objects.create(
                    user=user,
                    doctor_name=full_name,
                    experience=exp,
                    new_patient_fee=Decimal(str(new_fee)),
                    old_patient_fee=Decimal(str(old_fee)),
                    about=(
                        f"Fictional demonstration doctor profile for {full_name} ({spec_name}) "
                        f"in Ahmedabad. Intended exclusively for location search and testing."
                    ),
                )
            else:
                doctor.doctor_name = full_name
                doctor.experience = exp
                doctor.new_patient_fee = Decimal(str(new_fee))
                doctor.old_patient_fee = Decimal(str(old_fee))
                doctor.save()

            # Associate with clinic (round-robin distribution: 5 doctors per clinic)
            clinic = clinics[(i - 1) % total_clinics]
            self.first_or_create(DoctorClinic, doctor=doctor, clinic=clinic)

            # Specialization
            spec_obj = specs.get(spec_name)
            if spec_obj:
                self.first_or_create(DoctorSpecialization, doctor=doctor, specialization=spec_obj)

            # Qualification
            qual_obj = quals.get(qual_name)
            if qual_obj:
                self.first_or_create(DoctorQualification, doctor=doctor, qualification=qual_obj)

            # Availability: Mon-Fri slots
            for d_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                day_obj = days[d_name]
                self.first_or_create(
                    DoctorAvailability,
                    doctor=doctor,
                    clinic=clinic,
                    day=day_obj,
                    start_time='09:00',
                    end_time='13:00',
                )
                self.first_or_create(
                    DoctorAvailability,
                    doctor=doctor,
                    clinic=clinic,
                    day=day_obj,
                    start_time='16:00',
                    end_time='20:00',
                )

            processed_doctors += 1

        return len(clinics), processed_doctors
