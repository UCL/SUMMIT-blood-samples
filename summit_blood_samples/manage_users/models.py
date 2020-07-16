from django.db import models
from django.contrib.auth.models import User, AbstractUser
from django.conf import settings
from django.contrib.auth.hashers import check_password


class ManageRoles(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    class Meta:
        verbose_name_plural = "Roles"

    def __str__(self):
        return str(self.name)



class UserRoles(models.Model):
    user_id = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='UserRoles_user')
    role_id = models.ForeignKey(
        ManageRoles, on_delete=models.CASCADE, related_name='UserRoles_roles')

    class Meta:
        verbose_name_plural = "User Roles"

    def __str__(self):
        return str(f'{self.user_id.username} | {self.role_id.name}')