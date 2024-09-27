from django.db import models
from django.conf import settings
from hooks.models import Package


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)
    credits = models.IntegerField(blank=True, null=True)
    merge_credits = models.IntegerField(blank=True, null=True)
    def __str__(self):
        return f'You have {self.credits} credits.'
