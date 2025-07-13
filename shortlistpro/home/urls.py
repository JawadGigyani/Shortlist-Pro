from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='home'),
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('dashboard/jobs/', views.job_descriptions, name='job_descriptions'),
    path('dashboard/resumes/', views.resumes, name='resumes'),
    path('dashboard/matching/', views.matching, name='matching'),
    path('dashboard/shortlisted/', views.shortlisted, name='shortlisted'),
    path('dashboard/emails/', views.emails, name='emails'),
    path('dashboard/interviews/', views.interviews, name='interviews'),
    path('dashboard/reports/', views.reports, name='reports'),
    path('dashboard/settings/', views.settings_view, name='settings'),
    # path('register/', views.register, name='register'),
    # path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
]
