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
    """
    Enhanced view to handle resume uploads with FastAPI parsing integration
    """
    job_descriptions = JobDescription.objects.filter(user=request.user).order_by('-created_at')
    
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
                            skills_str = ', '.join(skills_list) if skills_list else ''
                            
                            # Extract education as text
                            education_list = result.get('education', [])
                            education_str = ''
                            if education_list:
                                education_parts = []
                                for edu in education_list:
                                    edu_text = f"{edu.get('degree', '')} in {edu.get('major', '')}" if edu.get('major') else edu.get('degree', '')
                                    if edu.get('university_name'):
                                        edu_text += f" from {edu.get('university_name')}"
                                    if edu.get('end_year'):
                                        edu_text += f" ({edu.get('end_year')})"
                                    education_parts.append(edu_text)
                                education_str = '; '.join(education_parts)
                            
                            # Extract experience as text
                            experience_list = result.get('work_experience', [])
                            experience_str = ''
                            if experience_list:
                                exp_parts = []
                                for exp in experience_list:
                                    exp_text = f"{exp.get('job_title', '')} at {exp.get('company_name', '')}"
                                    if exp.get('end_date'):
                                        exp_text += f" ({exp.get('start_date', '')} - {exp.get('end_date', '')})"
                                    exp_parts.append(exp_text)
                                experience_str = '; '.join(exp_parts)
                            
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
    
    # For GET requests and after processing, fetch JDs and attach resumes for template
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