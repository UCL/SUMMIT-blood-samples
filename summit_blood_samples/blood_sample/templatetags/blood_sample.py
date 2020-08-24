from django import template
from django.conf import settings
from manage_users.models import UserRoles
# import the logging library
import logging

# Get an instance of a logger
logger = logging.getLogger('default')

register = template.Library()


@register.simple_tag
def user_is_entry_admin_tag(user):
    try:
        return user.is_authenticated and UserRoles.objects.get(user_id=user).role_id.id in [1]
    except Exception as e:
        # Log an error message
        logger.debug(f'User with {user.id} id is having issue {e}')
        return None


@register.simple_tag
def user_is_entry_datamanager_tag(user):
    return user.is_authenticated and UserRoles.objects.get(user_id=user).role_id.id in [2]


@register.simple_tag
def user_is_entry_bloodsamplemanager_tag(user):
    return user.is_authenticated and UserRoles.objects.get(user_id=user).role_id.id in [3]

@register.simple_tag
def last_but_one(data):
    return data[-2]