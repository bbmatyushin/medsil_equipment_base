"""Signals for the contracts app.

Recalculates contract totals on Payment and ContractExpense changes,
including spare part shipments.
"""

from django.db.models import Sum
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import Contract, Payment, ContractExpense
from spare_part.models import SparePartShipmentV2, SparePartShipmentM2M


def recalc_contract(contract):
    """Пересчитывает payment_amount, expenses_amount, debt, profit."""
    if contract is None:
        return

    payment_amount = contract.payments.aggregate(s=Sum("amount"))["s"] or 0

    shipment_expenses = contract.spare_part_shipments.aggregate(
        s=Sum("shipment_m2m__sum")
    )["s"] or 0

    manual_expenses = contract.expenses.aggregate(s=Sum("sum"))["s"] or 0
    expenses_amount = shipment_expenses + manual_expenses

    contract.payment_amount = payment_amount
    contract.expenses_amount = expenses_amount
    contract.debt = contract.contract_amount - payment_amount
    contract.profit = payment_amount - expenses_amount
    contract.save(update_fields=["payment_amount", "expenses_amount", "debt", "profit"])


@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, **kwargs):
    recalc_contract(instance.contract)


@receiver(post_delete, sender=Payment)
def payment_post_delete(sender, instance, **kwargs):
    try:
        contract = Contract.objects.get(pk=instance.contract_id)
    except Contract.DoesNotExist:
        return
    recalc_contract(contract)


@receiver(post_save, sender=ContractExpense)
def contract_expense_post_save(sender, instance, **kwargs):
    recalc_contract(instance.contract)


@receiver(post_delete, sender=ContractExpense)
def contract_expense_post_delete(sender, instance, **kwargs):
    try:
        contract = Contract.objects.get(pk=instance.contract_id)
    except Contract.DoesNotExist:
        return
    recalc_contract(contract)


@receiver(post_save, sender=SparePartShipmentV2)
def shipment_post_save(sender, instance, **kwargs):
    if instance.contract_id:
        recalc_contract(instance.contract)


@receiver(post_delete, sender=SparePartShipmentV2)
def shipment_post_delete(sender, instance, **kwargs):
    if instance.contract_id:
        try:
            contract = Contract.objects.get(pk=instance.contract_id)
            recalc_contract(contract)
        except Contract.DoesNotExist:
            pass


@receiver(post_save, sender=SparePartShipmentM2M)
def shipment_m2m_post_save(sender, instance, **kwargs):
    contract_id = instance.shipment_id and getattr(instance.shipment, 'contract_id', None)
    if contract_id:
        try:
            contract = Contract.objects.get(pk=contract_id)
            recalc_contract(contract)
        except Contract.DoesNotExist:
            pass


@receiver(post_delete, sender=SparePartShipmentM2M)
def shipment_m2m_post_delete(sender, instance, **kwargs):
    contract_id = getattr(instance.shipment, 'contract_id', None) if instance.shipment_id else None
    if contract_id:
        try:
            contract = Contract.objects.filter(pk=contract_id).first()
            if contract:
                recalc_contract(contract)
        except Exception:
            pass
