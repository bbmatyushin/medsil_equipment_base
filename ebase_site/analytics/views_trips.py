"""Вкладка «Командировки» раздела «Аналитика»."""

import math

from .charts import chart_spec
from .filters import Period, TripsFilterForm, month_label
from .links import change_url, changelist_url
from .services import trips
from .views import (
    CONTRACTS,
    MAX_LINK_IDS,
    AnalyticsTabView,
    _horizontal_chart_height,
)

# Списки в админке: сюда ведут клики по виджетам
TRIPS = "business_trip_businesstrip"
RECEIPTS = "business_trip_moneyreceipt"

# Сколько направлений показывать на графике «Направления за период»
TOP_DIRECTIONS = 15

# Плитки: ключ показателя trips_kpis, подпись, вид значения, «рост — плохо»
TRIPS_TILES = [
    ("total", "Всего потрачено", "money", True),
    ("count", "Командировок", "count", False),
    ("person_days", "Человеко-дней", "count", False),
    ("avg_trip", "Средняя поездка", "money", True),
    ("avg_day", "Средний день", "money", True),
]


def _trips_tiles(kpis: dict) -> list[dict]:
    """Плитки: значение, дельта к прошлому году, вид значения."""
    return [
        {
            "label": label,
            "value": kpis["current"][key],
            "delta": kpis["delta_pct"][key],
            "inverse": inverse,
            "kind": kind,
        }
        for key, label, kind, inverse in TRIPS_TILES
    ]


def _employee_param(employee) -> str | None:
    """Значение GET-параметра `employee` для ссылок в списки; None — без него.

    `employee` — сотрудник или его pk.
    """
    if employee is None:
        return None
    return str(getattr(employee, "pk", employee))


def _trips_list_url(period: Period, employee, **params) -> str:
    """Список командировок периода (по дате выезда), опционально сотрудника."""
    return changelist_url(
        TRIPS,
        beg_dt__gte=period.date_from.isoformat(),
        beg_dt__lte=period.date_to.isoformat(),
        employee=_employee_param(employee),
        **params,
    )


def _ids_link(ids: list[str]) -> str | None:
    """Список этих командировок; пусто или больше `MAX_LINK_IDS` — без ссылки.

    Длинный `?id__in=` gunicorn отклонил бы с ответом 400.
    """
    if not ids or len(ids) > MAX_LINK_IDS:
        return None
    return changelist_url(TRIPS, id__in=ids)


def _service_type_links(rows: list[dict], period: Period, employee) -> list[dict]:
    """Строки «По видам работ» со ссылкой на командировки этого вида за период."""
    result = []
    for row in rows:
        if row["id"] is None:
            # параметр бокового фильтра «Виды работ» для пустого значения
            params = {"service_type__isnull": "True"}
        else:
            params = {"service_type__id__exact": row["id"]}
        result.append({**row, "url": _trips_list_url(period, employee, **params)})
    return result


def _with_load_shades(load: dict) -> dict:
    """Ячейки «сотрудник × месяц» с насыщенностью заливки (0–1).

    Насыщенность — корень доли дней от самой загруженной ячейки: редкие
    короткие поездки не пропадают на фоне длинных.
    """
    top = load["max"]
    load["labels"] = [month_label(month) for month in load["months"]]
    for row in load["rows"]:
        row["cells"] = [
            {"days": days, "shade": round(math.sqrt(days / top), 2) if top else 0}
            for days in row["days"]
        ]
    return load


def _with_trip_links(rows: list[dict]) -> list[dict]:
    """Строки командировок со ссылкой на карточку командировки."""
    return [{**row, "url": change_url(TRIPS, row["id"])} for row in rows]


def _with_pair_links(rows: list[dict]) -> list[dict]:
    """Пары «можно было объединить» со ссылками на карточки обеих командировок."""
    return [
        {
            **row,
            "first_url": change_url(TRIPS, row["first"]["id"]),
            "second_url": change_url(TRIPS, row["second"]["id"]),
        }
        for row in rows
    ]


def _with_receipt_links(rows: list[dict]) -> list[dict]:
    """Строки подотчёта со ссылкой на поступления ДС сотрудника."""
    return [
        {**row, "url": changelist_url(RECEIPTS, employee=row["id"])} for row in rows
    ]


def _with_employee_links(rows: list[dict], period: Period) -> list[dict]:
    """Строки «Дни в разъездах» со ссылкой на командировки сотрудника за период."""
    return [{**row, "url": _trips_list_url(period, row["id"])} for row in rows]


