from datetime import datetime, timedelta
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction, IntegrityError, OperationalError
from django.utils import timezone
from accounts.context_processors import login_required, role_required, current_user
from .models import Appointment, Payment
from accounts.models import Patient, Clinic, User, Role
from doctors.models import Doctor, DoctorAvailability
from records.models import PatientRecord, Prescription, Report
from doctors.models import Review
from django.http import JsonResponse


@login_required
@role_required('patient')
def book_appointment(request, doctor_id):
    user = current_user(request)
    patient = Patient.objects.filter(user=user).first()
    if not patient:
        messages.warning(request, 'Please complete your patient profile first.')
        return redirect('register_patient')
    doctor = get_object_or_404(Doctor, doctor_id=doctor_id)
    if not doctor.user.is_verified or getattr(doctor, 'license_verification_status', 'Pending') != 'Approved' or doctor.user.account_status.lower() != 'active':
        messages.error(request, "This doctor is not currently verified or eligible for booking.")
        return redirect('doctor_list')
    from doctors.views import haversine_distance_km

    # Read location coordinates if provided (via GET query or session)
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

    doctor_clinics = list(doctor.doctor_clinic.all().select_related('clinic', 'clinic__city'))

    if user_lat is not None and user_lng is not None:
        for dc in doctor_clinics:
            cl = dc.clinic
            if cl.latitude is not None and cl.longitude is not None:
                try:
                    dist = haversine_distance_km(user_lat, user_lng, float(cl.latitude), float(cl.longitude))
                    dc.distance_km = round(dist, 1)
                    cl.distance_km = dc.distance_km
                except (ValueError, TypeError):
                    dc.distance_km = None
                    cl.distance_km = None
            else:
                dc.distance_km = None
                cl.distance_km = None
        doctor_clinics.sort(key=lambda dc: (dc.distance_km is None, dc.distance_km))
    else:
        for dc in doctor_clinics:
            dc.distance_km = None
            dc.clinic.distance_km = None

    clinics = doctor_clinics

    if request.method == 'POST':
        clinic_id = request.POST.get('clinic_id')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        selected_slot = request.POST.get('selected_slot')
        symptoms = request.POST.get('symptoms', '')
        patient_type = request.POST.get('patient_type', 'New')

        if selected_slot and '|' in selected_slot:
            parts = [p.strip() for p in selected_slot.split('|')]
            if len(parts) >= 2:
                appointment_date = parts[0]
                appointment_time = parts[1]
                if len(parts) >= 3 and parts[2]:
                    clinic_id = parts[2]

        clinic = None
        if clinic_id:
            try:
                clinic_id_int = int(clinic_id)
                clinic = Clinic.objects.filter(clinic_id=clinic_id_int, doctorclinic__doctor=doctor).first()
            except (ValueError, TypeError):
                clinic = None
        elif clinics:
            clinic = clinics[0].clinic

        if not clinic:
            if clinics:
                clinic = clinics[0].clinic
            else:
                messages.error(request, "This doctor is not currently associated with a clinic.")
                return redirect('doctor_detail', doctor_id=doctor_id)

        try:
            selected_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            selected_time = datetime.strptime(appointment_time, '%H:%M').time()
        except (TypeError, ValueError):
            messages.warning(request, "Please choose a valid available date and time.")
            return redirect('book_appointment', doctor_id=doctor_id)
        if selected_date < timezone.localdate() or (selected_date == timezone.localdate() and selected_time <= timezone.localtime().time()):
            messages.warning(request, "Please choose a future appointment time.")
            return redirect('book_appointment', doctor_id=doctor_id)
        if not DoctorAvailability.objects.filter(doctor=doctor, clinic=clinic, day__day_name__iexact=selected_date.strftime('%A'), start_time__lte=selected_time, end_time__gt=selected_time).exists():
            messages.warning(request, "That time is not available at the selected clinic.")
            return redirect('book_appointment', doctor_id=doctor_id)
        # Double-booking check
        if Appointment.objects.filter(
            doctor=doctor, appointment_date=selected_date,
            appointment_time=selected_time, status__in=['Pending', 'Confirmed']
        ).exists():
            messages.warning(request, "This time slot is already booked. Please select another.")
            return redirect('book_appointment', doctor_id=doctor_id)

        fee = doctor.new_patient_fee if patient_type == 'New' else doctor.old_patient_fee

        # Concurrency-safe atomic section with row locking on the Doctor
        try:
            with transaction.atomic():
                Doctor.objects.select_for_update().get(doctor_id=doctor.doctor_id)
                if Appointment.objects.filter(doctor=doctor, appointment_date=selected_date,
                                              appointment_time=selected_time,
                                              status__in=['Pending', 'Confirmed']).exists():
                    messages.error(request, "This time slot was just booked by another patient. Please select another time.")
                    return redirect('book_appointment', doctor_id=doctor_id)
                appointment = Appointment.objects.create(
                    patient=patient, doctor=doctor, clinic=clinic,
                    appointment_date=selected_date, appointment_time=selected_time,
                    symptoms=symptoms, status='Pending', patient_type=patient_type,
                    fee_charged=fee)
        except IntegrityError:
            messages.error(request, "This time slot was just booked by another patient. Please select another time.")
            return redirect('book_appointment', doctor_id=doctor_id)
        except OperationalError:
            slot_occupied = False
            try:
                slot_occupied = Appointment.objects.filter(
                    doctor=doctor, appointment_date=selected_date,
                    appointment_time=selected_time, status__in=['Pending', 'Confirmed']
                ).exists()
            except OperationalError:
                slot_occupied = False

            if slot_occupied:
                messages.error(request, "This time slot was just booked by another patient. Please select another time.")
            else:
                messages.error(request, "The booking system is currently busy. Please try again.")
            return redirect('book_appointment', doctor_id=doctor_id)
        return redirect('appointment_confirmation', appointment_id=appointment.appointment_id)

    # Get available slots
    today = timezone.localdate()
    now_time = timezone.localtime().time()
    next_14_days = [today + timedelta(days=i) for i in range(14)]
    availabilities = DoctorAvailability.objects.filter(doctor=doctor).select_related('day', 'clinic')

    # Build available dates/slots
    available_slots = {}
    for avail in availabilities:
        day_name = avail.day.day_name.lower()
        for d in next_14_days:
            if d.strftime('%A').lower() == day_name:
                date_str = d.strftime('%Y-%m-%d')
                if date_str not in available_slots:
                    available_slots[date_str] = {'date': d, 'slots': []}

    booked = Appointment.objects.filter(
        doctor=doctor, appointment_date__in=[s['date'] for s in available_slots.values()],
        status__in=['Pending', 'Confirmed']
    ).values_list('appointment_date', 'appointment_time')

    clinic_slot_counts = {}
    for date_str, data in available_slots.items():
        d = data['date']
        day_qs = availabilities.filter(day__day_name__iexact=d.strftime('%A'))
        for avail_obj in day_qs:
            start_time = datetime.strptime(str(avail_obj.start_time), '%H:%M:%S').time()
            end_time = datetime.strptime(str(avail_obj.end_time), '%H:%M:%S').time()

            current = datetime.combine(d, start_time)
            end_dt = datetime.combine(d, end_time)
            interval = timedelta(minutes=30)
            while current < end_dt:
                slot_time = current.time().strftime('%H:%M')
                if d == today and current.time() <= now_time:
                    current += interval
                    continue
                already_booked = any(
                    b[0] == d and b[1] == current.time()
                    for b in booked
                )
                slot_entry = {'time': slot_time, 'clinic_id': avail_obj.clinic.clinic_id}
                if not already_booked and slot_entry not in data['slots']:
                    data['slots'].append(slot_entry)
                    clinic_slot_counts[avail_obj.clinic.clinic_id] = clinic_slot_counts.get(avail_obj.clinic.clinic_id, 0) + 1
                current += interval
        
        # Sort slots chronologically
        data['slots'].sort(key=lambda x: x['time'])

    # Filter out dates with no slots
    available_slots = {k: v for k, v in available_slots.items() if v['slots']}

    # Track slot availability per clinic
    for dc in clinics:
        dc.has_available_slots = (clinic_slot_counts.get(dc.clinic.clinic_id, 0) > 0)
        dc.clinic.has_available_slots = dc.has_available_slots

    # Pre-select clinic: explicit requested clinic > nearest clinic with available slots > first clinic
    requested_clinic_raw = request.GET.get('clinic_id')
    default_clinic_id = None
    if requested_clinic_raw:
        try:
            rc_id = int(requested_clinic_raw)
            if any(dc.clinic.clinic_id == rc_id for dc in clinics):
                default_clinic_id = rc_id
        except (ValueError, TypeError):
            default_clinic_id = None

    if not default_clinic_id:
        for dc in clinics:
            if dc.has_available_slots:
                default_clinic_id = dc.clinic.clinic_id
                break
        if not default_clinic_id and clinics:
            default_clinic_id = clinics[0].clinic.clinic_id

    return render(request, 'appointments/book_appointment.html', {
        'doctor': doctor,
        'patient': patient,
        'clinics': clinics,
        'default_clinic_id': default_clinic_id,
        'available_slots': available_slots,
        'user_lat': user_lat if user_lat is not None else '',
        'user_lng': user_lng if user_lng is not None else '',
    })


