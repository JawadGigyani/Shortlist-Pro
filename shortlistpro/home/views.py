from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'home/index.html')

def pricing(request):
    return render(request, 'home/pricing.html')

def contact(request):
    return render(request, 'home/contact.html')

def documentation(request):
    return render(request, 'home/documentation.html')

def privacy_policy(request):
    return render(request, 'home/privacy_policy.html')

def terms_of_service(request):
    return render(request, 'home/terms_of_service.html')

# def register(request):
#     return render(request, 'home/register.html')


import requests
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect
from django.http import JsonResponse
from .forms import UserForm, ProfileForm, JobDescriptionForm, ResumeForm
from .models import Resume, Shortlisted, Interview, JobDescription, MatchingResult
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from datetime import timedelta
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

# FastAPI matching service configuration
FASTAPI_MATCHING_URL = "http://localhost:8001/match-resume"
FASTAPI_TIMEOUT = 60  # Increased timeout for AI processing


def call_fastapi_matching_service(job_description, resume):
    """
    Call the FastAPI resume matching service
    
    Args:
        job_description: JobDescription model instance
        resume: Resume model instance
        
    Returns:
        dict: Response from FastAPI service or None if failed
    """
    try:
        # Prepare resume data as JSON string
        resume_data = {
            "candidate_name": resume.candidate_name or "Unknown",
            "email": resume.email or "",
            "phone": resume.phone or "",
            "years_of_experience": resume.years_of_experience or 0,
            "career_level": resume.career_level or "",
            "experience": resume.work_experience or [],
            "education": resume.education or [],
            "skills": resume.skills or [],
            "certifications": resume.certifications or [],
            "projects": resume.projects or [],
            "extracurricular_activities": resume.extracurricular or [],
            "summary": resume.professional_summary or "",
            "languages": getattr(resume, 'languages', []) or []
        }
        
        # Prepare request payload
        payload = {
            "job_description": job_description.description,
            "candidate_resume_json": json.dumps(resume_data)
        }
        
        # Make the API call
        logger.info(f"Calling FastAPI matching service for resume {resume.id}")
        response = requests.post(
            FASTAPI_MATCHING_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=FASTAPI_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Successfully processed resume {resume.id}")
            return result
        else:
            logger.error(f"FastAPI service returned status {response.status_code}: {response.text}")
            return {
                'success': False,
                'error': f"Service error: {response.status_code}"
            }
            
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to FastAPI matching service")
        return {
            'success': False,
            'error': "Matching service is not available. Please ensure the AI service is running."
        }
    except requests.exceptions.Timeout:
        logger.error("FastAPI matching service timeout")
        return {
            'success': False,
            'error': "Matching service timeout. Please try again."
        }
    except Exception as e:
        logger.error(f"Error calling FastAPI service: {str(e)}")
        return {
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }


def get_notifications(user):
    """Helper function to get notifications for header - filtered by user"""
    notifications = []
    
    # Get recent resumes for notifications - filtered by user
    recent_resumes_notif = Resume.objects.filter(user=user).order_by('-uploaded_at')[:2]
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
    
    # Get recent shortlisted for notifications - filtered by user
    recent_shortlisted_notif = Shortlisted.objects.filter(resume__user=user).select_related('resume').order_by('-created_at')[:2]
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
    
    # Get upcoming interviews for notifications - filtered by user
    upcoming_interviews = Interview.objects.filter(
        resume__user=user,
        scheduled_at__gte=timezone.now(),
        scheduled_at__lte=timezone.now() + timedelta(hours=24)
    ).select_related('resume').order_by('scheduled_at')[:1]
    
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
    # Filter all data by current user
    user = request.user
    resumes_count = Resume.objects.filter(user=user).count()
    shortlisted_count = Shortlisted.objects.filter(resume__user=user).count()
    pending_interviews_count = Interview.objects.filter(resume__user=user, status='pending').count()

    # Activity data for last 7 days - filtered by user
    today = timezone.now().date()
    activity_labels = []
    activity_resumes = []
    activity_shortlisted = []
    activity_interviews = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        activity_labels.append(day.strftime('%a'))
        activity_resumes.append(Resume.objects.filter(user=user, uploaded_at__date=day).count())
        activity_shortlisted.append(Shortlisted.objects.filter(resume__user=user, created_at__date=day).count())
        activity_interviews.append(Interview.objects.filter(resume__user=user, scheduled_at__date=day).count())

    # Recent Activities (last 10 activities across all models) - filtered by user
    recent_activities = []
    
    # Get recent resumes for current user only
    recent_resumes = Resume.objects.filter(user=user).order_by('-uploaded_at')[:3]
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
    
    # Get recent shortlisted candidates for current user only
    recent_shortlisted = Shortlisted.objects.filter(resume__user=user).select_related('resume').order_by('-created_at')[:3]
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
    
    # Get recent interviews for current user only
    recent_interviews = Interview.objects.filter(resume__user=user).select_related('resume').order_by('-scheduled_at')[:3]
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

    # Get notifications for current user
    notifications = get_notifications(user)

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
    notifications = get_notifications(request.user)
    
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
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if 'bulk_upload' in request.POST:
            jd_id = request.POST.get('jd_id')
            jd = JobDescription.objects.filter(id=jd_id, user=request.user).first()
            files = request.FILES.getlist('resume_files')
            
            if not jd:
                error_msg = 'Please select a valid job description.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_msg})
                messages.error(request, error_msg)
                return redirect('resumes')
            
            if not files:
                error_msg = 'Please select at least one resume file.'
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_msg})
                messages.error(request, error_msg)
                return redirect('resumes')
            
            # Validate file extensions
            supported_extensions = ['.pdf', '.doc', '.docx']
            invalid_files = []
            for f in files:
                file_ext = '.' + f.name.split('.')[-1].lower() if '.' in f.name else ''
                if file_ext not in supported_extensions:
                    invalid_files.append(f.name)
            
            if invalid_files:
                error_msg = f"Unsupported file format: {', '.join(invalid_files)}. Only PDF, DOC, and DOCX files are allowed."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_msg})
                messages.error(request, error_msg)
                return redirect('resumes')
            
            # Send files to FastAPI for parsing (one by one)
            fastapi_url = 'http://127.0.0.1:8001/parse-resumes'
            parsed_data = []
            
            for f in files:
                try:
                    # Reset file pointer for each file
                    f.seek(0)
                    files_payload = {'file': (f.name, f.read(), f.content_type)}
                    
                    response = requests.post(fastapi_url, files=files_payload)
                    response.raise_for_status()
                    api_response = response.json()
                    
                    # Convert FastAPI response to expected format
                    if api_response.get('success'):
                        data = api_response.get('data', {})
                        basic_info = data.get('basic_info', {})
                        professional_summary = data.get('professional_summary', {})
                        additional_info = data.get('additional_info', {})
                        
                        result = {
                            'status': 'success',
                            'filename': api_response.get('filename'),
                            'full_data': data,  # Store the complete data
                            'basic_info': basic_info,
                            'professional_summary': professional_summary,
                            'additional_info': additional_info,
                            # Flattened for backward compatibility
                            'full_name': basic_info.get('full_name', 'Unknown'),
                            'email': basic_info.get('email', 'no-email@example.com'),
                            'phone': basic_info.get('phone', ''),
                            'skills': data.get('skills', []),
                            'education': data.get('education', []),
                            'work_experience': data.get('work_experience', []),
                            'certifications': data.get('certifications', []),
                            'extracurricular': data.get('extracurricular', []),
                        }
                    else:
                        result = {
                            'status': 'error',
                            'filename': api_response.get('filename'),
                            'message': api_response.get('error')
                        }
                    parsed_data.append(result)
                    
                except requests.exceptions.ConnectionError:
                    parsed_data.append({
                        'status': 'error',
                        'filename': f.name,
                        'message': 'Cannot connect to resume parser service'
                    })
                except Exception as e:
                    parsed_data.append({
                        'status': 'error',
                        'filename': f.name,
                        'message': str(e)
                    })
            
            try:
                
                # Process successful parses and save to database
                successful_saves = 0
                for result in parsed_data:
                    if result.get('status') == 'success':
                        try:
                            # Use data from the current result
                            basic_info = result.get('basic_info', {})
                            professional_summary = result.get('professional_summary', {})
                            additional_info = result.get('additional_info', {})
                            data = result.get('full_data', {})
                            
                            # Update or create Resume object with full structured data
                            resume, created = Resume.objects.update_or_create(
                                user=request.user,
                                email=basic_info.get('email', 'no-email@example.com'),
                                jobdescription=jd,  # Include JD in lookup to allow same candidate for multiple JDs
                                defaults={
                                    # Basic Info
                                    'candidate_name': basic_info.get('full_name', 'Unknown'),
                                    'phone': basic_info.get('phone', ''),
                                    'location': basic_info.get('location', ''),
                                    'linkedin_url': basic_info.get('linkedin_url', ''),
                                    'github_url': basic_info.get('github_url', ''),
                                    'portfolio_url': basic_info.get('portfolio_url', ''),
                                    # Professional Summary
                                    'professional_summary': professional_summary.get('summary', ''),
                                    'career_level': professional_summary.get('career_level', 'Entry-level'),
                                    'years_of_experience': professional_summary.get('years_of_experience', 0),
                                    # Structured Data (JSON)
                                    'skills': data.get('skills', []),
                                    'work_experience': data.get('work_experience', []),
                                    'education': data.get('education', []),
                                    'projects': data.get('projects', []),
                                    'certifications': data.get('certifications', []),
                                    'extracurricular': data.get('extracurricular', []),
                                    # Additional Info
                                    'availability': additional_info.get('availability', ''),
                                    'willing_to_relocate': additional_info.get('willing_to_relocate', ''),
                                    'salary_expectations': additional_info.get('salary_expectations', ''),
                                    'preferred_work_mode': additional_info.get('preferred_work_mode', ''),
                                }
                            )
                            successful_saves += 1
                            
                            # Optional: Add different messages for create vs update
                            action = "created" if created else "updated"
                            print(f"Resume {action} for {basic_info.get('full_name', 'Unknown')}")
                        except Exception as e:
                            messages.warning(request, f"Parsed {result.get('filename', 'unknown file')} but failed to save: {str(e)}")
                
                # Show results
                failed_parses = [result for result in parsed_data if result.get('status') == 'error']
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    # AJAX request - return JSON response
                    if successful_saves > 0 and not failed_parses:
                        return JsonResponse({
                            'success': True,
                            'type': 'success',
                            'message': f'Successfully processed and saved {successful_saves} resume(s) for {jd.title}!'
                        })
                    elif successful_saves > 0 and failed_parses:
                        failed_files = [failed.get('filename', 'unknown file') for failed in failed_parses]
                        return JsonResponse({
                            'success': True,
                            'type': 'warning',
                            'message': f'Successfully processed {successful_saves} resume(s) for {jd.title}. Failed to parse: {", ".join(failed_files)}'
                        })
                    else:
                        failed_files = [failed.get('filename', 'unknown file') for failed in failed_parses]
                        # Check if the failures are due to unsupported formats
                        format_errors = []
                        parsing_errors = []
                        
                        for failed in failed_parses:
                            error_msg = failed.get('message', '')
                            filename = failed.get('filename', 'unknown file')
                            
                            # Check if it's a format-related error
                            if ('Only PDF files are supported' in error_msg or 
                                'unsupported' in error_msg.lower() or 
                                'format' in error_msg.lower() or
                                filename.lower().endswith(('.doc', '.docx', '.txt', '.jpg', '.png'))):
                                format_errors.append(filename)
                            else:
                                parsing_errors.append(filename)
                        
                        if format_errors and not parsing_errors:
                            # All errors are format-related
                            message = f'Unsupported file format: {", ".join(format_errors)}. Please upload only PDF, DOC, or DOCX files.'
                        elif format_errors and parsing_errors:
                            # Mixed errors
                            message = f'Upload failed: Unsupported formats ({", ".join(format_errors)}) and parsing errors ({", ".join(parsing_errors)}). Please upload only PDF, DOC, or DOCX files.'
                        else:
                            # All are parsing errors
                            message = f'Failed to parse files: {", ".join(failed_files)}. Please ensure files are valid and not corrupted.'
                        
                        return JsonResponse({
                            'success': False,
                            'type': 'error',
                            'message': message
                        })
                else:
                    # Regular form submission - use messages
                    if successful_saves > 0:
                        messages.success(request, f'Successfully processed and saved {successful_saves} resume(s) for {jd.title}!')
                    
                    if failed_parses:
                        for failed in failed_parses:
                            messages.error(request, f"Failed to parse {failed.get('filename', 'unknown file')}: {failed.get('message', 'Unknown error')}")
                    
                    # Redirect to avoid showing temporary parsing results
                    return redirect('resumes')
                
            except Exception as e:
                messages.error(request, f"Unexpected error processing resumes: {str(e)}")
                return redirect('resumes')
        
        # Handle delete resume
        elif 'delete_resume_id' in request.POST:
            resume_id = request.POST.get('delete_resume_id')
            Resume.objects.filter(id=resume_id, user=request.user).delete()
            messages.success(request, 'Resume deleted successfully!')
            return redirect('resumes')
        
        # Handle bulk delete resumes
        elif 'bulk_delete_resumes' in request.POST:
            resume_ids = request.POST.get('resume_ids', '')
            if resume_ids:
                resume_ids_list = [int(id.strip()) for id in resume_ids.split(',') if id.strip()]
                deleted_count = Resume.objects.filter(id__in=resume_ids_list, user=request.user).count()
                Resume.objects.filter(id__in=resume_ids_list, user=request.user).delete()
                messages.success(request, f'Successfully deleted {deleted_count} resume{"s" if deleted_count != 1 else ""}!')
            else:
                messages.error(request, 'No resumes selected for deletion.')
            return redirect('resumes')
    
    # Get notifications for header
    notifications = get_notifications(request.user)
    
    # Calculate statistics
    total_resumes = sum(jd.resumes.count() for jd in job_descriptions)
    ai_parsed_count = sum(1 for jd in job_descriptions for resume in jd.resumes.all() if resume.candidate_name)
    
    # Count recent uploads (last 7 days)
    from datetime import datetime, timedelta
    week_ago = timezone.now() - timedelta(days=7)
    recent_uploads_count = sum(1 for jd in job_descriptions for resume in jd.resumes.all() if resume.uploaded_at >= week_ago)

    return render(request, 'home/resumes.html', {
        'job_descriptions': job_descriptions,
        'notifications': notifications,
        'notifications_count': len(notifications),
        'total_resumes': total_resumes,
        'ai_parsed_count': ai_parsed_count,
        'recent_uploads_count': recent_uploads_count,
    })

