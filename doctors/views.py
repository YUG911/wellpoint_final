                    from datetime import datetime

from django.db.models import Q, Avg
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from accounts.context_processors import login_required, role_required, current_user
from .models import Doctor, DoctorAvailability, Review, SpecializationMaster
from .recommendation import predict_specialization, match_specialization, model_is_available
from accounts.models import Patient, Clinic, DayMaster
from appointments.models import Appointment


def doctor_list(request):
    search = request.GET.get('search', '')
    specialization = request.GET.get('specialization', '')
    location = request.GET.get('location', '')

    if search:
        doctors = doctors.filter(
            Q(doctor_name__icontains=search) |
            Q(doctor_specialization__specialization__specialization_name__icontains=search)
        ).distinct()
    if specialization:
        doctors = doctors.filter(
            doctor_specialization__specialization__specialization_name__icontains=specialization
        ).distinct()
    if location:
        doctors = doctors.filter(
            doctor_clinic__clinic__city__city_name__icontains=location
        ).distinct()

    specializations = SpecializationMaster.objects.all()
    cities = Clinic.objects.values_list('city__city_name', flat=True).distinct()
    clinic_locations = list(
        Clinic.objects.exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .values_list('city__city_name', 'latitude', 'longitude')
        .distinct()
    )

    return render(request, 'doctors/doctor_list.html', {
        'doctors': doctors,
        'specializations': specializations,
        'cities': cities,
        'clinic_locations': clinic_locations,
    })


def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(Doctor, doctor_id=doctor_id)
    specializations = doctor.doctor_specialization.all().select_related('specialization')
    qualifications = doctor.doctor_qualification.all().select_related('qualification')
    clinic_links = doctor.doctor_clinic.all().select_related('clinic')
    clinics = [cl.clinic for cl in clinic_links]
    availabilities = DoctorAvailability.objects.filter(doctor=doctor).select_related('day', 'clinic')

    reviews = Review.objects.filter(doctor=doctor).order_by('-created_at')[:5]
    avg_rating = 0
    if reviews:
        avg_rating = sum(float(r.rating) for r in reviews) / len(reviews)

    return render(request, 'doctors/doctor_detail.html', {
        'doctor': doctor,
        'specializations': specializations,
        'qualifications': qualifications,
        'clinics': clinics,
        'availabilities': availabilities,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
    })


@login_required
@role_required('patient')
def recommend_doctor(request):
    context = {'model_ready': model_is_available()}
    symptoms = request.POST.get('symptoms', '') if request.method == 'POST' else request.GET.get('symptoms', '')

    if not symptoms.strip():
        if request.method == 'POST':
            messages.error(request, 'Please describe your symptoms first.')
        return render(request, 'doctors/recommend_doctor.html', context)

    predicted, inference_time = predict_specialization(symptoms)
    context.update({'symptoms': symptoms, 'inference_time': inference_time})

    if predicted is None:
        messages.error(request, 'The recommendation model is not available right now. Please use normal doctor search.')
        return render(request, 'doctors/recommend_doctor.html', context)

    context['predicted_specialization'] = predicted
    specialization = match_specialization(predicted)

    if specialization is None:
        context['no_specialization'] = predicted
        return render(request, 'doctors/recommend_doctor.html', context)

    context['specialization'] = specialization

    doctors = (
        Doctor.objects.filter(doctor_specialization__specialization=specialization)
        .distinct()
    )

    ranked = []
    for doctor in doctors:
        availability_slots = DoctorAvailability.objects.filter(doctor=doctor).count()
        clinic_count = doctor.doctor_clinic.count()
        rating = (
            Review.objects.filter(doctor=doctor)
            .aggregate(value=Avg('rating'))['value']
        )
        ranked.append({
            'doctor': doctor,
            'availability_slots': availability_slots,
            'clinic_count': clinic_count,
            'rating': round(float(rating), 1) if rating else 0.0,
            'is_available': availability_slots > 0,
            'score': availability_slots + clinic_count * 2 + (float(rating) if rating else 0.0),
        })

    ranked.sort(key=lambda row: (-row['score'], row['doctor'].doctor_name))
    context['recommendations'] = ranked
    return render(request, 'doctors/recommend_doctor.html', context)


