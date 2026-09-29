from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import render, redirect, get_object_or_404
from accounts.forms import (
    LoginForm, RegisterForm, PatientProfileForm,
    DoctorProfileForm, ClinicForm, AdminForm, UserProfileForm
)
from accounts.models import (
    User, Role, Patient, Clinic, ClinicStaff, Admin,
    CityMaster, StateMaster, DayMaster
)
from doctors.models import Doctor, DoctorAvailability, Review, SpecializationMaster, QualificationMaster
from appointments.models import Appointment, Payment
from records.models import PatientRecord, Prescription, Report


# ─── HOME ───────────────────────────────────────────────────────
def home(request):
    from doctors.models import Doctor, SpecializationMaster
    doctors = Doctor.objects.all()[:3]
    specializations_list = SpecializationMaster.objects.all()
    return render(request, 'home.html', {
        'doctors': doctors,
        'specializations': specializations_list,
    })


# ─── AUTHENTICATION ─────────────────────────────────────────────

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                user = User.objects.select_related('role').get(email=email)
            except User.DoesNotExist:
                messages.error(request, "Invalid email or password.")
                return render(request, 'accounts/login.html', {'form': form})

            if check_password(password, user.password_hash):
                if user.account_status.lower() != 'active':
                    messages.error(request, "Your account is not active.")
                    return render(request, 'accounts/login.html', {'form': form})

                request.session['user_id'] = user.user_id
                messages.success(request, f"Welcome back, {user.full_name}!")

                role = user.role.role_name.lower()
                if role == 'patient':
                    return redirect('patient_dashboard')
                if role == 'doctor':
                    return redirect('doctor_dashboard')
                if role == 'clinic':
                    return redirect('clinic_dashboard')
                if role == 'clinic staff':
                    return redirect('staff_dashboard')
                if role == 'admin':
                    return redirect('admin_dashboard')
                return redirect('home')
            else:
                messages.error(request, "Invalid email or password.")
                return render(request, 'accounts/login.html', {'form': form})
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out.")
    return redirect('home')


# ─── REGISTRATION ───────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            user = User(
                full_name=form.cleaned_data['full_name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                password_hash=make_password(form.cleaned_data['password']),
                address=form.cleaned_data.get('address', ''),
                role=role,
                is_verified=False,
                account_status='active'
            )
            user.save()
            request.session['reg_user_id'] = user.user_id
            request.session['reg_role'] = role.role_name

            if role.role_name.lower() == 'patient':
                return redirect('register_patient')
            if role.role_name.lower() == 'doctor':
                return redirect('register_doctor')
            if role.role_name.lower() == 'clinic':
                return redirect('register_clinic')
            if role.role_name.lower() == 'clinic staff':
                return redirect('register_staff')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def register_patient(request):
    user_id = request.session.get('reg_user_id') or request.session.get('user_id')
    if not user_id:
        return redirect('register')
    if request.method == 'POST':
        form = PatientProfileForm(request.POST)
        if form.is_valid():
            user = get_object_or_404(User, user_id=user_id)
            Patient.objects.create(
                user=user,
                date_of_birth=form.cleaned_data['date_of_birth'],
                gender=form.cleaned_data['gender'],
                blood_group=form.cleaned_data['blood_group'],
                emergency_contact=form.cleaned_data['emergency_contact']
            )
            del request.session['reg_user_id']
            del request.session['reg_role']
            messages.success(request, "Registration complete! Please log in.")
            return redirect('login')
    else:
        form = PatientProfileForm()
    return render(request, 'accounts/register_patient.html', {'form': form})


def register_doctor(request):
    user_id = request.session.get('reg_user_id') or request.session.get('user_id')
    if not user_id:
        return redirect('register')
    if request.method == 'POST':
        form = DoctorProfileForm(request.POST)
        if form.is_valid():
            user = get_object_or_404(User, user_id=user_id)
            doctor = Doctor.objects.create(
                user=user,
                doctor_name=form.cleaned_data['doctor_name'],
                experience=form.cleaned_data.get('experience'),
                new_patient_fee=form.cleaned_data['new_patient_fee'],
                old_patient_fee=form.cleaned_data['old_patient_fee'],
                about=form.cleaned_data.get('about', '')
            )
            from doctors.models import DoctorSpecialization, DoctorQualification
            for spec in form.cleaned_data['specializations']:
                DoctorSpecialization.objects.get_or_create(doctor=doctor, specialization=spec)
            for qual in form.cleaned_data['qualifications']:
                DoctorQualification.objects.get_or_create(doctor=doctor, qualification=qual)
            del request.session['reg_user_id']
            del request.session['reg_role']
            messages.success(request, "Registration complete! Your account is pending admin verification.")
            return redirect('login')
    else:
        form = DoctorProfileForm()
    return render(request, 'accounts/register_doctor.html', {'form': form})


