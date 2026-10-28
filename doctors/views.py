from datetime import date
from django.db.models import Q
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from accounts.context_processors import login_required, role_required, current_user
from .models import Doctor, DoctorAvailability, Review
from accounts.models import Patient, Clinic, DayMaster
from appointments.models import Appointment


import math
import os
import logging
from django.conf import settings
import joblib

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees) using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def doctor_list(request):
    search = request.GET.get('search', '')
    specialization = request.GET.get('specialization', '')
    location = request.GET.get('location', '')
    symptoms = request.GET.get('symptoms', '')
    user_lat_raw = request.GET.get('user_lat', '').strip()
    user_lng_raw = request.GET.get('user_lng', '').strip()

    user_lat = None
    user_lng = None
    if user_lat_raw and user_lng_raw:
        try:
            lat_f = float(user_lat_raw)
            lng_f = float(user_lng_raw)
            if -90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0:
                user_lat = lat_f
                user_lng = lng_f
        except (ValueError, TypeError):
            user_lat = None
            user_lng = None

    is_geo_search = (user_lat is not None and user_lng is not None)

    # If the user performed a manual location search (not 'Current Location' or 'Near Me'),
    # prioritize manual search and discard any stale GPS coordinates
    loc_clean = location.strip()
    if loc_clean and loc_clean.lower() not in ('current location', 'my location', 'near me'):
        is_geo_search = False
        user_lat = None
        user_lng = None
    
    predicted_specialization = None
    if symptoms:
        try:
            model_path = os.path.join(settings.BASE_DIR, 'ml_model', 'symptom_model.joblib')
            pipeline = joblib.load(model_path)
            predicted_specialization = pipeline.predict([symptoms])[0]
            # Override specialization with the predicted one
            specialization = predicted_specialization
        except Exception as e:
            logger.warning("ML Prediction Error: %s", e)

    doctors = Doctor.objects.all()
    if search:
        doctors = doctors.filter(
            Q(doctor_name__icontains=search) |
            Q(doctor_specialization__specialization__specialization_name__icontains=search)
        ).distinct()
    if specialization and specialization.strip():
        doctors = doctors.filter(
            doctor_specialization__specialization__specialization_name__iexact=specialization.strip()
        ).distinct()
    if loc_clean:
        # If geolocation is active and location is a label like 'Current Location', skip textual filter
        if not (is_geo_search and loc_clean.lower() in ('current location', 'my location', 'near me')):
            doctors = doctors.filter(
                Q(doctor_clinic__clinic__city__city_name__icontains=loc_clean) |
                Q(doctor_clinic__clinic__address__icontains=loc_clean) |
                Q(doctor_clinic__clinic__clinic_name__icontains=loc_clean)
            ).distinct()

    from doctors.models import SpecializationMaster
    specializations = SpecializationMaster.objects.all()
    cities = Clinic.objects.values_list('city__city_name', flat=True).distinct()

    doctors = doctors.prefetch_related(
        'doctor_clinic__clinic__city',
        'doctor_specialization__specialization',
        'doctoravailability_set__clinic',
    )

    if is_geo_search:
        request.session['user_lat'] = str(user_lat)
        request.session['user_lng'] = str(user_lng)
        with_distance = []
        without_distance = []
        for doc in doctors:
            available_clinic_ids = {av.clinic_id for av in doc.doctoravailability_set.all()}
            min_dist = None
            nearest_clinic = None

            # 1. Primary: Closest clinic where doctor actually has availability
            for dc in doc.doctor_clinic.all():
                if dc.clinic_id in available_clinic_ids:
                    clinic = dc.clinic
                    if clinic and clinic.latitude is not None and clinic.longitude is not None:
                        try:
                            c_lat = float(clinic.latitude)
                            c_lng = float(clinic.longitude)
                            dist = haversine_distance_km(user_lat, user_lng, c_lat, c_lng)
                            if min_dist is None or dist < min_dist:
                                min_dist = dist
                                nearest_clinic = clinic
                        except (ValueError, TypeError):
                            continue

            # 2. Fallback: If no available clinic has coordinates or doctor has no availability set,
            # consider any associated clinic with coordinates
            if min_dist is None:
                for dc in doc.doctor_clinic.all():
                    clinic = dc.clinic
                    if clinic and clinic.latitude is not None and clinic.longitude is not None:
                        try:
                            c_lat = float(clinic.latitude)
                            c_lng = float(clinic.longitude)
                            dist = haversine_distance_km(user_lat, user_lng, c_lat, c_lng)
                            if min_dist is None or dist < min_dist:
                                min_dist = dist
                                nearest_clinic = clinic
                        except (ValueError, TypeError):
                            continue

            if min_dist is not None:
                doc.distance_km = round(min_dist, 1)
                doc.nearest_clinic = nearest_clinic
                with_distance.append(doc)
            else:
                doc.distance_km = None
                chosen_clinic = None
                for dc in doc.doctor_clinic.all():
                    if dc.clinic_id in available_clinic_ids:
                        chosen_clinic = dc.clinic
                        break
                if not chosen_clinic:
                    first_dc = doc.doctor_clinic.first()
                    chosen_clinic = first_dc.clinic if first_dc else None
                doc.nearest_clinic = chosen_clinic
                without_distance.append(doc)

        with_distance.sort(key=lambda d: d.distance_km)
        ordered_doctors = with_distance + without_distance
    else:
        if loc_clean and loc_clean.lower() not in ('current location', 'my location', 'near me'):
            request.session.pop('user_lat', None)
            request.session.pop('user_lng', None)
        ordered_doctors = list(doctors)
        for doc in ordered_doctors:
            doc.distance_km = None
            first_dc = doc.doctor_clinic.first()
            doc.nearest_clinic = first_dc.clinic if first_dc else None

    return render(request, 'doctors/doctor_list.html', {
        'doctors': ordered_doctors,
        'specializations': specializations,
        'cities': cities,
        'predicted_specialization': predicted_specialization,
        'symptoms_query': symptoms,
        'user_lat': user_lat if user_lat is not None else '',
        'user_lng': user_lng if user_lng is not None else '',
        'has_user_location': is_geo_search,
    })


