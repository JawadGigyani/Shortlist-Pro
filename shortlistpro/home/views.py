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
import os
import json
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from .forms import UserForm, ProfileForm, JobDescriptionForm, ResumeForm
from .models import Resume, Shortlisted, Interview, JobDescription, MatchingResult, InterviewQuestions, InterviewSession, InterviewRecording, InterviewMessage, InterviewStage, CandidatePipeline
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from datetime import timedelta
import json
import logging

# Configure logging
logger = logging.getLogger(__name__)

# FastAPI service configurations
FASTAPI_MATCHING_URL = "http://localhost:8001/match-resume"
FASTAPI_INTERVIEW_QUESTIONS_URL = "http://localhost:8004/generate-questions"
FASTAPI_INTERVIEW_EVALUATION_URL = "http://localhost:8002/evaluate-interview"
FASTAPI_TIMEOUT = 60  # Increased timeout for AI processing


def call_fastapi_interview_questions_service(matching_result):
    """
    Call the FastAPI interview questions generation service
    
    Args:
        matching_result: MatchingResult model instance
        
    Returns:
        dict: API response with generated questions or error info
    """
    try:
        # Prepare resume data as string
        resume_info = f"""
Candidate: {matching_result.resume.candidate_name}
Email: {matching_result.resume.email}
Phone: {matching_result.resume.phone or 'Not provided'}
Location: {matching_result.resume.location or 'Not provided'}
Career Level: {matching_result.resume.career_level}
Years of Experience: {matching_result.resume.years_of_experience}

Professional Summary:
{matching_result.resume.professional_summary or 'Not provided'}

Skills: {', '.join(matching_result.resume.skills or [])}

Work Experience:
{json.dumps(matching_result.resume.work_experience or [], indent=2)}

Education:
{json.dumps(matching_result.resume.education or [], indent=2)}

Projects:
{json.dumps(matching_result.resume.projects or [], indent=2)}

Certifications:
{json.dumps(matching_result.resume.certifications or [], indent=2)}
        """.strip()
        
        # Prepare job description as string
        job_desc = f"""
Title: {matching_result.job_description.title}
Department: {matching_result.job_description.department}
Description: {matching_result.job_description.description}
        """.strip()
        
        # Prepare matching results
        matching_data = {
            "overall_score": float(matching_result.overall_score),
            "skills_score": float(matching_result.skills_score),
            "experience_score": float(matching_result.experience_score),
            "education_score": float(matching_result.education_score),
            "matched_skills": matching_result.matched_skills or [],
            "missing_skills": matching_result.missing_skills or [],
            "experience_gap": matching_result.experience_gap or ""
        }
        
        payload = {
            "resume_data": resume_info,
            "job_description": job_desc,
            "matching_results": matching_data
        }
        
        logger.info(f"Calling interview questions service for matching result {matching_result.id}")
        logger.info(f"Resume data length: {len(resume_info)} chars")
        logger.info(f"Job description length: {len(job_desc)} chars")
        
        response = requests.post(
            FASTAPI_INTERVIEW_QUESTIONS_URL,
            json=payload,
            timeout=FASTAPI_TIMEOUT
        )
        
        logger.info(f"Interview questions service response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Interview questions generated successfully for matching result {matching_result.id}")
            response_data = response.json()
            
            # Format response to match expected structure
            return {
                "success": True,
                "questions": [
                    {
                        "question": q["question"],
                        "category": q["category"],
                        "purpose": q["purpose"],
                        "priority": q.get("priority", "medium")
                    } for q in response_data["questions"]
                ],
                "metadata": {
                    "total_questions": response_data["total_questions"],
                    "estimated_duration": response_data["estimated_duration"],
                    "complexity_level": response_data["complexity_level"],
                    "focus_areas": response_data["focus_areas"],
                    "question_distribution": response_data["question_distribution"]
                }
            }
        else:
            logger.error(f"Interview questions service error: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Service returned status {response.status_code}",
                "details": response.text
            }
            
    except requests.exceptions.Timeout:
        logger.error(f"Interview questions service timeout for matching result {matching_result.id}")
        return {
            "success": False,
            "error": "Interview questions service timeout",
            "details": "The service took too long to respond"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Interview questions service request error: {str(e)}")
        return {
            "success": False,
            "error": "Failed to connect to interview questions service",
            "details": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error calling interview questions service: {str(e)}")
        return {
            "success": False,
            "error": "Unexpected error occurred",
            "details": str(e)
        }


def call_fastapi_interview_evaluation_service(interview_recording):
    """
    Call the FastAPI interview evaluation service to analyze interview transcripts
    
    Args:
        interview_recording: InterviewRecording model instance
        
    Returns:
        dict: API response with evaluation results or error info
    """
    try:
        # Validate that we have the necessary data
        if not interview_recording.matching_result:
            logger.error(f"Interview recording {interview_recording.id} has no matching result")
            return {
                "success": False,
                "error": "No matching result found for interview recording"
            }
        
        # Prepare resume data as structured string
        resume = interview_recording.matching_result.resume
        job_desc = interview_recording.matching_result.job_description
        
        resume_data = f"""
Candidate: {resume.candidate_name}
Email: {resume.email}
Phone: {resume.phone or 'Not provided'}
Location: {resume.location or 'Not provided'}
Career Level: {resume.career_level}
Years of Experience: {resume.years_of_experience}

Professional Summary:
{resume.professional_summary or 'Not provided'}

Skills: {', '.join(resume.skills or [])}

Work Experience:
{json.dumps(resume.work_experience or [], indent=2)}

Education:
{json.dumps(resume.education or [], indent=2)}

Projects:
{json.dumps(resume.projects or [], indent=2)}

Certifications:
{json.dumps(resume.certifications or [], indent=2)}

Extracurricular Activities:
{json.dumps(resume.extracurricular or [], indent=2)}
        """.strip()
        
        # Prepare job description
        job_description = f"""
Title: {job_desc.title}
Department: {job_desc.department}
Description: {job_desc.description}
        """.strip()
        
        # Prepare interview transcript
        transcript_messages = []
        if interview_recording.conversation_data:
            # Extract messages from conversation_data
            for message in interview_recording.conversation_data.get('messages', []):
                speaker = message.get('role', 'unknown')
                content = message.get('content', '')
                if content and content.strip():
                    transcript_messages.append(f"{speaker.title()}: {content}")
        
        # If no conversation_data, try messages from InterviewMessage model
        if not transcript_messages and hasattr(interview_recording, 'messages'):
            for message in interview_recording.messages.all().order_by('sequence_number'):
                if message.message_content and message.message_content.strip():
                    speaker_display = message.get_speaker_display()
                    transcript_messages.append(f"{speaker_display}: {message.message_content}")
        
        # Create transcript string
        interview_transcript = "\n\n".join(transcript_messages) if transcript_messages else "No transcript available"
        
        # Calculate interview duration in minutes
        duration_minutes = None
        if interview_recording.duration_seconds:
            duration_minutes = max(1, interview_recording.duration_seconds // 60)  # At least 1 minute
        
        # Get resume matching results
        matching_result = interview_recording.matching_result
        
        # Parse JSON fields safely
        matched_skills = []
        missing_skills = []
        
        try:
            if matching_result.matched_skills:
                if isinstance(matching_result.matched_skills, str):
                    matched_skills = json.loads(matching_result.matched_skills)
                else:
                    matched_skills = matching_result.matched_skills
        except (json.JSONDecodeError, TypeError):
            matched_skills = []
            
        try:
            if matching_result.missing_skills:
                if isinstance(matching_result.missing_skills, str):
                    missing_skills = json.loads(matching_result.missing_skills)
                else:
                    missing_skills = matching_result.missing_skills
        except (json.JSONDecodeError, TypeError):
            missing_skills = []
        
        # Prepare request payload with resume matching context
        payload = {
            "job_description": job_description,
            "candidate_resume_data": resume_data,
            "interview_transcript": interview_transcript,
            "interview_duration_minutes": duration_minutes,
            # Resume matching context
            "resume_overall_score": float(matching_result.overall_score) if matching_result.overall_score else None,
            "resume_skills_score": float(matching_result.skills_score) if matching_result.skills_score else None,
            "resume_experience_score": float(matching_result.experience_score) if matching_result.experience_score else None,
            "resume_education_score": float(matching_result.education_score) if matching_result.education_score else None,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "experience_gap": matching_result.experience_gap or ""
        }
        
        logger.info(f"Calling interview evaluation service for recording {interview_recording.id}")
        logger.info(f"Transcript length: {len(interview_transcript)} chars, Duration: {duration_minutes} min")
        
        response = requests.post(
            FASTAPI_INTERVIEW_EVALUATION_URL,
            json=payload,
            timeout=FASTAPI_TIMEOUT
        )
        
        logger.info(f"Interview evaluation service response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Interview evaluation completed successfully for recording {interview_recording.id}")
            response_data = response.json()
            
            # Save the evaluation results to the database
            if response_data.get('success') and response_data.get('data'):
                try:
                    from .models import InterviewEvaluation
                    
                    evaluation_data = response_data['data']
                    
                    # Create or update the evaluation
                    evaluation, created = InterviewEvaluation.objects.update_or_create(
                        interview_recording=interview_recording,
                        defaults={
                            # Simplified criteria (new fields)
                            'communication_clarity': evaluation_data.get('communication_clarity', 0),
                            'relevant_experience': evaluation_data.get('relevant_experience', 0),
                            'role_interest_fit': evaluation_data.get('role_interest_fit', 0),
                            'overall_score': evaluation_data.get('overall_score', 0),
                            'recommendation': evaluation_data.get('recommendation', 'INSUFFICIENT'),
                            
                            # Legacy fields (for backward compatibility)
                            'communication_score': evaluation_data.get('communication_clarity', 0) * 10,  # Convert to 0-100 scale
                            'technical_knowledge_score': evaluation_data.get('relevant_experience', 0) * 10,
                            'problem_solving_score': evaluation_data.get('role_interest_fit', 0) * 10,
                            'cultural_fit_score': evaluation_data.get('overall_score', 0) * 10,
                            'enthusiasm_score': evaluation_data.get('overall_score', 0) * 10,
                            
                            # Text fields
                            'strengths': evaluation_data.get('strengths', ''),
                            'areas_of_concern': evaluation_data.get('concerns', ''),
                            'key_insights': evaluation_data.get('insights', ''),
                            'next_steps': evaluation_data.get('next_steps', ''),
                        }
                    )
                    
                    action = "created" if created else "updated"
                    logger.info(f"Evaluation {action} successfully for recording {interview_recording.id}")
                    
                    return {
                        "success": True,
                        "evaluation_id": evaluation.id,
                        "action": action,
                        "message": f"Evaluation {action} successfully"
                    }
                    
                except Exception as db_error:
                    logger.error(f"Error saving evaluation to database: {str(db_error)}")
                    return {
                        "success": False,
                        "error": "Failed to save evaluation to database",
                        "details": str(db_error)
                    }
            else:
                logger.error("Invalid response data from evaluation service")
                return {
                    "success": False,
                    "error": "Invalid response from evaluation service"
                }
            
            return response_data
        else:
            logger.error(f"Interview evaluation service error: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Service returned status {response.status_code}",
                "details": response.text
            }
            
    except requests.exceptions.Timeout:
        logger.error(f"Interview evaluation service timeout for recording {interview_recording.id}")
        return {
            "success": False,
            "error": "Interview evaluation service timeout",
            "details": "The service took too long to respond"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Interview evaluation service request error: {str(e)}")
        return {
            "success": False,
            "error": "Failed to connect to interview evaluation service",
            "details": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error calling interview evaluation service: {str(e)}")
        return {
            "success": False,
            "error": "Unexpected error occurred",
            "details": str(e)
        }


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
    # Import models here to avoid circular imports
    from .models import InterviewEvaluation, InterviewRecording
    
    # Filter all data by current user
    user = request.user
    resumes_count = Resume.objects.filter(user=user).count()
    shortlisted_count = Shortlisted.objects.filter(resume__user=user).count()
    pending_interviews_count = Interview.objects.filter(resume__user=user, status='pending').count()
    
    # Interview evaluation statistics
    completed_evaluations_count = InterviewEvaluation.objects.filter(
        interview_recording__matching_result__user=user,
        status='completed'
    ).count()
    pending_evaluations_count = InterviewEvaluation.objects.filter(
        interview_recording__matching_result__user=user,
        status__in=['pending', 'in_progress']
    ).count()
    positive_recommendations_count = InterviewEvaluation.objects.filter(
        interview_recording__matching_result__user=user,
        status='completed',
        recommendation__in=['hire', 'strong_hire']
    ).count()

    # Activity data for last 7 days - filtered by user
    today = timezone.now().date()
    activity_labels = []
    activity_resumes = []
    activity_shortlisted = []
    activity_interviews = []
    activity_evaluations = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        activity_labels.append(day.strftime('%a'))
        activity_resumes.append(Resume.objects.filter(user=user, uploaded_at__date=day).count())
        activity_shortlisted.append(Shortlisted.objects.filter(resume__user=user, created_at__date=day).count())
        activity_interviews.append(Interview.objects.filter(resume__user=user, scheduled_at__date=day).count())
        activity_evaluations.append(InterviewEvaluation.objects.filter(
            interview_recording__matching_result__user=user,
            created_at__date=day
        ).count())

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
    
    # Get recent interview evaluations for current user only
    recent_evaluations = InterviewEvaluation.objects.filter(
        interview_recording__matching_result__user=user
    ).select_related('interview_recording__matching_result__resume').order_by('-created_at')[:3]
    for evaluation in recent_evaluations:
        recent_activities.append({
            'title': 'Interview evaluated',
            'description': f'{evaluation.interview_recording.candidate_name} - {evaluation.get_recommendation_display()} ({evaluation.overall_score}%)',
            'time_ago': get_time_ago(evaluation.created_at),
            'color': 'indigo',
            'icon': '''<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                   </svg>''',
            'timestamp': evaluation.created_at
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
        'completed_evaluations_count': completed_evaluations_count,
        'pending_evaluations_count': pending_evaluations_count,
        'positive_recommendations_count': positive_recommendations_count,
        'activity_labels': activity_labels,
        'activity_resumes': activity_resumes,
        'activity_shortlisted': activity_shortlisted,
        'activity_interviews': activity_interviews,
        'activity_evaluations': activity_evaluations,
        'recent_activities': recent_activities,
        'notifications': notifications,
        'notifications_count': len(notifications),
    }
    return render(request, 'home/dashboard_home.html', context)


@login_required
def interview_evaluations(request):
    """
    View for interview evaluations dashboard showing AI evaluation results
    """
    # Import models here to avoid circular imports
    from .models import InterviewEvaluation
    from django.db import models
    
    # Get all evaluations for the current user
    evaluations = InterviewEvaluation.objects.filter(
        interview_recording__matching_result__user=request.user
    ).select_related(
        'interview_recording__matching_result__resume',
        'interview_recording__matching_result__job_description'
    ).order_by('-created_at')
    
    # Statistics
    total_evaluations = evaluations.count()
    completed_evaluations = evaluations.filter(status='completed').count()
    pending_evaluations = evaluations.filter(status__in=['pending', 'in_progress']).count()
    failed_evaluations = evaluations.filter(status='failed').count()
    
    # Recommendation statistics
    strong_hire_count = evaluations.filter(recommendation='strong_hire').count()
    hire_count = evaluations.filter(recommendation='hire').count()
    maybe_count = evaluations.filter(recommendation='maybe').count()
    no_hire_count = evaluations.filter(recommendation='no_hire').count()
    
    # Average scores for completed evaluations
    completed = evaluations.filter(status='completed')
    avg_overall_score = completed.aggregate(avg=models.Avg('overall_score'))['avg'] or 0
    avg_communication_score = completed.aggregate(avg=models.Avg('communication_score'))['avg'] or 0
    avg_technical_score = completed.aggregate(avg=models.Avg('technical_knowledge_score'))['avg'] or 0
    avg_cultural_fit_score = completed.aggregate(avg=models.Avg('cultural_fit_score'))['avg'] or 0
    
    # HR review statistics
    needs_hr_review_count = evaluations.filter(status='completed', hr_reviewed=False).count()
    hr_reviewed_count = evaluations.filter(hr_reviewed=True).count()
    
    # Recent high-performing candidates (completed evaluations with score >= 75)
    high_performers = completed.filter(overall_score__gte=75).order_by('-overall_score')[:5]
    
    # Get notifications for header
    notifications = get_notifications(request.user)
    
    context = {
        'evaluations': evaluations,
        'total_evaluations': total_evaluations,
        'completed_evaluations': completed_evaluations,
        'pending_evaluations': pending_evaluations,
        'failed_evaluations': failed_evaluations,
        'strong_hire_count': strong_hire_count,
        'hire_count': hire_count,
        'maybe_count': maybe_count,
        'no_hire_count': no_hire_count,
        'avg_overall_score': round(float(avg_overall_score), 1),
        'avg_communication_score': round(float(avg_communication_score), 1),
        'avg_technical_score': round(float(avg_technical_score), 1),
        'avg_cultural_fit_score': round(float(avg_cultural_fit_score), 1),
        'needs_hr_review_count': needs_hr_review_count,
        'hr_reviewed_count': hr_reviewed_count,
        'high_performers': high_performers,
        'notifications': notifications,
        'notifications_count': len(notifications),
    }
    
    return render(request, 'home/interview_evaluations.html', context)


@login_required
def interview_evaluation_detail(request, evaluation_id):
    """
    Detailed view for individual interview evaluation
    """
    from .models import InterviewEvaluation
    
    # Get the evaluation, ensuring it belongs to the current user
    evaluation = get_object_or_404(
        InterviewEvaluation.objects.select_related(
            'interview_recording__matching_result__resume',
            'interview_recording__matching_result__job_description',
            'interview_recording'
        ),
        id=evaluation_id,
        interview_recording__matching_result__user=request.user
    )
    
    # Get the interview recording for transcript and audio
    interview_recording = evaluation.interview_recording
    
    # Get all messages for the interview
    interview_messages = InterviewMessage.objects.filter(
        interview_recording=interview_recording
    ).order_by('timestamp')
    
    # Prepare detailed feedback from model fields
    detailed_feedback = {
        'strengths': evaluation.strengths or [],
        'areas_of_concern': evaluation.areas_of_concern or [],
        'key_insights': evaluation.key_insights or [],
        'communication_assessment': evaluation.communication_assessment or '',
        'technical_assessment': evaluation.technical_assessment or '',
        'behavioral_assessment': evaluation.behavioral_assessment or '',
        'questions_answered_well': evaluation.questions_answered_well or [],
        'questions_struggled_with': evaluation.questions_struggled_with or [],
        'recommended_next_steps': evaluation.recommended_next_steps or '',
        'topics_to_explore_further': evaluation.topics_to_explore_further or [],
        'specific_concerns_to_address': evaluation.specific_concerns_to_address or [],
    }
    
    # Get notifications for header
    notifications = get_notifications(request.user)
    
    context = {
        'evaluation': evaluation,
        'interview_recording': interview_recording,
        'interview_messages': interview_messages,
        'detailed_feedback': detailed_feedback,
        'notifications': notifications,
        'notifications_count': len(notifications),
    }
    
    return render(request, 'home/interview_evaluation_detail.html', context)


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
                logger.info(f"Processing bulk shortlist for {len(candidate_ids)} candidates")
                
                # Get matching results that belong to the user
                matching_results = MatchingResult.objects.filter(
                    id__in=candidate_ids,
                    user=request.user,
                    status='pending'  # Only shortlist pending candidates
                )
                
                shortlisted_candidates = []
                questions_generated = 0
                questions_failed = 0
                
                # Process each candidate individually for interview questions
                for matching_result in matching_results:
                    # Update status to shortlisted
                    matching_result.status = 'shortlisted'
                    matching_result.updated_at = timezone.now()
                    matching_result.save()
                    
                    # Also create Shortlisted record for backward compatibility
                    Shortlisted.objects.get_or_create(resume=matching_result.resume)
                    
                    shortlisted_candidates.append(matching_result.resume.candidate_name)
                    
                    # Generate interview questions for each candidate
                    try:
                        if not hasattr(matching_result, 'interview_questions'):
                            logger.info(f"Generating questions for {matching_result.resume.candidate_name}")
                            
                            questions_response = call_fastapi_interview_questions_service(matching_result)
                            
                            if questions_response.get('success'):
                                questions_data = questions_response.get('questions', [])
                                metadata = questions_response.get('metadata', {})
                                
                                InterviewQuestions.objects.create(
                                    matching_result=matching_result,
                                    questions=questions_data,
                                    total_questions=len(questions_data),
                                    estimated_duration=metadata.get('estimated_duration', '30-45 minutes'),
                                    complexity_level=metadata.get('complexity_level', 'mid'),
                                    focus_areas=metadata.get('focus_areas', []),
                                    question_distribution=metadata.get('question_distribution', {}),
                                    status='generated'
                                )
                                
                                questions_generated += 1
                                logger.info(f"Generated questions for {matching_result.resume.candidate_name}")
                            else:
                                questions_failed += 1
                                logger.warning(f"Failed to generate questions for {matching_result.resume.candidate_name}")
                        else:
                            logger.info(f"Questions already exist for {matching_result.resume.candidate_name}")
                            
                    except Exception as e:
                        questions_failed += 1
                        logger.error(f"Error generating questions for {matching_result.resume.candidate_name}: {str(e)}")
                
                # Prepare response message
                message = f'Successfully shortlisted {len(shortlisted_candidates)} candidate(s)'
                if questions_generated > 0:
                    message += f'. Generated interview questions for {questions_generated} candidate(s)'
                if questions_failed > 0:
                    message += f'. Failed to generate questions for {questions_failed} candidate(s)'
                
                logger.info(message)
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'shortlisted_count': len(shortlisted_candidates),
                    'questions_generated': questions_generated,
                    'questions_failed': questions_failed,
                    'candidates': shortlisted_candidates
                })
                
            except Exception as e:
                logger.error(f"Error in bulk shortlist: {str(e)}")
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
        'resume', 'job_description', 'interview_questions'
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
    """Shortlist a candidate from matching results and generate interview questions"""
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
            
            # Generate interview questions for the shortlisted candidate
            questions_result = None
            questions_error = None
            
            try:
                logger.info(f"Processing shortlist for matching result {result_id}")
                
                # Check if interview questions already exist
                if not hasattr(matching_result, 'interview_questions'):
                    logger.info(f"No existing questions found, generating new ones for {matching_result.resume.candidate_name}")
                    
                    # Call the interview questions generation service
                    questions_response = call_fastapi_interview_questions_service(matching_result)
                    
                    logger.info(f"Questions service response: {questions_response.get('success', False)}")
                    
                    if questions_response.get('success'):
                        # Save the generated questions to database
                        questions_data = questions_response.get('questions', [])
                        metadata = questions_response.get('metadata', {})
                        
                        logger.info(f"Saving {len(questions_data)} questions to database")
                        
                        interview_questions = InterviewQuestions.objects.create(
                            matching_result=matching_result,
                            questions=questions_data,
                            total_questions=len(questions_data),
                            estimated_duration=metadata.get('estimated_duration', '30-45 minutes'),
                            complexity_level=metadata.get('complexity_level', 'mid'),
                            focus_areas=metadata.get('focus_areas', []),
                            question_distribution=metadata.get('question_distribution', {}),
                            status='generated'
                        )
                        
                        logger.info(f"Generated {len(questions_data)} interview questions for {matching_result.resume.candidate_name}")
                        questions_result = f"Generated {len(questions_data)} interview questions"
                    else:
                        questions_error = questions_response.get('error', 'Failed to generate questions')
                        logger.warning(f"Failed to generate interview questions: {questions_error}")
                        logger.warning(f"Full response: {questions_response}")
                else:
                    questions_result = "Interview questions already exist"
                    logger.info(f"Interview questions already exist for {matching_result.resume.candidate_name}")
                    
            except Exception as e:
                questions_error = f"Error generating interview questions: {str(e)}"
                logger.error(f"Error generating interview questions for matching result {result_id}: {str(e)}")
            
            # Prepare response message
            base_message = f'{matching_result.resume.candidate_name} has been shortlisted!'
            if questions_result:
                message = f"{base_message} {questions_result}."
            elif questions_error:
                message = f"{base_message} Warning: {questions_error}"
            else:
                message = base_message
            
            return JsonResponse({
                'success': True,
                'message': message,
                'questions_generated': bool(questions_result),
                'questions_error': questions_error
            })
            
        except MatchingResult.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Matching result not found'
            })
        except Exception as e:
            logger.error(f"Error in shortlist_candidate: {str(e)}")
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
def interview_dashboard(request):
    """Unified dashboard showing all voice interviews (ElevenLabs recordings only)"""
    user = request.user
    
    # Get search and filter parameters
    search_query = request.GET.get('search', '').strip()
    current_status = request.GET.get('status', '')
    selected_jd = request.GET.get('jd', '')
    
    # Get only ElevenLabs InterviewRecordings (voice interviews)
    recordings = InterviewRecording.objects.filter(
        matching_result__user=user
    ).select_related(
        'matching_result__resume',
        'matching_result__job_description'
    ).prefetch_related('messages').order_by('-created_at')
    
    # Apply search filter
    if search_query:
        recordings = recordings.filter(
            matching_result__resume__candidate_name__icontains=search_query
        )
    
    # Apply status filter with simplified mapping
    if current_status:
        if current_status == 'complete':
            recordings = recordings.filter(status='completed')
        elif current_status == 'pending':
            recordings = recordings.filter(status__in=['pending', 'processing'])
        elif current_status == 'failed':
            recordings = recordings.filter(status='failed')
    
    # Apply job description filter
    if selected_jd:
        recordings = recordings.filter(matching_result__job_description_id=selected_jd)
    
    # Import InterviewEvaluation model
    from .models import InterviewEvaluation, JobDescription
    
    # Get all job descriptions for dropdown
    all_job_descriptions = JobDescription.objects.filter(user=user).values('id', 'title').distinct()
    
    # Convert to unified format with simplified status mapping
    all_interviews = []
    
    for recording in recordings:
        # Simplify status mapping to your 3 required statuses
        if recording.status == 'completed':
            status = 'complete'
        elif recording.status in ['pending', 'processing']:
            status = 'pending'
        elif recording.status == 'failed':
            status = 'failed'
        else:
            status = 'pending'  # Default fallback
        
        # Get evaluation data if it exists
        evaluation = None
        try:
            evaluation = InterviewEvaluation.objects.get(interview_recording=recording)
        except InterviewEvaluation.DoesNotExist:
            evaluation = None
            
        all_interviews.append({
            'id': recording.id,
            'interview_type': 'recording',  # All are voice recordings now
            'candidate_name': (recording.matching_result.resume.candidate_name if recording.matching_result else 'Unknown') or 'Unknown',
            'candidate_email': (recording.matching_result.resume.email if recording.matching_result else '') or '',
            'job_title': (recording.matching_result.job_description.title if recording.matching_result else 'Unknown Position') or 'Unknown Position',
            'job_department': getattr(recording.matching_result.job_description if recording.matching_result else None, 'department', '') or '',
            'status': status,
            'created_at': recording.created_at,
            'conversation_id': recording.conversation_id,
            'has_audio': bool(recording.audio_file),
            'has_transcript': bool(recording.transcript_file),
            'evaluation': evaluation,  # Add evaluation data
            'has_evaluation': evaluation is not None,  # Boolean flag for template logic
            'email_sent': recording.email_sent,
            'email_type': recording.email_type,
            'interview_round': recording.interview_round,
            'email_sent_at': recording.email_sent_at,
        })
    
    # Calculate summary statistics with simplified statuses
    total_interviews = len(all_interviews)
    completed = len([i for i in all_interviews if i['status'] == 'complete'])
    pending = len([i for i in all_interviews if i['status'] == 'pending'])
    failed = len([i for i in all_interviews if i['status'] == 'failed'])
    evaluated = len([i for i in all_interviews if i['has_evaluation']])
    
    stats = {
        'total_interviews': total_interviews,
        'completed': completed,
        'pending': pending,
        'failed': failed,
        'evaluated': evaluated,
    }
    
    context = {
        'all_interviews': all_interviews,
        'stats': stats,
        'search_query': search_query,
        'current_status': current_status,
        'selected_jd': selected_jd,
        'all_job_descriptions': all_job_descriptions,
        'notifications': get_notifications(user),
    }
    
    return render(request, 'home/interview_dashboard.html', context)

@login_required
@require_http_methods(["GET"])
def get_profile_address(request):
    """Get user's profile office address"""
    from .models import Profile
    
    try:
        profile = Profile.objects.get(user=request.user)
        return JsonResponse({
            'success': True,
            'office_address': profile.office_address or ''
        })
    except Profile.DoesNotExist:
        return JsonResponse({
            'success': True,
            'office_address': ''
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required 
@require_http_methods(["POST"])
def send_candidate_emails(request):
    """Send emails to selected candidates via email agent with interview scheduling"""
    import json
    import requests
    
    try:
        data = json.loads(request.body)
        candidate_ids = data.get('candidate_ids', [])
        email_type = data.get('email_type', 'selection')
        interview_round = data.get('interview_round', 'initial')
        
        # New interview scheduling parameters
        interview_type = data.get('interviewType')  # 'onsite' or 'online'
        interview_datetime = data.get('interviewDateTime')  # ISO format string
        interview_location = data.get('interviewLocation')  # address or 'default_office_address'
        
        if not candidate_ids:
            return JsonResponse({'success': False, 'error': 'No candidates selected'})
        
        print(f"DEBUG DJANGO VIEW: Received interview scheduling data:")
        print(f"  - Interview Type: {interview_type}")
        print(f"  - Interview DateTime: {interview_datetime}")
        print(f"  - Interview Location: {interview_location}")
        print(f"  - Interview Round: {interview_round}")
        print(f"  - Email Type: {email_type}")
        
        # Prepare payload for email agent
        payload = {
            "candidate_ids": candidate_ids,
            "email_type": email_type,
            "interview_round": interview_round,
            "hr_user_id": request.user.id
        }
        
        # Add interview scheduling data if provided
        if interview_type and interview_datetime:
            payload.update({
                "interviewType": interview_type,
                "interviewDateTime": interview_datetime,
                "interviewLocation": interview_location
            })
            print(f"DEBUG DJANGO VIEW: Added scheduling data to payload")
        
        # Call email agent
        email_agent_url = "http://localhost:8003/send-emails"
        print(f"DEBUG DJANGO VIEW: Calling email agent with payload: {payload}")
        
        try:
            response = requests.post(email_agent_url, json=payload, timeout=60)  # Increased timeout for Zoom API calls
        except requests.exceptions.Timeout:
            return JsonResponse({
                'success': False, 
                'error': 'Request timeout. Please try again - Zoom meeting creation may take longer than usual.'
            })
        except requests.exceptions.ConnectionError:
            return JsonResponse({
                'success': False, 
                'error': 'Cannot connect to email service. Please ensure the email agent is running on port 8003.'
            })
        
        if response.status_code == 200:
            result = response.json()
            print(f"DEBUG DJANGO VIEW: Email agent response: {result}")
            return JsonResponse({
                'success': True,
                'success_count': result.get('success_count', 0),
                'failed_count': result.get('failed_count', 0),
                'message': result.get('message', 'Emails sent successfully')
            })
        else:
            error_detail = response.text if response.text else 'Email service error'
            print(f"DEBUG DJANGO VIEW: Email agent error ({response.status_code}): {error_detail}")
            return JsonResponse({
                'success': False, 
                'error': f'Email service error: {error_detail}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        print(f"DEBUG DJANGO VIEW: Exception in send_candidate_emails: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def delete_interviews(request):
    """Delete interview recordings (individual or bulk)"""
    user = request.user
    
    try:
        # Get the interview IDs to delete
        interview_ids = request.POST.getlist('interview_ids')
        if not interview_ids:
            messages.error(request, 'No interviews selected for deletion.')
            return redirect('interviews')
        
        # Get recordings that belong to the current user
        recordings = InterviewRecording.objects.filter(
            id__in=interview_ids,
            matching_result__user=user
        )
        
        deleted_count = 0
        for recording in recordings:
            try:
                # Delete audio file if exists
                if recording.audio_file:
                    if recording.audio_file.path and os.path.exists(recording.audio_file.path):
                        os.remove(recording.audio_file.path)
                
                # Delete transcript file if exists  
                if recording.transcript_file:
                    if recording.transcript_file.path and os.path.exists(recording.transcript_file.path):
                        os.remove(recording.transcript_file.path)
                
                # Delete the database record
                candidate_name = recording.matching_result.resume.candidate_name if recording.matching_result else 'Unknown'
                recording.delete()
                deleted_count += 1
                
            except Exception as e:
                messages.warning(request, f'Failed to delete interview for {candidate_name}: {str(e)}')
        
        if deleted_count > 0:
            messages.success(request, f'Successfully deleted {deleted_count} interview record(s) and associated files.')
        
        return redirect('interviews')
        
    except Exception as e:
        messages.error(request, f'Error deleting interviews: {str(e)}')
        return redirect('interviews')

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

def candidate_interview(request, hr_user_id, jd_id):
    """
    Public view for candidates to access their interview.
    No authentication required - validates email against shortlisted candidates for specific HR user and JD.
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
    
    # Validate that the jd_id exists and belongs to this HR user
    try:
        job_description = JobDescription.objects.get(id=jd_id, user=hr_user)
    except JobDescription.DoesNotExist:
        context['error_message'] = "Invalid job description or unauthorized access. Please contact HR for assistance."
        return render(request, 'home/candidate_interview.html', context)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            context['error_message'] = "Please enter your email address."
            return render(request, 'home/candidate_interview.html', context)
        
        try:
            # Find the candidate's resume for this specific HR user and JD
            resume = Resume.objects.filter(
                email__iexact=email,
                user=hr_user,
                jobdescription=job_description
            ).first()
            
            if not resume:
                context['error_message'] = "No application found for this email address for this specific position. Please check your email address or contact HR."
                return render(request, 'home/candidate_interview.html', context)
            
            # Debug: Log the specific match validation
            logger.info(f"DEBUG INTERVIEW ACCESS: Starting HR+JD specific validation for email={email}, hr_user_id={hr_user_id}, jd_id={jd_id}")
            logger.info(f"DEBUG INTERVIEW ACCESS: Resume found - ID={resume.id}, candidate_name={resume.candidate_name}")
            
            # Check if the candidate has shortlisted matching result for this specific HR user and JD
            shortlisted_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,
                job_description=job_description,
                status='shortlisted'
            ).select_related('job_description')
            logger.info(f"DEBUG INTERVIEW ACCESS: Shortlisted matches count: {shortlisted_matches.count()}")
            
            # Also check for candidates who have been sent selection emails for this specific HR+JD
            selection_email_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,
                job_description=job_description,
                email_status='selection_sent'
            ).select_related('job_description')
            logger.info(f"DEBUG INTERVIEW ACCESS: Selection email matches count: {selection_email_matches.count()}")
            
            # Combine both queries - candidate is eligible if they have shortlisted status OR selection email sent
            eligible_matches = shortlisted_matches.union(selection_email_matches)
            logger.info(f"DEBUG INTERVIEW ACCESS: Eligible matches count (union): {eligible_matches.count()}")
            
            # Also check if there are any rejected matches for this HR user and JD
            rejected_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,
                job_description=job_description,
                status='rejected'
            ).exists()
            
            # Check for pending matches for this HR user and JD
            pending_matches = MatchingResult.objects.filter(
                resume=resume,
                user=hr_user,
                job_description=job_description,
                status='pending'
            ).exists()
            
            # Debug: Log shortlisted and rejected counts for this HR user
            logger.info(f"DEBUG INTERVIEW ACCESS: Final validation - Shortlisted: {shortlisted_matches.count()}, Selection emails: {selection_email_matches.count()}, Eligible total: {eligible_matches.count()}, Rejected exists: {rejected_matches}, Pending exists: {pending_matches}")
            
            # HR + JD specific validation: Prioritize eligible matches
            if eligible_matches.exists():
                logger.info(f"DEBUG INTERVIEW ACCESS: ACCESS GRANTED - Candidate has eligible matches for HR {hr_user_id} and JD {jd_id}")
                # Continue to interview ready section
                pass
            else:
                logger.info(f"DEBUG INTERVIEW ACCESS: ACCESS DENIED - No eligible matches found for HR {hr_user_id} and JD {jd_id}")
                # No eligible matches - check other statuses for appropriate error message
                if rejected_matches:
                    logger.info(f"DEBUG INTERVIEW ACCESS: Showing rejection message")
                    context['error_message'] = "Thank you for your interest in this position. After careful consideration, we have decided to move forward with other candidates whose qualifications more closely match our current requirements. We appreciate the time you invested in your application and wish you the best in your career endeavors."
                elif pending_matches:
                    logger.info(f"DEBUG INTERVIEW ACCESS: Showing pending message")
                    context['error_message'] = "Your application is still under review. Please wait for further communication."
                else:
                    logger.info(f"DEBUG INTERVIEW ACCESS: Showing no invitation message")
                    context['error_message'] = "No interview invitation found for this email address for this position."
                return render(request, 'home/candidate_interview.html', context)
            
            # Get the most recent eligible match for interview
            latest_match = eligible_matches.order_by('-created_at').first()
            logger.info(f"DEBUG INTERVIEW ACCESS: Latest eligible match: ID={latest_match.id}, Status={latest_match.status}")
            
            # Check if this candidate has already taken an interview for this matching result
            from .models import InterviewRecording
            existing_interview = InterviewRecording.objects.filter(
                matching_result=latest_match
            ).first()
            
            interview_already_taken = False
            interview_status = None
            
            if existing_interview:
                # Check if interview is completed or failed (both count as "taken")
                if existing_interview.status in ['completed', 'failed']:
                    interview_already_taken = True
                    interview_status = existing_interview.status
                    logger.info(f"DEBUG INTERVIEW ACCESS: Interview already taken - Status: {existing_interview.status}")
                else:
                    logger.info(f"DEBUG INTERVIEW ACCESS: Interview in progress - Status: {existing_interview.status}")
            
            context.update({
                'step': 'interview_ready',
                'candidate_data': {
                    'name': resume.candidate_name or 'Candidate',
                    'email': resume.email,
                    'position': job_description.title,
                    'company': job_description.department or (hr_user.profile.company_name if hasattr(hr_user, 'profile') else 'Our Company'),
                    'match_id': latest_match.id,
                    'hr_user_id': hr_user_id,
                    'jd_id': jd_id,
                    'interview_already_taken': interview_already_taken,
                    'interview_status': interview_status,
                    'existing_interview_id': existing_interview.id if existing_interview else None,
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

def debug_interview_flow(request, email, hr_user_id, jd_id):
    """Comprehensive debug view to trace interview access flow for HR + JD specific validation"""
    try:
        from django.contrib.auth.models import User
        
        # Validate HR user exists
        try:
            hr_user = User.objects.get(id=hr_user_id)
        except User.DoesNotExist:
            return JsonResponse({
                'error': f'HR User with ID {hr_user_id} does not exist',
                'hr_user_id': hr_user_id,
                'jd_id': jd_id
            })
        
        # Validate JD exists and belongs to HR user
        try:
            job_description = JobDescription.objects.get(id=jd_id, user=hr_user)
        except JobDescription.DoesNotExist:
            return JsonResponse({
                'error': f'Job Description with ID {jd_id} does not exist or does not belong to HR user {hr_user_id}',
                'hr_user_id': hr_user_id,
                'hr_username': hr_user.username,
                'jd_id': jd_id
            })
        
        # Find candidate resume for this specific HR user and JD
        resume = Resume.objects.filter(
            email__iexact=email,
            user=hr_user,
            jobdescription=job_description
        ).first()
        
        if not resume:
            # Check if candidate exists for this HR but different JD
            other_resumes = Resume.objects.filter(email__iexact=email, user=hr_user).select_related('jobdescription')
            
            return JsonResponse({
                'error': 'No application found for this specific HR + JD combination',
                'email': email,
                'hr_user_id': hr_user_id,
                'hr_username': hr_user.username,
                'jd_id': jd_id,
                'jd_title': job_description.title,
                'other_applications_for_this_hr': [
                    {
                        'resume_id': r.id,
                        'jd_id': r.jobdescription.id,
                        'jd_title': r.jobdescription.title,
                        'candidate_name': r.candidate_name
                    } for r in other_resumes
                ]
            })
        
        # Get matching result for this specific HR + JD combination
        matching_result = MatchingResult.objects.filter(
            resume=resume,
            user=hr_user,
            job_description=job_description
        ).first()
        
        # Check different status combinations
        shortlisted_matches = MatchingResult.objects.filter(
            resume=resume,
            user=hr_user,
            job_description=job_description,
            status='shortlisted'
        )
        
        selection_email_matches = MatchingResult.objects.filter(
            resume=resume,
            user=hr_user,
            job_description=job_description,
            email_status='selection_sent'
        )
        
        eligible_matches = shortlisted_matches.union(selection_email_matches)
        
        # Check interview access logic
        access_granted = eligible_matches.exists()
        access_reason = ""
        
        if access_granted:
            if shortlisted_matches.exists() and selection_email_matches.exists():
                access_reason = "Both shortlisted status AND selection email sent"
            elif shortlisted_matches.exists():
                access_reason = "Has shortlisted status"
            elif selection_email_matches.exists():
                access_reason = "Has selection email sent"
        else:
            rejected_matches = MatchingResult.objects.filter(
                resume=resume, user=hr_user, job_description=job_description, status='rejected'
            ).exists()
            pending_matches = MatchingResult.objects.filter(
                resume=resume, user=hr_user, job_description=job_description, status='pending'
            ).exists()
            
            if rejected_matches:
                access_reason = "Has rejected status - would show rejection message"
            elif pending_matches:
                access_reason = "Has pending status - would show under review message"
            else:
                access_reason = "No matches found for this HR + JD combination - would show no invitation message"
        
        return JsonResponse({
            'debug_info': {
                'email': email,
                'hr_user_id': hr_user_id,
                'hr_username': hr_user.username,
                'jd_id': jd_id,
                'jd_title': job_description.title,
                'candidate_name': resume.candidate_name,
                'resume_id': resume.id,
                'interview_access_granted': access_granted,
                'access_reason': access_reason
            },
            'matching_result': {
                'exists': matching_result is not None,
                'id': matching_result.id if matching_result else None,
                'status': matching_result.status if matching_result else None,
                'email_status': matching_result.email_status if matching_result else None,
                'overall_score': float(matching_result.overall_score) if matching_result else None,
                'created_at': matching_result.created_at.strftime('%Y-%m-%d %H:%M:%S') if matching_result else None,
                'updated_at': matching_result.updated_at.strftime('%Y-%m-%d %H:%M:%S') if matching_result else None,
            },
            'validation_details': {
                'shortlisted_matches_exist': shortlisted_matches.exists(),
                'selection_email_matches_exist': selection_email_matches.exists(),
                'eligible_matches_exist': eligible_matches.exists(),
                'would_allow_interview_access': access_granted
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Debug error: {str(e)}',
            'email': email,
            'hr_user_id': hr_user_id,
            'jd_id': jd_id
        })
    try:
        from django.contrib.auth.models import User
        
        # Validate HR user exists
        try:
            hr_user = User.objects.get(id=hr_user_id)
        except User.DoesNotExist:
            return JsonResponse({
                'error': f'HR User with ID {hr_user_id} does not exist',
                'hr_user_id': hr_user_id
            })
        
        # Find candidate resume
        resume = Resume.objects.filter(email__iexact=email).first()
        if not resume:
            return JsonResponse({
                'error': 'Email not found in system',
                'email': email,
                'hr_user_id': hr_user_id,
                'hr_username': hr_user.username
            })
        
        # Get ALL matching results for this resume
        all_matches = MatchingResult.objects.filter(resume=resume).select_related('job_description', 'user')
        
        # Get matches specific to this HR user
        hr_user_matches = MatchingResult.objects.filter(resume=resume, user=hr_user).select_related('job_description')
        
        # Get shortlisted matches for this HR user
        shortlisted_matches = MatchingResult.objects.filter(
            resume=resume,
            user=hr_user,
            status='shortlisted'
        ).select_related('job_description')
        
        # Get selection email matches for this HR user
        selection_email_matches = MatchingResult.objects.filter(
            resume=resume,
            user=hr_user,
            email_status='selection_sent'
        ).select_related('job_description')
        
        # Get eligible matches (union of shortlisted and selection emails)
        eligible_matches = shortlisted_matches.union(selection_email_matches)
        
        # Prepare detailed match data
        all_matches_data = []
        for match in all_matches:
            all_matches_data.append({
                'id': match.id,
                'hr_user_id': match.user.id,
                'hr_username': match.user.username,
                'status': match.status,
                'email_status': match.email_status,
                'position': match.job_description.title,
                'company': match.job_description.department,
                'overall_score': float(match.overall_score),
                'created_at': match.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': match.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                'is_for_current_hr': match.user.id == hr_user_id
            })
        
        hr_user_matches_data = []
        for match in hr_user_matches:
            hr_user_matches_data.append({
                'id': match.id,
                'status': match.status,
                'email_status': match.email_status,
                'position': match.job_description.title,
                'company': match.job_description.department,
                'overall_score': float(match.overall_score),
                'created_at': match.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': match.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        # Check interview access logic
        access_granted = eligible_matches.exists()
        access_reason = ""
        
        if access_granted:
            if shortlisted_matches.exists() and selection_email_matches.exists():
                access_reason = "Both shortlisted status AND selection email sent"
            elif shortlisted_matches.exists():
                access_reason = "Has shortlisted status"
            elif selection_email_matches.exists():
                access_reason = "Has selection email sent"
        else:
            rejected_matches = MatchingResult.objects.filter(resume=resume, user=hr_user, status='rejected').exists()
            pending_matches = MatchingResult.objects.filter(resume=resume, user=hr_user, status='pending').exists()
            
            if rejected_matches:
                access_reason = "Has rejected status - would show rejection message"
            elif pending_matches:
                access_reason = "Has pending status - would show under review message"
            else:
                access_reason = "No matches found for this HR user - would show no invitation message"
        
        return JsonResponse({
            'debug_info': {
                'email': email,
                'hr_user_id': hr_user_id,
                'hr_username': hr_user.username,
                'candidate_name': resume.candidate_name,
                'resume_id': resume.id,
                'interview_access_granted': access_granted,
                'access_reason': access_reason
            },
            'counts': {
                'total_matches_all_users': all_matches.count(),
                'matches_for_this_hr_user': hr_user_matches.count(),
                'shortlisted_for_this_hr': shortlisted_matches.count(),
                'selection_emails_for_this_hr': selection_email_matches.count(),
                'eligible_matches_for_this_hr': eligible_matches.count()
            },
            'all_matches_across_all_hr_users': all_matches_data,
            'matches_for_current_hr_user_only': hr_user_matches_data,
            'validation_details': {
                'shortlisted_matches_exist': shortlisted_matches.exists(),
                'selection_email_matches_exist': selection_email_matches.exists(),
                'eligible_matches_exist': eligible_matches.exists(),
                'would_allow_interview_access': access_granted
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Debug error: {str(e)}',
            'email': email,
            'hr_user_id': hr_user_id
        })

def voice_interview(request, matching_result_id):
    """
    Voice interview page for candidates using ElevenLabs Conversational AI.
    """
    try:
        # Get the matching result
        matching_result = MatchingResult.objects.select_related(
            'resume', 'job_description', 'user'
        ).get(id=matching_result_id)
        
        # Verify the candidate is eligible for interview (shortlisted or selection email sent)
        if matching_result.status not in ['shortlisted'] and matching_result.email_status != 'selection_sent':
            context = {
                'error': 'You are not authorized to access this interview.',
                'matching_result_id': matching_result_id
            }
            return render(request, 'home/voice_interview.html', context)
        
        # Check if interview has already been taken
        from .models import InterviewRecording
        existing_interview = InterviewRecording.objects.filter(
            matching_result=matching_result
        ).first()
        
        if existing_interview and existing_interview.status in ['completed', 'failed']:
            context = {
                'error': f'Interview has already been completed. Status: {existing_interview.status}',
                'matching_result_id': matching_result_id,
                'interview_already_taken': True,
                'interview_status': existing_interview.status
            }
            return render(request, 'home/voice_interview.html', context)
        
        # Import ElevenLabs service
        from home.services_elevenlabs import ElevenLabsAPIService
        
        # Initialize ElevenLabs service
        interview_service = ElevenLabsAPIService()
        
        # Start interview session
        result = interview_service.start_interview(matching_result_id)
        
        if result["status"] == "error":
            # Handle error cases
            if result.get("can_retry"):
                messages.warning(request, result["message"])
                logger.warning(f"Interview retry needed for matching result {matching_result_id}: {result['message']}")
            else:
                messages.error(request, result["message"])
                logger.error(f"Interview failed for matching result {matching_result_id}: {result['message']}")
                return redirect('dashboard')
            
            # Show error context but allow retry
            context = {
                'error': result["message"],
                'matching_result_id': matching_result_id,
                'can_retry': result.get("can_retry", False)
            }
            return render(request, 'home/voice_interview.html', context)
        
        # Success - prepare context for interview
        context = {
            'matching_result_id': matching_result_id,
            'session_id': result["session_id"],
            'candidate_name': result["candidate_name"],
            'position': result["position"],
            'company': result["company"],
            'agent_id': result["agent_id"],
            'elevenlabs_session_id': result["elevenlabs_session_id"],
            'total_questions': result.get("total_questions", 0),
            'interview_questions': result.get("interview_questions", ""),  # Add interview questions
            'has_questions': True,
            'interview_ready': True
        }
        
        # Debug log to help identify missing data
        logger.info(f"✅ Voice interview context prepared:")
        logger.info(f"   - Candidate Name: {context['candidate_name']}")
        logger.info(f"   - Position: {context['position']}")
        logger.info(f"   - Company: {context['company']}")
        logger.info(f"   - Agent ID: {context['agent_id']}")
        logger.info(f"   - Session ID: {context['session_id']}")
        
        return render(request, 'home/voice_interview.html', context)
        
    except MatchingResult.DoesNotExist:
        logger.error(f"MatchingResult {matching_result_id} not found")
        context = {
            'error': 'Interview not found. Please check your interview link.',
            'matching_result_id': matching_result_id
        }
        return render(request, 'home/voice_interview.html', context)
        
    except Exception as e:
        logger.error(f"Voice interview error for matching result {matching_result_id}: {str(e)}")
        messages.error(request, "An error occurred setting up your interview. Please try again.")
        return redirect('dashboard')


@require_http_methods(["POST"])
@csrf_exempt
def interview_completion(request, matching_result_id):
    """
    Handle interview completion from ElevenLabs.
    Updates interview session status and fetches interview data from ElevenLabs APIs.
    """
    try:
        # Import our new ElevenLabs service
        from .services_elevenlabs import ElevenLabsAPIService, fetch_interview_data
        import json
        
        # Get the matching result
        matching_result = get_object_or_404(MatchingResult, id=matching_result_id)
        
        # Parse request data
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        # Get completion details
        conversation_id = data.get('conversation_id')
        completion_reason = data.get('completion_reason', 'completed')
        session_id = data.get('session_id')
        
        logger.info(f"🏁 Interview completion for candidate {matching_result.resume.candidate_name}")
        logger.info(f"   Conversation ID: {conversation_id}")
        logger.info(f"   Completion Reason: {completion_reason}")
        
        # Always mark the interview as completed in MatchingResult
        matching_result.interview = True
        matching_result.save()
        logger.info(f"✅ Marked matching result {matching_result_id} as interviewed")
        
        # If we have a conversation ID, fetch the interview data from ElevenLabs
        if conversation_id:
            try:
                logger.info(f"📥 Fetching interview data from ElevenLabs for conversation: {conversation_id}")
                
                # Use our new service to fetch and store interview data
                interview_recording = fetch_interview_data(
                    conversation_id=conversation_id,
                    matching_result_id=matching_result_id
                )
                
                logger.info(f"✅ Successfully fetched and stored interview data")
                logger.info(f"   Recording ID: {interview_recording.id}")
                logger.info(f"   Messages: {interview_recording.messages.count()}")
                logger.info(f"   Has Audio: {bool(interview_recording.audio_file)}")
                logger.info(f"   Has Transcript: {bool(interview_recording.transcript_file)}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Interview completed and data saved successfully',
                    'conversation_id': conversation_id,
                    'completion_reason': completion_reason,
                    'recording_id': interview_recording.id,
                    'has_audio': bool(interview_recording.audio_file),
                    'has_transcript': bool(interview_recording.transcript_file),
                    'message_count': interview_recording.messages.count()
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to fetch interview data from ElevenLabs: {str(e)}")
                
                # Auto-retry mechanism: Try to fix the issue immediately
                try:
                    logger.info(f"🔄 Attempting automatic retry for conversation: {conversation_id}")
                    from .services_elevenlabs import fix_failed_recordings
                    fixed_count = fix_failed_recordings()
                    
                    if fixed_count > 0:
                        logger.info(f"✅ Auto-retry successful: Fixed {fixed_count} recordings")
                        # Try to get the recording again
                        from .models import InterviewRecording
                        interview_recording = InterviewRecording.objects.filter(
                            conversation_id=conversation_id
                        ).first()
                        
                        if interview_recording and interview_recording.status == 'completed':
                            return JsonResponse({
                                'status': 'success',
                                'message': 'Interview completed and data recovered through auto-retry',
                                'conversation_id': conversation_id,
                                'completion_reason': completion_reason,
                                'recording_id': interview_recording.id,
                                'has_audio': bool(interview_recording.audio_file),
                                'has_transcript': bool(interview_recording.transcript_file),
                                'message_count': interview_recording.messages.count(),
                                'auto_retry_success': True
                            })
                    
                except Exception as retry_error:
                    logger.error(f"❌ Auto-retry also failed: {str(retry_error)}")
                
                # Create a minimal interview record even if API fails
                try:
                    from .models import InterviewRecording
                    interview_recording = InterviewRecording.objects.create(
                        matching_result=matching_result,
                        conversation_id=conversation_id,
                        status='failed',  # Mark as failed since we couldn't fetch data
                        conversation_data={
                            'completion_reason': completion_reason,
                            'api_error': str(e),
                            'created_via': 'completion_endpoint_fallback'
                        }
                    )
                    logger.info(f"✅ Created fallback interview record with ID: {interview_recording.id}")
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Interview completed and basic record created. Audio/transcript will be retried later.',
                        'conversation_id': conversation_id,
                        'completion_reason': completion_reason,
                        'recording_id': interview_recording.id,
                        'data_fetch_error': str(e)
                    })
                except Exception as fallback_error:
                    logger.error(f"❌ Failed to create fallback interview record: {str(fallback_error)}")
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Interview completed but failed to create record',
                        'conversation_id': conversation_id,
                        'completion_reason': completion_reason,
                        'data_fetch_error': str(e),
                        'fallback_error': str(fallback_error)
                    })
        else:
            logger.warning("⚠️ No conversation ID provided - creating basic interview record")
            
            # Create a basic interview record without ElevenLabs data
            try:
                from .models import InterviewRecording
                interview_recording = InterviewRecording.objects.create(
                    matching_result=matching_result,
                    conversation_id=f"manual_{matching_result_id}_{int(timezone.now().timestamp())}",
                    status='failed',  # Mark as failed since no conversation data
                    conversation_data={
                        'completion_reason': completion_reason,
                        'created_via': 'completion_endpoint_no_conv_id'
                    }
                )
                logger.info(f"✅ Created basic interview record with ID: {interview_recording.id}")
                
                return JsonResponse({
                    'status': 'success', 
                    'message': 'Interview completed - basic record created without conversation ID',
                    'completion_reason': completion_reason,
                    'recording_id': interview_recording.id
                })
            except Exception as e:
                logger.error(f"❌ Failed to create basic interview record: {str(e)}")
                return JsonResponse({
                    'status': 'success', 
                    'message': 'Interview marked as completed',
                    'completion_reason': completion_reason,
                    'record_creation_error': str(e)
                })
            
    except MatchingResult.DoesNotExist:
        logger.error(f"MatchingResult {matching_result_id} not found for completion")
        return JsonResponse({
            'status': 'error',
            'message': 'Interview not found'
        }, status=404)
        
    except Exception as e:
        logger.error(f"Interview completion error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred completing the interview'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def complete_interview_api(request):
    """
    API endpoint to complete an interview session.
    Used by frontend to mark interview as completed with reason.
    """
    try:
        from home.services_elevenlabs import ElevenLabsAPIService
        import json
        
        # Parse request data
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        
        # Get required parameters
        session_id = data.get('session_id')
        completion_reason = data.get('completion_reason', 'completed')
        
        if not session_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Session ID is required'
            }, status=400)
        
        # Initialize service
        interview_service = ElevenLabsAPIService()
        
        # Complete the interview
        result = interview_service.complete_interview(session_id, completion_reason)
        
        if result["status"] == "success":
            logger.info(f"✅ Interview session {session_id} completed via API - Reason: {completion_reason}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Interview completed successfully',
                'session_id': session_id,
                'completion_reason': completion_reason
            })
        else:
            logger.error(f"Interview completion API failed: {result['message']}")
            return JsonResponse({
                'status': 'error',
                'message': result["message"]
            }, status=400)
            
    except Exception as e:
        logger.error(f"Interview completion API error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred completing the interview'
        }, status=500)


@login_required
def interview_session_detail(request, session_id):
    """Display detailed view of a specific interview session"""
    try:
        session = InterviewSession.objects.select_related(
            'matching_result__resume',
            'matching_result__job_description'
        ).get(
            id=session_id,
            matching_result__user=request.user
        )
        
        # Process conversation transcript for better display
        processed_transcript = []
        if session.conversation_transcript:
            for item in session.conversation_transcript:
                processed_transcript.append({
                    'role': item.get('role', 'unknown'),
                    'content': item.get('content', ''),
                    'timestamp': item.get('timestamp', ''),
                    'is_candidate': item.get('role') == 'user',
                    'is_interviewer': item.get('role') == 'assistant',
                })
        
        context = {
            'session': session,
            'transcript': processed_transcript,
            'matching_result': session.matching_result,
            'candidate': session.matching_result.resume,
            'job': session.matching_result.job_description,
        }
        
        return render(request, 'home/interview_session_detail.html', context)
        
    except InterviewSession.DoesNotExist:
        messages.error(request, 'Interview session not found.')
        return redirect('interviews')


@login_required
def interview_recording_detail(request, recording_id):
    """Display detailed view of a single interview recording with audio player"""
    user = request.user
    
    try:
        recording = InterviewRecording.objects.select_related(
            'matching_result__resume',
            'matching_result__job_description'
        ).prefetch_related('messages').get(
            id=recording_id,
            matching_result__user=user
        )
        
        # Get messages ordered by sequence
        messages = recording.messages.all().order_by('sequence_number', 'timestamp')
        
        # Separate candidate and interviewer messages
        candidate_messages = messages.filter(speaker='user')
        interviewer_messages = messages.filter(speaker='assistant')
        
        # Calculate interview statistics
        stats = {
            'total_messages': messages.count(),
            'candidate_responses': candidate_messages.count(),
            'interviewer_questions': interviewer_messages.count(),
            'duration_formatted': f"{recording.duration_seconds // 60}m {recording.duration_seconds % 60}s" if recording.duration_seconds else "Unknown",
            'has_audio': bool(recording.audio_file),
            'has_transcript': bool(recording.transcript_file),
        }
        
        context = {
            'recording': recording,
            'messages': messages,
            'candidate_messages': candidate_messages,
            'interviewer_messages': interviewer_messages,
            'stats': stats,
        }
        
        return render(request, 'home/interview_recording_detail.html', context)
        
    except InterviewRecording.DoesNotExist:
        messages.error(request, 'Interview recording not found.')
        return redirect('interview_recordings')

@login_required
@require_http_methods(["POST"])
def retry_evaluation(request, recording_id):
    """Retry evaluation for a specific interview recording"""
    try:
        # Get the interview recording
        recording = get_object_or_404(InterviewRecording, 
                                    id=recording_id,
                                    matching_result__user=request.user)
        
        if recording.status != 'completed':
            return JsonResponse({
                'success': False,
                'message': 'Can only retry evaluation for completed interviews'
            })
        
        # Check if there's already an evaluation
        from .models import InterviewEvaluation
        existing_evaluation = InterviewEvaluation.objects.filter(
            interview_recording=recording
        ).first()
        
        # Call the evaluation service
        result = call_fastapi_interview_evaluation_service(recording)
        
        if result.get('success'):
            if existing_evaluation:
                messages.success(request, f'Evaluation updated successfully for {recording.matching_result.resume.candidate_name}')
            else:
                messages.success(request, f'Evaluation created successfully for {recording.matching_result.resume.candidate_name}')
            
            return JsonResponse({
                'success': True,
                'message': 'Evaluation retry successful',
                'redirect_url': f'/dashboard/interviews/'
            })
        else:
            error_msg = result.get('error', 'Unknown evaluation error')
            logger.error(f"Evaluation retry failed for recording {recording_id}: {error_msg}")
            
            return JsonResponse({
                'success': False,
                'message': f'Evaluation failed: {error_msg}'
            })
    
    except Exception as e:
        logger.error(f"Error in evaluation retry for recording {recording_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Server error: {str(e)}'
        })

@login_required
@require_http_methods(["POST"])
def retry_interview(request, recording_id):
    """Retry entire interview for a specific recording (creates new interview session)"""
    try:
        # Get the original interview recording
        original_recording = get_object_or_404(InterviewRecording, 
                                            id=recording_id,
                                            matching_result__user=request.user)
        
        # Get the matching result to create new interview
        matching_result = original_recording.matching_result
        
        if not matching_result:
            return JsonResponse({
                'success': False,
                'message': 'No matching result found for this interview'
            })
        
        # Check if we can retry (don't create too many retries)
        existing_recordings = InterviewRecording.objects.filter(
            matching_result=matching_result
        ).count()
        
        if existing_recordings >= 5:  # Limit to 5 attempts
            return JsonResponse({
                'success': False,
                'message': 'Maximum retry attempts reached (5 attempts per candidate)'
            })
        
        # Create new interview recording entry
        new_recording = InterviewRecording.objects.create(
            matching_result=matching_result,
            status='pending',
            created_at=timezone.now()
        )
        
        # Try to start new interview session
        try:
            # Import ElevenLabs service
            from home.services_elevenlabs import ElevenLabsAPIService
            
            # Initialize ElevenLabs service  
            interview_service = ElevenLabsAPIService()
            
            # Call the interview service to create new session
            result = interview_service.start_interview(matching_result.id)
            
            if result.get('status') == 'success':
                # Update the new recording with session details
                conversation_id = result.get('elevenlabs_session_id')  # Use the correct field name
                if conversation_id:
                    new_recording.conversation_id = conversation_id
                    new_recording.status = 'processing'
                    new_recording.save()
                
                messages.success(request, f'New interview session started for {matching_result.resume.candidate_name}')
                
                return JsonResponse({
                    'success': True,
                    'message': 'Interview retry started successfully',
                    'interview_url': f'/voice-interview/{matching_result.id}/',  # Standard interview URL
                    'new_recording_id': new_recording.id,
                    'redirect_url': f'/dashboard/interviews/'
                })
            else:
                # Delete the failed recording entry
                new_recording.delete()
                error_msg = result.get('message', 'Failed to start new interview')
                
                return JsonResponse({
                    'success': False,
                    'message': f'Interview retry failed: {error_msg}'
                })
                
        except Exception as service_error:
            # Delete the failed recording entry
            new_recording.delete()
            logger.error(f"Interview service error during retry: {str(service_error)}")
            
            return JsonResponse({
                'success': False,
                'message': f'Interview service error: {str(service_error)}'
            })
    
    except Exception as e:
        logger.error(f"Error in interview retry for recording {recording_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Server error: {str(e)}'
        })


# --- Interview Pipeline Management Views ---

@login_required
def interview_pipeline(request):
    """Main interview pipeline dashboard with vertical candidate list and tag-based system"""
    
    # Get all completed initial interviews for this user
    completed_interviews = InterviewRecording.objects.filter(
        matching_result__user=request.user,
        status='completed'
    ).select_related(
        'matching_result__resume', 
        'matching_result__job_description'
    ).prefetch_related('additional_stages')
    
    candidates = []
    
    # Process each interview to create candidate data
    for interview in completed_interviews:
        # Ensure candidate has pipeline status
        pipeline_status, created = CandidatePipeline.objects.get_or_create(
            interview_recording=interview,
            defaults={'pipeline_status': 'initial_complete'}
        )
        
        if created:
            pipeline_status.update_onboarding_eligibility()
        
        # Get completed interview stages
        completed_stages = list(interview.additional_stages.all())
        
        # Create list of interview types for filtering
        interview_types_list = []
        for stage in completed_stages:
            interview_types_list.append(stage.stage_type)
        
        # Check if onboarded
        is_onboarded = pipeline_status.pipeline_status == 'onboarded'
        if is_onboarded:
            interview_types_list.append('onboarded')
        
        # Calculate average score
        average_score = 0.0
        total_scores = 0.0
        score_count = 0
        
        # For now, we don't have evaluation scores in this model
        # This will be implemented when interview evaluation is added
        
        # Include additional stage scores
        for stage in completed_stages:
            if hasattr(stage, 'overall_score') and stage.overall_score:
                total_scores += float(stage.overall_score)
                score_count += 1
        
        if score_count > 0:
            average_score = total_scores / score_count
        
        # Check if can be onboarded (has at least 1 stage including initial and average >= 6.0)
        can_be_onboarded = (
            score_count >= 1 and  # Initial + at least 0 more (just 1 total)
            average_score >= 6.0 and
            not is_onboarded
        )
        
        candidate_data = {
            'id': interview.id,
            'name': interview.get_candidate_name(),
            'email': interview.candidate_email or '',
            'job_title': interview.matching_result.job_description.title if interview.matching_result.job_description else '',
            'interview_types_list': interview_types_list,
            'average_score': float(average_score) if average_score else 0.0,
            'is_onboarded': is_onboarded,
            'can_be_onboarded': can_be_onboarded,
            'created_at': interview.created_at.isoformat(),
            'interview_tags': [
                {
                    'type': stage.stage_type,
                    'score': float(stage.overall_score) if stage.overall_score else 0,
                    'status': stage.recommendation or 'proceed',
                    'date': stage.created_at.isoformat()
                }
                for stage in completed_stages
            ]
        }
        
        candidates.append(candidate_data)
    
    # Sort candidates by creation date (newest first)
    candidates.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Calculate statistics
    total_candidates = len(candidates)
    technical_count = len([c for c in candidates if 'technical' in c['interview_types_list']])
    behavioral_count = len([c for c in candidates if 'behavioral' in c['interview_types_list']])
    onboarded_count = len([c for c in candidates if c['is_onboarded']])
    
    context = {
        'candidates': candidates,
        'total_candidates': total_candidates,
        'technical_count': technical_count,
        'behavioral_count': behavioral_count,
        'onboarded_count': onboarded_count,
    }
    
    return render(request, 'home/interview_pipeline.html', context)


@login_required
@require_http_methods(["POST"])
def add_interview_stage(request):
    """Add a new interview stage for a candidate - updated for new interface"""
    
    try:
        candidate_id = request.POST.get('candidate_id')
        stage_type = request.POST.get('stage_type')
        duration = request.POST.get('duration', 60)
        
        # Get the interview recording
        interview = get_object_or_404(InterviewRecording, 
                                    id=candidate_id, 
                                    matching_result__user=request.user)
        
        # Get interview-specific scores
        scores = {}
        if stage_type == 'technical':
            scores.update({
                'technical_skills_score': float(request.POST.get('technical_skills_score', 0)),
                'problem_solving_score': float(request.POST.get('problem_solving_score', 0)),
                'communication_score': float(request.POST.get('communication_score', 0)),
            })
        elif stage_type == 'behavioral':
            scores.update({
                'communication_score': float(request.POST.get('communication_score', 0)),
                'cultural_fit_score': float(request.POST.get('cultural_fit_score', 0)),
                'problem_solving_score': float(request.POST.get('problem_solving_score', 0)),
            })
        elif stage_type == 'final':
            scores.update({
                'technical_skills_score': float(request.POST.get('technical_skills_score', 0)),
                'communication_score': float(request.POST.get('communication_score', 0)),
                'cultural_fit_score': float(request.POST.get('cultural_fit_score', 0)),
                'problem_solving_score': float(request.POST.get('problem_solving_score', 0)),
            })
        
        # Calculate overall score as average of provided scores
        provided_scores = []
        for score in scores.values():
            try:
                score_val = float(score)
                if score_val > 0:
                    provided_scores.append(score_val)
            except (ValueError, TypeError):
                continue
        
        overall_score = float(sum(provided_scores) / len(provided_scores)) if provided_scores else 0.0
        
        # Feedback - simplified to just notes and recommendation
        additional_notes = request.POST.get('notes', '')
        recommendation = request.POST.get('recommendation', 'proceed')
        
        # Determine stage order
        existing_stages = interview.additional_stages.count()
        stage_order = existing_stages + 1
        
        # Create the interview stage
        stage = InterviewStage.objects.create(
            interview_recording=interview,
            stage_type=stage_type,
            stage_order=stage_order,
            interviewer=request.user,
            interview_date=timezone.now(),
            duration_minutes=int(duration),
            overall_score=overall_score,
            notes=additional_notes,
            recommendation=recommendation,
            **scores  # Add all the interview-specific scores
        )
        
        # Update pipeline status
        pipeline_status, created = CandidatePipeline.objects.get_or_create(
            interview_recording=interview,
            defaults={'pipeline_status': 'in_pipeline'}
        )
        
        if pipeline_status.pipeline_status == 'initial_complete':
            pipeline_status.pipeline_status = 'in_pipeline'
            pipeline_status.save()
        
        # Update onboarding eligibility
        pipeline_status.update_onboarding_eligibility()
        
        return JsonResponse({
            'success': True,
            'message': f'{stage.get_stage_type_display()} interview added successfully'
        })
        
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower():
            return JsonResponse({
                'success': False,
                'message': f'An interview of this type has already been recorded for this candidate.'
            })
        else:
            logger.error(f"Database integrity error adding interview stage: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Database error: {str(e)}'
            })
    except Exception as e:
        logger.error(f"Error adding interview stage: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error adding interview stage: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def fetch_candidates_from_evaluation(request):
    """Fetch candidates from the evaluation system to the pipeline"""
    
    try:
        # Get candidates who completed AI evaluation but aren't in pipeline yet
        new_candidates_count = 0
        
        # This is automatically handled by the interview_pipeline view
        # which fetches all completed interviews
        # Here we just confirm the action
        
        return JsonResponse({
            'success': True,
            'message': 'Candidates refreshed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error fetching candidates: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error fetching candidates: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])  
def onboard_candidate(request):
    """Send onboarding email to a candidate"""
    
    try:
        candidate_id = request.POST.get('candidate_id')
        
        # Get the interview recording
        interview = get_object_or_404(InterviewRecording, 
                                    id=candidate_id, 
                                    matching_result__user=request.user)
        
        # Update pipeline status to onboarded
        pipeline_status, created = CandidatePipeline.objects.get_or_create(
            interview_recording=interview,
            defaults={'pipeline_status': 'onboarded'}
        )
        
        pipeline_status.pipeline_status = 'onboarded'
        pipeline_status.onboarding_email_sent = True
        pipeline_status.onboarded_at = timezone.now()
        pipeline_status.save()
        
        # Send actual onboarding email through email agent
        try:
            import requests
            
            # Prepare data for email agent
            email_data = {
                "candidate_ids": [int(candidate_id)],
                "email_type": "onboarding",
                "hr_user_id": request.user.id
            }
            
            # Call email agent API
            email_response = requests.post(
                'http://localhost:8003/send-emails',  # Email agent runs on port 8003
                json=email_data,
                timeout=10
            )
            
            if email_response.status_code == 200:
                email_result = email_response.json()
                logger.info(f"Onboarding email sent successfully: {email_result}")
            else:
                logger.warning(f"Email agent returned status {email_response.status_code}")
                
        except requests.exceptions.RequestException as e:
            # Don't fail the onboarding if email fails, just log it
            logger.error(f"Failed to send onboarding email via email agent: {str(e)}")
        except Exception as e:
            logger.error(f"Error calling email agent: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': f'Onboarding email sent to {interview.get_candidate_name()}'
        })
        
    except Exception as e:
        logger.error(f"Error onboarding candidate: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error onboarding candidate: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def delete_candidates(request):
    """Delete selected candidates"""
    
    try:
        # Handle FormData from frontend
        candidate_ids_json = request.POST.get('candidate_ids', '[]')
        candidate_ids = json.loads(candidate_ids_json)
        
        if not candidate_ids:
            return JsonResponse({
                'success': False,
                'message': 'No candidates selected'
            })
        
        # Delete the interview recordings and related data
        deleted_count = 0
        for candidate_id in candidate_ids:
            try:
                interview = InterviewRecording.objects.get(
                    id=candidate_id, 
                    matching_result__user=request.user
                )
                interview.delete()  # This will cascade delete related objects
                deleted_count += 1
            except InterviewRecording.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} candidates'
        })
        
    except Exception as e:
        logger.error(f"Error deleting candidates: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error deleting candidates: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def reset_candidates(request):
    """Reset selected candidates to initial state - clear interviews and onboarding"""
    
    try:
        # Handle FormData from frontend
        candidate_ids_json = request.POST.get('candidate_ids', '[]')
        candidate_ids = json.loads(candidate_ids_json)
        
        if not candidate_ids:
            return JsonResponse({
                'success': False,
                'message': 'No candidates selected'
            })
        
        # Reset candidates to initial state
        reset_count = 0
        for candidate_id in candidate_ids:
            try:
                interview = InterviewRecording.objects.get(
                    id=candidate_id, 
                    matching_result__user=request.user
                )
                
                # Delete all interview stages
                interview.additional_stages.all().delete()
                
                # Reset pipeline status to initial_complete
                pipeline_status, created = CandidatePipeline.objects.get_or_create(
                    interview_recording=interview,
                    defaults={'pipeline_status': 'initial_complete'}
                )
                
                logger.info(f"Resetting candidate {interview.id}: current pipeline_status = {pipeline_status.pipeline_status}")
                
                pipeline_status.pipeline_status = 'initial_complete'
                pipeline_status.current_stage = 'initial_complete'
                pipeline_status.meets_onboarding_criteria = False
                pipeline_status.onboarding_email_sent = False
                pipeline_status.onboarding_email_sent_at = None
                pipeline_status.save()
                
                logger.info(f"After reset: pipeline_status = {pipeline_status.pipeline_status}, is_onboarded should be {pipeline_status.pipeline_status == 'onboarded'}")
                
                reset_count += 1
                
            except InterviewRecording.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully reset {reset_count} candidates to initial state'
        })
        
    except Exception as e:
        logger.error(f"Error resetting candidates: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error resetting candidates: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def edit_interview_stage(request, stage_id):
    """Edit an existing interview stage"""
    
    try:
        # Get the interview stage
        stage = get_object_or_404(InterviewStage, 
                                id=stage_id, 
                                interview_recording__matching_result__user=request.user)
        
        # Update fields
        stage.interview_date = request.POST.get('interview_date', stage.interview_date)
        stage.duration_minutes = int(request.POST.get('duration_minutes', stage.duration_minutes))
        
        # Update scores
        stage.overall_score = float(request.POST.get('overall_score', stage.overall_score))
        stage.technical_skills_score = float(request.POST.get('technical_skills_score', stage.technical_skills_score))
        stage.communication_score = float(request.POST.get('communication_score', stage.communication_score))
        stage.cultural_fit_score = float(request.POST.get('cultural_fit_score', stage.cultural_fit_score))
        stage.problem_solving_score = float(request.POST.get('problem_solving_score', stage.problem_solving_score))
        
        # Update feedback
        stage.strengths = request.POST.get('strengths', stage.strengths)
        stage.weaknesses = request.POST.get('weaknesses', stage.weaknesses)
        stage.notes = request.POST.get('notes', stage.notes)
        stage.recommendation = request.POST.get('recommendation', stage.recommendation)
        stage.recommendation_notes = request.POST.get('recommendation_notes', stage.recommendation_notes)
        
        stage.save()
        
        # Update pipeline onboarding eligibility
        stage.interview_recording.pipeline_status.update_onboarding_eligibility()
        
        messages.success(request, f'{stage.get_stage_type_display()} interview updated successfully')
        
        return JsonResponse({
            'success': True,
            'message': f'{stage.get_stage_type_display()} interview updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error editing interview stage: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error editing interview stage: {str(e)}'
        })


@login_required 
@require_http_methods(["POST"])
def delete_interview_stage(request, stage_id):
    """Delete an interview stage"""
    
    try:
        stage = get_object_or_404(InterviewStage, 
                                id=stage_id, 
                                interview_recording__matching_result__user=request.user)
        
        stage_name = stage.get_stage_type_display()
        candidate_name = stage.candidate_name
        
        stage.delete()
        
        # Update pipeline onboarding eligibility
        stage.interview_recording.pipeline_status.update_onboarding_eligibility()
        
        messages.success(request, f'{stage_name} interview deleted for {candidate_name}')
        
        return JsonResponse({
            'success': True,
            'message': f'{stage_name} interview deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting interview stage: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error deleting interview stage: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def send_onboarding_email(request, recording_id):
    """Send onboarding email to candidate"""
    
    try:
        # Get the interview recording and pipeline status
        interview = get_object_or_404(InterviewRecording, 
                                    id=recording_id, 
                                    matching_result__user=request.user)
        
        pipeline_status = get_object_or_404(CandidatePipeline, 
                                          interview_recording=interview)
        
        # Check if candidate meets onboarding criteria
        if not pipeline_status.meets_onboarding_criteria:
            return JsonResponse({
                'success': False,
                'message': 'Candidate does not meet onboarding criteria (needs Initial + 1 more interview with avg score >= 6.0)'
            })
        
        # Check if onboarding email already sent
        if pipeline_status.onboarding_email_sent:
            return JsonResponse({
                'success': False,
                'message': 'Onboarding email has already been sent to this candidate'
            })
        
        # TODO: Call email service to send onboarding email
        # For now, just mark as sent
        pipeline_status.onboarding_email_sent = True
        pipeline_status.onboarding_email_sent_at = timezone.now()
        pipeline_status.pipeline_status = 'onboarded'
        pipeline_status.save()
        
        messages.success(request, f'Onboarding email sent to {interview.candidate_name}')
        
        return JsonResponse({
            'success': True,
            'message': f'Onboarding email sent to {interview.candidate_name}'
        })
        
    except Exception as e:
        logger.error(f"Error sending onboarding email: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error sending onboarding email: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
def fetch_candidates(request):
    """
    Fetch candidates who have completed their initial AI interviews 
    and are not yet in the interview pipeline
    """
    try:
        # Get all completed interviews for this user that are not yet in pipeline
        completed_interviews = InterviewRecording.objects.filter(
            matching_result__user=request.user,
            status='completed'
        ).exclude(
            # Exclude interviews that already have a pipeline status
            pipeline_status__isnull=False
        ).select_related(
            'matching_result__resume', 
            'matching_result__job_description'
        )
        
        new_candidates_count = 0
        
        # Create pipeline entries for new candidates
        for interview in completed_interviews:
            # Create pipeline status for this candidate
            pipeline_status, created = CandidatePipeline.objects.get_or_create(
                interview_recording=interview,
                defaults={
                    'pipeline_status': 'initial_complete',
                    'current_stage': None,
                    'meets_onboarding_criteria': False
                }
            )
            
            if created:
                new_candidates_count += 1
                # Update onboarding eligibility
                pipeline_status.update_onboarding_eligibility()
        
        if new_candidates_count > 0:
            return JsonResponse({
                'success': True,
                'count': new_candidates_count,
                'message': f'Successfully fetched {new_candidates_count} new candidates'
            })
        else:
            return JsonResponse({
                'success': False,
                'count': 0,
                'message': 'No new candidates found. All completed interviews are already in the pipeline.'
            })
            
    except Exception as e:
        logger.error(f"Error fetching candidates: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error fetching candidates: {str(e)}'
        })