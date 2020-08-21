from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from rest_framework.authtoken.models import Token

from .models import UserRoles

# User._meta.get_field('email')._unique = True
# User._meta.get_field('email').blank = False

# Unregister the provided model admin
admin.site.unregister(Site)
admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.unregister(Token)

class RoleAdmin(admin.TabularInline):
    list_display = ('name')
    list_filter = ['name']
    model = UserRoles
    extra = 1
    max_num = 1
    min_num = 1
    can_delete = False


class EmailRequiredMixin(object):
    def __init__(self, *args, **kwargs):
        super(EmailRequiredMixin, self).__init__(*args, **kwargs)
        self.fields['email'].required = True


class UserAdmin(admin.ModelAdmin):
    inlines = [RoleAdmin, ]
    fields = ('first_name', 'last_name', 'username', 'email', 'is_active',)
    exclude = ('password1', 'password2',)
    list_display = ('username', 'first_name', 'last_name',
                    'email', 'is_active', 'role')
    list_per_page = 20
    search_fields = ['first_name', 'last_name', 'username', 'email']
    list_filter = ['is_active']
    unique_together = ('email',)

    def role(self, obj):
        return UserRoles.objects.filter(user_id=obj.id).first()
    role.admin_order_field = 'role_id__name'


admin.site.register(User, UserAdmin)
