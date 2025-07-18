from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'home/index.html')

# def register(request):
#     return render(request, 'home/register.html')

from django.contrib.auth.decorators import login_required

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
