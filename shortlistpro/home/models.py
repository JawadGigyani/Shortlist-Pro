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
    candidate_name = models.CharField(max_length=255, default='Unknown Candidate')
    email = models.EmailField(default='no-email@example.com')
    phone = models.CharField(max_length=20, blank=True, null=True)
    skills = models.TextField(blank=True, null=True)
    education = models.CharField(max_length=255, blank=True, null=True)
    experience = models.TextField(blank=True, null=True)
    certifications = models.JSONField(default=list, blank=True)
    resume_file = models.FileField(upload_to='resumes/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensure that each user can only have one resume per email address
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'email'], 
                name='unique_user_email_resume',
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
