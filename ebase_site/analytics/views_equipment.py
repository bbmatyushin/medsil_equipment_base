"""Вкладка «Оборудование» раздела «Аналитика»."""

from datetime import timedelta

from .charts import chart_spec
from .filters import EquipmentFilterForm, month_label
from .links import change_url, changelist_url
from .services import equipment
from .templatetags.analytics_tags import number
from .views import MAX_LINK_IDS, AnalyticsTabView, _horizontal_chart_height
from .views_trips import _with_load_shades

# Списки в админке: сюда ведут клики по виджетам
ACCOUNTING = "ebase_equipmentaccounting"
SERVICES = "ebase_service"
REPLACEMENTS = "ebase_replacementequipment"

OURS_LABEL = "Поставлено нами"
OTHERS_LABEL = "Поставлено не нами"

# Плитки «Ремонты»: ключ repairs_kpis, подпись, вид значения, «рост — плохо»
REPAIR_TILES = [
    ("total", "Всего работ", "count", False),
    ("planned", "ТО проведено", "count", False),
    ("breakdowns", "Поломок", "count", True),
    ("median_days", "Медиана ремонта, дней", "count", True),
    ("replacement_share", "Поломок с подменой", "percent", False),
]

# Запасные ссылки «Полноты данных», когда записей больше `MAX_LINK_IDS`:
# фильтр списка, который показывает надмножество этих записей
GAP_FALLBACKS = {
    "no_install": {"install_dt": "nulldt"},
    "no_install_date": {"install_dt": "nulldt"},
    "no_status": {"equipment_status__name__isnull": "True"},
    "no_service_type": {"service_type__isnull": "True"},
}


def ids_link(admin_name: str, ids: list[str], **fallback) -> str | None:
    """Список этих записей; пусто — без ссылки.

    Больше `MAX_LINK_IDS` id gunicorn отклонил бы (длинная строка запроса):
    тогда ссылка ведёт на фильтр `fallback` (надмножество), а без него её нет.
    """
    if not ids:
        return None
    if len(ids) <= MAX_LINK_IDS:
        return changelist_url(admin_name, id__in=ids)
    if fallback:
        return changelist_url(admin_name, **fallback)
    return None


def _supply_series(rows: list[dict]) -> list[dict]:
    """Две серии «нами / не нами» по строкам с ключами `ours` и `others`."""
    return [
        {"label": OURS_LABEL, "data": [row["ours"] for row in rows], "color": "c1"},
        {"label": OTHERS_LABEL, "data": [row["others"] for row in rows], "color": "c2"},
    ]


def _structure_chart(rows: list[dict], links: list[str | None]) -> dict:
    """Горизонтальный стек «нами / не нами» по строкам структуры парка."""
    return chart_spec(
        "bar",
        [row["label"] for row in rows],
        _supply_series(rows),
        fmt="count",
        horizontal=True,
        stacked=True,
        links=links,
    )


def _direction_link(row: dict) -> str | None:
    if row["key"] is None:
        return ids_link(ACCOUNTING, row["ids"])
    return ids_link(ACCOUNTING, row["ids"], med_direction=row["key"])


def _status_link(row: dict) -> str | None:
    if row["key"] is None:
        return ids_link(ACCOUNTING, row["ids"], equipment_status__name__isnull="True")
    return ids_link(ACCOUNTING, row["ids"], equipment_status__name=row["key"])


def _park_tiles(kpis: dict) -> list[dict]:
    """Плитки парка (на сегодня, без дельты)."""
    return [
        {
            "label": "Учтено приборов",
            "value": kpis["total"],
            "kind": "count",
            "note": f"нами {number(kpis['ours'])} · не нами {number(kpis['others'])}",
        },
        {"label": "У клиентов", "value": kpis["at_client"], "kind": "count"},
        {
            "label": "Нет данных о монтаже",
            "value": kpis["no_install"],
            "kind": "count",
            "note": f"монтаж снят: {number(kpis['removed'])}",
        },
        {"label": "Клиентов с приборами", "value": kpis["clients"], "kind": "count"},
        {"label": "Средний возраст парка", "value": kpis["avg_age"], "kind": "years"},
        {
            "label": "С отметкой «Проведено ТО»",
            "value": kpis["our_service"],
            "kind": "count",
        },
    ]


