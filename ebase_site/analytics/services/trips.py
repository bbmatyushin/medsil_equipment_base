"""Расчёты вкладки «Командировки»: атрибуция затрат к пунктам и виджеты.

Полная стоимость командировки — все затраты плюс суточные. Затраты и суточные
разносятся по пунктам (`trip_shares`), из этих долей строятся города, регионы
и клиенты. Чистые функции без обращения к request; арифметика дат
и группировка — в Python, как в `services/finance.py`.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal

from django.db.models import QuerySet

from analytics.filters import Period
from business_trip.models import BusinessTrip, BusinessTripDestination

ZERO = Decimal("0")
KOPECK = Decimal("0.01")

ALLOWANCE_LABEL = "Суточные"
NO_DESTINATIONS_LABEL = "Пункты не указаны"
NO_CITY_LABEL = "Город не указан"
NO_REGION_SUFFIX = " (регион не указан)"
NO_CLIENT_LABEL = "Клиент не указан"


@dataclass(frozen=True)
class Share:
    """Доля стоимости командировки, отнесённая к пункту.

    `destination` — None, если у командировки нет пунктов. `kind` — вид затрат
    (`ExpenseType.name`) или «Суточные».
    """

    trip: BusinessTrip
    destination: BusinessTripDestination | None
    kind: str
    amount: Decimal


def split_proportional(total: Decimal, weights: list[int]) -> list[Decimal]:
    """Делит сумму пропорционально весам с точностью до копеек.

    Доли округляются вниз, остаток прибавляется к первой (как `split_amount`
    в `business_trip/services.py`): сумма долей всегда равна `total`.
    """
    total = Decimal(total)
    weight_sum = sum(weights)
    shares = [
        (total * weight / weight_sum).quantize(KOPECK, rounding=ROUND_DOWN)
        for weight in weights
    ]
    shares[0] += total - sum(shares)
    return shares


def destination_days(dest: BusinessTripDestination) -> int:
    """Дни пребывания в пункте (граничные даты включаются)."""
    return (dest.end_dt - dest.beg_dt).days + 1


def trip_total(trip: BusinessTrip) -> Decimal:
    """Полная стоимость командировки: все затраты + суточные."""
    expenses = sum((expense.amount for expense in trip.expenses.all()), ZERO)
    return expenses + (trip.allowance_amount or ZERO)


def _sorted_destinations(trip: BusinessTrip) -> list[BusinessTripDestination]:
    return sorted(trip.destinations.all(), key=lambda d: (d.beg_dt, d.end_dt))


def trip_shares(trip: BusinessTrip) -> list[Share]:
    """Доли стоимости командировки по пунктам.

    Затрата с датой внутри дат пункта уходит в него (при нескольких подходящих —
    в пункт с наименьшей датой прибытия). Остальные затраты (например, билеты
    до выезда) и суточные делятся между пунктами пропорционально дням. Без
    пунктов доли получают `destination=None`. Нулевые доли не создаются.
    """
    destinations = _sorted_destinations(trip)
    weights = [destination_days(dest) for dest in destinations]
    shares = []

    def spread(kind: str, amount: Decimal):
        if not destinations:
            parts = [(None, amount)]
        else:
            parts = zip(destinations, split_proportional(amount, weights))
        shares.extend(Share(trip, dest, kind, part) for dest, part in parts if part)

    for expense in trip.expenses.all():
        kind = expense.expense_type.name
        matching = next(
            (d for d in destinations if d.beg_dt <= expense.date <= d.end_dt), None
        )
        if matching is not None:
            if expense.amount:
                shares.append(Share(trip, matching, kind, expense.amount))
        else:
            spread(kind, expense.amount)
    spread(ALLOWANCE_LABEL, trip.allowance_amount or ZERO)
    return shares


def direction_of(dest: BusinessTripDestination | None, group: str) -> tuple[str, str]:
    """Направление пункта: (ключ, подпись) — город или регион (`group`)."""
    if dest is None:
        return "none", NO_DESTINATIONS_LABEL
    city = dest.department.city
    if city is None:
        return "no_city", NO_CITY_LABEL
    if group == "region":
        region = (city.region or "").strip()
        if region:
            return f"region:{region}", region
        return f"city:{city.pk}", f"{city.name}{NO_REGION_SUFFIX}"
    return f"city:{city.pk}", str(city).strip()


def client_of(dest: BusinessTripDestination | None) -> tuple[str, str]:
    """Клиент пункта: (ключ, подпись)."""
    if dest is None:
        return "none", NO_DESTINATIONS_LABEL
    client = dest.department.client
    if client is None:
        return "no_client", NO_CLIENT_LABEL
    return str(client.pk), client.name


def load_trips(queryset: QuerySet) -> list[BusinessTrip]:
    """Командировки со всем нужным расчётам: в циклах запросов нет."""
    return list(
        queryset.select_related("employee").prefetch_related(
            "destinations__department__city",
            "destinations__department__client",
            "expenses__expense_type",
            "service_type",
            "contract",
        )
    )


def _filtered(queryset: QuerySet, employee) -> QuerySet:
    if employee is not None:
        queryset = queryset.filter(employee=employee)
    return queryset


def trips_in_period(period: Period, employee=None) -> list[BusinessTrip]:
    """Командировки, начавшиеся в периоде (границы включительно)."""
    queryset = BusinessTrip.objects.filter(
        beg_dt__range=(period.date_from, period.date_to)
    )
    return load_trips(_filtered(queryset, employee))


def trips_until(today: date, employee=None) -> list[BusinessTrip]:
    """Командировки, начавшиеся не позже `today` (вся история)."""
    queryset = BusinessTrip.objects.filter(beg_dt__lte=today)
    return load_trips(_filtered(queryset, employee))