@login_required
@role_required('patient')
def appointment_confirmation(request, appointment_id):
    patient = get_object_or_404(Patient, user=current_user(request))
    appointment = get_object_or_404(Appointment.objects.select_related('doctor', 'clinic'), appointment_id=appointment_id, patient=patient)
    return render(request, 'appointments/appointment_confirmation.html', {'appointment': appointment})

@login_required
@role_required('patient')
def my_appointments(request):
    user = current_user(request)
    patient = Patient.objects.filter(user=user).first()
    if not patient:
        messages.warning(request, 'Please complete your patient profile first.')
        return redirect('register_patient')
    appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date')
    return render(request, 'appointments/my_appointments.html', {
        'patient': patient,
        'appointments': appointments,
    })


@login_required
@role_required('patient')
def reschedule_appointment(request, appointment_id):
    user = current_user(request)
    patient = Patient.objects.filter(user=user).first()
    if not patient:
        messages.warning(request, 'Please complete your patient profile first.')
        return redirect('register_patient')
    appointment = get_object_or_404(
        Appointment, appointment_id=appointment_id, patient=patient,
        status__in=['Pending', 'Confirmed']
    )
    doctor = appointment.doctor

    if request.method == 'POST':
        new_date = request.POST.get('appointment_date')
        new_time = request.POST.get('appointment_time')
        selected_slot = request.POST.get('selected_slot')

        if selected_slot and '|' in selected_slot:
            parts = [p.strip() for p in selected_slot.split('|')]
            if len(parts) >= 2:
                if not new_date:
                    new_date = parts[0]
                if not new_time:
                    new_time = parts[1]

        try:
            selected_date = datetime.strptime(new_date, '%Y-%m-%d').date()
            selected_time = datetime.strptime(new_time, '%H:%M').time()
        except (TypeError, ValueError):
            messages.error(request, "Please choose a valid available date and time.")
            return redirect('reschedule_appointment', appointment_id=appointment_id)
        if selected_date < timezone.localdate() or (selected_date == timezone.localdate() and selected_time <= timezone.localtime().time()):
            messages.error(request, "Please choose a future appointment time.")
            return redirect('reschedule_appointment', appointment_id=appointment_id)
        if not DoctorAvailability.objects.filter(doctor=doctor, clinic=appointment.clinic,
                day__day_name__iexact=selected_date.strftime('%A'), start_time__lte=selected_time,
                end_time__gt=selected_time).exists():
            messages.error(request, "That time is not available at this clinic.")
            return redirect('reschedule_appointment', appointment_id=appointment_id)
        try:
            with transaction.atomic():
                Doctor.objects.select_for_update().get(doctor_id=doctor.doctor_id)
                if Appointment.objects.filter(
                    doctor=doctor, appointment_date=selected_date,
                    appointment_time=selected_time, status__in=['Pending', 'Confirmed']
                ).exclude(appointment_id=appointment_id).exists():
                    messages.error(request, "This time slot was just booked by another patient. Please select another time.")
                    return redirect('reschedule_appointment', appointment_id=appointment_id)

                appointment.appointment_date = selected_date
                appointment.appointment_time = selected_time
                appointment.save()
        except IntegrityError:
            messages.error(request, "This time slot was just booked by another patient. Please select another time.")
            return redirect('reschedule_appointment', appointment_id=appointment_id)
        except OperationalError:
            slot_occupied = False
            try:
                slot_occupied = Appointment.objects.filter(
                    doctor=doctor, appointment_date=selected_date,
                    appointment_time=selected_time, status__in=['Pending', 'Confirmed']
                ).exclude(appointment_id=appointment_id).exists()
            except OperationalError:
                slot_occupied = False

            if slot_occupied:
                messages.error(request, "This time slot was just booked by another patient. Please select another time.")
            else:
                messages.error(request, "The rescheduling system is currently busy. Please try again.")
            return redirect('reschedule_appointment', appointment_id=appointment_id)

        messages.success(request, "Appointment rescheduled successfully.")
        return redirect('my_appointments')

    today = timezone.localdate()
    now_time = timezone.localtime().time()
    availabilities = DoctorAvailability.objects.filter(doctor=doctor, clinic=appointment.clinic).select_related('day', 'clinic')

    available_slots = {}
    for d_idx in range(14):
        d = today + timedelta(days=d_idx)
        day_name = d.strftime('%A').lower()
        day_qs = availabilities.filter(day__day_name__iexact=day_name)
        if day_qs.exists():
            date_str = d.strftime('%Y-%m-%d')
            slots = []
            for avail_obj in day_qs:
                start_time = datetime.strptime(str(avail_obj.start_time), '%H:%M:%S').time()
                end_time = datetime.strptime(str(avail_obj.end_time), '%H:%M:%S').time()

                current = datetime.combine(d, start_time)
                end_dt = datetime.combine(d, end_time)
                interval = timedelta(minutes=30)
                while current < end_dt:
                    slot_time = current.time().strftime('%H:%M')
                    if d == today and current.time() <= now_time:
                        current += interval
                        continue
                    already_booked = Appointment.objects.filter(
                        doctor=doctor, appointment_date=d,
                        appointment_time=current.time()
                    ).exclude(appointment_id=appointment_id).exists()
                    if not already_booked and slot_time not in slots:
                        slots.append(slot_time)
                    current += interval
            if slots:
                slots.sort()
                available_slots[date_str] = {'date': d, 'slots': slots}

    return render(request, 'appointments/reschedule_appointment.html', {
        'appointment': appointment,
        'doctor': doctor,
        'available_slots': available_slots,
    })


