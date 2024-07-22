from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user

from .models import *


# @receiver(pre_save, sender=EquipmentAccounting)
# def set_user_id(sender, instance, **kwargs):
#     EquipmentAccounting.objects.update(user=get_user(instance.pk))
