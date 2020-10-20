# Settings for UCL local development.
# These are based on the production settings, but with emails printed to console.

from .production import *


# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = False
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = False

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