@login_required
@role_required('patient')
def cancel_appointment(request, appointment_id):
    patient = get_object_or_404(Patient, user=current_user(request))
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id, patient=patient,
                                    status__in=['Pending', 'Confirmed'])
    if request.method == 'POST':
        appointment.status = 'Cancelled'
        appointment.save(update_fields=['status'])
        messages.success(request, 'Appointment cancelled.')
    return redirect('my_appointments')


@login_required
@role_required('patient')
def submit_review(request, appointment_id):
    user = current_user(request)
    patient = Patient.objects.filter(user=user).first()
    if not patient:
        messages.warning(request, 'Please complete your patient profile first.')
        return redirect('register_patient')
    appointment = get_object_or_404(
        Appointment, appointment_id=appointment_id, patient=patient, status='Completed'
    )
    if Review.objects.filter(appointment=appointment).exists():
        messages.info(request, "You have already reviewed this appointment.")
        return redirect('my_appointments')

    if request.method == 'POST':
        try:
            rating = float(request.POST.get('rating', 0))
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            messages.error(request, "Please provide a valid rating between 1 and 5.")
            return redirect('submit_review', appointment_id=appointment_id)
            
        review_text = request.POST.get('review_text', '')
        Review.objects.create(
            patient=patient, doctor=appointment.doctor,
            appointment=appointment, rating=rating, review_text=review_text
        )
        messages.success(request, "Your review has been submitted.")
        return redirect('my_appointments')
    return render(request, 'appointments/submit_review.html', {
        'appointment': appointment, 'doctor': appointment.doctor,
    })



@login_required
@role_required('patient')
def payment_page(request, appointment_id):
    patient = get_object_or_404(Patient, user=current_user(request))
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id, patient=patient)
    payment = Payment.objects.filter(appointment=appointment).first()
    if request.method == 'POST':
        method = request.POST.get('payment_method')
        if method not in {'Cash at Clinic', 'Online'}:
            messages.error(request, 'Choose a payment method.')
        else:
            payment, _ = Payment.objects.update_or_create(
                appointment=appointment,
                defaults={'amount': appointment.fee_charged or 0, 'payment_method': method, 'payment_status': 'Pending'},
            )
            messages.success(request, 'Payment preference saved. Payment remains pending until processed.')
            return redirect('my_appointments')
    return render(request, 'appointments/payment.html', {'appointment': appointment, 'payment': payment})
