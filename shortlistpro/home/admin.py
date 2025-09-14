# home/admin.py
from django.contrib import admin
from .models import Profile, JobDescription, Resume, MatchingResult, Shortlisted, Interview, InterviewQuestions

# Basic registrations for simple models
admin.site.register(Profile)
admin.site.register(Shortlisted)
admin.site.register(Interview)

# Simple registrations for models managed primarily through frontend
admin.site.register(JobDescription)
admin.site.register(Resume)
admin.site.register(MatchingResult)

# Custom admin only for the AI-generated content that needs monitoring
@admin.register(InterviewQuestions)
class InterviewQuestionsAdmin(admin.ModelAdmin):
    list_display = ['matching_result', 'total_questions', 'complexity_level', 'status', 'generated_at']
    list_filter = ['status', 'complexity_level', 'generated_at']
    search_fields = ['matching_result__resume__candidate_name', 'matching_result__job_description__title']
    readonly_fields = ['generated_at', 'updated_at', 'questions', 'question_distribution', 'focus_areas']
    
    # Keep fieldsets for better organization of the complex data
    fieldsets = (
        ('Basic Information', {
            'fields': ('matching_result', 'status')
        }),
        ('Generated Content', {
            'fields': ('questions', 'total_questions', 'question_distribution', 'focus_areas')
        }),
        ('Metadata', {
            'fields': ('estimated_duration', 'complexity_level')
        }),
        ('Timestamps', {
            'fields': ('generated_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
