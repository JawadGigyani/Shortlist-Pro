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
