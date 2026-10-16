"""Расчёты вкладки «Деньги»: плитки, движение денег, заключённые контракты,
возраст долга и матрица «оказано × оплачено».

Чистые функции без обращения к request. Группировка по месяцам выполняется
в Python (`_bucket_by_month`), а не функциями БД: SQLite и PostgreSQL ведут
себя по-разному.
"""

from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import accumulate
from typing import Iterable

from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone

from analytics.filters import Period
from business_trip.models import BusinessTripContractExpense
from clients.models import Client
from contracts.models import Contract, ContractExpense, Payment
from spare_part.models import SparePartShipmentM2M

# Суммируемые поля контракта (как в итогах реестра)
TOTAL_KEYS = ("contract_amount", "payment_amount", "expenses_amount", "debt", "profit")

ZERO = Decimal("0")
TENTH = Decimal("0.1")

# Корзины возраста долга: (ключ, подпись) в порядке показа
AGING_BUCKETS = [
    ("not_due", "Срок не наступил"),
    ("0_30", "0–30 дн."),
    ("31_90", "31–90 дн."),
    ("91_180", "91–180 дн."),
    ("180_plus", "Более 180 дн."),
]


def _round_tenth(value: Decimal) -> Decimal:
    """Округление до 0,1 по правилу «от нуля» для половинки (12,25 -> 12,3)."""
    return value.quantize(TENTH, rounding=ROUND_HALF_UP)


def _bucket_by_month(
    pairs: Iterable[tuple[date, Decimal]], months: list[date]
) -> list[Decimal]:
    """Суммирует значения по месяцам.

    `months` — первые числа месяцев. Значения с датами вне этих месяцев
    игнорируются. Результат той же длины, что и `months`.
    """
    totals = {month: ZERO for month in months}
    for day, value in pairs:
        key = day.replace(day=1)
        if key in totals:
            totals[key] += value
    return [totals[month] for month in months]


def contracts_in_period(period: Period, client: Client | None = None) -> QuerySet:
    """Контракты, заключённые в периоде (границы включительно), опционально клиента."""
    queryset = Contract.objects.filter(
        conclusion_date__range=(period.date_from, period.date_to)
    )
    if client is not None:
        queryset = queryset.filter(client=client)
    return queryset


def _totals(period: Period, client: Client | None) -> dict:
    """Итоги по контрактам периода: количество, суммы, маржа."""
    aggregates = contracts_in_period(period, client).aggregate(
        count=Count("id"), **{key: Sum(key) for key in TOTAL_KEYS}
    )
    totals = {"count": aggregates["count"]}
    for key in TOTAL_KEYS:
        totals[key] = aggregates[key] or ZERO
    if totals["payment_amount"] == 0:
        totals["margin_pct"] = None
    else:
        totals["margin_pct"] = _round_tenth(
            totals["profit"] * 100 / totals["payment_amount"]
        )
    return totals


def _delta_pct(current, previous) -> Decimal | None:
    """Изменение в % к модулю прошлого значения; при прошлом 0 или None — None."""
    if current is None or previous is None or previous == 0:
        return None
    current, previous = Decimal(current), Decimal(previous)
    return _round_tenth((current - previous) * 100 / abs(previous))


def finance_kpis(period: Period, client: Client | None = None) -> dict:
    """Плитки вкладки «Деньги» и дельты к тому же периоду прошлого года.

    Суммы берутся из сохранённых полей контрактов, как в итогах реестра.
    Дельта маржи считается в процентных пунктах, остальных показателей — в %.
    """
    current = _totals(period, client)
    previous = _totals(period.previous_year(), client)

    delta_pct = {
        key: _delta_pct(current[key], previous[key]) for key in (*TOTAL_KEYS, "count")
    }
    if current["margin_pct"] is None or previous["margin_pct"] is None:
        delta_pct["margin_pct"] = None
    else:
        delta_pct["margin_pct"] = current["margin_pct"] - previous["margin_pct"]
    return {"current": current, "previous": previous, "delta_pct": delta_pct}


def _local_day_bounds(period: Period) -> tuple[datetime, datetime]:
    """Границы периода [начало первого дня, начало дня после последнего) в текущей зоне."""
    start = timezone.make_aware(datetime.combine(period.date_from, time.min))
    end = timezone.make_aware(
        datetime.combine(period.date_to + timedelta(days=1), time.min)
    )
    return start, end


