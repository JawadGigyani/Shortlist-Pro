from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'home/index.html')

# def register(request):
#     return render(request, 'home/register.html')


import requests
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


def get_notifications():
    """Helper function to get notifications for header"""
    notifications = []
    
    # Get recent resumes for notifications
    recent_resumes_notif = Resume.objects.order_by('-uploaded_at')[:2]
    for resume in recent_resumes_notif:
        notifications.append({
            'title': 'New resume uploaded',
            'description': f'A new candidate has submitted their resume',
            'time_ago': get_time_ago(resume.uploaded_at),
            'color': 'blue',
            'icon': '''<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                   </svg>''',
            'timestamp': resume.uploaded_at
        })
    
    # Get recent shortlisted for notifications
    recent_shortlisted_notif = Shortlisted.objects.select_related('resume').order_by('-created_at')[:2]
    for shortlisted in recent_shortlisted_notif:
        notifications.append({
            'title': 'Candidate shortlisted',
            'description': f'AI matching found a high-potential candidate',
            'time_ago': get_time_ago(shortlisted.created_at),
            'color': 'green',
            'icon': '''<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                   </svg>''',
            'timestamp': shortlisted.created_at
        })
    
    # Get upcoming interviews for notifications
    upcoming_interviews = Interview.objects.select_related('resume').filter(
        scheduled_at__gte=timezone.now(),
        scheduled_at__lte=timezone.now() + timedelta(hours=24)
    ).order_by('scheduled_at')[:1]
    
    for interview in upcoming_interviews:
        notifications.append({
            'title': 'Interview reminder',
            'description': f'You have an interview scheduled soon',
            'time_ago': get_time_ago(interview.scheduled_at),
            'color': 'purple',
            'icon': '''<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                   </svg>''',
            'timestamp': interview.scheduled_at
        })
    
    # Sort notifications by timestamp (most recent first) and limit to 5
    notifications.sort(key=lambda x: x['timestamp'], reverse=True)
    return notifications[:5]


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

    # Recent Activities (last 10 activities across all models)
    recent_activities = []
    
    # Get recent resumes
    recent_resumes = Resume.objects.order_by('-uploaded_at')[:3]
    for resume in recent_resumes:
        recent_activities.append({
            'title': 'New resume uploaded',
            'description': f'{resume.candidate_name or "Unknown Candidate"} - {resume.email or "No email"}',
            'time_ago': get_time_ago(resume.uploaded_at),
            'color': 'blue',
            'icon': '''<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                   </svg>''',
            'timestamp': resume.uploaded_at
        })
    
    # Get recent shortlisted candidates
    recent_shortlisted = Shortlisted.objects.select_related('resume').order_by('-created_at')[:3]
    for shortlisted in recent_shortlisted:
        recent_activities.append({
            'title': 'Candidate shortlisted',
            'description': f'{shortlisted.resume.candidate_name or "Unknown Candidate"} - {shortlisted.resume.email or "No email"}',
            'time_ago': get_time_ago(shortlisted.created_at),
            'color': 'green',
            'icon': '''<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                   </svg>''',
            'timestamp': shortlisted.created_at
        })
    
    # Get recent interviews
    recent_interviews = Interview.objects.select_related('resume').order_by('-scheduled_at')[:3]
    for interview in recent_interviews:
        # Use scheduled_at since there's no created_at field
        interview_time = interview.scheduled_at or timezone.now()  # fallback if scheduled_at is None
        recent_activities.append({
            'title': 'Interview scheduled',
            'description': f'{interview.resume.candidate_name or "Unknown Candidate"} - {interview.resume.email or "No email"}',
            'time_ago': get_time_ago(interview_time),
            'color': 'purple',
            'icon': '''<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                   </svg>''',
            'timestamp': interview_time
        })
    
    # Sort all activities by timestamp (most recent first) and limit to 5
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:5]

    # Get notifications
    notifications = get_notifications()

    context = {
        'resumes_count': resumes_count,
        'shortlisted_count': shortlisted_count,
        'pending_interviews_count': pending_interviews_count,
        'activity_labels': activity_labels,
        'activity_resumes': activity_resumes,
        'activity_shortlisted': activity_shortlisted,
        'activity_interviews': activity_interviews,
        'recent_activities': recent_activities,
        'notifications': notifications,
        'notifications_count': len(notifications),
    }
    return render(request, 'home/dashboard_home.html', context)


