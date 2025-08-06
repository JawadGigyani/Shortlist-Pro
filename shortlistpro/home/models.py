from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
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
    
    # Core relationships
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='matching_results')
    job_description = models.ForeignKey(JobDescription, on_delete=models.CASCADE, related_name='matching_results')
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # For easy filtering
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
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
        if self.overall_score >= 90:
            return 'High'
        elif self.overall_score >= 70:
            return 'Medium'
        else:
            return 'Low'
    
    @property
    def match_category(self):
        """Categorize match quality"""
        if self.overall_score >= 90:
            return 'Excellent Match'
        elif self.overall_score >= 80:
            return 'Good Match'
        elif self.overall_score >= 70:
            return 'Fair Match'
        else:
            return 'Poor Match'
