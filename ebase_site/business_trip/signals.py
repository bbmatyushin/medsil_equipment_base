"""Сигналы приложения командировок.

Пересчёт долей расходов командировок по контрактам (BusinessTripContractExpense)
и затрат затронутых контрактов.
"""

from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import receiver

from contracts.models import Contract

from .models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
)
from .services import sync_trip_contract_shares


@receiver(m2m_changed, sender=BusinessTrip.contract.through)
def trip_contracts_changed(sender, instance, action, reverse, **kwargs):
    """Изменился список контрактов командировки."""
    if reverse or action not in ("post_add", "post_remove", "post_clear"):
        return
    sync_trip_contract_shares(instance)


@receiver(post_save, sender=BusinessTripExpense)
def trip_expense_saved(sender, instance, **kwargs):
    sync_trip_contract_shares(instance.business_trip)


@receiver(post_delete, sender=BusinessTripExpense)
def trip_expense_deleted(sender, instance, **kwargs):
    try:
        trip = instance.business_trip
    except BusinessTrip.DoesNotExist:
        # Затрата удалена каскадом вместе с командировкой — пересчёт не нужен
        return
    sync_trip_contract_shares(trip)


@receiver(post_save, sender=BusinessTripDestination)
def trip_destination_saved(sender, instance, **kwargs):
    sync_trip_contract_shares(instance.business_trip)


@receiver(post_delete, sender=BusinessTripDestination)
def trip_destination_deleted(sender, instance, **kwargs):
    try:
        trip = instance.business_trip
    except BusinessTrip.DoesNotExist:
        return
    sync_trip_contract_shares(trip)


@receiver(post_save, sender=BusinessTrip)
def trip_saved(sender, instance, **kwargs):
    """Даты командировки влияют на суточные, значит и на доли контрактов."""
    sync_trip_contract_shares(instance)


@receiver(pre_delete, sender=BusinessTrip)
def trip_pre_delete(sender, instance, **kwargs):
    """Запоминаем контракты, чтобы пересчитать их после удаления командировки."""
    instance._expense_contract_ids = list(
        instance.contract_expenses.values_list("contract_id", flat=True)
    )


@receiver(post_delete, sender=BusinessTrip)
def trip_post_delete(sender, instance, **kwargs):
    from contracts.signals import recalc_contract

    for contract in Contract.objects.filter(
        pk__in=getattr(instance, "_expense_contract_ids", [])
    ):
        recalc_contract(contract)


@receiver(pre_save, sender=Contract)
def contract_pre_save(sender, instance, **kwargs):
    """Запоминаем старого клиента контракта для отслеживания его смены."""
    if instance.pk:
        instance._old_client_id = (
            Contract.objects.filter(pk=instance.pk)
            .values_list("client_id", flat=True)
            .first()
        )
    else:
        instance._old_client_id = None


@receiver(post_save, sender=Contract)
def contract_post_save(sender, instance, **kwargs):
    """При смене клиента контракта пересчитываем доли всех его командировок."""
    if instance.client_id == getattr(instance, "_old_client_id", None):
        return
    for trip in instance.business_trip.all():
        sync_trip_contract_shares(trip)
