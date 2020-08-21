from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class ManageRoles(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    class Meta:
        verbose_name_plural = "Roles"

    def __str__(self):
        return str(self.name)


class UserRoles(models.Model):
    user_id = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='UserRoles')
    role_id = models.ForeignKey(
        ManageRoles, on_delete=models.CASCADE, related_name='UserRoles_roles')

    class Meta:
        verbose_name_plural = "User Roles"

    def __str__(self):
        return str(f'{self.role_id.name}')

    def save(self, *args, **kwargs):
        if self.role_id_id == 1 and self.user_id.is_superuser != True and self.user_id.is_staff != True:
            self.user_id.is_superuser = True
            self.user_id.is_staff = True
            self.user_id.save()
        super(UserRoles, self).save(*args, **kwargs)
