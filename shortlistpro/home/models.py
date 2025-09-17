from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    company_name = models.CharField(max_length=255, default='')
    office_address = models.TextField(blank=True, null=True, help_text="Default office address for onsite interviews")
    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"


class EmailVerificationOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_otp')
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Email Verification OTP"
        verbose_name_plural = "Email Verification OTPs"
    
    def is_expired(self):
        """Check if OTP is expired (10 minutes)"""
        expiry_time = self.created_at + timedelta(minutes=10)
        return timezone.now() > expiry_time
    
    def can_attempt(self):
        """Check if user can still attempt verification (max 3 attempts)"""
        return self.attempts < 3
    
    def increment_attempts(self):
        """Increment failed attempts"""
        self.attempts += 1
        self.save()
    
    def verify_otp(self, otp_code):
        """Verify OTP code and return success/error message"""
        if self.is_expired():
            return False, "OTP has expired. Please request a new one."
        
        if not self.can_attempt():
            return False, "Too many failed attempts. Please request a new OTP."
        
        if self.otp_code == otp_code:
            self.is_verified = True
            self.user.is_active = True  # Activate the user account
            self.save()
            self.user.save()
            return True, "Email verified successfully!"
        else:
            self.increment_attempts()
            remaining = 3 - self.attempts
            return False, f"Invalid OTP code. {remaining} attempts remaining."
    
    def __str__(self):
        return f"OTP for {self.email} - {'Verified' if self.is_verified else 'Pending'}"


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
    
    EMAIL_TYPE_CHOICES = [
        ('selection', 'Selection'),
        ('rejection', 'Rejection'),
    ]
    
    INTERVIEW_ROUND_CHOICES = [
        ('initial', 'Initial Interview'),
        ('technical', 'Technical Interview'),
        ('behavioral', 'Behavioral Interview'),
        ('final', 'Final Interview'),
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
    
    # Email status tracking
    email_sent = models.BooleanField(default=False)
    email_type = models.CharField(max_length=20, choices=EMAIL_TYPE_CHOICES, blank=True, null=True)
    interview_round = models.CharField(max_length=20, choices=INTERVIEW_ROUND_CHOICES, blank=True, null=True)
    email_sent_at = models.DateTimeField(blank=True, null=True)
    
    # Interview scheduling fields
    interview_type = models.CharField(max_length=20, choices=[('onsite', 'Onsite'), ('online', 'Online')], blank=True, null=True)
    interview_date = models.DateTimeField(blank=True, null=True)
    interview_location = models.TextField(blank=True, null=True, help_text="Office address for onsite interviews")
    meeting_link = models.URLField(blank=True, null=True, help_text="Zoom meeting link for online interviews")
    meeting_id = models.CharField(max_length=255, blank=True, null=True, help_text="Zoom meeting ID")
    meeting_password = models.CharField(max_length=50, blank=True, null=True, help_text="Zoom meeting password")
    
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
    def candidate_email(self):
        """Get candidate email from related matching result"""
        if self.matching_result and self.matching_result.resume:
            return self.matching_result.resume.email
        return ""
    
    def get_candidate_name(self):
        """Method version of candidate_name property for compatibility"""
        return self.candidate_name
    
    def get_candidate_email(self):
        """Method version of candidate_email property for compatibility"""
        return self.candidate_email
    
    @property
    def job_title(self):
        """Get job title from related matching result"""
        if self.matching_result and self.matching_result.job_description:
            return self.matching_result.job_description.title
        return "Unknown Position"
    
    @property  
    def company_name(self):
        """Get company name from user's profile"""
        if self.matching_result and self.matching_result.user and hasattr(self.matching_result.user, 'profile'):
            return self.matching_result.user.profile.company_name or "Not specified"
        return "Not specified"


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


class InterviewEvaluation(models.Model):
    """Model to store AI-powered evaluation of interview transcripts"""
    
    # Evaluation status choices
    STATUS_CHOICES = [
        ('pending', 'Evaluation Pending'),
        ('in_progress', 'Evaluation In Progress'),
        ('completed', 'Evaluation Completed'),
        ('failed', 'Evaluation Failed'),
    ]
    
    # Next round recommendation choices
    RECOMMENDATION_CHOICES = [
        ('strong_hire', 'Strong Hire - Proceed Immediately'),
        ('hire', 'Hire - Proceed to Next Round'),
        ('maybe', 'Maybe - Consider with Caution'),
        ('no_hire', 'No Hire - Do Not Proceed'),
        ('insufficient_data', 'Insufficient Data for Decision'),
    ]
    
    # Confidence level choices
    CONFIDENCE_CHOICES = [
        ('high', 'High Confidence'),
        ('medium', 'Medium Confidence'),
        ('low', 'Low Confidence'),
    ]
    
    # Core relationships
    interview_recording = models.OneToOneField(
        InterviewRecording, 
        on_delete=models.CASCADE, 
        related_name='evaluation'
    )
    
    # Evaluation status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Simplified Pre-screening Evaluation Criteria (0-10 scale)
    communication_clarity = models.DecimalField(max_digits=4, decimal_places=2, default=0.00, help_text="Clear communication and professional articulation")
    relevant_experience = models.DecimalField(max_digits=4, decimal_places=2, default=0.00, help_text="Experience relevance and depth matching resume claims")
    role_interest_fit = models.DecimalField(max_digits=4, decimal_places=2, default=0.00, help_text="Understanding of role and genuine interest")
    
    # Overall score (calculated from above 3 criteria)
    overall_score = models.DecimalField(max_digits=4, decimal_places=2, default=0.00)
    
    # Legacy detailed scores (kept for backward compatibility, will be deprecated)
    communication_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="DEPRECATED: Use communication_clarity instead")
    technical_knowledge_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="DEPRECATED: Detailed scoring not needed for pre-screening")
    problem_solving_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="DEPRECATED: Detailed scoring not needed for pre-screening")
    cultural_fit_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="DEPRECATED: Use role_interest_fit instead")
    enthusiasm_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="DEPRECATED: Use role_interest_fit instead")
    
    # Simplified recommendation choices for pre-screening
    SIMPLIFIED_RECOMMENDATION_CHOICES = [
        ('PROCEED', 'Proceed to Next Round - Strong candidate'),
        ('CONDITIONAL', 'Conditional - Needs further evaluation'),
        ('REJECT', 'Reject - Not suitable for this position'),
        ('INSUFFICIENT', 'Insufficient Data - Interview incomplete'),
    ]
    
    # Recommendation and confidence (updated for pre-screening focus)
    recommendation = models.CharField(max_length=30, choices=SIMPLIFIED_RECOMMENDATION_CHOICES, default='INSUFFICIENT')
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_CHOICES, default='medium')
    
    # Detailed qualitative feedback
    strengths = models.JSONField(default=list, blank=True, help_text="List of candidate strengths identified")
    areas_of_concern = models.JSONField(default=list, blank=True, help_text="List of areas that need improvement or raise concerns")
    key_insights = models.JSONField(default=list, blank=True, help_text="Important insights about the candidate")
    
    # Interview analysis
    communication_assessment = models.TextField(blank=True, null=True, help_text="Analysis of candidate's communication skills")
    technical_assessment = models.TextField(blank=True, null=True, help_text="Analysis of technical knowledge and skills")
    behavioral_assessment = models.TextField(blank=True, null=True, help_text="Analysis of behavioral responses and cultural fit")
    
    # Questions analysis
    questions_answered_well = models.JSONField(default=list, blank=True, help_text="Questions the candidate handled effectively")
    questions_struggled_with = models.JSONField(default=list, blank=True, help_text="Questions the candidate had difficulty with")
    
    # Next round preparation
    recommended_next_steps = models.TextField(blank=True, null=True, help_text="Specific recommendations for next interview round")
    topics_to_explore_further = models.JSONField(default=list, blank=True, help_text="Topics that need deeper exploration")
    specific_concerns_to_address = models.JSONField(default=list, blank=True, help_text="Specific concerns to address in next round")
    
    # HR workflow
    hr_reviewed = models.BooleanField(default=False, help_text="Whether HR has reviewed this evaluation")
    hr_notes = models.TextField(blank=True, null=True, help_text="Additional notes from HR review")
    hr_decision_override = models.CharField(max_length=30, choices=RECOMMENDATION_CHOICES, blank=True, null=True, help_text="HR override of AI recommendation")
    
    # Email campaign integration
    next_round_email_sent = models.BooleanField(default=False, help_text="Whether next round invitation email has been sent")
    rejection_email_sent = models.BooleanField(default=False, help_text="Whether rejection email has been sent")
    
    # Evaluation metadata
    evaluation_duration_seconds = models.IntegerField(default=0, help_text="Time taken for AI evaluation")
    evaluation_model_version = models.CharField(max_length=50, blank=True, null=True, help_text="Version of AI model used for evaluation")
    
    # Raw AI response
    raw_ai_response = models.JSONField(blank=True, null=True, help_text="Raw response from AI evaluation agent")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    evaluation_completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['recommendation']),
            models.Index(fields=['overall_score']),
            models.Index(fields=['hr_reviewed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        candidate_name = self.interview_recording.candidate_name
        return f"Evaluation: {candidate_name} - {self.get_recommendation_display()} ({self.overall_score}%)"
    
    @property
    def score_breakdown(self):
        """Return formatted score breakdown using simplified criteria"""
        return {
            'overall': float(self.overall_score),
            'communication_clarity': float(self.communication_clarity),
            'relevant_experience': float(self.relevant_experience),
            'role_interest_fit': float(self.role_interest_fit),
            # Legacy fields for backward compatibility
            'communication': float(self.communication_score),
            'technical': float(self.technical_knowledge_score),
            'problem_solving': float(self.problem_solving_score),
            'cultural_fit': float(self.cultural_fit_score),
            'enthusiasm': float(self.enthusiasm_score),
        }
    
    @property
    def is_positive_recommendation(self):
        """Check if recommendation is positive (proceed or conditional)"""
        return self.recommendation in ['PROCEED', 'CONDITIONAL']
    
    @property
    def is_proceed_recommendation(self):
        """Check if recommendation is to proceed to next round"""
        return self.recommendation == 'PROCEED'
    
    @property
    def needs_hr_review(self):
        """Check if evaluation needs HR review"""
        return not self.hr_reviewed and self.status == 'completed'
    
    @property
    def candidate_info(self):
        """Get candidate information from related interview recording"""
        recording = self.interview_recording
        if recording.matching_result and recording.matching_result.resume:
            resume = recording.matching_result.resume
            return {
                'name': resume.candidate_name,
                'email': resume.email,
                'position': recording.job_title,
                'interview_date': recording.created_at,
            }
        return {
            'name': 'Unknown Candidate',
            'email': '',
            'position': 'Unknown Position',
            'interview_date': recording.created_at,
        }
    
    @property
    def evaluation_summary(self):
        """Generate a brief evaluation summary for dashboard display using simplified criteria"""
        if self.status != 'completed':
            return f"Evaluation {self.get_status_display()}"
        
        summary = f"{self.get_recommendation_display()} "
        summary += f"({self.overall_score}/10 overall, {self.get_confidence_level_display()})"
        
        # Show top performing area from simplified criteria
        scores = {
            'Communication': self.communication_clarity,
            'Experience': self.relevant_experience, 
            'Role Fit': self.role_interest_fit
        }
        top_area = max(scores, key=scores.get)
        if scores[top_area] > 0:
            summary += f" - Strongest: {top_area} ({scores[top_area]}/10)"
        
        return summary

    def calculate_overall_score(self):
        """Calculate overall score as average of 3 simplified criteria"""
        scores = [self.communication_clarity, self.relevant_experience, self.role_interest_fit]
        valid_scores = [float(score) for score in scores if score > 0]
        if valid_scores:
            return round(sum(valid_scores) / len(valid_scores), 2)
        return 0.00
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate overall score"""
        # Auto-calculate overall score from simplified criteria
        if any([self.communication_clarity, self.relevant_experience, self.role_interest_fit]):
            self.overall_score = self.calculate_overall_score()
        
        super().save(*args, **kwargs)


# --- Interview Pipeline Models ---
class InterviewStage(models.Model):
    """Model to track additional interview stages beyond initial AI interview"""
    
    STAGE_CHOICES = [
        ('technical', 'Technical Interview'),
        ('behavioral', 'Behavioral Interview'),
        ('final', 'Final Interview'),
        ('panel', 'Panel Interview'),
        ('cultural_fit', 'Cultural Fit Interview'),
    ]
    
    RECOMMENDATION_CHOICES = [
        ('reject', 'Reject'),
        ('on_hold', 'On Hold'),
        ('proceed', 'Proceed to Next Stage'),
        ('hire', 'Recommend for Hire'),
    ]
    
    # Link to original interview recording
    interview_recording = models.ForeignKey(
        'InterviewRecording', 
        on_delete=models.CASCADE, 
        related_name='additional_stages'
    )
    
    # Stage information
    stage_type = models.CharField(max_length=20, choices=STAGE_CHOICES)
    stage_order = models.IntegerField(default=1, help_text="Order of this stage in pipeline")
    
    # Interview details
    interviewer = models.ForeignKey(User, on_delete=models.CASCADE, help_text="HR/Manager who conducted interview")
    interview_date = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=0, help_text="Interview duration in minutes")
    
    # Evaluation
    overall_score = models.FloatField(default=0.0, help_text="Score out of 10")
    technical_skills_score = models.FloatField(default=0.0, help_text="Technical competency (0-10)")
    communication_score = models.FloatField(default=0.0, help_text="Communication skills (0-10)")
    cultural_fit_score = models.FloatField(default=0.0, help_text="Cultural fit (0-10)")
    problem_solving_score = models.FloatField(default=0.0, help_text="Problem solving ability (0-10)")
    
    # Qualitative feedback
    strengths = models.TextField(blank=True, help_text="Candidate's key strengths")
    weaknesses = models.TextField(blank=True, help_text="Areas for improvement")
    notes = models.TextField(blank=True, help_text="Additional interview notes")
    
    # Decision
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default='proceed')
    recommendation_notes = models.TextField(blank=True, help_text="Reasoning for recommendation")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['interview_recording', 'stage_order']
        unique_together = ['interview_recording', 'stage_type']  # One interview per stage type per candidate
    
    def __str__(self):
        candidate_name = self.interview_recording.candidate_name
        return f"{candidate_name} - {self.get_stage_type_display()} ({self.overall_score}/10)"
    
    @property
    def candidate_name(self):
        return self.interview_recording.candidate_name
    
    @property
    def candidate_email(self):
        return self.interview_recording.candidate_email
    
    @property
    def job_title(self):
        return self.interview_recording.job_title
    
    def calculate_overall_score(self):
        """Calculate overall score as average of individual scores"""
        scores = [
            self.technical_skills_score,
            self.communication_score, 
            self.cultural_fit_score,
            self.problem_solving_score
        ]
        valid_scores = []
        for score in scores:
            try:
                score_val = float(score)
                if score_val > 0:
                    valid_scores.append(score_val)
            except (ValueError, TypeError):
                continue
        
        if valid_scores:
            return round(sum(valid_scores) / len(valid_scores), 1)
        return 0.0
    
    def save(self, *args, **kwargs):
        """Auto-calculate overall score if individual scores provided"""
        if any([self.technical_skills_score, self.communication_score, 
               self.cultural_fit_score, self.problem_solving_score]):
            self.overall_score = self.calculate_overall_score()
        super().save(*args, **kwargs)


class CandidatePipeline(models.Model):
    """Model to track candidate's overall progress through interview pipeline"""
    
    STATUS_CHOICES = [
        ('initial_complete', 'Initial Interview Complete'),
        ('in_pipeline', 'In Interview Pipeline'),
        ('ready_for_onboarding', 'Ready for Onboarding'),
        ('onboarded', 'Onboarded'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Candidate Withdrawn'),
    ]
    
    # Core relationships
    interview_recording = models.OneToOneField(
        'InterviewRecording',
        on_delete=models.CASCADE,
        related_name='pipeline_status'
    )
    
    # Pipeline tracking
    current_stage = models.CharField(max_length=50, default='initial_complete')
    pipeline_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='initial_complete')
    
    # Onboarding eligibility
    meets_onboarding_criteria = models.BooleanField(default=False)
    onboarding_email_sent = models.BooleanField(default=False)
    onboarding_email_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Pipeline metadata
    pipeline_started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    
    # HR notes
    hr_notes = models.TextField(blank=True, help_text="Internal HR notes about candidate")
    
    class Meta:
        ordering = ['-last_activity_at']
    
    def __str__(self):
        candidate_name = self.interview_recording.candidate_name
        return f"{candidate_name} - {self.get_pipeline_status_display()}"
    
    @property
    def candidate_name(self):
        return self.interview_recording.candidate_name
    
    @property
    def candidate_email(self):
        return self.interview_recording.candidate_email
    
    @property
    def job_title(self):
        return self.interview_recording.job_title
    
    @property
    def total_stages_completed(self):
        """Count total interview stages completed (including initial)"""
        additional_stages = self.interview_recording.additional_stages.count()
        return 1 + additional_stages  # 1 for initial interview + additional stages
    
    @property
    def has_required_stages(self):
        """Check if candidate has minimum stages for onboarding (Initial + at least 1 more)"""
        return self.total_stages_completed >= 2
    
    @property
    def average_score(self):
        """Calculate average score across all interview stages"""
        scores = []
        
        # Add initial interview score
        if hasattr(self.interview_recording, 'evaluation') and self.interview_recording.evaluation:
            scores.append(self.interview_recording.evaluation.overall_score)
        
        # Add additional stage scores
        for stage in self.interview_recording.additional_stages.all():
            if stage.overall_score > 0:
                scores.append(stage.overall_score)
        
        if scores:
            return round(sum(scores) / len(scores), 1)
        return 0.0
    
    def update_onboarding_eligibility(self):
        """Update onboarding eligibility based on completed stages and scores"""
        if self.has_required_stages and self.average_score >= 6.0:
            self.meets_onboarding_criteria = True
            if self.pipeline_status == 'in_pipeline':
                self.pipeline_status = 'ready_for_onboarding'
        else:
            self.meets_onboarding_criteria = False
        
        self.save()
    
    def get_next_suggested_stages(self):
        """Get suggested next interview stages"""
        completed_stages = set(self.interview_recording.additional_stages.values_list('stage_type', flat=True))
        all_stages = ['technical', 'behavioral', 'final']
        return [stage for stage in all_stages if stage not in completed_stages]
