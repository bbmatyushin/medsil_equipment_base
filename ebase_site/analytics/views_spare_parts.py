"""Вкладка «Запчасти» раздела «Аналитика»."""

from .charts import chart_spec
from .filters import SparePartFilterForm, month_label
from .links import change_url, changelist_url
from .services import spare_parts
from .views import MAX_LINK_IDS, AnalyticsTabView, _horizontal_chart_height

SPARE_PARTS = "spare_part_sparepart"
SHIPMENTS = "spare_part_sparepartshipmentv2"
STOCK_ROWS_LIMIT = 100


def _ids_link(admin_name, ids) -> str | None:
    """Ссылка на конкретные документы, если список не слишком длинный."""
    ids = list(ids)
    if not ids or len(ids) > MAX_LINK_IDS:
        return None
    return changelist_url(admin_name, id__in=ids)


def _overview_context(source, filters, period, today) -> dict:
    """Плитки и основная таблица текущего склада."""
    kpis = spare_parts.overview_kpis(period, today, filters, source)
    rows = spare_parts.stock_rows(period, today, filters, source)
    for row in rows:
        row["url"] = change_url(SPARE_PARTS, row["id"])
    tiles = [
        {
            "label": "Позиций с остатком",
            "value": kpis["positive_count"],
            "kind": "count",
        },
        {
            "label": "Оценочная стоимость остатка",
            "value": kpis["stock_value"],
            "kind": "money",
            "note": f"цена известна: {kpis['priced_count']} из {kpis['priced_total']} позиций",
        },
        {
            "label": "Закуплено за период",
            "value": kpis["purchase_amount"],
            "kind": "money",
            "note": f"{period.date_from:%d.%m.%Y} — {period.date_to:%d.%m.%Y}",
        },
        {
            "label": "Отгружено за период",
            "value": kpis["shipment_cost"],
            "kind": "money",
            "note": f"{period.date_from:%d.%m.%Y} — {period.date_to:%d.%m.%Y}",
        },
    ]
    return {
        "tiles": tiles,
        "stock_rows": rows[:STOCK_ROWS_LIMIT],
        "stock_rows_total": len(rows),
        "stock_rows_limit": STOCK_ROWS_LIMIT,
        "kpis": kpis,
    }


def _movement_context(source, filters, period, today) -> dict:
    """Денежный поток и топы себестоимости отгрузок."""
    flow = spare_parts.money_by_month(period, filters, source)
    parts = spare_parts.top_parts(period, filters, source)
    equipment = spare_parts.top_equipment(period, filters, source)
    equipment_rows = equipment["rows"]
    charts = {
        "money_by_month": chart_spec(
            "bar",
            [month_label(month) for month in flow["months"]],
            [
                {"label": "Закуплено", "data": flow["purchases"], "color": "c1"},
                {"label": "Отгружено", "data": flow["shipments"], "color": "c2"},
                {
                    "label": "Сальдо",
                    "data": flow["balance"],
                    "kind": "line",
                    "color": "c3",
                },
            ],
            fmt="money",
        ),
        "top_parts": chart_spec(
            "bar",
            [row["label"] for row in parts],
            [{"label": "Себестоимость", "data": [row["cost"] for row in parts]}],
            fmt="money",
            horizontal=True,
            links=[_ids_link(SHIPMENTS, row["shipment_ids"]) for row in parts],
        ),
        "top_equipment": chart_spec(
            "bar",
            [row["label"] for row in equipment_rows],
            [
                {
                    "label": "Себестоимость",
                    "data": [row["cost"] for row in equipment_rows],
                }
            ],
            fmt="money",
            horizontal=True,
            links=[_ids_link(SHIPMENTS, row["shipment_ids"]) for row in equipment_rows],
        ),
    }
    return {
        "top_parts": parts,
        "top_equipment": equipment_rows,
        "without_equipment_cost": equipment["without_equipment_cost"],
        "top_parts_height": _horizontal_chart_height(len(parts)),
        "top_equipment_height": _horizontal_chart_height(len(equipment_rows)),
        "charts": charts,
    }


class SparePartsView(AnalyticsTabView):
    tab_key = "spare_parts"
    form_class = SparePartFilterForm
    template_name = "analytics/spare_parts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.form.get_filters()
        source = spare_parts.SparePartSet.load()
        period, today = context["period"], context["today"]
        context.update(filters=filters, charts={})
        context.update(_overview_context(source, filters, period, today))
        context.update(_movement_context(source, filters, period, today))
        return context
