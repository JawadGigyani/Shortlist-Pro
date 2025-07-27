from registration.forms import RegistrationForm
from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture']


# Job Description Form
from .models import JobDescription, Resume
class JobDescriptionForm(forms.ModelForm):
    class Meta:
        model = JobDescription
        fields = ['title', 'department', 'description']

class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['candidate_name', 'email', 'phone', 'skills', 'education', 'experience', 'resume_file']
        widgets = {
            'candidate_name': forms.TextInput(attrs={'class': 'w-full border rounded px-3 py-2'}),
            'email': forms.EmailInput(attrs={'class': 'w-full border rounded px-3 py-2'}),
            'phone': forms.TextInput(attrs={'class': 'w-full border rounded px-3 py-2'}),
            'skills': forms.Textarea(attrs={'class': 'w-full border rounded px-3 py-2', 'rows': 3}),
            'education': forms.TextInput(attrs={'class': 'w-full border rounded px-3 py-2'}),
            'experience': forms.Textarea(attrs={'class': 'w-full border rounded px-3 py-2', 'rows': 3}),
            'resume_file': forms.FileInput(attrs={'class': 'w-full border rounded px-3 py-2'}),
        }

class CustomRegistrationForm(RegistrationForm):
    first_name = forms.CharField(max_length=30, required=True, help_text='Required')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required')
    email = forms.EmailField(required=True, help_text='Required')
    # ...existing code...
from registration.forms import RegistrationForm
from django import forms
from django.contrib.auth.models import User

class CustomRegistrationForm(RegistrationForm):
    first_name = forms.CharField(max_length=30, required=True, help_text='Required')
    last_name = forms.CharField(max_length=30, required=True, help_text='Required')
    email = forms.EmailField(required=True, help_text='Required')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']  # make sure you save email

        if commit:
            user.save()
        return user
