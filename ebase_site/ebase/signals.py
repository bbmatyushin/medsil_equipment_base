from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from contracts.signals import recalc_contract
from .models import Service, ServiceExpense
from spare_part.models import SparePart, SparePartSupplyItem


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


def get_fifo_price(spare_part):
    """Возвращает закупочную цену по FIFO для запчасти.

    Берётся цена самой ранней партии поставки.
    Если цена не найдена, возвращает 0.
    """
    supply_items = SparePartSupplyItem.objects.filter(
        spare_part=spare_part
    ).order_by('supply__supply_dt', 'expiration_dt')

    first = supply_items.first()
    return first.price if first else 0


@receiver(post_save, sender=Service)
def service_post_save(sender, instance, created, **kwargs):
    """Материализуем расходы на запчасти и пересчитываем контракт."""
    # Удаляем старые расходы
    instance.service_expenses.all().delete()

    # Получаем выбранные запчасти и их количества из JSON-поля spare_part_count
    spare_part_counts = instance.spare_part_count or {}

    # Fallback: если spare_part_count пуст, используем M2M с quantity=1
    if not spare_part_counts and instance.spare_part.exists():
        spare_part_counts = {
            str(part.pk): [{"expiration_dt": None, "service_part_count": 1}]
            for part in instance.spare_part.all()
        }

    for spare_part_id, entries in spare_part_counts.items():
        try:
            spare_part = SparePart.objects.select_related('unit').get(pk=spare_part_id)
        except SparePart.DoesNotExist:
            continue

        total_quantity = sum(
            (entry.get('service_part_count') or 0) for entry in entries
        )
        price = get_fifo_price(spare_part)

        ServiceExpense.objects.create(
            service=instance,
            spare_part=spare_part,
            quantity=total_quantity,
            unit=spare_part.unit.short_name if spare_part.unit else 'шт.',
            price=price,
        )

    # Пересчитываем связанный контракт
    if instance.contract:
        recalc_contract(instance.contract)

    # Пересчитываем старый контракт, если он был изменён
    old_contract_id = getattr(instance, '_old_contract_id', None)
    if old_contract_id and old_contract_id != instance.contract_id:
        from contracts.models import Contract
        try:
            old_contract = Contract.objects.get(pk=old_contract_id)
            recalc_contract(old_contract)
        except Contract.DoesNotExist:
            pass
