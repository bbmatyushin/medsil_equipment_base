"""Расчёты вкладки «Командировки»: атрибуция затрат к пунктам и виджеты.

Полная стоимость командировки — все затраты плюс суточные. Затраты и суточные
разносятся по пунктам (`trip_shares`), из этих долей строятся города, регионы
и клиенты. Чистые функции без обращения к request; арифметика дат
и группировка — в Python, как в `services/finance.py`.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.db.models import QuerySet

from analytics.filters import Period
from analytics.services.finance import _bucket_by_month, _delta_pct
from business_trip.models import BusinessTrip, BusinessTripDestination

ZERO = Decimal("0")
KOPECK = Decimal("0.01")
TENTH = Decimal("0.1")

ALLOWANCE_LABEL = "Суточные"
NO_DESTINATIONS_LABEL = "Пункты не указаны"
NO_CITY_LABEL = "Город не указан"
NO_REGION_SUFFIX = " (регион не указан)"
NO_CLIENT_LABEL = "Клиент не указан"
OTHER_KINDS_LABEL = "Прочие виды"

# Серий на графике «Затраты по месяцам» не больше, чем цветов палитры charts.js
MAX_MONTH_SERIES = 6

KPI_KEYS = ("total", "count", "person_days", "avg_trip", "avg_day")


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


def _ratio(value, divisor, step: Decimal = KOPECK) -> Decimal | None:
    """value / divisor с округлением до `step`; при нулевом делителе — None."""
    if not divisor:
        return None
    return (Decimal(value) / Decimal(divisor)).quantize(step, rounding=ROUND_HALF_UP)


# --- Основа: плитки, затраты по месяцам, структура -----------------------------


def _kpi_values(trips: list[BusinessTrip]) -> dict:
    total = sum((trip_total(trip) for trip in trips), ZERO)
    person_days = sum(trip.days_count or 0 for trip in trips)
    return {
        "total": total,
        "count": len(trips),
        "person_days": person_days,
        "avg_trip": _ratio(total, len(trips)),
        "avg_day": _ratio(total, person_days),
    }


def trips_kpis(period: Period, employee=None) -> dict:
    """Плитки вкладки и дельты к тому же периоду прошлого года.

    Всего потрачено — затраты и суточные командировок периода; человеко-дни —
    сумма дней командировок; средние — до копеек, без данных — None.
    """
    current = _kpi_values(trips_in_period(period, employee))
    previous = _kpi_values(trips_in_period(period.previous_year(), employee))
    return {
        "current": current,
        "previous": previous,
        "delta_pct": {key: _delta_pct(current[key], previous[key]) for key in KPI_KEYS},
    }


def _kind_amounts(trip: BusinessTrip) -> list[tuple[str, Decimal]]:
    """(вид затрат, сумма) по затратам командировки и её суточным."""
    pairs = [(e.expense_type.name, e.amount) for e in trip.expenses.all()]
    pairs.append((ALLOWANCE_LABEL, trip.allowance_amount or ZERO))
    return pairs


def _expense_kinds_by_total(trips: list[BusinessTrip]) -> list[str]:
    """Виды затрат (без суточных) с ненулевой суммой — по убыванию суммы."""
    totals = {}
    for trip in trips:
        for expense in trip.expenses.all():
            name = expense.expense_type.name
            totals[name] = totals.get(name, ZERO) + expense.amount
    return [
        name
        for name, amount in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        if amount
    ]


def costs_by_month(period: Period, employee=None) -> dict:
    """Затраты по месяцам начала командировок: серии по видам затрат и суточные.

    Если видов больше, чем помещается в палитру, крупнейшие идут отдельными
    сериями, остальные — одной «Прочие виды»; «Суточные» всегда последние.
    """
    months = period.months()
    trips = trips_in_period(period, employee)
    kinds = _expense_kinds_by_total(trips)
    if len(kinds) > MAX_MONTH_SERIES - 1:
        shown = kinds[: MAX_MONTH_SERIES - 2]
    else:
        shown = kinds

    def series_of(kind: str) -> str:
        if kind == ALLOWANCE_LABEL or kind in shown:
            return kind
        return OTHER_KINDS_LABEL

    labels = list(shown)
    if len(shown) < len(kinds):
        labels.append(OTHER_KINDS_LABEL)
    labels.append(ALLOWANCE_LABEL)
    pairs = {label: [] for label in labels}
    for trip in trips:
        for kind, amount in _kind_amounts(trip):
            pairs[series_of(kind)].append((trip.beg_dt, amount))
    return {
        "months": months,
        "series": [
            {"label": label, "data": _bucket_by_month(pairs[label], months)}
            for label in labels
        ],
    }


def cost_structure(period: Period, employee=None) -> list[dict]:
    """Затраты периода по видам и суточные: сумма и доля в %, по убыванию."""
    totals = {}
    for trip in trips_in_period(period, employee):
        for kind, amount in _kind_amounts(trip):
            totals[kind] = totals.get(kind, ZERO) + amount
    grand_total = sum(totals.values(), ZERO)
    return [
        {
            "label": kind,
            "amount": amount,
            "share_pct": _ratio(amount * 100, grand_total, TENTH),
        }
        for kind, amount in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        if amount
    ]
