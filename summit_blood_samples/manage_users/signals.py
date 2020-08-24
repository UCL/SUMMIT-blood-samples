from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpRequest
from django.conf import settings


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Method to Send Password reset email to the user, when an Administrator creates the User
    """
    if created:
        form = PasswordResetForm({'email': instance.email})

        if form.is_valid():
            current_site = get_current_site(request=None)
            request = HttpRequest()
            request.META['HTTP_HOST'] = current_site.domain
            form.save(
                request=request,
                use_https=False,
                from_email=settings.DEFAULT_FROM_EMAIL,
                html_email_template_name='registration/new_user_html_password_reset_email.html')
