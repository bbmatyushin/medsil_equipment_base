"""Вкладка «Оборудование» раздела «Аналитика»."""

from datetime import timedelta

from .charts import chart_spec
from .filters import EquipmentFilterForm
from .links import changelist_url
from .services import equipment
from .templatetags.analytics_tags import number
from .views import MAX_LINK_IDS, AnalyticsTabView, _horizontal_chart_height

# Списки в админке: сюда ведут клики по виджетам
ACCOUNTING = "ebase_equipmentaccounting"
SERVICES = "ebase_service"
REPLACEMENTS = "ebase_replacementequipment"

OURS_LABEL = "Поставлено нами"
OTHERS_LABEL = "Поставлено не нами"

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


class EquipmentView(AnalyticsTabView):
    """Вкладка «Оборудование»: парк, ремонты, надёжность, подменный фонд."""

    tab_key = "equipment"
    form_class = EquipmentFilterForm
    template_name = "analytics/equipment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.form.get_filters()
        today = context["today"]
        # данные загружаются один раз на всю страницу, виджеты отбирают из набора
        source = equipment.EquipmentSet.load()

        charts = {}
        for block in (_park_context(source, filters, today),):
            charts.update(block.pop("charts"))
            context.update(block)
        context.update(filters=filters, charts=charts)
        return context
