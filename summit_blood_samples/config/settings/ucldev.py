# Settings for UCL local development.
# These are based on the production settings, but with emails printed to console.

from .production import *

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
