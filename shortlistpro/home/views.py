from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'home/index.html')

# def register(request):
#     return render(request, 'home/register.html')


import requests
import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db import IntegrityError
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
                skipped_duplicates = 0
                for result in parsed_data:
                    if result.get('status') == 'success':
                        try:
                            # Check for duplicate email before processing
                            candidate_email = result.get('email', '').strip().lower()
                            if candidate_email and candidate_email != 'no-email@example.com':
                                # Check if resume with this email already exists for this user
                                existing_resume = Resume.objects.filter(
                                    user=request.user, 
                                    email__iexact=candidate_email
                                ).first()
                                
                                if existing_resume:
                                    messages.warning(request, f"Skipped {result.get('filename', 'unknown file')}: Resume for {candidate_email} already exists (candidate: {existing_resume.candidate_name})")
                                    skipped_duplicates += 1
                                    continue
                            
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
                            try:
                                Resume.objects.create(
                                    user=request.user,
                                    jobdescription=jd,
                                    candidate_name=result.get('full_name', 'Unknown'),
                                    email=candidate_email if candidate_email else 'no-email@example.com',
                                    phone=result.get('phone', ''),
                                    skills=skills_str,
                                    education=education_str,
                                    experience=experience_str,
                                    certifications=result.get('certifications', []),
                                    # Note: We're not saving the file here as it was already processed
                                )
                                successful_saves += 1
                            except IntegrityError:
                                # This catches database constraint violations as a backup
                                messages.warning(request, f"Skipped {result.get('filename', 'unknown file')}: Resume for {candidate_email} already exists in database")
                                skipped_duplicates += 1
                        except Exception as e:
                            messages.warning(request, f"Parsed {result.get('filename', 'unknown file')} but failed to save: {str(e)}")
                
                # Show results
                failed_parses = [result for result in parsed_data if result.get('status') == 'error']
                
                if successful_saves > 0:
                    messages.success(request, f'Successfully processed and saved {successful_saves} resume(s) for {jd.title}!')
                
                if skipped_duplicates > 0:
                    messages.info(request, f'Skipped {skipped_duplicates} duplicate resume(s) based on email addresses.')
                
                if failed_parses:
                    for failed in failed_parses:
                        messages.error(request, f"Failed to parse {failed.get('filename', 'unknown file')}: {failed.get('message', 'Unknown error')}")
                
                # Get all existing resumes from database and combine with new parsed data
                all_resumes = []
                
                # Add existing saved resumes from database
                existing_resumes = Resume.objects.filter(user=request.user, jobdescription=jd).order_by('-uploaded_at')
                for resume in existing_resumes:
                    # Convert database resume to display format
                    skills_list = [skill.strip() for skill in resume.skills.split(',') if skill.strip()] if resume.skills else []
                    certifications_list = []  # We'll add this field to model later
                    
                    all_resumes.append({
                        'id': resume.id,  # Add the database ID
                        'status': 'success',
                        'filename': f"{resume.candidate_name}_resume.pdf",
                        'full_name': resume.candidate_name,
                        'email': resume.email,
                        'phone': resume.phone,
                        'skills': skills_list,
                        'education': [{'degree': resume.education, 'university_name': '', 'major': '', 'start_year': '', 'end_year': ''}] if resume.education else [],
                        'work_experience': [{'job_title': resume.experience, 'company_name': '', 'location': '', 'start_date': '', 'end_date': '', 'description': ''}] if resume.experience else [],
                        'certifications': resume.certifications if resume.certifications else [],
                        'job_description_id': str(jd.id),
                        'from_database': True,
                        'created_at': resume.uploaded_at.isoformat(),
                        'file': {'name': resume.resume_file.name if resume.resume_file else ''}
                    })
                
                # Add failed parses to the list so user can retry
                for failed in failed_parses:
                    failed['job_description_id'] = str(jd.id)
                    all_resumes.append(failed)
                
                # Return with all resumes (existing + new + failed)
                return render(request, 'home/resumes.html', {
                    'parsed_data': all_resumes, 
                    'job_descriptions': job_descriptions,
                    'show_retry_options': True,
                    'resumes_data': json.dumps(all_resumes),
                    'job_descriptions_data': json.dumps([{
                        'id': jd.id,
                        'title': jd.title,
                        'department': jd.department
                    } for jd in job_descriptions])
                })
                
            except requests.exceptions.ConnectionError:
                messages.error(request, "Cannot connect to resume parser service. Please make sure the FastAPI server is running.")
                return redirect('resumes')
            except Exception as e:
                messages.error(request, f"Error communicating with resume parser: {str(e)}")
                return redirect('resumes')
        
        # Handle retry parsing request (JSON)
        elif request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                if data.get('retry_parse'):
                    resume_id = data.get('resume_id')
                    file_path = data.get('file_path')
                    
                    if not resume_id:
                        return JsonResponse({'success': False, 'error': 'Resume ID is required'})
                    
                    try:
                        resume = Resume.objects.get(id=resume_id, user=request.user)
                        
                        # Re-parse the resume using FastAPI
                        fastapi_url = "http://localhost:8001/parse_resume"
                        
                        # Prepare the file for re-parsing (if file exists)
                        if resume.resume_file and resume.resume_file.path:
                            with open(resume.resume_file.path, 'rb') as file:
                                files = {'file': (resume.resume_file.name, file, 'application/pdf')}
                                response = requests.post(fastapi_url, files=files, timeout=30)
                        else:
                            return JsonResponse({'success': False, 'error': 'Resume file not found'})
                        
                        if response.status_code == 200:
                            parsed_data = response.json()
                            
                            # Check for duplicate email if email has changed
                            new_email = parsed_data.get('email', '').strip().lower()
                            if new_email and new_email != resume.email.lower() and new_email != 'no-email@example.com':
                                # Check if another resume with this email already exists
                                existing_resume = Resume.objects.filter(
                                    user=request.user, 
                                    email__iexact=new_email
                                ).exclude(id=resume.id).first()
                                
                                if existing_resume:
                                    return JsonResponse({
                                        'success': False, 
                                        'error': f'Cannot update email to {new_email}: Resume for this email already exists (candidate: {existing_resume.candidate_name})'
                                    })
                            
                            # Update the resume with new parsed data
                            resume.candidate_name = parsed_data.get('full_name', resume.candidate_name)
                            resume.email = new_email if new_email else resume.email
                            resume.phone = parsed_data.get('phone', resume.phone)
                            
                            # Format experience
                            experience_list = parsed_data.get('work_experience', [])
                            if experience_list:
                                exp_parts = []
                                for exp in experience_list:
                                    exp_text = f"{exp.get('job_title', '')} at {exp.get('company_name', '')}"
                                    if exp.get('end_date'):
                                        exp_text += f" ({exp.get('start_date', '')} - {exp.get('end_date', '')})"
                                    exp_parts.append(exp_text)
                                resume.experience = '; '.join(exp_parts)
                            
                            # Format education
                            education_list = parsed_data.get('education', [])
                            if education_list:
                                education_parts = []
                                for edu in education_list:
                                    edu_text = f"{edu.get('degree', '')} in {edu.get('major', '')}" if edu.get('major') else edu.get('degree', '')
                                    if edu.get('university_name'):
                                        edu_text += f" from {edu.get('university_name')}"
                                    if edu.get('end_year'):
                                        edu_text += f" ({edu.get('end_year')})"
                                    education_parts.append(edu_text)
                                resume.education = '; '.join(education_parts)
                            
                            # Format skills
                            skills_list = parsed_data.get('skills', [])
                            resume.skills = ', '.join(skills_list) if skills_list else ''
                            
                            # Format certifications
                            certifications_list = parsed_data.get('certifications', [])
                            resume.certifications = certifications_list
                            
                            try:
                                resume.save()
                            except IntegrityError:
                                return JsonResponse({
                                    'success': False, 
                                    'error': f'Cannot update email to {new_email}: Resume for this email already exists (database constraint)'
                                })
                            
                            # Return the updated resume data
                            return JsonResponse({
                                'success': True,
                                'data': {
                                    'id': resume.id,
                                    'candidate_name': resume.candidate_name,
                                    'email': resume.email,
                                    'phone': resume.phone,
                                    'experience': resume.experience,
                                    'education': resume.education,
                                    'skills': resume.skills,
                                    'certifications': resume.certifications,
                                    'created_at': resume.uploaded_at.isoformat(),
                                }
                            })
                        else:
                            return JsonResponse({
                                'success': False, 
                                'error': f'FastAPI parsing failed: {response.text}'
                            })
                            
                    except Resume.DoesNotExist:
                        return JsonResponse({'success': False, 'error': 'Resume not found'})
                    except Exception as e:
                        return JsonResponse({'success': False, 'error': str(e)})
                        
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
        
        # Handle delete resume
        elif 'delete_resume_id' in request.POST:
            resume_id = request.POST.get('delete_resume_id')
            Resume.objects.filter(id=resume_id, user=request.user).delete()
            messages.success(request, 'Resume deleted successfully!')
            return redirect('resumes')
    
    # For GET requests, show existing resumes from database
    all_existing_resumes = []
    for jd in job_descriptions:
        existing_resumes = Resume.objects.filter(user=request.user, jobdescription=jd).order_by('-uploaded_at')
        for resume in existing_resumes:
            skills_list = [skill.strip() for skill in resume.skills.split(',') if skill.strip()] if resume.skills else []
            
            all_existing_resumes.append({
                'id': resume.id,  # Add the database ID
                'status': 'success',
                'filename': f"{resume.candidate_name}_resume.pdf",
                'full_name': resume.candidate_name,
                'email': resume.email,
                'phone': resume.phone,
                'skills': skills_list,
                'education': [{'degree': resume.education, 'university_name': '', 'major': '', 'start_year': '', 'end_year': ''}] if resume.education else [],
                'work_experience': [{'job_title': resume.experience, 'company_name': '', 'location': '', 'start_date': '', 'end_date': '', 'description': ''}] if resume.experience else [],
                'certifications': resume.certifications if resume.certifications else [],
                'job_description_id': str(jd.id),
                'from_database': True,
                'created_at': resume.uploaded_at.isoformat(),
                'file': {'name': resume.resume_file.name if resume.resume_file else ''}
            })
    
    return render(request, 'home/resumes.html', {
        'job_descriptions': job_descriptions,
        'parsed_data': all_existing_resumes if all_existing_resumes else None,
        'resumes_data': json.dumps(all_existing_resumes) if all_existing_resumes else "[]",
        'job_descriptions_data': json.dumps([{
            'id': jd.id,
            'title': jd.title,
            'department': jd.department
        } for jd in job_descriptions])
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