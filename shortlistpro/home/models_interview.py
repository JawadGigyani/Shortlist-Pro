"""
Interview Recording Models for storing ElevenLabs conversation data
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class InterviewRecording(models.Model):
    """Store interview audio recordings and transcripts"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Link to existing MatchingResult
    matching_result = models.OneToOneField(
        'MatchingResult', 
        on_delete=models.CASCADE, 
        related_name='interview_recording'
    )
    
    # ElevenLabs data
    elevenlabs_conversation_id = models.CharField(max_length=255, unique=True)
    elevenlabs_agent_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Audio file
    audio_file = models.FileField(upload_to='interview_recordings/', blank=True, null=True)
    audio_url = models.URLField(blank=True, null=True)  # ElevenLabs audio URL
    audio_duration_seconds = models.IntegerField(default=0)
    
    # Transcript
    transcript = models.TextField(blank=True, null=True)
    
    # Metadata
    interview_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # ElevenLabs conversation metadata
    conversation_status = models.CharField(max_length=50, blank=True, null=True)  # done, processing, etc.
    start_time_unix_secs = models.BigIntegerField(blank=True, null=True)
    has_audio = models.BooleanField(default=False)
    has_user_audio = models.BooleanField(default=False)
    has_response_audio = models.BooleanField(default=False)
    
    # Analysis (we can add AI analysis later)
    ai_summary = models.TextField(blank=True, null=True)
    conversation_analysis = models.JSONField(default=dict, blank=True)
    dynamic_variables_used = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        candidate_name = getattr(self.matching_result.resume, 'candidate_name', 'Unknown')
        return f"Interview Recording - {candidate_name} ({self.status})"
    
    @property
    def candidate_name(self):
        return getattr(self.matching_result.resume, 'candidate_name', 'Unknown')
    
    @property
    def position_title(self):
        return getattr(self.matching_result.job_description, 'title', 'Unknown Position')
    
    @property
    def duration_formatted(self):
        """Return duration in MM:SS format"""
        if self.audio_duration_seconds:
            minutes = self.audio_duration_seconds // 60
            seconds = self.audio_duration_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "00:00"
    
    class Meta:
        ordering = ['-interview_date']

class InterviewMessage(models.Model):
    """Store individual messages from the interview conversation"""
    
    SPEAKER_CHOICES = [
        ('interviewer', 'AI Interviewer'),
        ('candidate', 'Candidate'),
    ]
    
    interview_recording = models.ForeignKey(
        InterviewRecording, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    
    speaker = models.CharField(max_length=20, choices=SPEAKER_CHOICES)
    message = models.TextField()
    time_in_call_secs = models.IntegerField(default=0)  # When in the call this message occurred
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Additional ElevenLabs data
    role = models.CharField(max_length=20, blank=True, null=True)  # 'user' or 'agent' from API
    has_tool_calls = models.BooleanField(default=False)
    message_metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['time_in_call_secs', 'timestamp']
    
    def __str__(self):
        return f"{self.speaker}: {self.message[:50]}..."