@login_required
@role_required('doctor')
def doctor_profile(request):
    user = current_user(request)
    doctor = get_object_or_404(Doctor, user=user)
    from doctors.models import DoctorSpecialization, DoctorQualification, DoctorClinic
    specializations = DoctorSpecialization.objects.filter(doctor=doctor).select_related('specialization')
    qualifications = DoctorQualification.objects.filter(doctor=doctor).select_related('qualification')
    clinics = DoctorClinic.objects.filter(doctor=doctor).select_related('clinic')
    return render(request, 'doctors/doctor_profile.html', {
        'doctor': doctor,
        'specializations': specializations,
        'qualifications': qualifications,
        'clinics': clinics,
    })


@login_required
@role_required('doctor')
def doctor_availability(request):
    user = current_user(request)
    doctor = get_object_or_404(Doctor, user=user)
    days = DayMaster.objects.all().order_by('day_id')
    clinics = Clinic.objects.filter(doctorclinic__doctor=doctor)

    if request.method == 'POST':
        new_slots = []
        for day in days:
            day_id = day.day_id
            start = request.POST.get(f'start_{day_id}')
            end = request.POST.get(f'end_{day_id}')
            clinic_ids = request.POST.getlist(f'clinics_{day_id}')
            if start and end and clinic_ids:
                try:
                    start_time = datetime.strptime(start, '%H:%M').time()
                    end_time = datetime.strptime(end, '%H:%M').time()
                except ValueError:
                    messages.error(request, f'{day.day_name}: enter times as HH:MM.')
                    return redirect('doctor_availability')
                if start_time >= end_time:
                    messages.error(request, f'{day.day_name}: end time must be after start time.')
                    return redirect('doctor_availability')
                for clinic_id in clinic_ids:
                    clinic = get_object_or_404(
                        Clinic, clinic_id=clinic_id, doctorclinic__doctor=doctor
                    )
                    new_slots.append((clinic, day, start_time, end_time))
        DoctorAvailability.objects.filter(doctor=doctor).delete()
        for clinic, day, start_time, end_time in new_slots:
            DoctorAvailability.objects.create(doctor=doctor, clinic=clinic, day=day,
                                              start_time=start_time, end_time=end_time)
        messages.success(request, "Availability updated successfully.")
        return redirect('doctor_availability')

    existing = DoctorAvailability.objects.filter(doctor=doctor).select_related('day', 'clinic')
    return render(request, 'doctors/doctor_availability.html', {
        'doctor': doctor,
        'days': days,
        'clinics': clinics,
        'existing_availability': existing,
    })


@login_required
@role_required('doctor')
def doctor_appointments(request):
    user = current_user(request)
    doctor = get_object_or_404(Doctor, user=user)
    status_filter = request.GET.get('status', '')
    patient_id = request.GET.get('patient', '')
    appointments = Appointment.objects.filter(doctor=doctor).order_by('-appointment_date')
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if patient_id:
        appointments = appointments.filter(patient__patient_id=patient_id)
    return render(request, 'doctors/doctor_appointments.html', {
        'doctor': doctor,
        'appointments': appointments,
    })


@login_required
@role_required('doctor')
def doctor_patients(request):
    user = current_user(request)
    doctor = get_object_or_404(Doctor, user=user)
    patients = Patient.objects.filter(
        appointment__doctor=doctor
    ).distinct()
    return render(request, 'doctors/doctor_patients.html', {
        'doctor': doctor,
        'patients': patients,
    })



@login_required
@role_required('doctor')
def doctor_appointment_detail(request, appointment_id):
    doctor = get_object_or_404(Doctor, user=current_user(request))
    appointment = get_object_or_404(Appointment.objects.select_related('patient__user', 'clinic'), appointment_id=appointment_id, doctor=doctor)
    return render(request, 'doctors/doctor_appointment_detail.html', {'doctor': doctor, 'appointment': appointment})
