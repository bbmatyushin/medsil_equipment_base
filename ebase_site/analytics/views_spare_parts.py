"""Вкладка «Запчасти» раздела «Аналитика»."""

from .charts import chart_spec
from .filters import SparePartFilterForm, month_label
from .links import change_url, changelist_url
from .services import spare_parts
from .views import MAX_LINK_IDS, AnalyticsTabView, _horizontal_chart_height

SPARE_PARTS = "spare_part_sparepart"
COUNTS = "spare_part_sparepartcount"
SUPPLIES = "spare_part_sparepartsupplyv2"
SHIPMENTS = "spare_part_sparepartshipmentv2"
ARCHIVE_SUPPLIES = "spare_part_sparepartsupply"
ARCHIVE_SHIPMENTS = "spare_part_sparepartshipment"
QUALITY_TARGETS = {
    "counts": COUNTS,
    "supplies": SUPPLIES,
    "shipments": SHIPMENTS,
    "archive_supplies": ARCHIVE_SUPPLIES,
    "archive_shipments": ARCHIVE_SHIPMENTS,
}
STOCK_ROWS_LIMIT = 100
STOCK_CONTROL_LIMIT = 50


def _ids_link(admin_name, ids) -> str | None:
    """Ссылка на конкретные документы, если список не слишком длинный."""
    ids = list(ids)
    if not ids or len(ids) > MAX_LINK_IDS:
        return None
    return changelist_url(admin_name, id__in=ids)


def _stock_page_number(request, pages: int) -> int:
    """Номер страницы складской таблицы; мусор и выход за диапазон — первая."""
    try:
        page = int(request.GET.get("stock_page", ""))
    except ValueError:
        return 1
    return page if 1 <= page <= pages else 1


def _page_url(request, page: int) -> str:
    """Ссылка на страницу складской таблицы с сохранением фильтров."""
    params = request.GET.copy()
    if page == 1:
        params.pop("stock_page", None)
    else:
        params["stock_page"] = page
    query = params.urlencode()
    return f"{request.path}?{query}" if query else request.path


def _overview_context(source, filters, period, today, request) -> dict:
    """Плитки и основная таблица текущего склада."""
    kpis = spare_parts.overview_kpis(period, today, filters, source)
    rows = spare_parts.stock_rows(period, today, filters, source)
    pages = max(1, -(-len(rows) // STOCK_ROWS_LIMIT))
    page = _stock_page_number(request, pages)
    start = (page - 1) * STOCK_ROWS_LIMIT
    page_rows = rows[start : start + STOCK_ROWS_LIMIT]
    for row in page_rows:
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
        {
            "label": "Просрочено",
            "value": kpis["expired_value"],
            "kind": "money",
            "note": "оценка на сегодня",
        },
        {
            "label": "Неликвиды",
            "value": kpis["nonmoving_value"],
            "kind": "money",
            "note": "без отгрузок 365 дней",
        },
    ]
    return {
        "tiles": tiles,
        "stock_rows": page_rows,
        "stock_rows_total": len(rows),
        "stock_rows_from": start + 1,
        "stock_rows_to": start + len(page_rows),
        "stock_page": page,
        "stock_pages": pages,
        "stock_page_links": [
            {
                "page": number,
                "url": _page_url(request, number),
                "active": number == page,
            }
            for number in range(1, pages + 1)
        ],
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


def _expiration_context(source, filters, today) -> dict:
    """Корзины сроков годности и ссылки на складские записи."""
    rows = spare_parts.expiration_rows(today, filters, source)
    for row in rows:
        row["url"] = _ids_link(COUNTS, row["count_ids"])
        row["too_many"] = len(row["count_ids"]) > MAX_LINK_IDS
    chart = chart_spec(
        "bar",
        [row["label"] for row in rows],
        [{"label": "Оценочная стоимость", "data": [row["value"] for row in rows]}],
        fmt="money",
        horizontal=True,
        links=[row["url"] for row in rows],
    )
    return {
        "expiration_rows": rows,
        "expiration_height": _horizontal_chart_height(len(rows)),
        "charts": {"expiration": chart},
    }


def _control_context(source, filters, today) -> dict:
    """Неликвиды, пополнение и ошибки учёта."""
    nonmoving = spare_parts.nonmoving_rows(today, filters, source)
    restock = spare_parts.restock_rows(today, filters, source)
    quality = spare_parts.data_quality(today, filters, source)
    for row in quality:
        row["url"] = _ids_link(QUALITY_TARGETS[row["target"]], row["ids"])
        row["too_many"] = len(row["ids"]) > MAX_LINK_IDS
    return {
        "nonmoving_rows": {
            days: rows[:STOCK_CONTROL_LIMIT] for days, rows in nonmoving.items()
        },
        "nonmoving_total": {days: len(rows) for days, rows in nonmoving.items()},
        "nonmoving_blocks": [
            {
                "days": days,
                "rows": rows[:STOCK_CONTROL_LIMIT],
                "total": len(rows),
            }
            for days, rows in nonmoving.items()
        ],
        "restock_rows": restock[:STOCK_CONTROL_LIMIT],
        "restock_total": len(restock),
        "stock_control_limit": STOCK_CONTROL_LIMIT,
        "data_quality": quality,
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
        context.update(_overview_context(source, filters, period, today, self.request))
        context.update(_movement_context(source, filters, period, today))
        expiration = _expiration_context(source, filters, today)
        context["charts"].update(expiration.pop("charts"))
        context.update(expiration)
        context.update(_control_context(source, filters, today))
        return context
