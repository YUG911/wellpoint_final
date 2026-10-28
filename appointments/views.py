from datetime import datetime, timedelta, time
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.utils import timezone
from accounts.context_processors import login_required, role_required, current_user
from .models import Appointment, Payment
from accounts.models import Patient, Clinic, ClinicHours
from doctors.models import Doctor, DoctorAvailability
from doctors.models import Review

SLOT_MINUTES = 30


def clinic_opens_at(clinic, when_date, at_time):
    """
    Returns (is_open, message) for a clinic at a given date/time.

    A clinic that has no ClinicHours rows configured is treated as always open
    so existing data keeps working. As soon as a clinic defines its hours, the
    working day, opening time and closing time are enforced.
    """
    hours = ClinicHours.objects.filter(
        clinic=clinic, day__day_name__iexact=when_date.strftime('%A')
    ).first()
    if hours is None:
        if ClinicHours.objects.filter(clinic=clinic).exists():
            return False, f'{clinic.clinic_name} is closed on {when_date.strftime("%A")}.'
        return True, ''
    if at_time < hours.open_time:
        return False, f'{clinic.clinic_name} opens at {hours.open_time.strftime("%H:%M")} on this day.'
    if at_time >= hours.close_time:
        return False, f'{clinic.clinic_name} closes at {hours.close_time.strftime("%H:%M")} on this day.'
    return True, ''


def effective_slot_window(availability, clinic, when_date):
    """The doctor's availability window narrowed by the clinic's own hours."""
    open_time = availability.start_time
    close_time = availability.end_time
    hours = ClinicHours.objects.filter(
        clinic=clinic, day__day_name__iexact=when_date.strftime('%A')
    ).first()
    if hours is None and not ClinicHours.objects.filter(clinic=clinic).exists():
        return open_time, close_time
    if hours is None:
        return None, None
    return max(open_time, hours.open_time), min(close_time, hours.close_time)


def build_available_slots(doctor, clinic, days=14, exclude_appointment_id=None):
    """
    Builds {date_string: {'date': date, 'slots': ['HH:MM', ...]}} using the
    existing doctor availability table, narrowed by clinic hours, with already
    booked times removed.
    """
    today = timezone.localdate()
    availabilities = DoctorAvailability.objects.filter(doctor=doctor).select_related('day', 'clinic')

    booked = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=today,
            appointment_date__lte=today + timedelta(days=days),
            status__in=['Pending', 'Confirmed'],
        )
        .exclude(appointment_id=exclude_appointment_id)
        .values_list('appointment_date', 'appointment_time')
    )

    result = {}
    for offset in range(days):
        current_date = today + timedelta(days=offset)
        day_name = current_date.strftime('%A')
        slots = []
        for availability in availabilities.filter(day__day_name__iexact=day_name):
            window_start, window_end = effective_slot_window(availability, availability.clinic, current_date)
            if window_start is None or window_end <= window_start:
                continue
            cursor = datetime.combine(current_date, window_start)
            window_close = datetime.combine(current_date, window_end)
            while cursor < window_close:
                slot_time = cursor.time()
                if cursor.date() == today and slot_time <= timezone.localtime().time():
                    cursor += timedelta(minutes=SLOT_MINUTES)
                    continue
                if (current_date, slot_time) not in booked:
                    slots.append((slot_time, availability.clinic))
                cursor += timedelta(minutes=SLOT_MINUTES)
        if slots:
            slots.sort(key=lambda item: item[0])
            result[current_date.isoformat()] = {
                'date': current_date,
                'slots': [slot.strftime('%H:%M') for slot, _ in slots],
            }
    return result


