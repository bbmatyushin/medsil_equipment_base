from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from contracts.signals import recalc_contract
from contracts.models import Contract
from .models import Service


@receiver(pre_save, sender=Service)
def service_pre_save(sender, instance, **kwargs):
    """Запоминаем старый contract_id для пересчёта старого контракта."""
    if instance.pk:
        try:
            old = Service.objects.get(pk=instance.pk)
            instance._old_contract_id = old.contract_id
        except Service.DoesNotExist:
            instance._old_contract_id = None
    else:
        instance._old_contract_id = None


def get_fifo_price(spare_part, expiration_dt=None):
    """Возвращает закупочную цену по FIFO для запчасти."""
    from spare_part.models import SparePartSupplyItem
    qs = SparePartSupplyItem.objects.filter(spare_part=spare_part)
    if expiration_dt is not None:
        qs = qs.filter(expiration_dt=expiration_dt)
    qs = qs.order_by("supply__supply_dt", "expiration_dt")
    first = qs.first()
    return first.price if first else 0


@receiver(post_save, sender=Service)
def service_post_save(sender, instance, created, **kwargs):
    """Пересчитываем связанный контракт при изменении ремонта."""
    if instance.contract:
        recalc_contract(instance.contract)

    old_contract_id = getattr(instance, "_old_contract_id", None)
    if old_contract_id and old_contract_id != instance.contract_id:
        try:
            old_contract = Contract.objects.get(pk=old_contract_id)
            recalc_contract(old_contract)
        except Contract.DoesNotExist:
            pass
