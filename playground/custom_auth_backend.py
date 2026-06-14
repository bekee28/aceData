from django.contrib.auth import get_user_model
from django.db.models import Q

from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class CustomAuthenticationBackend(ModelBackend):
    """Authenticate with either a username or an email in the username field.

    Per Django's backend contract, this returns ``None`` (never raises) when no
    matching, authenticatable user is found, so the login form surfaces the
    standard "please enter a correct username and password" error.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            # Run the default hasher once to mitigate timing attacks that could
            # reveal whether a username/email exists.
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            # An email collides with another user's username (or duplicate
            # emails exist). Fall back to an exact username match only.
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None