@login_required
@role_required('patient')
def book_appointment(request, doctor_id):
    user = current_user(request)
    patient = get_object_or_404(Patient, user=user)
    doctor = get_object_or_404(Doctor, doctor_id=doctor_id)
    clinics = doctor.doctor_clinic.all().select_related('clinic')

    if request.method == 'POST':
        clinic_id = request.POST.get('clinic_id')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        symptoms = request.POST.get('symptoms', '')
        patient_type = request.POST.get('patient_type', 'New')

        if clinic_id:
            clinic = get_object_or_404(Clinic, clinic_id=clinic_id, doctorclinic__doctor=doctor)
        elif clinics:
            clinic = clinics[0].clinic
        else:
            messages.error(request, "This doctor is not currently associated with a clinic.")
            return redirect('doctor_detail', doctor_id=doctor_id)

        try:
            selected_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            selected_time = datetime.strptime(appointment_time, '%H:%M').time()
        except (TypeError, ValueError):
            messages.error(request, "Please choose a valid available date and time.")
            return redirect('book_appointment', doctor_id=doctor_id)
        if selected_date < timezone.localdate() or (selected_date == timezone.localdate() and selected_time <= timezone.localtime().time()):
            messages.error(request, "Please choose a future appointment time.")
            return redirect('book_appointment', doctor_id=doctor_id)
        if not DoctorAvailability.objects.filter(doctor=doctor, clinic=clinic, day__day_name__iexact=selected_date.strftime('%A'), start_time__lte=selected_time, end_time__gt=selected_time).exists():
            messages.error(request, "That time is not available at the selected clinic.")
            return redirect('book_appointment', doctor_id=doctor_id)
        is_open, hours_message = clinic_opens_at(clinic, selected_date, selected_time)
        if not is_open:
            messages.error(request, hours_message)
            return redirect('book_appointment', doctor_id=doctor_id)
        if Appointment.objects.filter(
            doctor=doctor, appointment_date=selected_date,
            appointment_time=selected_time, status__in=['Pending', 'Confirmed']
        ).exists():
            messages.error(request, "This time slot is already booked. Please select another.")
            return redirect('book_appointment', doctor_id=doctor_id)

        fee = doctor.new_patient_fee if patient_type == 'New' else doctor.old_patient_fee

        with transaction.atomic():
            if Appointment.objects.filter(doctor=doctor, appointment_date=selected_date,
                                          appointment_time=selected_time,
                                          status__in=['Pending', 'Confirmed']).exists():
                messages.error(request, "This time slot was just booked. Please select another.")
                return redirect('book_appointment', doctor_id=doctor_id)
            appointment = Appointment.objects.create(
                patient=patient, doctor=doctor, clinic=clinic,
                appointment_date=selected_date, appointment_time=selected_time,
                symptoms=symptoms, status='Pending', patient_type=patient_type,
                fee_charged=fee)
        return redirect('appointment_confirmation', appointment_id=appointment.appointment_id)

    available_slots = build_available_slots(doctor, None)
    if clinics:
        clinic_slots = {}
        for link in clinics:
            clinic_slots.update(build_available_slots(doctor, link.clinic))
        available_slots = clinic_slots or available_slots

    return render(request, 'appointments/book_appointment.html', {
        'doctor': doctor,
        'patient': patient,
        'clinics': clinics,
        'available_slots': available_slots,
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
    patient = get_object_or_404(Patient, user=user)
    appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date')
    return render(request, 'appointments/my_appointments.html', {
        'patient': patient,
        'appointments': appointments,
    })


@login_required
@role_required('patient')
def reschedule_appointment(request, appointment_id):
    user = current_user(request)
    patient = get_object_or_404(Patient, user=user)
    appointment = get_object_or_404(
        Appointment, appointment_id=appointment_id, patient=patient,
        status__in=['Pending', 'Confirmed']
    )
    doctor = appointment.doctor

    if request.method == 'POST':
        new_date = request.POST.get('appointment_date')
        new_time = request.POST.get('appointment_time')

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
        is_open, hours_message = clinic_opens_at(appointment.clinic, selected_date, selected_time)
        if not is_open:
            messages.error(request, hours_message)
            return redirect('reschedule_appointment', appointment_id=appointment_id)
        if Appointment.objects.filter(
            doctor=doctor, appointment_date=selected_date,
            appointment_time=selected_time, status__in=['Pending', 'Confirmed']
        ).exclude(appointment_id=appointment_id).exists():
            messages.error(request, "This time slot is already booked.")
            return redirect('reschedule_appointment', appointment_id=appointment_id)

        appointment.appointment_date = selected_date
        appointment.appointment_time = selected_time
        appointment.save()
        messages.success(request, "Appointment rescheduled successfully.")
        return redirect('my_appointments')

    available_slots = build_available_slots(
        doctor, appointment.clinic, exclude_appointment_id=appointment_id
    )

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
    patient = get_object_or_404(Patient, user=user)
    appointment = get_object_or_404(
        Appointment, appointment_id=appointment_id, patient=patient, status='Completed'
    )
    if Review.objects.filter(appointment=appointment).exists():
        messages.info(request, "You have already reviewed this appointment.")
        return redirect('my_appointments')

    if request.method == 'POST':
        rating = request.POST.get('rating')
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