def _gap_rows(rows: list[dict], today) -> list[dict]:
    """Строки «Полноты данных» со ссылкой и признаком «список шире» (`superset`)."""
    fallbacks = {
        **GAP_FALLBACKS,
        "old_open": {
            "end_dt__isnull": "True",
            "beg_dt__lt": (
                today - timedelta(days=equipment.OPEN_REPAIR_DAYS)
            ).isoformat(),
        },
    }
    result = []
    for row in rows:
        admin_name = ACCOUNTING if row["target"] == "accounting" else SERVICES
        fallback = fallbacks.get(row["key"], {})
        result.append(
            {
                **row,
                "url": ids_link(admin_name, row["ids"], **fallback),
                "superset": len(row["ids"]) > MAX_LINK_IDS and bool(fallback),
            }
        )
    return result


def _park_context(source, filters, today) -> dict:
    """Блок «Парк оборудования»: плитки, графики, клиенты, полнота данных."""
    kpis = equipment.park_kpis(today, filters, source=source)
    by_year = equipment.installs_by_year(filters, source=source)
    structure = equipment.park_structure(filters, source=source)
    age = equipment.park_age(today, filters, source=source)
    charts = {
        "installs_by_year": chart_spec(
            "bar",
            [str(year) for year in by_year["years"]],
            [
                {"label": OURS_LABEL, "data": by_year["ours"], "color": "c1"},
                {"label": OTHERS_LABEL, "data": by_year["others"], "color": "c2"},
                {
                    "label": "Всего установлено",
                    "data": by_year["cumulative"],
                    "kind": "line",
                    "axis": "y2",
                    "fmt": "count",
                    "color": "c3",
                },
            ],
            fmt="count",
            stacked=True,
        ),
        "structure_directions": _structure_chart(
            structure["directions"],
            [_direction_link(row) for row in structure["directions"]],
        ),
        "structure_manufacturers": _structure_chart(
            structure["manufacturers"],
            [ids_link(ACCOUNTING, row["ids"]) for row in structure["manufacturers"]],
        ),
        "structure_statuses": _structure_chart(
            structure["statuses"],
            [_status_link(row) for row in structure["statuses"]],
        ),
        "structure_regions": _structure_chart(
            structure["regions"],
            [ids_link(ACCOUNTING, row["ids"]) for row in structure["regions"]],
        ),
        "park_age": chart_spec(
            "bar",
            [row["label"] for row in age],
            [
                {
                    "label": "Приборов",
                    "data": [row["count"] for row in age],
                    "color": "c1",
                }
            ],
            fmt="count",
            links=[ids_link(ACCOUNTING, row["ids"]) for row in age],
        ),
    }
    return {
        "park": kpis,
        "park_tiles": _park_tiles(kpis),
        "installs_no_date": by_year["no_date"],
        "structure": structure,
        "structure_heights": {
            key: _horizontal_chart_height(len(rows)) for key, rows in structure.items()
        },
        "top_clients": [
            {**row, "url": ids_link(ACCOUNTING, row["ids"])}
            for row in equipment.top_clients(filters, source=source)
        ],
        "data_gaps": _gap_rows(
            equipment.data_gaps(today, filters, source=source), today
        ),
        "charts": charts,
    }


def _repairs_tiles(kpis: dict) -> list[dict]:
    """Плитки ремонтов с дельтой к прошлому году и «В работе сейчас» (на сегодня)."""
    tiles = [
        {
            "label": label,
            "value": kpis["current"][key],
            "delta": kpis["delta_pct"][key],
            "inverse": inverse,
            "kind": kind,
            # доля в %, её дельта — в процентных пунктах
            "pp": key == "replacement_share",
            "snapshot": False,
        }
        for key, label, kind, inverse in REPAIR_TILES
    ]
    tiles.append(
        {
            "label": "В работе сейчас",
            "value": kpis["open_now"],
            "delta": None,
            "inverse": False,
            "kind": "count",
            "pp": False,
            "snapshot": True,
        }
    )
    return tiles


def _planned_chart(planned: dict) -> dict:
    """ТО по месяцам: стек «нами / не нами» (и «Прибор не указан») и линия прошлого года."""
    datasets = [
        {"label": OURS_LABEL, "data": planned["ours"], "color": "c1"},
        {"label": OTHERS_LABEL, "data": planned["others"], "color": "c2"},
    ]
    if sum(planned["no_device"]):
        datasets.append(
            {
                "label": equipment.NO_DEVICE_LABEL,
                "data": planned["no_device"],
                "color": "c4",
            }
        )
    datasets.append(
        {
            "label": "Прошлый год",
            "data": planned["previous"],
            "kind": "line",
            "color": "c5",
        }
    )
    return chart_spec(
        "bar",
        [month_label(month) for month in planned["months"]],
        datasets,
        fmt="count",
        stacked=True,
    )


