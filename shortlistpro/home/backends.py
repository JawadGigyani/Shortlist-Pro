from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(Q(username=username) | Q(email=username))
        except (User.MultipleObjectsReturned, User.DoesNotExist):
            return None

        if user.check_password(password):
            try:
                _ = user.profile  # Check if profile exists
            except:
                return None  # If user has no profile, deny login
            return user
        return None