def money_flow(period: Period, client: Client | None = None) -> dict:
    """Движение денег по месяцам по фактическим датам оплат и затрат.

    Затраты — только отнесённые на контракты: отгрузки запчастей (без контракта
    не учитываются), расходы контракта и доли командировок. Фильтр клиента
    действует через контракт.
    """
    months = period.months()
    date_range = (period.date_from, period.date_to)

    payments = Payment.objects.filter(date__range=date_range)
    shipments = SparePartShipmentM2M.objects.filter(
        shipment__contract__isnull=False, shipment__shipment_dt__range=date_range
    )
    # Расход без даты относим к локальной дате создания записи
    start, end = _local_day_bounds(period)
    expenses = ContractExpense.objects.filter(
        Q(date__range=date_range)
        | Q(date__isnull=True, create_dt__gte=start, create_dt__lt=end)
    )
    trips = BusinessTripContractExpense.objects.filter(
        business_trip__end_dt__range=date_range
    )
    if client is not None:
        payments = payments.filter(contract__client=client)
        shipments = shipments.filter(shipment__contract__client=client)
        expenses = expenses.filter(contract__client=client)
        trips = trips.filter(contract__client=client)

    inflow = _bucket_by_month(payments.values_list("date", "amount"), months)
    spare_parts = _bucket_by_month(
        shipments.values_list("shipment__shipment_dt", "sum"), months
    )
    other = _bucket_by_month(
        (
            (day or timezone.localdate(created), amount)
            for day, amount, created in expenses.values_list("date", "sum", "create_dt")
        ),
        months,
    )
    trips_series = _bucket_by_month(
        trips.values_list("business_trip__end_dt", "amount"), months
    )

    outflow = [
        parts + trip + rest
        for parts, trip, rest in zip(spare_parts, trips_series, other)
    ]
    balance = [received - spent for received, spent in zip(inflow, outflow)]
    return {
        "months": months,
        "inflow": inflow,
        "spare_parts": spare_parts,
        "trips": trips_series,
        "other": other,
        "outflow": outflow,
        "balance": balance,
    }


def concluded_by_month(period: Period, client: Client | None = None) -> dict:
    """Сумма заключённых контрактов по месяцам и накопительный итог в периоде."""
    months = period.months()
    amount = _bucket_by_month(
        contracts_in_period(period, client).values_list(
            "conclusion_date", "contract_amount"
        ),
        months,
    )
    return {"months": months, "amount": amount, "cumulative": list(accumulate(amount))}


def _aging_key(age_days: int) -> str:
    """Ключ корзины по возрасту долга в днях (отрицательный — срок не наступил)."""
    if age_days < 0:
        return "not_due"
    if age_days <= 30:
        return "0_30"
    if age_days <= 90:
        return "31_90"
    if age_days <= 180:
        return "91_180"
    return "180_plus"


def debt_aging(today: date, client: Client | None = None) -> list[dict]:
    """Возраст долга на `today` по всем контрактам с долгом; период не учитывается.

    Возраст считается от даты окончания услуг, а если её нет, то от даты
    заключения. Результат содержит все корзины `AGING_BUCKETS` в их порядке:
    `{"key", "label", "count", "amount", "ids"}`, где `ids` — `str(pk)` контрактов.
    """
    contracts = Contract.objects.filter(debt__gt=0)
    if client is not None:
        contracts = contracts.filter(client=client)

    buckets = {
        key: {"key": key, "label": label, "count": 0, "amount": ZERO, "ids": []}
        for key, label in AGING_BUCKETS
    }
    for pk, debt, end_date, conclusion_date in contracts.values_list(
        "id", "debt", "service_end_date", "conclusion_date"
    ):
        bucket = buckets[_aging_key((today - (end_date or conclusion_date)).days)]
        bucket["count"] += 1
        bucket["amount"] += debt
        bucket["ids"].append(str(pk))
    return list(buckets.values())


def status_matrix(period: Period, client: Client | None = None) -> dict:
    """Матрица «услуги оказаны × оплата» по контрактам периода.

    Строки — `Contract.SERVICES_PROVIDED_CHOICES`, столбцы —
    `Contract.PAYMENT_STATUS_CHOICES` в их порядке; сетка всегда полная, пустые
    ячейки нулевые. `amount` — сумма `contract_amount`.
    """
    grouped = (
        contracts_in_period(period, client)
        .order_by()
        .values("services_provided", "payment_status")
        .annotate(count=Count("id"), amount=Sum("contract_amount"))
    )
    found = {(row["services_provided"], row["payment_status"]): row for row in grouped}

    def cell(row_key: str, column_key: str) -> dict:
        data = found.get((row_key, column_key))
        return {
            "payment_status": column_key,
            "count": data["count"] if data else 0,
            "amount": (data["amount"] or ZERO) if data else ZERO,
        }

    return {
        "columns": [
            {"key": key, "label": label}
            for key, label in Contract.PAYMENT_STATUS_CHOICES
        ],
        "rows": [
            {
                "key": row_key,
                "label": row_label,
                "cells": [
                    cell(row_key, column_key)
                    for column_key, _ in Contract.PAYMENT_STATUS_CHOICES
                ],
            }
            for row_key, row_label in Contract.SERVICES_PROVIDED_CHOICES
        ],
    }
