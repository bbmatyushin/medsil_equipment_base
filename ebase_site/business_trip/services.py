"""Сервисные функции приложения командировок.

Пересчёт долей расходов командировки по контрактам (BusinessTripContractExpense).
"""

from decimal import Decimal, ROUND_DOWN

from django.db.models import Sum

from .models import BusinessTripContractExpense

TWO_PLACES = Decimal("0.01")


def split_amount(total, count):
    """Делит сумму на count равных частей с точностью до копеек.

    Базовая доля округляется вниз до сотых, остаток добавляется к первой части.
    Например, 4000.33 на 2 части -> [2000.17, 2000.16].
    """
    base = (total / count).quantize(TWO_PLACES, rounding=ROUND_DOWN)
    remainder = total - base * count
    shares = [base] * count
    shares[0] = base + remainder
    return shares


def recalc_trip_contract_shares(trip):
    """Пересчитывает доли расходов командировки по контрактам.

    Командировка относится к контракту, если контракт выбран в командировке
    и клиент контракта присутствует в подразделениях (пунктах) командировки.
    Сумма командировки (затраты + суточные) делится поровну между такими
    контрактами; остаток от деления уходит на первый по дате заключения.

    Возвращает set с ID контрактов, чьи доли могли измениться.
    """
    expenses_sum = trip.expenses.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total = expenses_sum + (trip.allowance_amount or Decimal("0"))

    client_ids = set(
        trip.destinations.exclude(department__client_id=None).values_list(
            "department__client_id", flat=True
        )
    )
    contracts = list(
        trip.contract.filter(client_id__in=client_ids).order_by(
            "conclusion_date", "contract_number"
        )
    )
    contract_ids = {c.pk for c in contracts}

    existing = {entry.contract_id: entry for entry in trip.contract_expenses.all()}
    affected_ids = set(existing) | contract_ids

    # Удаляем доли контрактов, выпавших из списка
    for contract_id, entry in existing.items():
        if contract_id not in contract_ids:
            entry.delete()

    if contracts:
        shares = split_amount(total, len(contracts))
        for contract, share in zip(contracts, shares):
            entry = existing.get(contract.pk)
            if entry is None:
                BusinessTripContractExpense.objects.create(
                    business_trip=trip, contract=contract, amount=share
                )
            elif entry.amount != share:
                entry.amount = share
                entry.save(update_fields=["amount"])

    return affected_ids


def sync_trip_contract_shares(trip):
    """Пересчитывает доли командировки и обновляет затраты затронутых контрактов."""
    from contracts.models import Contract
    from contracts.signals import recalc_contract

    affected_ids = recalc_trip_contract_shares(trip)
    for contract in Contract.objects.filter(pk__in=affected_ids):
        recalc_contract(contract)
