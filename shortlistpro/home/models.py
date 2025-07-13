from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_premium = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"
