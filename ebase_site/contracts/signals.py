"""Signals for the contracts app.

Recalculates contract totals on Payment and ContractExpense changes,
including materialized ServiceExpense rows from the linked repair.
"""
from django.db.models import Sum
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import Contract, Payment, ContractExpense


def recalc_contract(contract):
    """Пересчитывает payment_amount, expenses_amount, debt, profit."""
    if contract is None:
        return

    # Импорт внутри функции во избежание циклического импорта
    # (ebase.signals импортирует recalc_contract отсюда).
    from ebase.models import Service

    payment_amount = contract.payments.aggregate(s=Sum('amount'))['s'] or 0

    # Service.contract использует unique=True, поэтому обратный аксессор
    # related_name='service' ведёт себя как OneToOne и возвращает объект Service
    # (либо возбуждает Service.DoesNotExist).
    service_expenses = 0
    try:
        service_expenses = contract.service.service_expenses.aggregate(s=Sum('sum'))['s'] or 0
    except Service.DoesNotExist:
        service_expenses = 0

    manual_expenses = contract.expenses.aggregate(s=Sum('sum'))['s'] or 0
    expenses_amount = service_expenses + manual_expenses

    contract.payment_amount = payment_amount
    contract.expenses_amount = expenses_amount
    contract.debt = contract.contract_amount - payment_amount
    contract.profit = payment_amount - expenses_amount
    contract.save(update_fields=[
        'payment_amount', 'expenses_amount', 'debt', 'profit'
    ])


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


def recalc_contract_by_service(service):
    """Вызывается из ebase signals при изменении ServiceExpense."""
    if service is None:
        return
    recalc_contract(service.contract)