def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(Doctor, doctor_id=doctor_id)
    specializations = doctor.doctor_specialization.all().select_related('specialization')
    qualifications = doctor.doctor_qualification.all().select_related('qualification')
    clinic_links = list(doctor.doctor_clinic.all().select_related('clinic', 'clinic__city'))
    clinics = [cl.clinic for cl in clinic_links]
    availabilities = DoctorAvailability.objects.filter(doctor=doctor).select_related('day', 'clinic')

    user_lat = None
    user_lng = None
    lat_raw = (request.GET.get('user_lat') or request.session.get('user_lat') or '').strip()
    lng_raw = (request.GET.get('user_lng') or request.session.get('user_lng') or '').strip()
    if lat_raw and lng_raw:
        try:
            lat_f = float(lat_raw)
            lng_f = float(lng_raw)
            if -90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0:
                user_lat = lat_f
                user_lng = lng_f
        except (ValueError, TypeError):
            user_lat = None
            user_lng = None

    if user_lat is not None and user_lng is not None:
        for cl in clinics:
            if cl.latitude is not None and cl.longitude is not None:
                try:
                    cl.distance_km = round(haversine_distance_km(user_lat, user_lng, float(cl.latitude), float(cl.longitude)), 1)
                except (ValueError, TypeError):
                    cl.distance_km = None
            else:
                cl.distance_km = None
        clinics.sort(key=lambda c: (c.distance_km is None, c.distance_km))

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
        'user_lat': user_lat if user_lat is not None else '',
        'user_lng': user_lng if user_lng is not None else '',
    })


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
                if start >= end:
                    messages.error(request, f'{day.day_name}: end time must be after start time.')
                    return redirect('doctor_availability')
                for clinic_id in clinic_ids:
                    clinic = get_object_or_404(
                        Clinic, clinic_id=clinic_id, doctorclinic__doctor=doctor
                    )
                    new_slots.append((clinic, day, start, end))
        for clinic, day, start, end in new_slots:
            DoctorAvailability.objects.get_or_create(
                doctor=doctor, clinic=clinic, day=day,
                start_time=start, end_time=end,
            )
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


@login_required
@role_required('doctor')
def confirm_appointment(request, appointment_id):
    doctor = get_object_or_404(Doctor, user=current_user(request))
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id, doctor=doctor)
    if appointment.status == 'Pending':
        appointment.status = 'Confirmed'
        appointment.save()
        messages.success(request, f"Appointment #{appointment.appointment_id} has been confirmed.")
    return redirect(request.META.get('HTTP_REFERER') or 'doctor_dashboard')