def register_clinic(request):
    user_id = request.session.get('reg_user_id') or request.session.get('user_id')
    if not user_id:
        return redirect('register')
    states = StateMaster.objects.all()
    if request.method == 'POST':
        form = ClinicForm(request.POST)
        if form.is_valid():
            user = get_object_or_404(User, user_id=user_id)
            city_id = form.cleaned_data['city'].city_id
            city = get_object_or_404(CityMaster, city_id=city_id)
            Clinic.objects.create(
                user=user,
                clinic_name=form.cleaned_data['clinic_name'],
                address=form.cleaned_data['address'],
                city=city,
                contact_number=form.cleaned_data['contact_number'],
                latitude=form.cleaned_data['latitude'],
                longitude=form.cleaned_data['longitude']
            )
            del request.session['reg_user_id']
            del request.session['reg_role']
            messages.success(request, "Registration complete! Please log in.")
            return redirect('login')
    else:
        form = ClinicForm()
    return render(request, 'accounts/register_clinic.html', {'form': form, 'states': states})


def register_staff(request):
    user_id = request.session.get('reg_user_id') or request.session.get('user_id')
    if not user_id:
        return redirect('register')
    if request.method == 'POST':
        clinic_id = request.POST.get('clinic')
        user = get_object_or_404(User, user_id=user_id)
        clinic = get_object_or_404(Clinic, clinic_id=clinic_id)
        ClinicStaff.objects.create(user=user, clinic=clinic)
        del request.session['reg_user_id']
        del request.session['reg_role']
        messages.success(request, "Registration complete! Please log in.")
        return redirect('login')
    clinics = Clinic.objects.all()
    return render(request, 'accounts/register_staff.html', {'clinics': clinics})


# ─── DECORATORS ─────────────────────────────────────────────────

from accounts.context_processors import login_required, role_required, current_user


def get_user_obj(request):
    return current_user(request)


# ─── PATIENT DASHBOARD ──────────────────────────────────────────

@login_required
@role_required('patient')
def patient_dashboard(request):
    user = get_user_obj(request)
    patient = Patient.objects.filter(user=user).first()
    if not patient:
        messages.warning(request, 'Please complete your patient profile.')
        return redirect('register_patient')

    pending = Appointment.objects.filter(patient=patient, status__in=['Pending', 'Confirmed'])
    completed = Appointment.objects.filter(patient=patient, status='Completed')
    today = date.today()

    context = {
        'patient': patient,
        'pending_appointments': pending,
        'completed_appointments': completed[:5],
    }
    return render(request, 'accounts/patient_dashboard.html', context)


# ─── DOCTOR DASHBOARD ───────────────────────────────────────────

@login_required
@role_required('doctor')
def doctor_dashboard(request):
    user = get_user_obj(request)
    doctor = Doctor.objects.filter(user=user).first()
    if not doctor:
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.warning(request, 'Please complete your doctor profile.')
        return redirect('register_doctor')

    today = date.today()
    todays_appointments = Appointment.objects.filter(doctor=doctor, appointment_date=today)
    upcoming = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__gte=today,
        status__in=['Pending', 'Confirmed']
    )
    completed = Appointment.objects.filter(doctor=doctor, status='Completed')
    reviews = Review.objects.filter(doctor=doctor)

    total_rating = 0
    if reviews:
        total_rating = sum(float(r.rating) for r in reviews) / len(reviews)

    context = {
        'doctor': doctor,
        'todays_appointments': todays_appointments,
        'upcoming_appointments': upcoming[:5],
        'total_appointments': Appointment.objects.filter(doctor=doctor).count(),
        'completed_count': completed.count(),
        'avg_rating': round(total_rating, 1),
    }
    return render(request, 'doctors/doctor_dashboard.html', context)


# ─── CLINIC DASHBOARD ───────────────────────────────────────────

@login_required
@role_required('clinic')
def clinic_dashboard(request):
    user = get_user_obj(request)
    clinic = Clinic.objects.filter(user=user).first()
    if not clinic:
        messages.warning(request, 'Please complete your clinic profile.')
        return redirect('register_clinic')
    doctors = Doctor.objects.filter(doctor_clinic__clinic=clinic)

    context = {
        'clinic': clinic,
        'doctors': doctors,
    }
    return render(request, 'accounts/clinic_dashboard.html', context)


