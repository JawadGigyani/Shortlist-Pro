from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    company_name = models.CharField(max_length=255, default='')
    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"


# --- Dashboard Data Models ---
class JobDescription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.title} ({self.department})"
class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    jobdescription = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name='resumes', null=True, blank=True)
    
    # Basic Info (flattened for easy access)
    candidate_name = models.CharField(max_length=255, default='Unknown Candidate')
    email = models.EmailField(default='no-email@example.com')
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    github_url = models.URLField(blank=True, null=True)
    portfolio_url = models.URLField(blank=True, null=True)
    
    # Professional Summary
    professional_summary = models.TextField(blank=True, null=True)
    career_level = models.CharField(max_length=50, default='Entry-level')
    years_of_experience = models.IntegerField(default=0)
    
    # Structured Data (JSON Fields)
    skills = models.JSONField(blank=True, null=True, default=list)  # List of strings
    work_experience = models.JSONField(blank=True, null=True, default=list)  # List of work entries
    education = models.JSONField(blank=True, null=True, default=list)  # List of education entries
    projects = models.JSONField(blank=True, null=True, default=list)  # List of project entries
    certifications = models.JSONField(blank=True, null=True, default=list)  # List of certification entries
    extracurricular = models.JSONField(blank=True, null=True, default=list)  # List of extracurricular activities
    
    # Additional Info
    availability = models.CharField(max_length=100, blank=True, null=True)
    willing_to_relocate = models.CharField(max_length=20, blank=True, null=True)
    salary_expectations = models.CharField(max_length=100, blank=True, null=True)
    preferred_work_mode = models.CharField(max_length=20, blank=True, null=True)
    
    # File and metadata
    resume_file = models.FileField(upload_to='resumes/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensure that each user can only have one resume per email address per job description
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'email', 'jobdescription'], 
                name='unique_user_email_jd_resume',
                condition=~models.Q(email='no-email@example.com')  # Exclude default email from uniqueness
            )
        ]
    
    def __str__(self):
        return f"{self.candidate_name} - Resume ({self.user.username})"

