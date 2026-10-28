"""Idempotently add a small fictional data set for Seminar 3 demonstrations."""
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
    help = 'Create small, fictional, interconnected Seminar 3 demo data without duplicates.'

    def first_or_create(self, model, defaults=None, **lookup):
        return model.objects.filter(**lookup).first() or model.objects.create(**lookup, **(defaults or {}))

    def user(self, role, email, contact_number, full_name):
        return User.objects.filter(email=email).first() or User.objects.create(
            full_name=full_name, email=email, contact_number=contact_number,
            password_hash=make_password('Seminar3Demo!'), role=role,
            is_verified=True, account_status='active',
        )

    def handle(self, *args, **options):
        roles = {name: self.first_or_create(Role, role_name=name) for name in ('Patient', 'Doctor', 'Clinic', 'Clinic Staff', 'Admin')}
        locations = {
            'Gujarat': ('Ahmedabad', 'Surat', 'Vadodara', 'Rajkot', 'Gandhinagar'),
            'Maharashtra': ('Mumbai', 'Pune', 'Nagpur', 'Nashik'),
            'Rajasthan': ('Jaipur', 'Jodhpur', 'Udaipur'),
            'Karnataka': ('Bengaluru', 'Mysuru'),
            'Tamil Nadu': ('Chennai', 'Coimbatore'),
            'Telangana': ('Hyderabad',), 'West Bengal': ('Kolkata',),
            'Uttar Pradesh': ('Lucknow', 'Kanpur', 'Agra', 'Varanasi', 'Noida'),
            'Kerala': ('Kochi', 'Thiruvananthapuram'),
        }
        cities = {}
        for state_name, names in locations.items():
            state = self.first_or_create(StateMaster, state_name=state_name)
            for city_name in names:
                cities[(state_name, city_name)] = self.first_or_create(CityMaster, state=state, city_name=city_name)

        specs = {name: self.first_or_create(SpecializationMaster, specialization_name=name) for name in (
            'General Physician', 'Cardiologist', 'Dermatologist', 'Pediatrician', 'Orthopedic',
            'Gynecologist', 'Dentist', 'ENT Specialist', 'Neurologist', 'Ophthalmologist')}
        qualifications = {name: self.first_or_create(QualificationMaster, qualification_name=name) for name in ('MBBS', 'MD', 'MS', 'BDS', 'DNB', 'BAMS', 'BHMS')}
        days = {name: self.first_or_create(DayMaster, day_name=name) for name in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')}

        clinic_specs = [
            ('WellPoint Care Clinic', 'Gujarat', 'Ahmedabad', 'demo.clinic.ahmedabad@wellpoint.test', 9100001001),
            ('City Health Clinic', 'Gujarat', 'Surat', 'demo.clinic.surat@wellpoint.test', 9100001002),
            ('Mumbai Family Care Clinic', 'Maharashtra', 'Mumbai', 'demo.clinic.mumbai@wellpoint.test', 9100001003),
        ]
        clinics = {}
        for name, state, city, email, contact_number in clinic_specs:
            owner = self.user(roles['Clinic'], email, contact_number, name + ' Owner')
            clinics[name] = self.first_or_create(Clinic, user=owner, defaults={
                'clinic_name': name, 'address': 'Demo healthcare address', 'city': cities[(state, city)], 'contact_number': contact_number,
            })

        doctor_specs = [
            ('Aarav Sharma', 'General Physician', 'MBBS', 'WellPoint Care Clinic', 8, 500, 300),
            ('Meera Patel', 'Cardiologist', 'MD', 'WellPoint Care Clinic', 6, 600, 400),
            ('Riya Shah', 'Dermatologist', 'MBBS', 'City Health Clinic', 5, 550, 350),
            ('Ananya Desai', 'Gynecologist', 'MS', 'Mumbai Family Care Clinic', 7, 650, 450),
        ]
        doctors = []
        for index, (name, spec, qualification, clinic_name, experience, new_fee, old_fee) in enumerate(doctor_specs, 1):
            user = self.user(roles['Doctor'], f'demo.doctor{index}@wellpoint.test', 9100002000 + index, f'Dr. {name}')
            doctor = self.first_or_create(Doctor, user=user, defaults={
                'doctor_name': name, 'experience': experience, 'new_patient_fee': new_fee, 'old_patient_fee': old_fee,
                'about': f'Fictional Seminar 3 demonstration profile for Dr. {name}.',
            })
            clinic = clinics[clinic_name]
            self.first_or_create(DoctorClinic, doctor=doctor, clinic=clinic)
            self.first_or_create(DoctorSpecialization, doctor=doctor, specialization=specs[spec])
            self.first_or_create(DoctorQualification, doctor=doctor, qualification=qualifications[qualification])
            for d_name in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'):
                self.first_or_create(DoctorAvailability, doctor=doctor, clinic=clinic, day=days[d_name], start_time='10:00', end_time='16:00')
            doctors.append((doctor, clinic))

        patient_user = self.user(roles['Patient'], 'demo.patient@wellpoint.test', 9100003001, 'Demo Patient')
        patient = self.first_or_create(Patient, user=patient_user, defaults={'date_of_birth': '1995-05-15', 'gender': 'Other', 'blood_group': 'O+', 'emergency_contact': 9100003002})
        admin_user = self.user(roles['Admin'], 'demo.admin@wellpoint.test', 9100004001, 'Demo Administrator')
        self.first_or_create(Admin, user=admin_user, defaults={'access_level': 'Super Admin'})

        future_monday = timezone.localdate() + timedelta(days=(7 - timezone.localdate().weekday()) % 7 or 7)
        for doctor, clinic in doctors[:2]:
            appointment = self.first_or_create(Appointment, patient=patient, doctor=doctor, clinic=clinic,
                                               appointment_date=future_monday, appointment_time='10:00',
                                               defaults={'status': 'Confirmed', 'patient_type': 'New', 'fee_charged': doctor.new_patient_fee, 'symptoms': 'Fictional follow-up'})
            self.first_or_create(Payment, appointment=appointment, defaults={'amount': appointment.fee_charged, 'payment_method': 'Cash at Clinic', 'payment_status': 'Pending'})
        self.stdout.write(self.style.SUCCESS('Seminar 3 fictional demo data is ready.'))
