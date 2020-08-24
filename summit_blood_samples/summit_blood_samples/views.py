import logging

from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.utils.http import urlsafe_base64_decode

# Get an instance of a logger
logger = logging.getLogger(__name__)


def get_user(uidb64):
    """
    Method to get the User by converting the uidb64
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist, ValidationError):
        logger.error('Something went wrong in getting User')
        user = None
    return user


def reset_password_done(request):
    """
    Method to redirect the user to home by creating session
    """
    user = get_user(request.headers['Referer'].split('reset')[1].split('/')[1])

    if user is not None:
        login(request, user)
        return HttpResponseRedirect("/")
