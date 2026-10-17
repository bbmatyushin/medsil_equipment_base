"""Вкладка «Командировки» раздела «Аналитика»."""

from .charts import chart_spec
from .filters import Period, TripsFilterForm, month_label
from .links import changelist_url
from .services import trips
from .views import MAX_LINK_IDS, AnalyticsTabView, _horizontal_chart_height

# Список командировок в админке: сюда ведут клики по виджетам
TRIPS = "business_trip_businesstrip"

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
    """Значение GET-параметра `employee` для ссылок в списки; None — без него."""
    return str(employee.pk) if employee is not None else None


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


def _trips_charts(by_month: dict, structure: list[dict], top: list[dict]) -> dict:
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

        kpis = trips.trips_kpis(period, employee)
        structure = trips.cost_structure(period, employee)
        top = trips.directions(period, employee, group)[:TOP_DIRECTIONS]
        context.update(
            employee=employee,
            group=group,
            kpis=kpis,
            tiles=_trips_tiles(kpis),
            trips_list_url=_trips_list_url(period, employee),
            structure=structure,
            charts=_trips_charts(
                by_month=trips.costs_by_month(period, employee),
                structure=structure,
                top=top,
            ),
            directions_height=_horizontal_chart_height(len(top)),
            directions_limit=TOP_DIRECTIONS,
            annual=trips.annual_by_direction(today, employee, group),
            norms=trips.direction_norms(today, employee, group),
            service_types=_service_type_links(
                trips.by_service_type(period, employee), period, employee
            ),
        )
        return context