@login_required
def matching(request):
    """
    Enhanced view for AI-powered resume matching with dynamic JD selection
    """
    notifications = get_notifications(request.user)
    
    if request.method == 'POST':
        # Check if it's an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if 'get_unmatched_resumes' in request.POST:
            # Get unmatched resumes for selected JD
            jd_id = request.POST.get('jd_id')
            try:
                jd = JobDescription.objects.get(id=jd_id, user=request.user)
                
                # Get all resumes for this JD that don't have matching results yet
                all_resumes = Resume.objects.filter(user=request.user, jobdescription=jd)
                matched_resume_ids = MatchingResult.objects.filter(
                    user=request.user, 
                    job_description=jd
                ).values_list('resume_id', flat=True)
                
                unmatched_resumes = all_resumes.exclude(id__in=matched_resume_ids)
                
                resume_data = []
                for resume in unmatched_resumes:
                    resume_data.append({
                        'id': resume.id,
                        'candidate_name': resume.candidate_name,
                        'email': resume.email,
                        'years_of_experience': resume.years_of_experience,
                        'career_level': resume.career_level,
                        'uploaded_at': resume.uploaded_at.strftime('%Y-%m-%d')
                    })
                
                return JsonResponse({
                    'success': True,
                    'resumes': resume_data,
                    'total_count': len(resume_data)
                })
                
            except JobDescription.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid job description selected'
                })
        
        elif 'run_matching' in request.POST:
            # Run AI matching for selected resumes
            jd_id = request.POST.get('jd_id')
            resume_ids = request.POST.getlist('resume_ids')
            
            try:
                jd = JobDescription.objects.get(id=jd_id, user=request.user)
                resumes = Resume.objects.filter(
                    id__in=resume_ids, 
                    user=request.user, 
                    jobdescription=jd
                )
                
                if not resumes.exists():
                    return JsonResponse({
                        'success': False,
                        'error': 'No valid resumes selected for matching'
                    })
                
                # Process each resume through the FastAPI matching service
                results = []
                errors = []
                
                for resume in resumes:
                    try:
                        # Call the FastAPI matching service
                        result = call_fastapi_matching_service(jd, resume)
                        
                        if result and result.get('success'):
                            # Save the matching result to database
                            matching_data = result.get('data')
                            if matching_data:
                                # Create or update matching result
                                matching_result, created = MatchingResult.objects.update_or_create(
                                    user=request.user,
                                    resume=resume,
                                    job_description=jd,
                                    defaults={
                                        'overall_score': matching_data.get('overall_score', 0),
                                        'skills_score': matching_data.get('skills_score', 0),
                                        'experience_score': matching_data.get('experience_score', 0),
                                        'education_score': matching_data.get('education_score', 0),
                                        'match_reasoning': json.dumps({
                                            'interview_recommendation': matching_data.get('recommendation', ''),
                                            'confidence_level': matching_data.get('confidence', ''),
                                            'interview_priority': matching_data.get('interview_priority', ''),
                                            'top_strengths': matching_data.get('strengths', []),
                                            'concerns': matching_data.get('concerns', []),
                                            'conversation_topics': matching_data.get('conversation_topics', []),
                                            'key_questions': matching_data.get('key_questions', [])
                                        }),
                                        'matched_skills': json.dumps(matching_data.get('matched_skills', [])),
                                        'missing_skills': json.dumps(matching_data.get('missing_skills', [])),
                                        'experience_gap': (matching_data.get('experience_summary', '') or '')[:255],
                                        'created_at': timezone.now()
                                    }
                                )
                                results.append({
                                    'resume_id': resume.id,
                                    'candidate_name': resume.candidate_name,
                                    'score': matching_data.get('overall_score', 0),
                                    'recommendation': matching_data.get('recommendation', ''),
                                    'created': created
                                })
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'No response from matching service'
                            errors.append(f"{resume.candidate_name}: {error_msg}")
                            
                    except Exception as e:
                        errors.append(f"{resume.candidate_name}: {str(e)}")
                
                # Return results
                if results:
                    success_msg = f'Successfully processed {len(results)} resume(s)'
                    if errors:
                        success_msg += f' ({len(errors)} failed)'
                    
                    return JsonResponse({
                        'success': True,
                        'message': success_msg,
                        'results': results,
                        'errors': errors,
                        'total_processed': len(results),
                        'total_errors': len(errors)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to process any resumes',
                        'errors': errors
                    })
                
            except JobDescription.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid job description selected'
                })
        
        elif 'shortlist_multiple' in request.POST:
            # Handle multiple candidate shortlisting
            candidate_ids = request.POST.getlist('candidate_ids')
            
            try:
                # Get matching results that belong to the user
                matching_results = MatchingResult.objects.filter(
                    id__in=candidate_ids,
                    user=request.user,
                    status='pending'  # Only shortlist pending candidates
                )
                
                # Update status to shortlisted
                updated_count = matching_results.update(
                    status='shortlisted',
                    updated_at=timezone.now()
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully shortlisted {updated_count} candidate(s)',
                    'shortlisted_count': updated_count
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Failed to shortlist candidates: {str(e)}'
                })
        
        elif 'reject_multiple' in request.POST:
            # Handle multiple candidate rejection
            candidate_ids = request.POST.getlist('candidate_ids')
            
            try:
                # Get matching results that belong to the user
                matching_results = MatchingResult.objects.filter(
                    id__in=candidate_ids,
                    user=request.user,
                    status='pending'  # Only reject pending candidates
                )
                
                # Update status to rejected
                updated_count = matching_results.update(
                    status='rejected',
                    updated_at=timezone.now()
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully rejected {updated_count} candidate(s)',
                    'rejected_count': updated_count
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Failed to reject candidates: {str(e)}'
                })
        
        elif 'delete_selected' in request.POST:
            # Handle multiple candidate deletion
            candidate_ids = request.POST.getlist('candidate_ids')
            
            try:
                # Get matching results that belong to the user
                matching_results = MatchingResult.objects.filter(
                    id__in=candidate_ids,
                    user=request.user
                )
                
                # Count how many will be deleted
                delete_count = matching_results.count()
                
                # Delete the matching results
                matching_results.delete()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully deleted {delete_count} matching result(s)',
                    'deleted_count': delete_count
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Failed to delete matching results: {str(e)}'
                })
    
    # Get job descriptions for the user
    job_descriptions = JobDescription.objects.filter(user=request.user).order_by('-created_at')
    
    # Get existing matching results for display
    matching_results = MatchingResult.objects.filter(user=request.user).select_related(
        'resume', 'job_description'
    ).order_by('-overall_score', '-created_at')
    
    # Calculate statistics
    total_matches = matching_results.count()
    high_score_matches = matching_results.filter(overall_score__gte=90).count()
    medium_score_matches = matching_results.filter(
        overall_score__gte=70, overall_score__lt=90
    ).count()
    
    # Calculate status-based counts for tabs
    shortlisted_count = matching_results.filter(status='shortlisted').count()
    # Count rejected candidates instead of interviewed
    rejected_count = matching_results.filter(status='rejected').count()
    # Count pending candidates (those that haven't been shortlisted or rejected)
    pending_count = matching_results.filter(status='pending').count()
    
    # Calculate email status counts
    selection_emails_sent = matching_results.filter(email_status='selection_sent').count()
    rejection_emails_sent = matching_results.filter(email_status='rejection_sent').count()
    emails_not_sent = matching_results.filter(email_status='not_sent').count()
    emails_sent_count = selection_emails_sent + rejection_emails_sent
    
    avg_score = 0
    if total_matches > 0:
        total_score = sum(result.overall_score for result in matching_results)
        avg_score = round(total_score / total_matches, 1)
    
    return render(request, 'home/matching.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
        'job_descriptions': job_descriptions,
        'matching_results': matching_results,
        'total_matches': total_matches,
        'high_score_matches': high_score_matches,
        'medium_score_matches': medium_score_matches,
        'shortlisted_count': shortlisted_count,
        'rejected_count': rejected_count,
        'pending_count': pending_count,
        'avg_score': avg_score,
        'hr_user_id': request.user.id,  # Add user ID for email links
        'selection_emails_sent': selection_emails_sent,
        'rejection_emails_sent': rejection_emails_sent,
        'emails_not_sent': emails_not_sent,
        'emails_sent_count': emails_sent_count,
    })

