import random
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from accounts.models import (
    Role, StateMaster, CityMaster, User, Clinic, DayMaster
)
from doctors.models import (
    Doctor, SpecializationMaster, DoctorSpecialization,
    DoctorClinic, DoctorAvailability
)


class Command(BaseCommand):
    help = "Seeds idempotent demo data for WellPoint (State, City, Clinics, Doctors, Availability)"

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help="Clear ONLY demo data ending with @demo.test")

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing demo data...")
            User.objects.filter(email__endswith='@demo.test').delete()
            self.stdout.write(self.style.SUCCESS("Cleared demo data successfully."))
            return

        self.stdout.write("Starting demo data seed...")

        # 1. Setup Roles & Days
        role_clinic, _ = Role.objects.get_or_create(role_name='Clinic')
        role_doctor, _ = Role.objects.get_or_create(role_name='Doctor')
        days = list(DayMaster.objects.all())
        if not days:
            for name in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'):
                DayMaster.objects.get_or_create(day_name=name)
            days = list(DayMaster.objects.all())

        # 2. Setup State & Cities
        state_gujarat, _ = StateMaster.objects.get_or_create(state_name='Gujarat')
        city_names = ['Ahmedabad', 'Gandhinagar', 'Surat', 'Vadodara', 'Rajkot', 'Bhavnagar', 'Jamnagar']
        cities = []
        for cname in city_names:
            city, _ = CityMaster.objects.get_or_create(state=state_gujarat, city_name=cname)
            cities.append(city)
            
        # Also fix the placeholder if it exists
        placeholder_state = StateMaster.objects.filter(state_name='Workflow State').first()
        if placeholder_state:
            placeholder_state.state_name = 'Maharashtra'
            placeholder_state.save()
        placeholder_city = CityMaster.objects.filter(city_name='Workflow City').first()
        if placeholder_city:
            placeholder_city.city_name = 'Mumbai'
            placeholder_city.save()

        # 3. Setup Specializations
        spec_names = [
            'General Physician', 'Cardiologist', 'Dermatologist', 'ENT Specialist',
            'Gastroenterologist', 'Neurologist', 'Ophthalmologist', 'Orthopedic Surgeon',
            'Psychiatrist', 'Urologist'
        ]
        specializations = []
        for sname in spec_names:
            spec, _ = SpecializationMaster.objects.get_or_create(specialization_name=sname)
            specializations.append(spec)

        # 4. Create Clinics
        clinics = []
        clinic_lats = [23.0225, 23.2156, 21.1702, 22.3072, 22.3039]
        clinic_lons = [72.5714, 72.6369, 72.8311, 73.1812, 70.8022]
        
        for i in range(1, 6):
            email = f"demo_clinic_{i}@demo.test"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'full_name': f"Demo Clinic {i}",
                    'contact_number': f"990001000{i}",
                    'password_hash': make_password('Secret123!'),
                    'address': f"Demo Clinic Road {i}",
                    'role': role_clinic,
                    'is_verified': True,
                    'account_status': 'Active'
                }
            )
            city = cities[i % len(cities)]
            clinic, _ = Clinic.objects.get_or_create(
                user=user,
                defaults={
                    'clinic_name': f"WellPoint Demo Clinic {i}",
                    'address': f"Demo Clinic Road {i}",
                    'city': city,
                    'contact_number': f"990001000{i}",
                    'latitude': str(clinic_lats[i-1]),
                    'longitude': str(clinic_lons[i-1])
                }
            )
            clinics.append(clinic)

        # 5. Create Doctors
        doctor_idx = 1
        for spec in specializations:
            # 3 doctors per specialization
            for _ in range(3):
                email = f"demo_doc_{doctor_idx}@demo.test"
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'full_name': f"Dr. Demo {doctor_idx}",
                        'contact_number': f"9900020{doctor_idx:03d}",
                        'password_hash': make_password('Secret123!'),
                        'address': f"Demo Doctor Road {doctor_idx}",
                        'role': role_doctor,
                        'is_verified': True,
                        'account_status': 'Active'
                    }
                )
                
                doctor, _ = Doctor.objects.get_or_create(
                    user=user,
                    defaults={
                        'doctor_name': f"Dr. Demo {doctor_idx}",
                        'experience': random.randint(3, 20),
                        'new_patient_fee': float(random.choice([300, 400, 500, 600, 800])),
                        'old_patient_fee': float(random.choice([200, 300, 400, 500])),
                        'about': "Experienced demo doctor for WellPoint platform."
                    }
                )
                
                # Assign Specialization
                DoctorSpecialization.objects.get_or_create(doctor=doctor, specialization=spec)
                
                # Assign to 1 or 2 Clinics
                doc_clinics = random.sample(clinics, k=random.randint(1, 2))
                for c in doc_clinics:
                    DoctorClinic.objects.get_or_create(doctor=doctor, clinic=c)
                    
                    # Create some availability
                    DoctorAvailability.objects.get_or_create(
                        doctor=doctor, clinic=c, day=days[0],
                        defaults={'start_time': '09:00', 'end_time': '13:00'}
                    )
                    DoctorAvailability.objects.get_or_create(
                        doctor=doctor, clinic=c, day=days[1],
                        defaults={'start_time': '14:00', 'end_time': '18:00'}
                    )

                doctor_idx += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded demo data: {len(cities)} cities, {len(clinics)} clinics, {doctor_idx - 1} doctors."))