class Shortlisted(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    # Add more fields as needed
    def __str__(self):
        return f"Shortlisted ({self.resume.user.username})"

class Interview(models.Model):
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed')], default='pending')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    # Add more fields as needed
    def __str__(self):
        return f"Interview ({self.resume.user.username}) - {self.status}"


class MatchingResult(models.Model):
    """Model to store AI matching results between resumes and job descriptions"""
    
    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
    ]
    
    # Email status choices
    EMAIL_STATUS_CHOICES = [
        ('not_sent', 'Not Sent'),
        ('selection_sent', 'Selection Email Sent'),
        ('rejection_sent', 'Rejection Email Sent'),
    ]
    
    # Core relationships
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='matching_results')
    job_description = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name='matching_results')
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # For easy filtering
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    email_status = models.CharField(max_length=20, choices=EMAIL_STATUS_CHOICES, default='not_sent')
    
    # Matching scores (0-100)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    skills_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    experience_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    education_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Additional matching insights
    matched_skills = models.JSONField(default=list, blank=True)  # Skills that matched
    missing_skills = models.JSONField(default=list, blank=True)  # Skills required but missing
    experience_gap = models.CharField(max_length=255, blank=True, null=True)  # Experience analysis
    match_reasoning = models.TextField(blank=True, null=True)  # AI explanation
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Ensure unique matching result per resume-job combination
        unique_together = ['resume', 'job_description']
        ordering = ['-overall_score', '-created_at']  # Show best matches first
        indexes = [
            models.Index(fields=['user', '-overall_score']),
            models.Index(fields=['job_description', '-overall_score']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.resume.candidate_name} → {self.job_description.title} ({self.overall_score}%)"
    
    @property
    def confidence_level(self):
        """Return confidence level based on overall score"""
        if self.overall_score >= 70:
            return 'High'
        elif self.overall_score >= 50:
            return 'Medium'
        else:
            return 'Low'
    
    @property
    def match_category(self):
        """Categorize match quality for simplified screening"""
        if self.overall_score >= 60:
            return 'Interview'
        elif self.overall_score >= 40:
            return 'Maybe'
        else:
            return 'Skip'
    
    @property
    def has_interview_questions(self):
        """Safely check if interview questions exist"""
        try:
            return self.interview_questions is not None
        except InterviewQuestions.DoesNotExist:
            return False
    
    @property
    def safe_interview_questions(self):
        """Safely get interview questions or None"""
        try:
            return self.interview_questions
        except InterviewQuestions.DoesNotExist:
            return None


class InterviewQuestions(models.Model):
    """Model to store AI-generated interview questions for shortlisted candidates"""
    
    # Core relationship
    matching_result = models.OneToOneField(MatchingResult, on_delete=models.CASCADE, related_name='interview_questions')
    
    # Questions data (stored as JSON)
    questions = models.JSONField(help_text="List of interview questions with categories and purposes")
    
    # Question metadata
    total_questions = models.IntegerField(help_text="Total number of questions generated")
    estimated_duration = models.CharField(max_length=20, help_text="Estimated interview duration")
    complexity_level = models.CharField(max_length=20, help_text="Interview complexity: junior, mid, senior")
    focus_areas = models.JSONField(blank=True, null=True, help_text="Key areas the interview focuses on")
    question_distribution = models.JSONField(blank=True, null=True, help_text="Number of questions per category")
    
    # Status tracking
    STATUS_CHOICES = [
        ('generated', 'Questions Generated'),
        ('reviewed', 'Reviewed by HR'),
        ('used', 'Used in Interview'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generated')
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Interview Questions"
        verbose_name_plural = "Interview Questions"
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"Interview Questions for {self.matching_result.resume.candidate_name} - {self.matching_result.job_description.title}"
    
    @property
    def questions_by_category(self):
        """Group questions by category for easy display"""
        categorized = {
            'background_verification': [],
            'skill_validation': [],
            'gap_exploration': [],
            'motivation_fit': []
        }
        
        for question in self.questions:
            category = question.get('category', 'background_verification')
            if category in categorized:
                categorized[category].append(question)
        
        return categorized
    
    @property
    def high_priority_questions(self):
        """Get only high priority questions"""
        return [q for q in self.questions if q.get('priority') == 'high']


class InterviewSession(models.Model):
    """Model to store voice interview session data and transcripts"""
    
    # Status choices
    STATUS_CHOICES = [
        ('ready', 'Ready'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('partial', 'Partially Completed'),
        ('failed', 'Failed'),
    ]
    
    # Core relationship
    matching_result = models.ForeignKey(MatchingResult, on_delete=models.CASCADE, related_name='interview_sessions')
    
    # Session metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    completion_reason = models.CharField(max_length=100, blank=True, null=True, help_text="Reason for interview completion (completed, user_ended, timeout, etc.)")
    duration_seconds = models.IntegerField(default=0, help_text="Total interview duration in seconds")
    questions_asked = models.IntegerField(default=0, help_text="Number of questions asked")
    total_questions_planned = models.IntegerField(default=0, help_text="Total questions that were planned")
    
    # Interview data
    conversation_transcript = models.JSONField(help_text="Complete conversation between AI and candidate")
    interview_summary = models.TextField(blank=True, null=True, help_text="AI-generated summary of the interview")
    
    # Technical metadata
    session_id = models.CharField(max_length=100, blank=True, null=True, help_text="WebSocket session identifier")
    elevenlabs_session_id = models.CharField(max_length=255, blank=True, null=True, help_text="ElevenLabs session identifier")
    candidate_audio_quality = models.CharField(max_length=20, blank=True, null=True, help_text="Audio quality assessment")
    technical_issues = models.JSONField(default=list, blank=True, help_text="Any technical issues encountered")
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Interview Session"
        verbose_name_plural = "Interview Sessions"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['matching_result', '-started_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Interview Session: {self.matching_result.resume.candidate_name} - {self.status}"
    
    @property
    def duration_formatted(self):
        """Return formatted duration string"""
        if self.duration_seconds:
            minutes = self.duration_seconds // 60
            seconds = self.duration_seconds % 60
            return f"{minutes}m {seconds}s"
        return "0m 0s"
    
    @property
    def completion_percentage(self):
        """Calculate interview completion percentage"""
        if self.total_questions_planned > 0:
            return round((self.questions_asked / self.total_questions_planned) * 100, 1)
        return 0
    
    @property
    def candidate_responses(self):
        """Extract only candidate responses from transcript"""
        if not self.conversation_transcript:
            return []
        return [msg for msg in self.conversation_transcript if msg.get('role') == 'user']
    
    @property
    def interviewer_questions(self):
        """Extract only interviewer questions from transcript"""
        if not self.conversation_transcript:
            return []
        return [msg for msg in self.conversation_transcript if msg.get('role') == 'assistant']


# --- Voice Interview Models ---
class InterviewRecording(models.Model):
    """Model to store interview recordings and transcripts from ElevenLabs"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    ]
    
    # Core relationships
    matching_result = models.OneToOneField(
        MatchingResult, 
        on_delete=models.CASCADE, 
        related_name='interview_recording',
        null=True, blank=True
    )
    
    # ElevenLabs conversation data
    conversation_id = models.CharField(max_length=255, unique=True)
    
    # File storage
    audio_file = models.FileField(upload_to='interview_audio/', blank=True, null=True)
    transcript_file = models.FileField(upload_to='interview_transcripts/', blank=True, null=True)
    
    # Conversation metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    duration_seconds = models.IntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    # Raw data from ElevenLabs
    conversation_data = models.JSONField(blank=True, null=True)  # Full API response
    
    # Processed analysis
    key_points = models.JSONField(blank=True, null=True, default=list)
    analysis_summary = models.TextField(blank=True, null=True)
    
    # System timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        candidate_name = "Unknown"
        if self.matching_result and self.matching_result.resume:
            candidate_name = self.matching_result.resume.candidate_name
        return f"Interview: {candidate_name} ({self.conversation_id[:8]})"
    
    @property
    def candidate_name(self):
        """Get candidate name from related matching result"""
        if self.matching_result and self.matching_result.resume:
            return self.matching_result.resume.candidate_name
        return "Unknown Candidate"
    
    @property
    def job_title(self):
        """Get job title from related matching result"""
        if self.matching_result and self.matching_result.job_description:
            return self.matching_result.job_description.title
        return "Unknown Position"


class InterviewMessage(models.Model):
    """Model to store individual messages from interview conversation"""
    
    SPEAKER_CHOICES = [
        ('user', 'Candidate'),
        ('assistant', 'Interviewer'),
        ('system', 'System'),
    ]
    
    # Core relationships
    interview_recording = models.ForeignKey(
        InterviewRecording, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    
    # Message data
    speaker = models.CharField(max_length=20, choices=SPEAKER_CHOICES)
    message_content = models.TextField()
    timestamp = models.DateTimeField()
    sequence_number = models.IntegerField(default=0)
    
    # Metadata
    duration_ms = models.IntegerField(null=True, blank=True)  # Message duration in milliseconds
    confidence_score = models.FloatField(null=True, blank=True)  # Transcription confidence
    
    # Raw message data from ElevenLabs
    raw_message_data = models.JSONField(blank=True, null=True)
    
    class Meta:
        ordering = ['sequence_number', 'timestamp']
        indexes = [
            models.Index(fields=['interview_recording', 'sequence_number']),
            models.Index(fields=['speaker']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_speaker_display()}: {self.message_content[:50]}..."
