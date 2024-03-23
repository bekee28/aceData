from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError

User = get_user_model()

class CustomAuthenticationBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Check if the user can be authenticated with the provided username
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            try:
                # If user is not found with username, try with email
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                # Both username and email do not exist in the database
                raise ValidationError("Invalid username or email.")

        if user.check_password(password) and self.user_can_authenticate(user):
            return user