# ─── STAFF DASHBOARD ────────────────────────────────────────────

@login_required
@role_required('clinic staff')
def staff_dashboard(request):
    user = get_user_obj(request)
    staff = ClinicStaff.objects.filter(user=user).first()
    if not staff:
        messages.warning(request, 'Please complete your staff profile.')
        return redirect('register_staff')
    clinic = staff.clinic
    appointments = Appointment.objects.filter(clinic=clinic)

    context = {
        'staff': staff,
        'clinic': clinic,
        'appointments': appointments[:10],
    }
    return render(request, 'accounts/staff_dashboard.html', context)


# ─── ADMIN DASHBOARD ────────────────────────────────────────────

@login_required
@role_required('admin')
def admin_dashboard(request):
    verified = User.objects.filter(is_verified=True).count()
    pending = User.objects.filter(is_verified=False).exclude(account_status='rejected').count()
    total_patients = User.objects.filter(role__role_name='Patient').count()
    total_doctors = User.objects.filter(role__role_name='Doctor').count()
    total_clinics = User.objects.filter(role__role_name='Clinic').count()

    context = {
        'total_users': User.objects.count(),
        'verified_users': verified,
        'pending_verification': pending,
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_clinics': total_clinics,
        'unverified_users': User.objects.filter(is_verified=False).exclude(account_status='rejected')[:5],
    }
    return render(request, 'accounts/admin_dashboard.html', context)


# ─── PROFILE ────────────────────────────────────────────────────

@login_required
def profile(request):
    user = get_user_obj(request)
    form = UserProfileForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your profile has been updated.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'user': user, 'form': form})


# ─── VERIFICATION ───────────────────────────────────────────────

@login_required
@role_required('admin')
def verify_user(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '')
        target = get_object_or_404(User, user_id=user_id)
        admin = get_object_or_404(Admin, user=current_user(request))

        if action not in {'approve', 'reject'}:
            messages.error(request, 'Invalid verification action.')
            return redirect('admin_dashboard')
        status = 'Approved' if action == 'approve' else 'Rejected'
        from accounts.models import VerificationLog
        VerificationLog.objects.create(
            user=target, admin=admin, status=status, remarks=remarks
        )
        if action == 'approve':
            target.is_verified = True
            target.save()
        else:
            target.account_status = 'rejected'
            target.save()
        messages.success(request, f"User {target.full_name} {status.lower()}.")
    return redirect('admin_dashboard')


def get_cities(request):
    from django.http import JsonResponse
    state_name = request.GET.get('state', '')
    cities = CityMaster.objects.filter(state__state_name__iexact=state_name).values('city_id', 'city_name')
    return JsonResponse({'cities': list(cities)})



@login_required
@role_required('admin')
def user_management(request):
    users = User.objects.select_related('role').order_by('-user_id')
    return render(request, 'accounts/user_management.html', {'users': users})


@login_required
@role_required('admin')
def verification_history(request):
    from accounts.models import VerificationLog
    logs = VerificationLog.objects.select_related('user', 'admin__user').order_by('-verified_at')
    return render(request, 'accounts/verification_history.html', {'logs': logs})


@login_required
@role_required('clinic', 'clinic staff')
def clinic_appointments(request):
    user = current_user(request)
    clinic = Clinic.objects.filter(user=user).first() or get_object_or_404(ClinicStaff, user=user).clinic
    appointments = Appointment.objects.filter(clinic=clinic).select_related('patient__user', 'doctor').order_by('-appointment_date', '-appointment_time')
    return render(request, 'accounts/clinic_appointments.html', {'clinic': clinic, 'appointments': appointments})



@login_required
@role_required('clinic')
def clinic_profile(request):
    clinic = Clinic.objects.filter(user=current_user(request)).first()
    if not clinic:
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.warning(request, 'Please complete your clinic profile.')
        return redirect('register_clinic')
    if request.method == 'POST':
        clinic.clinic_name = request.POST.get('clinic_name', clinic.clinic_name).strip()
        clinic.address = request.POST.get('address', clinic.address).strip()
        clinic.contact_number = request.POST.get('contact_number', clinic.contact_number).strip()
        clinic.save(update_fields=['clinic_name', 'address', 'contact_number', 'updated_at'])
        messages.success(request, 'Clinic profile updated.')
        return redirect('clinic_profile')
    return render(request, 'accounts/clinic_profile.html', {'clinic': clinic})
