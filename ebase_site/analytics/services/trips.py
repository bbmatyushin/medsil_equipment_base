"""Расчёты вкладки «Командировки»: атрибуция затрат к пунктам и виджеты.

Полная стоимость командировки — все затраты плюс суточные. Затраты и суточные
разносятся по пунктам (`trip_shares`), из этих долей строятся города, регионы
и клиенты. Чистые функции без обращения к request; арифметика дат
и группировка — в Python, как в `services/finance.py`.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.db.models import Min, QuerySet

from analytics.filters import Period
from analytics.services.finance import _bucket_by_month, _delta_pct
from business_trip.models import BusinessTrip, BusinessTripDestination, MoneyReceipt
from business_trip.xlsx_report import EXCLUDED_EXPENSE_TYPE_NAME, employee_fio

ZERO = Decimal("0")
KOPECK = Decimal("0.01")
TENTH = Decimal("0.1")

ALLOWANCE_LABEL = "Суточные"
NO_DESTINATIONS_LABEL = "Пункты не указаны"
NO_CITY_LABEL = "Город не указан"
NO_REGION_SUFFIX = " (регион не указан)"
NO_CLIENT_LABEL = "Клиент не указан"
OTHER_KINDS_LABEL = "Прочие виды"
NO_SERVICE_TYPE_LABEL = "Вид работ не указан"

DAYS_IN_YEAR = 365
# Средняя длина месяца для подписи «оценка по N мес.»
DAYS_IN_MONTH = Decimal("30.4")

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


# --- Направления, среднее за год, нормативы, виды работ ---------------------------


def _direction_buckets(trips: list[BusinessTrip], group: str) -> dict[str, dict]:
    """Доли командировок, собранные по направлениям (город или регион).

    В корзине: подпись, сумма, суммы по видам затрат и по годам начала
    командировок, дни пунктов (у «Пункты не указаны» — дни командировок)
    и id командировок в порядке появления.
    """
    buckets = {}

    def bucket(dest) -> dict:
        key, label = direction_of(dest, group)
        if key not in buckets:
            buckets[key] = {
                "key": key,
                "label": label,
                "amount": ZERO,
                "by_kind": {},
                "by_year": {},
                "days": 0,
                "trip_ids": [],
            }
        return buckets[key]

    for trip in trips:
        destinations = list(trip.destinations.all())
        touched = []
        for dest in destinations:
            item = bucket(dest)
            item["days"] += destination_days(dest)
            touched.append(item)
        if not destinations:
            item = bucket(None)
            item["days"] += trip.days_count or 0
            touched.append(item)
        for share in trip_shares(trip):
            item = bucket(share.destination)
            item["amount"] += share.amount
            item["by_kind"][share.kind] = (
                item["by_kind"].get(share.kind, ZERO) + share.amount
            )
            year = trip.beg_dt.year
            item["by_year"][year] = item["by_year"].get(year, ZERO) + share.amount
        trip_id = str(trip.pk)
        for item in touched:
            if trip_id not in item["trip_ids"]:
                item["trip_ids"].append(trip_id)
    return buckets


def directions(period: Period, employee=None, group: str = "city") -> list[dict]:
    """Затраты командировок периода по направлениям, по убыванию суммы."""
    buckets = _direction_buckets(trips_in_period(period, employee), group)
    rows = [
        {
            "key": item["key"],
            "label": item["label"],
            "amount": item["amount"],
            "trips": len(item["trip_ids"]),
            "days": item["days"],
            "trip_ids": item["trip_ids"],
        }
        for item in buckets.values()
    ]
    return sorted(rows, key=lambda row: (-row["amount"], row["label"]))


def annual_by_direction(today: date, employee=None, group: str = "city") -> dict:
    """Сколько в среднем за год уходит на каждое направление (вся история).

    Окно — от самой ранней даты выезда во всей базе (фильтр сотрудника на него
    не влияет) до сегодня; будущие командировки не учитываются. Среднее за год —
    сумма за окно × 365 / дней окна; при окне меньше года это оценка.
    """
    start = BusinessTrip.objects.filter(beg_dt__lte=today).aggregate(
        start=Min("beg_dt")
    )["start"]
    if start is None:
        return {
            "start": None,
            "window_days": 0,
            "months": 0,
            "is_estimate": False,
            "years": [],
            "rows": [],
        }
    window_days = (today - start).days + 1
    years = list(range(start.year, today.year + 1))
    buckets = _direction_buckets(trips_until(today, employee), group)
    rows = []
    for item in buckets.values():
        rows.append(
            {
                "key": item["key"],
                "label": item["label"],
                "by_year": [item["by_year"].get(year, ZERO) for year in years],
                "total": item["amount"],
                "per_year": _ratio(item["amount"] * DAYS_IN_YEAR, window_days),
                "trips_per_year": _ratio(
                    len(item["trip_ids"]) * DAYS_IN_YEAR, window_days, TENTH
                ),
            }
        )
    return {
        "start": start,
        "window_days": window_days,
        "months": max(1, round(window_days / DAYS_IN_MONTH)),
        "is_estimate": window_days < DAYS_IN_YEAR,
        "years": years,
        "rows": sorted(rows, key=lambda row: (-row["total"], row["label"])),
    }


def direction_norms(today: date, employee=None, group: str = "city") -> dict:
    """Типовые затраты по направлениям за всю историю: на поездку и на день.

    ₽ в день — на день пребывания в пункте. Командировки без пунктов
    в нормативы не входят.
    """
    trips = trips_until(today, employee)
    kinds = _expense_kinds_by_total(trips) + [ALLOWANCE_LABEL]
    buckets = _direction_buckets(trips, group)
    rows = []
    for item in buckets.values():
        if item["key"] == "none" or not item["days"]:
            continue
        count = len(item["trip_ids"])
        rows.append(
            {
                "key": item["key"],
                "label": item["label"],
                "trips": count,
                "avg_days": _ratio(item["days"], count, TENTH),
                "avg_trip": _ratio(item["amount"], count),
                "per_day": _ratio(item["amount"], item["days"]),
                "per_day_by_kind": [
                    _ratio(item["by_kind"].get(kind, ZERO), item["days"])
                    for kind in kinds
                ],
            }
        )
    return {
        "kinds": kinds,
        "rows": sorted(rows, key=lambda row: (-row["trips"], row["label"])),
    }


def by_service_type(period: Period, employee=None) -> list[dict]:
    """Командировки периода по видам работ: средняя поездка, длительность, ₽ в день.

    Командировка с несколькими видами работ считается в каждом из них целиком.
    """
    buckets = {}
    for trip in trips_in_period(period, employee):
        types = list(trip.service_type.all()) or [None]
        total = trip_total(trip)
        for service_type in types:
            key = service_type.pk if service_type is not None else None
            item = buckets.setdefault(
                key,
                {
                    "id": key,
                    "label": (
                        service_type.name
                        if service_type is not None
                        else NO_SERVICE_TYPE_LABEL
                    ),
                    "trips": 0,
                    "amount": ZERO,
                    "days": 0,
                },
            )
            item["trips"] += 1
            item["amount"] += total
            item["days"] += trip.days_count or 0
    rows = [
        {
            "id": item["id"],
            "label": item["label"],
            "trips": item["trips"],
            "avg_trip": _ratio(item["amount"], item["trips"]),
            "avg_days": _ratio(item["days"], item["trips"], TENTH),
            "per_day": _ratio(item["amount"], item["days"]),
        }
        for item in buckets.values()
    ]
    return sorted(rows, key=lambda row: (-row["trips"], row["label"]))


# --- Сотрудники и подотчёт ---------------------------------------------------------


def employee_name(user) -> str:
    """ФИО сотрудника, без ФИО — логин."""
    return employee_fio(user) or user.username


def employee_days(period: Period, employee=None) -> list[dict]:
    """Дни в командировках по сотрудникам за период, по убыванию дней."""
    rows = {}
    for trip in trips_in_period(period, employee):
        row = rows.setdefault(
            trip.employee_id,
            {
                "id": trip.employee_id,
                "name": employee_name(trip.employee),
                "trips": 0,
                "days": 0,
                "amount": ZERO,
            },
        )
        row["trips"] += 1
        row["days"] += trip.days_count or 0
        row["amount"] += trip_total(trip)
    result = [
        {**row, "per_day": _ratio(row["amount"], row["days"])} for row in rows.values()
    ]
    return sorted(result, key=lambda row: (-row["days"], row["name"]))


def employee_month_load(period: Period, employee=None) -> dict:
    """Дни в отъезде «сотрудник × месяц».

    Берутся командировки, пересекающие период (даже начавшиеся раньше); дни
    обрезаются по границам периода и раскладываются по календарным месяцам.
    """
    months = period.months()
    index = {month: position for position, month in enumerate(months)}
    queryset = BusinessTrip.objects.filter(
        beg_dt__lte=period.date_to, end_dt__gte=period.date_from
    )
    rows = {}
    for trip in load_trips(_filtered(queryset, employee)):
        row = rows.setdefault(
            trip.employee_id,
            {
                "id": trip.employee_id,
                "name": employee_name(trip.employee),
                "days": [0] * len(months),
                "total": 0,
            },
        )
        day = max(trip.beg_dt, period.date_from)
        last = min(trip.end_dt, period.date_to)
        while day <= last:
            row["days"][index[day.replace(day=1)]] += 1
            row["total"] += 1
            day += timedelta(days=1)
    result = sorted(rows.values(), key=lambda row: (-row["total"], row["name"]))
    return {
        "months": months,
        "rows": result,
        "max": max((max(row["days"]) for row in result), default=0),
    }


def accountable_spent(trip: BusinessTrip) -> Decimal:
    """Расход по подотчёту: затраты без «Я.командировки» и суточные.

    Как «ИТОГО расход» отчёта по ДС: «Я.командировки» оплачены компанией
    напрямую и через сотрудника не проходят.
    """
    expenses = sum(
        (
            expense.amount
            for expense in trip.expenses.all()
            if expense.expense_type.name != EXCLUDED_EXPENSE_TYPE_NAME
        ),
        ZERO,
    )
    return expenses + (trip.allowance_amount or ZERO)


def accountable(period: Period, today: date, employee=None) -> list[dict]:
    """Подотчёт сотрудников: получено и расход за период, остаток на сегодня.

    Получено — поступления ДС по дате получения; расход — `accountable_spent`
    командировок по месяцу выезда. Остаток = все поступления − весь расход по
    сегодняшний день (будущие командировки не учитываются). Плюс — деньги
    у сотрудника, минус — компания должна сотруднику.
    """
    receipts = _filtered(MoneyReceipt.objects.select_related("employee"), employee)
    rows = {}

    def row_of(user) -> dict:
        return rows.setdefault(
            user.pk,
            {
                "id": user.pk,
                "name": employee_name(user),
                "received": ZERO,
                "spent": ZERO,
                "balance": ZERO,
            },
        )

    date_range = (period.date_from, period.date_to)
    for receipt in receipts.filter(receipt_date__range=date_range):
        row_of(receipt.employee)["received"] += receipt.amount
    for receipt in receipts.filter(receipt_date__lte=today):
        row_of(receipt.employee)["balance"] += receipt.amount
    for trip in trips_in_period(period, employee):
        row_of(trip.employee)["spent"] += accountable_spent(trip)
    for trip in trips_until(today, employee):
        row_of(trip.employee)["balance"] -= accountable_spent(trip)
    result = [
        {**row, "diff": row["received"] - row["spent"]}
        for row in rows.values()
        if row["received"] or row["spent"] or row["balance"]
    ]
    return sorted(result, key=lambda row: row["name"])
