from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('contact/', views.contact, name='contact'),
    path('documentation/', views.documentation, name='documentation'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('dashboard/jobs/', views.job_descriptions, name='job_descriptions'),
    path('dashboard/resumes/', views.resumes, name='resumes'),
    path('dashboard/matching/', views.matching, name='matching'),
    path('dashboard/shortlisted/', views.shortlisted, name='shortlisted'),
    path('dashboard/shortlist-candidate/', views.shortlist_candidate, name='shortlist_candidate'),
    path('dashboard/reject-candidate/', views.reject_candidate, name='reject_candidate'),
    path('dashboard/delete-matching-result/', views.delete_matching_result, name='delete_matching_result'),
    path('dashboard/emails/', views.emails, name='emails'),
    # Unified Interview Dashboard (replaces old interviews/ and interview-recordings/)
    path('dashboard/interviews/', views.interview_dashboard, name='interviews'),
    path('dashboard/interviews/delete/', views.delete_interviews, name='delete_interviews'),
    path('dashboard/interviews/retry-evaluation/<int:recording_id>/', views.retry_evaluation, name='retry_evaluation'),
    path('dashboard/interviews/retry-interview/<int:recording_id>/', views.retry_interview, name='retry_interview'),
    
    # Interview Pipeline Management
    path('dashboard/interview-pipeline/', views.interview_pipeline, name='interview_pipeline'),
    path('dashboard/interview-pipeline/add-stage/', views.add_interview_stage, name='add_interview_stage'),
    path('dashboard/interview-pipeline/fetch-candidates/', views.fetch_candidates_from_evaluation, name='fetch_candidates_from_evaluation'),
    path('dashboard/interview-pipeline/fetch-new-candidates/', views.fetch_candidates, name='fetch_candidates'),
    path('dashboard/interview-pipeline/onboard-candidate/', views.onboard_candidate, name='onboard_candidate'),
    path('dashboard/interview-pipeline/delete-candidates/', views.delete_candidates, name='delete_candidates'),
    path('dashboard/interview-pipeline/reset-candidates/', views.reset_candidates, name='reset_candidates'),
    
    path('send-candidate-emails/', views.send_candidate_emails, name='send_candidate_emails'),
    path('get_profile_address/', views.get_profile_address, name='get_profile_address'),
    # Legacy evaluations page - replaced by unified dashboard
    # path('dashboard/interview-evaluations/', views.interview_evaluations, name='interview_evaluations'),
    path('dashboard/interview-evaluation/<int:evaluation_id>/', views.interview_evaluation_detail, name='interview_evaluation_detail'),
    path('dashboard/interview-session/<int:session_id>/', views.interview_session_detail, name='interview_session_detail'),
    path('dashboard/interview-recording/<int:recording_id>/', views.interview_recording_detail, name='interview_recording_detail'),
    path('dashboard/reports/', views.reports, name='reports'),
    path('dashboard/profile/', views.profile_view, name='profile'),
    # Candidate interview access (no authentication required) - HR + JD specific
    path('interview/<int:hr_user_id>/<int:jd_id>/', views.candidate_interview, name='candidate_interview'),
    # Voice interview page for candidates
    path('voice-interview/<int:matching_result_id>/', views.voice_interview, name='voice_interview'),
    # Interview completion endpoint for ElevenLabs
    path('voice-interview/<int:matching_result_id>/complete/', views.interview_completion, name='interview_completion'),
    # Debug view to check database status
    path('debug/check-status/<str:email>/', views.debug_check_status, name='debug_check_status'),
    # path('register/', views.register, name='register'),
    # path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
]