def _repairs_context(source, filters, period, today) -> dict:
    """Блок «Ремонты»: плитки, работы и ТО по месяцам, длительность, открытые, инженеры."""
    kpis = equipment.repairs_kpis(period, today, filters, source=source)
    by_month = equipment.works_by_month(period, filters, source=source)
    durations = equipment.duration_stats(period, filters, source=source)
    opened = equipment.open_repairs(today, filters, source=source)
    opened["rows"] = [
        {**row, "url": change_url(SERVICES, row["id"])} for row in opened["rows"]
    ]
    charts = {
        "works_by_month": chart_spec(
            "bar",
            [month_label(month) for month in by_month["months"]],
            [
                {"label": series["label"], "data": series["data"]}
                for series in by_month["series"]
            ],
            fmt="count",
            stacked=True,
        ),
        "planned_by_month": _planned_chart(
            equipment.planned_by_month(period, filters, source=source)
        ),
        "durations": chart_spec(
            "bar",
            [row["label"] for row in durations["buckets"]],
            [
                {
                    "label": "Поломок",
                    "data": [row["count"] for row in durations["buckets"]],
                    "color": "c1",
                }
            ],
            fmt="count",
            links=[ids_link(SERVICES, row["ids"]) for row in durations["buckets"]],
        ),
    }
    return {
        "repairs": kpis,
        "repairs_tiles": _repairs_tiles(kpis),
        "open_repairs": opened,
        "old_open_url": ids_link(
            SERVICES,
            opened["old_ids"],
            end_dt__isnull="True",
            beg_dt__lt=opened["old_before"].isoformat(),
        ),
        "durations": durations,
        "engineer_load": _with_load_shades(
            equipment.engineer_load(period, filters, source=source)
        ),
        "charts": charts,
    }


def _reliability_context(source, filters, period, today) -> dict:
    """Блок «Надёжность моделей»: частота поломок, повторы, проблемные, сводная."""
    rows = equipment.reliability(period, today, filters, source=source)
    repeats = equipment.repeat_repairs(period, filters, source=source)
    repeats["rows"] = [
        {
            **row,
            "previous_url": change_url(SERVICES, row["previous_id"]),
            "current_url": change_url(SERVICES, row["current_id"]),
        }
        for row in repeats["rows"]
    ]
    return {
        "reliability": rows,
        "reliability_height": _horizontal_chart_height(len(rows)),
        "min_units": equipment.MIN_UNITS_FOR_RELIABILITY,
        "repeats": repeats,
        "repeat_windows": equipment.REPEAT_WINDOWS,
        "problem_devices": [
            {**row, "url": change_url(ACCOUNTING, row["device_id"])}
            for row in equipment.problem_devices(period, filters, source=source)
        ],
        "models_summary": equipment.models_summary(
            period, today, filters, source=source
        ),
        "charts": {
            "reliability": chart_spec(
                "bar",
                [row["label"] for row in rows],
                [
                    {
                        "label": "Поломок на прибор в год",
                        "data": [row["per_unit_year"] for row in rows],
                        "color": "c1",
                    }
                ],
                fmt="decimal",
                horizontal=True,
                links=[ids_link(SERVICES, row["service_ids"]) for row in rows],
            ),
        },
    }


class EquipmentView(AnalyticsTabView):
    """Вкладка «Оборудование»: парк, ремонты, надёжность, подменный фонд."""

    tab_key = "equipment"
    form_class = EquipmentFilterForm
    template_name = "analytics/equipment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.form.get_filters()
        today = context["today"]
        period = context["period"]
        # данные загружаются один раз на всю страницу, виджеты отбирают из набора
        source = equipment.EquipmentSet.load()

        charts = {}
        for block in (
            _park_context(source, filters, today),
            _repairs_context(source, filters, period, today),
            _reliability_context(source, filters, period, today),
        ):
            charts.update(block.pop("charts"))
            context.update(block)
        context.update(filters=filters, charts=charts)
        return context
