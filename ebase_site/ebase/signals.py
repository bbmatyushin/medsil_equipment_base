from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from contracts.signals import recalc_contract, recalc_contract_by_service
from .models import Service
from spare_part.models import SparePartSupplyItem


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
    """Возвращает закупочную цену по FIFO для запчасти.

    Если передан срок годности, ищет самую раннюю поставку именно этой партии.
    Иначе берётся цена самой ранней поставки запчасти.
    Если цена не найдена, возвращает 0.
    """
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
        recalc_contract_by_service(instance)

    # Пересчитываем старый контракт, если он был изменён
    old_contract_id = getattr(instance, "_old_contract_id", None)
    if old_contract_id and old_contract_id != instance.contract_id:
        from contracts.models import Contract

        try:
            old_contract = Contract.objects.get(pk=old_contract_id)
            recalc_contract(old_contract)
        except Contract.DoesNotExist:
            pass
