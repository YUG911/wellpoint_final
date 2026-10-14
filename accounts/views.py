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
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
    from doctors.models import Doctor, SpecializationMaster
    doctors = Doctor.objects.all()[:3]
    specializations_list = SpecializationMaster.objects.all()
    return render(request, 'home.html', {
        'doctors': doctors,
        'specializations': specializations_list,
    })


# ─── AUTHENTICATION ─────────────────────────────────────────────

def login_view(request):
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
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

                role_lower = user.role.role_name.lower()
                if role_lower in {'doctor', 'clinic', 'clinic staff'} and not user.is_verified:
                    messages.warning(request, "Your account is pending administrative verification. Please wait for approval before logging in.")
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
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data['role']
            user = User(
                full_name=form.cleaned_data['full_name'],
                email=form.cleaned_data['email'],
                contact_number=form.cleaned_data['contact_number'],
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
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
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
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
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
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
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
            messages.success(request, "Registration complete! Your clinic account is pending admin verification.")
            return redirect('login')
    else:
        form = ClinicForm()
    return render(request, 'accounts/register_clinic.html', {'form': form, 'states': states})


def register_staff(request):
    redirect_url = redirect_based_on_role(request)
    if redirect_url:
        return redirect(redirect_url)
    user_id = request.session.get('reg_user_id')
    reg_role = request.session.get('reg_role')
    if not user_id or (reg_role and reg_role.lower() != 'clinic staff'):
        messages.error(request, "Please register as Clinic Staff first.")
        return redirect('register')
    if request.method == 'POST':
        clinic_id = request.POST.get('clinic')
        user = get_object_or_404(User, user_id=user_id)
        if user.role.role_name.lower() != 'clinic staff':
            messages.error(request, "User is not authorized for staff registration.")
            return redirect('register')
        clinic = get_object_or_404(Clinic, clinic_id=clinic_id)
        ClinicStaff.objects.create(user=user, clinic=clinic)
        if 'reg_user_id' in request.session:
            del request.session['reg_user_id']
        if 'reg_role' in request.session:
            del request.session['reg_role']
        messages.success(request, "Registration complete! Your staff account is pending admin verification.")
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

    if request.method == 'POST':
        return add_clinic_doctor(request)

    from doctors.models import Doctor
    doctors = Doctor.objects.filter(doctor_clinic__clinic=clinic).prefetch_related('doctor_specialization__specialization')
    available_doctors = Doctor.objects.filter(
        user__is_verified=True,
        user__account_status='active'
    ).exclude(
        doctor_clinic__clinic=clinic
    ).prefetch_related('doctor_specialization__specialization').order_by('doctor_name')

    context = {
        'clinic': clinic,
        'doctors': doctors,
        'available_doctors': available_doctors,
    }
    return render(request, 'accounts/clinic_dashboard.html', context)


@login_required
@role_required('clinic')
def add_clinic_doctor(request):
    user = get_user_obj(request)
    clinic = Clinic.objects.filter(user=user).first()
    if not clinic:
        messages.warning(request, 'Please complete your clinic profile.')
        return redirect('register_clinic')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method. Doctor associations must be submitted via POST.')
        return redirect('clinic_dashboard')

    # Security check: clinic cannot modify another clinic's associations
    submitted_clinic_id = request.POST.get('clinic_id')
    if submitted_clinic_id and str(submitted_clinic_id).strip() != str(clinic.clinic_id):
        messages.error(request, 'Unauthorized action: You cannot modify associations for another clinic.')
        return redirect('clinic_dashboard')

    raw_doctor_id = request.POST.get('doctor_id', '').strip()
    if not raw_doctor_id:
        messages.error(request, 'Invalid doctor selection. Please choose a valid doctor.')
        return redirect('clinic_dashboard')

    try:
        doctor_id = int(raw_doctor_id)
    except (ValueError, TypeError):
        messages.error(request, 'Invalid doctor ID format.')
        return redirect('clinic_dashboard')

    from doctors.models import Doctor, DoctorClinic
    try:
        doctor = Doctor.objects.select_related('user').get(doctor_id=doctor_id)
    except Doctor.DoesNotExist:
        messages.error(request, 'Selected doctor does not exist.')
        return redirect('clinic_dashboard')

    if not doctor.user.is_verified:
        messages.error(request, 'This doctor is pending administrative verification and cannot be associated yet.')
        return redirect('clinic_dashboard')

    if doctor.user.account_status.lower() != 'active':
        messages.error(request, "This doctor's account is not active and cannot be associated.")
        return redirect('clinic_dashboard')

    assoc, created = DoctorClinic.objects.get_or_create(doctor=doctor, clinic=clinic)
    doc_display = doctor.doctor_name if doctor.doctor_name.startswith("Dr.") else f"Dr. {doctor.doctor_name}"
    if created:
        messages.success(request, f"Successfully associated {doc_display} with {clinic.clinic_name}.")
    else:
        messages.warning(request, f"{doc_display} is already associated with {clinic.clinic_name}.")

    return redirect('clinic_dashboard')


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
        messages.warning(request, 'Please complete your clinic profile.')
        return redirect('register_clinic')
    if request.method == 'POST':
        name = request.POST.get('clinic_name', '').strip()
        address = request.POST.get('address', '').strip()
        contact = request.POST.get('contact_number', '').strip()

        if not name or not address or not contact:
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/clinic_profile.html', {'clinic': clinic})

        try:
            contact_int = int(contact)
        except ValueError:
            messages.error(request, 'Please enter a valid numeric contact number.')
            return render(request, 'accounts/clinic_profile.html', {'clinic': clinic})

        clinic.clinic_name = name
        clinic.address = address
        clinic.contact_number = contact_int
        clinic.save(update_fields=['clinic_name', 'address', 'contact_number', 'updated_at'])
        messages.success(request, 'Clinic profile updated.')
        return redirect('clinic_profile')
    return render(request, 'accounts/clinic_profile.html', {'clinic': clinic})


def redirect_based_on_role(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    from accounts.models import User
    try:
        user = User.objects.select_related('role').get(user_id=user_id)
        if user.account_status.lower() != 'active':
            return None
        role = user.role.role_name.lower()
        if role in {'doctor', 'clinic', 'clinic staff'} and not user.is_verified:
            return None
        if role == 'patient': return 'patient_dashboard'
        if role == 'doctor': return 'doctor_dashboard'
        if role == 'clinic': return 'clinic_dashboard'
        if role == 'clinic staff': return 'staff_dashboard'
        if role == 'admin': return 'admin_dashboard'
    except:
        pass
    return None
