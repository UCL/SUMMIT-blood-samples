from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from rest_framework.authtoken.views import obtain_auth_token
from django.conf.urls import url
import django.views.static
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from summit_blood_samples.views import *

admin.autodiscover()
admin.site.login = login_required(admin.site.login)

urlpatterns = [
    path(settings.URL_PATTERN_PREFIX, include('blood_sample.urls')),
    path(settings.URL_PATTERN_PREFIX + 'accounts/password_reset/', auth_views.PasswordResetView.as_view(
        html_email_template_name='registration/html_password_reset_email.html',
        subject_template_name='registration/forgot_password_subject.html'
    ), name="reset_password"),
    path(settings.URL_PATTERN_PREFIX + 'accounts/login/',
         auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    url(settings.URL_PATTERN_PREFIX + r'accounts/reset/done/$', reset_password_done, name="reset_password_done"),
    path(settings.URL_PATTERN_PREFIX + 'accounts/', include('django.contrib.auth.urls')),
    # path('admin/', admin.site.urls),
    path(settings.URL_PATTERN_PREFIX + 'admin/', admin.site.urls, name='custom_admin'),
    url(settings.URL_PATTERN_PREFIX + r'^static/(?P<path>.*)$', django.views.static.serve,
        {'document_root': settings.STATIC_ROOT, 'show_indexes': settings.DEBUG})


    # path("", TemplateView.as_view(template_name="pages/home.html"), name="home"),
    # path(
    #     "about/", TemplateView.as_view(template_name="pages/about.html"), name="about"
    # ),
    # # Django Admin, use {% url 'admin:index' %}
    # path(settings.ADMIN_URL, admin.site.urls),
    # # User management
    # path("users/", include("summit_blood_samples.users.urls", namespace="users")),
    # path("accounts/", include("allauth.urls")),
    # Your stuff: custom urls includes go here
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# API URLS
urlpatterns += [
    # API base url
    # path("api/", include("config.api_router")),
    # DRF auth token
    # path("auth-token/", obtain_auth_token),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
