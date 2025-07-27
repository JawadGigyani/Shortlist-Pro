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
from .forms import UserForm, ProfileForm, JobDescriptionForm, ResumeForm
from .models import Resume, Shortlisted, Interview, JobDescription
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from datetime import timedelta


@login_required
def dashboard_home(request):
    resumes_count = Resume.objects.count()
    shortlisted_count = Shortlisted.objects.count()
    pending_interviews_count = Interview.objects.filter(status='pending').count()

    # Activity data for last 7 days
    today = timezone.now().date()
    activity_labels = []
    activity_resumes = []
    activity_shortlisted = []
    activity_interviews = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        activity_labels.append(day.strftime('%a'))
        activity_resumes.append(Resume.objects.filter(uploaded_at__date=day).count())
        activity_shortlisted.append(Shortlisted.objects.filter(created_at__date=day).count())
        activity_interviews.append(Interview.objects.filter(scheduled_at__date=day).count())

    context = {
        'resumes_count': resumes_count,
        'shortlisted_count': shortlisted_count,
        'pending_interviews_count': pending_interviews_count,
        'activity_labels': activity_labels,
        'activity_resumes': activity_resumes,
        'activity_shortlisted': activity_shortlisted,
        'activity_interviews': activity_interviews,
    }
    return render(request, 'home/dashboard_home.html', context)



@login_required
def job_descriptions(request):
    # Handle add new JD
    if request.method == 'POST' and 'add_jd' in request.POST:
        form = JobDescriptionForm(request.POST)
        if form.is_valid():
            jd = form.save(commit=False)
            jd.user = request.user
            jd.save()
            messages.success(request, 'Job Description added!')
            return redirect('job_descriptions')
    # Handle edit JD
    elif request.method == 'POST' and 'edit_jd_id' in request.POST:
        jd_id = request.POST.get('edit_jd_id')
        jd = JobDescription.objects.get(id=jd_id, user=request.user)
        form = JobDescriptionForm(request.POST, instance=jd)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job Description updated!')
            return redirect('job_descriptions')
    # Handle delete JD
    elif request.method == 'POST' and 'delete_jd_id' in request.POST:
        jd_id = request.POST.get('delete_jd_id')
        JobDescription.objects.filter(id=jd_id, user=request.user).delete()
        messages.success(request, 'Job Description deleted!')
        return redirect('job_descriptions')
    else:
        form = JobDescriptionForm()

    job_descriptions = JobDescription.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'home/job_descriptions.html', {
        'form': form,
        'job_descriptions': job_descriptions,
    })

@login_required
def resumes(request):
    # Handle bulk upload
    if request.method == 'POST' and 'bulk_upload' in request.POST:
        jd_id = request.POST.get('jd_id')
        jd = JobDescription.objects.filter(id=jd_id, user=request.user).first()
        files = request.FILES.getlist('resume_files')
        if jd and files:
            for f in files:
                Resume.objects.create(
                    user=request.user,
                    resume_file=f,
                    candidate_name='Unknown',
                    email='no-email@example.com',
                    phone='',
                    skills='',
                    education='',
                    experience='',
                    jobdescription=jd
                )
            messages.success(request, f'{len(files)} resumes uploaded for {jd.title}.')
            return redirect('resumes')
        else:
            messages.error(request, 'Please select a JD and upload at least one file.')
            return redirect('resumes')
    # Handle delete resume
    elif request.method == 'POST' and 'delete_resume_id' in request.POST:
        resume_id = request.POST.get('delete_resume_id')
        Resume.objects.filter(id=resume_id, user=request.user).delete()
        messages.success(request, 'Resume deleted successfully!')
        return redirect('resumes')

    # Fetch JDs and attach resumes for template
    job_descriptions = JobDescription.objects.filter(user=request.user).order_by('-created_at')
    for jd in job_descriptions:
        jd._resumes = Resume.objects.filter(user=request.user, jobdescription=jd).order_by('-uploaded_at')

    return render(request, 'home/resumes.html', {
        'job_descriptions': job_descriptions,
    })

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
