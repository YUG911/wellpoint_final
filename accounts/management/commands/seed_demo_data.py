
import random
from datetime import timedelta
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Admin, CityMaster, Clinic, DayMaster, Patient, Role, StateMaster, User
from appointments.models import Appointment, Payment
from doctors.models import (Doctor, DoctorAvailability, DoctorClinic,
                            DoctorQualification, DoctorSpecialization,
                            QualificationMaster, SpecializationMaster)

class Command(BaseCommand):
    help = 'Create 25-40 fictional demo doctors for Seminar 4 without duplicates.'

    def get_or_create_user(self, role, email, contact_number, full_name):
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'full_name': full_name,
                'contact_number': contact_number,
                'password_hash': make_password('Seminar4Demo!'),
                'role': role,
                'is_verified': True,
                'account_status': 'active'
            }
        )
        return user

    def handle(self, *args, **options):
        roles = {}
        for r in ['Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin']:
            roles[r], _ = Role.objects.get_or_create(role_name=r)

        state, _ = StateMaster.objects.get_or_create(state_name='Gujarat')
        cities = ['Ahmedabad', 'Gandhinagar', 'Surat', 'Vadodara', 'Rajkot', 'Bhavnagar', 'Jamnagar']
        city_objs = [CityMaster.objects.get_or_create(state=state, city_name=c)[0] for c in cities]

        clinics = []
        for i, c in enumerate(city_objs):
            user = self.get_or_create_user(roles['Clinic'], f'clinic{i}@demo.com', 9000000000+i, f'WellPoint {c.city_name} Center')
            clinic, _ = Clinic.objects.get_or_create(
                user=user, defaults={'clinic_name': f'WellPoint {c.city_name} Center', 'address': f'10{i} Main St, {c.city_name}', 'city': c, 'contact_number': 9000000000+i, 'latitude': 23.0+i*0.1, 'longitude': 72.0+i*0.1}
            )
            clinics.append(clinic)

        specs = ['General Medicine', 'Cardiology', 'Dermatology', 'Pediatrics', 'Orthopedics', 'ENT', 'Ophthalmology', 'Gynecology', 'Neurology', 'Psychiatry']
        spec_objs = {s: SpecializationMaster.objects.get_or_create(specialization_name=s)[0] for s in specs}

        quals = ['MBBS', 'MD', 'MS', 'DNB', 'DO']
        qual_objs = {q: QualificationMaster.objects.get_or_create(qualification_name=q)[0] for q in quals}

        first_names = ['Amit', 'Priya', 'Rahul', 'Sneha', 'Vikram', 'Neha', 'Rohan', 'Anjali', 'Karan', 'Pooja', 'Suresh', 'Kavita', 'Ramesh', 'Sunita', 'Raj', 'Anita']
        last_names = ['Patel', 'Sharma', 'Shah', 'Desai', 'Mehta', 'Joshi', 'Trivedi', 'Bhatt', 'Rathod', 'Chauhan']

        doctor_count = 0
        for s_name, spec in spec_objs.items():
            for i in range(3):
                fname = random.choice(first_names)
                lname = random.choice(last_names)
                full_name = f'Dr. {fname} {lname}'
                email = f'dr.{fname.lower()}{lname.lower()}{i}{s_name[:3].lower()}@demo.com'

                user = self.get_or_create_user(roles['Doctor'], email, 8000000000+doctor_count, full_name)
                doctor, created = Doctor.objects.get_or_create(
                    user=user,
                    defaults={
                        'doctor_name': full_name,
                        'experience': random.randint(3, 25),
                        'new_patient_fee': random.choice([500, 800, 1000, 1200]),
                        'old_patient_fee': random.choice([300, 500, 800, 1000]),
                        'about': f'Experienced {s_name} specialist.'
                    }
                )

                if created:
                    DoctorSpecialization.objects.get_or_create(doctor=doctor, specialization=spec)
                    DoctorQualification.objects.get_or_create(doctor=doctor, qualification=random.choice(list(qual_objs.values())))
                    DoctorClinic.objects.get_or_create(doctor=doctor, clinic=random.choice(clinics))

                    for d_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                        DayMaster.objects.get_or_create(day_name=d_name)
                    days = DayMaster.objects.all()
                    first_dc = doctor.doctor_clinic.first()
                    if first_dc and first_dc.clinic:
                        for d in days[:5]:
                            DoctorAvailability.objects.get_or_create(
                                doctor=doctor, clinic=first_dc.clinic, day=d,
                                start_time='09:00:00', end_time='13:00:00'
                            )
                doctor_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {doctor_count} doctors.'))