def get_time_ago(datetime_obj):
    """Helper function to calculate human-readable time difference"""
    if datetime_obj is None:
        return "Unknown time"
    
    now = timezone.now()
    diff = now - datetime_obj
    
    if diff.days > 0:
        if diff.days == 1:
            return "1 day ago"
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"
    else:
        return "Just now"



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
    
    # Get notifications for header
    notifications = get_notifications()
    
    return render(request, 'home/job_descriptions.html', {
        'form': form,
        'job_descriptions': job_descriptions,
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def resumes(request):
    """
    Enhanced view to handle resume uploads with FastAPI parsing integration
    """
    job_descriptions = JobDescription.objects.filter(user=request.user).prefetch_related('resumes').order_by('-created_at')
    
    if request.method == 'POST':
        if 'bulk_upload' in request.POST:
            jd_id = request.POST.get('jd_id')
            jd = JobDescription.objects.filter(id=jd_id, user=request.user).first()
            files = request.FILES.getlist('resume_files')
            
            if not jd:
                messages.error(request, 'Please select a valid job description.')
                return redirect('resumes')
            
            if not files:
                messages.error(request, 'Please select at least one resume file.')
                return redirect('resumes')
            
            # Send files to FastAPI for parsing
            fastapi_url = 'http://127.0.0.1:8001/parse-resumes'
            files_payload = []
            for f in files:
                files_payload.append(('files', (f.name, f.read(), f.content_type)))
            
            try:
                response = requests.post(fastapi_url, files=files_payload)
                response.raise_for_status()
                api_response = response.json()
                parsed_data = api_response.get('results', [])
                
                # Process successful parses and save to database
                successful_saves = 0
                for result in parsed_data:
                    if result.get('status') == 'success':
                        try:
                            # Extract skills as comma-separated string
                            skills_list = result.get('skills', [])
                            skills_parts = []
                            if skills_list:
                                for skill in skills_list:
                                    if isinstance(skill, dict):
                                        skills_parts.append(skill.get('name', str(skill)))
                                    else:
                                        skills_parts.append(str(skill))
                            skills_str = ', '.join(skills_parts) if skills_parts else ''
                            
                            # Extract education as text
                            education_list = result.get('education', [])
                            education_parts = []
                            if education_list:
                                for edu in education_list:
                                    if isinstance(edu, dict):
                                        edu_text = f"{edu.get('degree', '')} in {edu.get('major', '')}" if edu.get('major') else edu.get('degree', '')
                                        if edu.get('university_name'):
                                            edu_text += f" from {edu.get('university_name')}"
                                        if edu.get('end_year'):
                                            edu_text += f" ({edu.get('end_year')})"
                                        education_parts.append(edu_text.strip())
                                    else:
                                        education_parts.append(str(edu))
                            education_str = '; '.join(education_parts) if education_parts else ''
                            
                            # Extract experience as text
                            experience_list = result.get('work_experience', [])
                            exp_parts = []
                            if experience_list:
                                for exp in experience_list:
                                    if isinstance(exp, dict):
                                        exp_text = f"{exp.get('job_title', 'Unknown Position')} at {exp.get('company_name', 'Unknown Company')}"
                                        if exp.get('start_date') or exp.get('end_date'):
                                            exp_text += f" ({exp.get('start_date', '')} - {exp.get('end_date', '')})"
                                        exp_parts.append(exp_text)
                                    else:
                                        exp_parts.append(str(exp))
                            experience_str = '; '.join(exp_parts) if exp_parts else ''
                            
                            # Extract certifications as text
                            certifications_list = result.get('certifications', [])
                            cert_parts = []
                            if certifications_list:
                                for cert in certifications_list:
                                    if isinstance(cert, dict):
                                        cert_parts.append(cert.get('name', str(cert)))
                                    else:
                                        cert_parts.append(str(cert))
                            certifications_str = ', '.join(cert_parts) if cert_parts else ''
                            
                            # Create Resume object with parsed data
                            Resume.objects.create(
                                user=request.user,
                                jobdescription=jd,
                                candidate_name=result.get('full_name', 'Unknown'),
                                email=result.get('email', 'no-email@example.com'),
                                phone=result.get('phone', ''),
                                skills=skills_str,
                                education=education_str,
                                experience=experience_str,
                                certifications=certifications_str,
                                # Note: We're not saving the file here as it was already processed
                            )
                            successful_saves += 1
                        except Exception as e:
                            messages.warning(request, f"Parsed {result.get('filename', 'unknown file')} but failed to save: {str(e)}")
                
                # Show results
                failed_parses = [result for result in parsed_data if result.get('status') == 'error']
                
                if successful_saves > 0:
                    messages.success(request, f'Successfully processed and saved {successful_saves} resume(s) for {jd.title}!')
                
                if failed_parses:
                    for failed in failed_parses:
                        messages.error(request, f"Failed to parse {failed.get('filename', 'unknown file')}: {failed.get('message', 'Unknown error')}")
                
                # Return with parsed data for display
                return render(request, 'home/resumes.html', {
                    'parsed_data': parsed_data, 
                    'job_descriptions': job_descriptions
                })
                
            except requests.exceptions.ConnectionError:
                messages.error(request, "Cannot connect to resume parser service. Please make sure the FastAPI server is running.")
                return redirect('resumes')
            except Exception as e:
                messages.error(request, f"Error communicating with resume parser: {str(e)}")
                return redirect('resumes')
        
        # Handle delete resume
        elif 'delete_resume_id' in request.POST:
            resume_id = request.POST.get('delete_resume_id')
            Resume.objects.filter(id=resume_id, user=request.user).delete()
            messages.success(request, 'Resume deleted successfully!')
            return redirect('resumes')
    
    # Get notifications for header
    notifications = get_notifications()

    return render(request, 'home/resumes.html', {
        'job_descriptions': job_descriptions,
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def matching(request):
    notifications = get_notifications()
    return render(request, 'home/matching.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def shortlisted(request):
    notifications = get_notifications()
    return render(request, 'home/shortlisted.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def emails(request):
    notifications = get_notifications()
    return render(request, 'home/emails.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def interviews(request):
    notifications = get_notifications()
    return render(request, 'home/interviews.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def reports(request):
    notifications = get_notifications()
    return render(request, 'home/reports.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })



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
        elif 'remove_picture' in request.POST:
            # Remove the profile picture
            if request.user.profile.profile_picture:
                request.user.profile.profile_picture.delete()
                request.user.profile.profile_picture = None
                request.user.profile.save()
                messages.success(request, 'Profile picture removed successfully.')
            else:
                messages.error(request, 'No profile picture to remove.')
            return redirect('profile')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
                return redirect('profile')
            else:
                messages.error(request, 'Please correct the errors below.')

    # Get notifications for header
    notifications = get_notifications()

    return render(request, 'home/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'notifications': notifications,
        'notifications_count': len(notifications),
    })