@login_required
def shortlisted(request):
    notifications = get_notifications(request.user)
    
    # Get all shortlisted candidates for the user
    shortlisted_results = MatchingResult.objects.filter(
        user=request.user, 
        status='shortlisted'
    ).select_related('resume', 'job_description').order_by('-created_at')
    
    # Calculate stats
    total_shortlisted = shortlisted_results.count()
    
    return render(request, 'home/shortlisted.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
        'shortlisted_results': shortlisted_results,
        'total_shortlisted': total_shortlisted,
    })


@login_required
def shortlist_candidate(request):
    """Shortlist a candidate from matching results"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            result_id = request.POST.get('result_id')
            matching_result = MatchingResult.objects.get(
                id=result_id, 
                user=request.user
            )
            
            # Update status to shortlisted
            matching_result.status = 'shortlisted'
            matching_result.save()
            
            # Also create a Shortlisted record for backward compatibility
            shortlisted, created = Shortlisted.objects.get_or_create(
                resume=matching_result.resume
            )
            
            return JsonResponse({
                'success': True,
                'message': f'{matching_result.resume.candidate_name} has been shortlisted!'
            })
            
        except MatchingResult.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Matching result not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def reject_candidate(request):
    """Reject a candidate from matching results"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            result_id = request.POST.get('result_id')
            matching_result = MatchingResult.objects.get(
                id=result_id, 
                user=request.user
            )
            
            # Update status to rejected
            matching_result.status = 'rejected'
            matching_result.save()
            
            return JsonResponse({
                'success': True,
                'message': f'{matching_result.resume.candidate_name} has been rejected.'
            })
            
        except MatchingResult.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Matching result not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def delete_matching_result(request):
    """Delete a matching result"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            result_id = request.POST.get('result_id')
            matching_result = MatchingResult.objects.get(
                id=result_id, 
                user=request.user
            )
            
            candidate_name = matching_result.resume.candidate_name
            matching_result.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Matching result for {candidate_name} has been deleted.'
            })
            
        except MatchingResult.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Matching result not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def emails(request):
    notifications = get_notifications(request.user)
    return render(request, 'home/emails.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def interviews(request):
    notifications = get_notifications(request.user)
    return render(request, 'home/interviews.html', {
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

@login_required
def reports(request):
    notifications = get_notifications(request.user)
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
    notifications = get_notifications(request.user)

    return render(request, 'home/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'notifications': notifications,
        'notifications_count': len(notifications),
    })

def candidate_interview(request, hr_user_id):
    """
    Public view for candidates to access their interview.
    No authentication required - validates email against shortlisted candidates for specific HR user.
    """
    context = {
        'step': 'email_validation',  # email_validation or interview_ready
        'error_message': None,
        'candidate_data': None,
    }
    
    # Validate that the hr_user_id exists
    try:
        from django.contrib.auth.models import User
        hr_user = User.objects.get(id=hr_user_id)
    except User.DoesNotExist:
        context['error_message'] = "Invalid interview link. Please contact HR for assistance."
        return render(request, 'home/candidate_interview.html', context)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            context['error_message'] = "Please enter your email address."
            return render(request, 'home/candidate_interview.html', context)
        
        try:
            # Find the candidate's resume and check if they are shortlisted for interview
            resume = Resume.objects.filter(email__iexact=email).first()
            
            if not resume:
                context['error_message'] = "Email not found in our system. Please check your email address."
                return render(request, 'home/candidate_interview.html', context)
            
            # Debug: Log all matching results for this resume and HR user
            all_matches = MatchingResult.objects.filter(resume=resume, user=hr_user)
            logger.info(f"DEBUG: All matches for {email} with HR user {hr_user_id}: {[(m.id, m.status, m.job_description.title) for m in all_matches]}")
            
            # Check if the candidate has any shortlisted matching results for this HR user (exclude rejected ones)
            shortlisted_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,  # Filter by specific HR user
                status='shortlisted'
            ).select_related('job_description')
            
            # Also check if there are any rejected matches for this HR user to provide better error message
            rejected_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,  # Filter by specific HR user
                status='rejected'
            ).exists()
            
            # STRICT CHECK: If ANY match is rejected for this HR user, block access entirely
            pending_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,  # Filter by specific HR user
                status='pending'
            ).exists()
            
            # Debug: Log shortlisted and rejected counts for this HR user
            logger.info(f"DEBUG: For HR user {hr_user_id} - Shortlisted count: {shortlisted_matches.count()}, Rejected exists: {rejected_matches}, Pending exists: {pending_matches}")
            
            # Enhanced validation: Only allow if there are shortlisted matches for this HR user AND no rejected/pending
            if not shortlisted_matches.exists():
                if rejected_matches:
                    context['error_message'] = "Thank you for your interest in our position. After careful consideration, we have decided to move forward with other candidates whose qualifications more closely match our current requirements. We appreciate the time you invested in your application and wish you the best in your career endeavors."
                elif pending_matches:
                    context['error_message'] = "Your application is still under review. Please wait for further communication."
                else:
                    context['error_message'] = "No interview invitation found for this email address."
                return render(request, 'home/candidate_interview.html', context)
            
            # Get the most recent shortlisted match for interview for this HR user
            latest_match = shortlisted_matches.order_by('-created_at').first()
            logger.info(f"DEBUG: Latest shortlisted match for HR user {hr_user_id}: {latest_match.id}, Status: {latest_match.status}")
            
            context.update({
                'step': 'interview_ready',
                'candidate_data': {
                    'name': resume.candidate_name or 'Candidate',
                    'email': resume.email,
                    'position': latest_match.job_description.title,
                    'company': latest_match.job_description.department or 'Our Company',
                    'match_id': latest_match.id,
                }
            })
            
        except Exception as e:
            logger.error(f"Error validating candidate email {email}: {str(e)}")
            context['error_message'] = "An error occurred while validating your email. Please try again."
    
    return render(request, 'home/candidate_interview.html', context)

def debug_check_status(request, email):
    """Debug view to check candidate status in database"""
    try:
        resume = Resume.objects.filter(email__iexact=email).first()
        if not resume:
            return JsonResponse({'error': 'Email not found'})
        
        # Get all matching results for this resume
        matches = MatchingResult.objects.filter(resume=resume).select_related('job_description')
        
        results = []
        for match in matches:
            results.append({
                'id': match.id,
                'status': match.status,
                'email_status': match.email_status,
                'position': match.job_description.title,
                'company': match.job_description.department,
                'overall_score': float(match.overall_score),
                'created_at': match.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': match.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        return JsonResponse({
            'email': email,
            'candidate_name': resume.candidate_name,
            'total_matches': len(results),
            'matches': results,
            'shortlisted_count': len([r for r in results if r['status'] == 'shortlisted']),
            'rejected_count': len([r for r in results if r['status'] == 'rejected']),
            'pending_count': len([r for r in results if r['status'] == 'pending']),
            'emails_sent_count': len([r for r in results if r.get('email_status') in ['selection_sent', 'rejection_sent']]),
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)})