def _trips_charts(
    by_month: dict,
    structure: list[dict],
    top: list[dict],
    days: list[dict],
    balance: list[dict],
    clients: list[dict],
) -> dict:
    """Спецификации графиков вкладки «Командировки»."""
    return {
        "by_month": chart_spec(
            "bar",
            [month_label(month) for month in by_month["months"]],
            [
                {"label": series["label"], "data": series["data"]}
                for series in by_month["series"]
            ],
            stacked=True,
        ),
        "structure": chart_spec(
            "bar",
            [row["label"] for row in structure],
            [{"label": "Сумма", "data": [row["amount"] for row in structure]}],
            horizontal=True,
        ),
        "directions": chart_spec(
            "bar",
            [row["label"] for row in top],
            [{"label": "Затраты", "data": [row["amount"] for row in top]}],
            horizontal=True,
            links=[_ids_link(row["trip_ids"]) for row in top],
        ),
        "employee_days": chart_spec(
            "bar",
            [row["name"] for row in days],
            [{"label": "Дней", "data": [row["days"] for row in days]}],
            fmt="count",
            horizontal=True,
            links=[row["url"] for row in days],
        ),
        "balance": chart_spec(
            "bar",
            [row["name"] for row in balance],
            [
                {
                    "label": "Остаток на сегодня",
                    "data": [row["balance"] for row in balance],
                    "sign_colors": True,
                }
            ],
            horizontal=True,
            links=[row["url"] for row in balance],
        ),
        "clients": chart_spec(
            "bar",
            [row["name"] for row in clients],
            [
                {
                    "label": "Затраты на выезды",
                    "data": [row["trips_amount"] for row in clients],
                }
            ],
            horizontal=True,
        ),
    }


class TripsView(AnalyticsTabView):
    """Вкладка «Командировки»."""

    tab_key = "trips"
    form_class = TripsFilterForm
    template_name = "analytics/trips.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = context["period"]
        employee = self.form.get_employee()
        group = self.form.get_group()

        today = context["today"]
        # командировки загружаются один раз на всю страницу, виджеты отбирают из набора
        source = trips.TripSet.load()

        kpis = trips.trips_kpis(period, employee, source=source)
        structure = trips.cost_structure(period, employee, source=source)
        top = trips.directions(period, employee, group, source=source)[:TOP_DIRECTIONS]
        days = _with_employee_links(
            trips.employee_days(period, employee, source=source), period
        )
        accountable = _with_receipt_links(
            trips.accountable(period, today, employee, source=source)
        )
        clients = trips.clients_trips_vs_payments(period, employee, source=source)
        unallocated = trips.unallocated_trips(period, employee, source=source)
        unallocated["rows"] = _with_trip_links(unallocated["rows"])
        context.update(
            employee=employee,
            group=group,
            kpis=kpis,
            tiles=_trips_tiles(kpis),
            trips_list_url=_trips_list_url(period, employee),
            structure=structure,
            charts=_trips_charts(
                by_month=trips.costs_by_month(period, employee, source=source),
                structure=structure,
                top=top,
                days=days,
                balance=accountable,
                clients=clients,
            ),
            employee_days=days,
            employee_days_height=_horizontal_chart_height(len(days)),
            load=_with_load_shades(
                trips.employee_month_load(period, employee, source=source)
            ),
            accountable=accountable,
            balance_height=_horizontal_chart_height(len(accountable)),
            contracts=[
                {**row, "url": change_url(CONTRACTS, row["id"])}
                for row in trips.contract_trip_shares(period, employee, source=source)
            ],
            clients=clients,
            clients_height=_horizontal_chart_height(len(clients)),
            unallocated=unallocated,
            unallocated_url=_ids_link(unallocated["ids"]),
            max_link_ids=MAX_LINK_IDS,
            repeats=[
                {
                    **row,
                    "url": change_url(TRIPS, row["trip_id"]),
                    "previous_url": change_url(TRIPS, row["previous_trip_id"]),
                }
                for row in trips.repeat_visits(period, employee, source=source)
            ],
            merges=_with_pair_links(
                trips.merge_candidates(period, employee, source=source)
            ),
            expensive=_with_trip_links(
                trips.expensive_trips(period, today, employee, source=source)
            ),
            repeat_window_days=trips.REPEAT_WINDOW_DAYS,
            merge_window_days=trips.MERGE_WINDOW_DAYS,
            directions_height=_horizontal_chart_height(len(top)),
            directions_limit=TOP_DIRECTIONS,
            annual=trips.annual_by_direction(today, employee, group, source=source),
            norms=trips.direction_norms(today, employee, group, source=source),
            service_types=_service_type_links(
                trips.by_service_type(period, employee, source=source), period, employee
            ),
        )
        return context
