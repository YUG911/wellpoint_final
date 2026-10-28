from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import (
    Role, User, StateMaster, CityMaster, Clinic,
    DayMaster, ClinicHours, Patient, ClinicStaff, Admin, VerificationLog
)
from doctors.models import (
    Doctor, SpecializationMaster, DoctorSpecialization,
    QualificationMaster, DoctorQualification, DoctorClinic, DoctorAvailability
)
from django.contrib.auth.hashers import make_password
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed demo data for WellPoint (idempotent, safe to run multiple times)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding WellPoint demo data...")

        with transaction.atomic():
            self.seed_roles()
            self.seed_states_cities()
            self.seed_specializations_qualifications()
            self.seed_days()
            demo_data = self.seed_demo_clinics()
            self.seed_demo_doctors(demo_data)
            self.seed_demo_patients()
            self.seed_admin()

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))

    def _get_unique_contact_number(self, prefix='9'):
        """Generate a contact number that doesn't exist in the DB."""
        for i in range(10000):
            contact = f"{prefix}{abs(hash(str(i))) % 100000000:08d}"
            if not User.objects.filter(contact_number=contact).exists():
                return contact
        import random
        return f"{prefix}{random.randint(10000000, 99999999)}"

    def _ensure_user(self, email, full_name, contact_number, password, role, is_verified=True, account_status='active'):
        """Get or create user, handling both email and contact_number uniqueness."""
        # Try to find by email first
        user = User.objects.filter(email=email).first()
        if user:
            # Update fields if needed
            if user.contact_number != contact_number and not User.objects.filter(contact_number=contact_number).exists():
                user.contact_number = contact_number
            user.full_name = full_name
            user.password_hash = make_password(password)
            user.role = role
            user.is_verified = is_verified
            user.account_status = account_status
            user.save()
            return user
        
        # Email not found, check if contact_number is taken
        if User.objects.filter(contact_number=contact_number).exists():
            contact_number = self._get_unique_contact_number(contact_number[0])
        
        # Create new user
        return User.objects.create(
            email=email,
            full_name=full_name,
            contact_number=contact_number,
            password_hash=make_password(password),
            role=role,
            is_verified=is_verified,
            account_status=account_status,
        )

    def seed_roles(self):
        roles = ['Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin']
        for name in roles:
            Role.objects.get_or_create(role_name=name)
        self.roles = {r.role_name: r for r in Role.objects.all()}

    def seed_states_cities(self):
        state, _ = StateMaster.objects.get_or_create(state_name='Gujarat')
        cities_data = [
            ('Ahmedabad', 'Workflow City'),
            ('Bopal', 'Bopal'),
            ('Ranip', 'Ranip'),
            ('Bapunagar', 'Bapunagar'),
            ('Kalupur', 'Kalupur'),
            ('Navrangpura', 'Navrangpura'),
            ('Maninagar', 'Maninagar'),
            ('Satellite', 'Satellite'),
        ]
        self.cities = {}
        for city_name, display_name in cities_data:
            city, _ = CityMaster.objects.get_or_create(state=state, city_name=city_name)
            self.cities[display_name] = city

    def seed_specializations_qualifications(self):
        specs = [
            'General Physician', 'Cardiologist', 'Dermatologist',
            'ENT Specialist', 'Gastroenterologist', 'Neurologist',
            'Ophthalmologist', 'Orthopedic Surgeon', 'Psychiatrist', 'Urologist'
        ]
        for s in specs:
            SpecializationMaster.objects.get_or_create(specialization_name=s)

        quals = ['MBBS', 'MD', 'MS', 'DNB', 'DM', 'MCh']
        for q in quals:
            QualificationMaster.objects.get_or_create(qualification_name=q)

    def seed_days(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for d in days:
            DayMaster.objects.get_or_create(day_name=d)

    def seed_demo_clinics(self):
        """Create 8 demo clinics at different coordinates."""
        clinics_data = [
            {
                'name': 'WellPoint Test Clinic',
                'address': 'Main St, Workflow City',
                'city': 'Workflow City',
                'contact': '900100001',
                'lat': Decimal('23.0225000'), 'lng': Decimal('72.5714000'),
            },
            {
                'name': 'Heart Care Clinic',
                'address': 'Cardiac Ave, Workflow City',
                'city': 'Workflow City',
                'contact': '900100002',
                'lat': Decimal('23.0500000'), 'lng': Decimal('72.6000000'),
            },
            {
                'name': 'Skin Wellness',
                'address': 'Derma Rd, Bopal',
                'city': 'Bopal',
                'contact': '900100003',
                'lat': Decimal('23.0800000'), 'lng': Decimal('72.5500000'),
            },
            {
                'name': 'ENT Care',
                'address': 'Voice St, Workflow City',
                'city': 'Workflow City',
                'contact': '900100004',
                'lat': Decimal('23.0100000'), 'lng': Decimal('72.5200000'),
            },
            {
                'name': 'Digestive Health',
                'address': 'Gut Blvd, Bopal',
                'city': 'Bopal',
                'contact': '900100005',
                'lat': Decimal('23.0600000'), 'lng': Decimal('72.5800000'),
            },
            {
                'name': 'Neuro Center',
                'address': 'Brain Ave, Workflow City',
                'city': 'Workflow City',
                'contact': '900100006',
                'lat': Decimal('23.0300000'), 'lng': Decimal('72.5400000'),
            },
            {
                'name': 'Eye Clinic',
                'address': 'Vision St, Bopal',
                'city': 'Bopal',
                'contact': '900100007',
                'lat': Decimal('23.0700000'), 'lng': Decimal('72.5600000'),
            },
            {
                'name': 'Bone & Joint',
                'address': 'Ortho Rd, Workflow City',
                'city': 'Workflow City',
                'contact': '900100008',
                'lat': Decimal('23.0400000'), 'lng': Decimal('72.5100000'),
            },
        ]

        clinics = {}
        for c in clinics_data:
            city = self.cities[c['city']]
            clinic_user = self._ensure_user(
                email=f"clinic_{c['name'].lower().replace(' ', '_')}@demo.example.com",
                full_name=c['name'] + ' Owner',
                contact_number=c['contact'],
                password='Demo@12345',
                role=self.roles['Clinic'],
            )
            clinic, _ = Clinic.objects.get_or_create(
                user=clinic_user,
                defaults={
                    'clinic_name': c['name'],
                    'address': c['address'],
                    'city': city,
                    'contact_number': c['contact'],
                    'latitude': c['lat'],
                    'longitude': c['lng'],
                }
            )
            clinics[c['name']] = clinic

        return clinics

    def seed_demo_doctors(self, clinics):
        doctors_data = [
            {'name': 'Dr. Aarav Sharma', 'spec': 'General Physician', 'exp': 8, 'fees': (500, 300), 'clinic': 'WellPoint Test Clinic', 'quals': ['MBBS', 'MD']},
            {'name': 'Dr. Priya Patel', 'spec': 'Cardiologist', 'exp': 12, 'fees': (800, 500), 'clinic': 'Heart Care Clinic', 'quals': ['MBBS', 'MD', 'DM']},
            {'name': 'Dr. Rohan Mehta', 'spec': 'Dermatologist', 'exp': 6, 'fees': (600, 400), 'clinic': 'Skin Wellness', 'quals': ['MBBS', 'MD']},
            {'name': 'Dr. Neha Shah', 'spec': 'ENT Specialist', 'exp': 9, 'fees': (700, 450), 'clinic': 'ENT Care', 'quals': ['MBBS', 'MS']},
            {'name': 'Dr. Vikram Joshi', 'spec': 'Gastroenterologist', 'exp': 11, 'fees': (750, 500), 'clinic': 'Digestive Health', 'quals': ['MBBS', 'MD', 'DM']},
            {'name': 'Dr. Anjali Desai', 'spec': 'Neurologist', 'exp': 10, 'fees': (900, 600), 'clinic': 'Neuro Center', 'quals': ['MBBS', 'MD', 'DM']},
            {'name': 'Dr. Karan Patel', 'spec': 'Ophthalmologist', 'exp': 8, 'fees': (650, 400), 'clinic': 'Eye Clinic', 'quals': ['MBBS', 'MS']},
            {'name': 'Dr. Riya Singh', 'spec': 'Orthopedic Surgeon', 'exp': 14, 'fees': (850, 550), 'clinic': 'Bone & Joint', 'quals': ['MBBS', 'MS', 'MCh']},
            {'name': 'Dr. Amit Kumar', 'spec': 'Psychiatrist', 'exp': 7, 'fees': (700, 450), 'clinic': 'WellPoint Test Clinic', 'quals': ['MBBS', 'MD']},
            {'name': 'Dr. Sneha Reddy', 'spec': 'Urologist', 'exp': 8, 'fees': (800, 500), 'clinic': 'Heart Care Clinic', 'quals': ['MBBS', 'MS']},
            {'name': 'Dr. Deepak Agarwal', 'spec': 'General Physician', 'exp': 5, 'fees': (400, 250), 'clinic': 'Skin Wellness', 'quals': ['MBBS']},
            {'name': 'Dr. Kavya Nair', 'spec': 'Cardiologist', 'exp': 13, 'fees': (900, 600), 'clinic': 'Neuro Center', 'quals': ['MBBS', 'MD', 'DM']},
            {'name': 'Dr. Manish Verma', 'spec': 'Dermatologist', 'exp': 7, 'fees': (550, 350), 'clinic': 'ENT Care', 'quals': ['MBBS', 'MD']},
            {'name': 'Dr. Pooja Iyer', 'spec': 'ENT Specialist', 'exp': 6, 'fees': (600, 380), 'clinic': 'Digestive Health', 'quals': ['MBBS', 'MS']},
            {'name': 'Dr. Sameer Khan', 'spec': 'Gastroenterologist', 'exp': 10, 'fees': (800, 500), 'clinic': 'Bone & Joint', 'quals': ['MBBS', 'MD', 'DM']},
        ]

        for d in doctors_data:
            doctor_user = self._ensure_user(
                email=f"doctor_{d['name'].lower().replace('dr. ', '').replace(' ', '_')}@demo.example.com",
                full_name=d['name'],
                contact_number=self._get_unique_contact_number('8'),
                password='Demo@12345',
                role=self.roles['Doctor'],
            )
            doctor, _ = Doctor.objects.get_or_create(
                user=doctor_user,
                defaults={
                    'doctor_name': d['name'],
                    'experience': d['exp'],
                    'new_patient_fee': Decimal(str(d['fees'][0])),
                    'old_patient_fee': Decimal(str(d['fees'][1])),
                    'about': f"Experienced {d['spec']} with {d['exp']} years of practice.",
                }
            )

            spec = SpecializationMaster.objects.get(specialization_name=d['spec'])
            DoctorSpecialization.objects.get_or_create(doctor=doctor, specialization=spec)

            for q_name in d['quals']:
                qual = QualificationMaster.objects.get(qualification_name=q_name)
                DoctorQualification.objects.get_or_create(doctor=doctor, qualification=qual)

            clinic = clinics[d['clinic']]
            DoctorClinic.objects.get_or_create(doctor=doctor, clinic=clinic)

            # Availability: Mon-Fri 9-13, 14-17
            for day_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                day = DayMaster.objects.get(day_name=day_name)
                DoctorAvailability.objects.get_or_create(
                    doctor=doctor, clinic=clinic, day=day,
                    defaults={'start_time': '09:00', 'end_time': '13:00'}
                )
                DoctorAvailability.objects.get_or_create(
                    doctor=doctor, clinic=clinic, day=day,
                    defaults={'start_time': '14:00', 'end_time': '17:00'}
                )

    def seed_demo_patients(self):
        for i in range(1, 6):
            patient_user = self._ensure_user(
                email=f'patient{i}@demo.example.com',
                full_name=f'Patient {i}',
                contact_number=self._get_unique_contact_number('7'),
                password='Demo@12345',
                role=self.roles['Patient'],
            )
            Patient.objects.get_or_create(
                user=patient_user,
                defaults={
                    'date_of_birth': f'199{i}-01-01',
                    'gender': 'Male' if i % 2 == 0 else 'Female',
                    'blood_group': 'O+' if i % 2 == 0 else 'A+',
                    'emergency_contact': f'800000000{i}',
                }
            )

    def seed_admin(self):
        admin_user = self._ensure_user(
            email='admin@demo.example.com',
            full_name='Admin User',
            contact_number=self._get_unique_contact_number('9'),
            password='Admin@12345',
            role=self.roles['Admin'],
        )
        Admin.objects.get_or_create(user=admin_user, defaults={'access_level': 'Super Admin'})