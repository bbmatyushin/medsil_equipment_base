"""Вкладка «Запчасти» раздела «Аналитика»."""

from .filters import SparePartFilterForm
from .links import change_url
from .services import spare_parts
from .views import AnalyticsTabView

SPARE_PARTS = "spare_part_sparepart"
STOCK_ROWS_LIMIT = 100


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


class SparePartsView(AnalyticsTabView):
    tab_key = "spare_parts"
    form_class = SparePartFilterForm
    template_name = "analytics/spare_parts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.form.get_filters()
        source = spare_parts.SparePartSet.load()
        context.update(filters=filters, charts={})
        context.update(_overview_context(source, filters, context["period"], context["today"]))
        return context
