from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user

from .models import *


@receiver(pre_save, sender=EquipmentAccounting)
def set_user_id(sender, instance, **kwargs):
    user = get_user()
    if user and not instance.user:
        instance.user = user
