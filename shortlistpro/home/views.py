from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'home/index.html')

# def register(request):
#     return render(request, 'home/register.html')


from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect
from .forms import UserForm, ProfileForm

@login_required
def dashboard_home(request):
    return render(request, 'home/dashboard_home.html')

@login_required
def job_descriptions(request):
    return render(request, 'home/job_descriptions.html')

@login_required
def resumes(request):
    return render(request, 'home/resumes.html')

@login_required
def matching(request):
    return render(request, 'home/matching.html')

@login_required
def shortlisted(request):
    return render(request, 'home/shortlisted.html')

@login_required
def emails(request):
    return render(request, 'home/emails.html')

@login_required
def interviews(request):
    return render(request, 'home/interviews.html')

@login_required
def reports(request):
    return render(request, 'home/reports.html')

@login_required
def settings_view(request):
    return render(request, 'home/settings.html')


# Profile management view
@login_required
def profile_view(request):
    user_form = UserForm(instance=request.user)
    profile_form = ProfileForm(instance=request.user.profile)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            user_form = UserForm(request.POST, instance=request.user)
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
            else:
                messages.error(request, 'Please correct the errors below.')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
                return redirect('profile')
            else:
                messages.error(request, 'Please correct the errors below.')

    return render(request, 'home/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    })
