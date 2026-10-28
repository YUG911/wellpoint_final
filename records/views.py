import os
import uuid
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.text import get_valid_filename
from accounts.context_processors import login_required, role_required, current_user
from .models import PatientRecord, Prescription, Report
from appointments.models import Appointment
from accounts.models import Patient
from doctors.models import Doctor

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.txt'}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_uploaded_file(uploaded_file):
    """
    Validates uploaded file size, extension, and content headers.
    Returns (is_valid, error_message, sanitized_filename).
    """
    if not uploaded_file:
        return False, "No file selected.", None

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        return False, "File exceeds the 5MB size limit.", None

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file format '{ext}'. Allowed formats: PDF, JPG, PNG, TXT.", None

    header = uploaded_file.read(512)
    uploaded_file.seek(0)

    if ext == '.pdf' and not header.startswith(b'%PDF-'):
        return False, "Invalid PDF file content.", None
    elif ext == '.png' and not header.startswith(b'\x89PNG\r\n\x1a\n'):
        return False, "Invalid PNG image content.", None
    elif ext in ('.jpg', '.jpeg') and not header.startswith(b'\xff\xd8\xff'):
        return False, "Invalid JPEG image content.", None
    elif ext == '.txt':
        try:
            text_sample = header.decode('utf-8', errors='ignore').lower()
            if '<script' in text_sample or '<html' in text_sample or '<?php' in text_sample:
                return False, "Invalid text file content.", None
        except Exception:
            return False, "Invalid text file encoding.", None

    base_name = get_valid_filename(os.path.splitext(uploaded_file.name)[0])[:30] or 'upload'
    safe_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
    return True, None, safe_name


@login_required
@role_required('doctor')
def add_record(request, appointment_id):
    user = current_user(request)
    doctor = get_object_or_404(Doctor, user=user)
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id, doctor=doctor)
    patient = appointment.patient

    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis', '')
        notes = request.POST.get('notes', '')
        PatientRecord.objects.update_or_create(
            appointment=appointment,
            defaults={
                'patient': patient,
                'doctor': doctor,
                'diagnosis': diagnosis,
                'notes': notes,
            }
        )
        appointment.status = 'Completed'
        appointment.save()
        if not Prescription.objects.filter(appointment=appointment).exists():
            Prescription.objects.create(appointment=appointment, uploaded_by=user, file_path='')
        messages.success(request, "Record added. Appointment marked as Completed.")
        return redirect('doctor_appointments')

    record_exists = PatientRecord.objects.filter(appointment=appointment).exists()
    existing_record = None
    if record_exists:
        existing_record = PatientRecord.objects.get(appointment=appointment)
    return render(request, 'records/add_record.html', {
        'doctor': doctor, 'appointment': appointment,
        'patient': patient, 'record_exists': record_exists,
        'record': existing_record,
    })


@login_required
@role_required('doctor')
def upload_prescription(request, appointment_id):
    user = current_user(request)
    doctor = get_object_or_404(Doctor, user=user)
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id, doctor=doctor)

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        is_valid, err, safe_name = validate_uploaded_file(uploaded_file)
        if not is_valid:
            messages.error(request, err)
            return render(request, 'records/upload_prescription.html', {
                'doctor': doctor, 'appointment': appointment,
            })
        from django.core.files.storage import default_storage
        saved_path = default_storage.save(f'prescriptions/{safe_name}', uploaded_file)
        Prescription.objects.update_or_create(
            appointment=appointment, defaults={'uploaded_by': user, 'file_path': saved_path}
        )
        messages.success(request, "Prescription uploaded.")
        return redirect('doctor_appointments')
    return render(request, 'records/upload_prescription.html', {
        'doctor': doctor, 'appointment': appointment,
    })


@login_required
@role_required('patient')
def my_records(request):
    user = current_user(request)
    patient = get_object_or_404(Patient, user=user)
    records = PatientRecord.objects.filter(patient=patient)
    return render(request, 'records/my_records.html', {'patient': patient, 'records': records})


@login_required
@role_required('patient')
def my_prescriptions(request):
    user = current_user(request)
    patient = get_object_or_404(Patient, user=user)
    prescriptions = Prescription.objects.filter(appointment__patient=patient)
    return render(request, 'records/my_prescriptions.html', {'patient': patient, 'prescriptions': prescriptions})


@login_required
@role_required('patient')
def my_reports(request):
    user = current_user(request)
    patient = get_object_or_404(Patient, user=user)
    reports = Report.objects.filter(appointment__patient=patient)
    return render(request, 'records/my_reports.html', {'patient': patient, 'reports': reports})


@login_required
@role_required('clinic staff')
def upload_report(request, appointment_id):
    user = current_user(request)
    appointment = get_object_or_404(
        Appointment, appointment_id=appointment_id, clinic__clinicstaff__user=user
    )
    if request.method == 'POST':
        report_name = request.POST.get('report_name', '').strip() or 'Medical Report'
        uploaded_file = request.FILES.get('file')
        is_valid, err, safe_name = validate_uploaded_file(uploaded_file)
        if not is_valid:
            messages.error(request, err)
            return render(request, 'records/upload_report.html', {'appointment': appointment})
        from django.core.files.storage import default_storage
        saved_path = default_storage.save(f'reports/{safe_name}', uploaded_file)
        Report.objects.create(
            appointment=appointment, uploaded_by=user,
            report_name=report_name, file_path=saved_path
        )
        messages.success(request, "Report uploaded successfully.")
        return redirect('staff_dashboard')
    return render(request, 'records/upload_report.html', {'appointment': appointment})
