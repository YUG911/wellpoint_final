from django import forms
from accounts.models import User, Role, StateMaster, CityMaster
from doctors.models import SpecializationMaster, QualificationMaster


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email address'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter your password'})
    )


class RegisterForm(forms.Form):

    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email address'})
    )
    phone = forms.IntegerField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'placeholder': 'Enter your phone number'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create a strong password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm your password'})
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.exclude(role_name__iexact='Admin').order_by('role_name'),
        empty_label='Select your role',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter your address'})
    )
    terms_accepted = forms.BooleanField(required=True, error_messages={'required': 'You must accept the Terms of Service and Privacy Policy.'})

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Phone number already registered.")
        return phone


class PatientProfileForm(forms.Form):
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    gender = forms.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
                               widget=forms.RadioSelect)
    blood_group = forms.ChoiceField(
    choices=[
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('Unknown', "Don't Know")
    ],
    widget=forms.Select(attrs={'class': 'form-control'})
)
    emergency_contact = forms.IntegerField(widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}))


class DoctorProfileForm(forms.Form):
    doctor_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    experience = forms.IntegerField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    new_patient_fee = forms.DecimalField(max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    old_patient_fee = forms.DecimalField(max_digits=10, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    about = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    specializations = forms.ModelMultipleChoiceField(
        queryset=SpecializationMaster.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )
    qualifications = forms.ModelMultipleChoiceField(
        queryset=QualificationMaster.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )


class ClinicForm(forms.Form):
    clinic_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(max_length=500, widget=forms.TextInput(attrs={'class': 'form-control'}))
    state = forms.ModelChoiceField(queryset=StateMaster.objects.all(), widget=forms.Select(attrs={'class': 'form-control'}))
    city = forms.ModelChoiceField(queryset=CityMaster.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    contact_number = forms.IntegerField(widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}))
    latitude = forms.DecimalField(max_digits=10, decimal_places=7, required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    longitude = forms.DecimalField(max_digits=10, decimal_places=7, required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        state_id = self.data.get('state') or self.initial.get('state')
        if state_id:
            self.fields['city'].queryset = CityMaster.objects.filter(state_id=state_id).order_by('city_name')


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('full_name', 'phone', 'address')
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
