from decimal import Decimal

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from utils import MainModelAdmin
from .models import Contract, Payment, ContractExpense


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1
    verbose_name = "Оплата"
    verbose_name_plural = "Оплаты"


class ContractExpenseInline(admin.TabularInline):
    model = ContractExpense
    extra = 1
    verbose_name = "Расход"
    verbose_name_plural = "Расходы"
    fields = (
        "expense_type",
        "name",
        "unit",
        "quantity",
        "cost",
        "sum",
        "date",
    )
    readonly_fields = ("sum", "create_dt")


@admin.register(Contract)
class ContractAdmin(MainModelAdmin):
    inlines = (PaymentInline, ContractExpenseInline)
    autocomplete_fields = ("client",)
    date_hierarchy = "conclusion_date"
    list_display = (
        "contract_number",
        "client",
        "conclusion_date",
        "contract_amount",
        "payment_amount",
        "expenses_amount",
        "debt",
        "profit",
        "services_provided",
        "payment_status",
    )
    list_filter = ()
    search_fields = ("contract_number", "order_number_1c")
    search_help_text = "Поиск по номеру контракта или номеру заказа 1С"
    readonly_fields = (
        "payment_amount",
        "expenses_amount",
        "debt",
        "profit",
        "spare_part_shipments_display",
    )
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    ("contract_number", "order_number_1c"),
                    "client",
                    ("conclusion_date", "service_end_date"),
                    "contract_amount",
                    "period",
                    "documentation_link",
                ),
            },
        ),
        (
            "Статусы и примечание",
            {
                "fields": ("services_provided", "payment_status", "note"),
            },
        ),
        (
            "Запчасти по контракту",
            {
                "fields": ("spare_part_shipments_display",),
                "description": "Запчасти, отгруженные по данному контракту.",
            },
        ),
        (
            "Финансы",
            {
                "fields": (
                    ("payment_amount", "expenses_amount", "debt", "profit"),
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("client", "client__city")
        )

    @admin.display(description="Запчасти по контракту")
    def spare_part_shipments_display(self, obj):
        """Отображает все запчасти из отгрузок по контракту."""
        lines = (
            obj.spare_part_shipments
            .prefetch_related("shipment_m2m__spare_part__unit")
            .order_by("shipment_dt", "shipment_m2m__create_dt")
        )

        rows = []
        total = Decimal("0.00")
        for shipment in lines:
            for line in shipment.shipment_m2m.all():
                part_name = line.spare_part.name if line.spare_part else "—"
                unit = line.spare_part.unit.short_name if line.spare_part and line.spare_part.unit else "—"
                rows.append(
                    format_html(
                        "<tr>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "</tr>",
                        part_name,
                        unit,
                        line.quantity,
                        f"{line.price:.2f}",
                        f"{line.sum:.2f}",
                        shipment.doc_num,
                        shipment.shipment_dt.strftime("%d.%m.%Y"),
                    )
                )
                total += line.sum or Decimal("0.00")

        if not rows:
            return "Нет отгрузок запчастей по контракту."

        html = (
            f"<table style='border-collapse: collapse; width: 100%;'>"
            f"<thead><tr>"
            f"<th style='text-align: left; padding: 4px 8px;'>Наименование</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Ед. изм.</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Кол-во</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Цена</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Сумма</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Отгрузка</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Дата</th>"
            f"</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"<tfoot><tr>"
            f"<td colspan='4' style='text-align: right; padding: 4px 8px;'><b>Итого:</b></td>"
            f"<td style='text-align: right; padding: 4px 8px;'><b>{total:.2f}</b></td>"
            f"<td colspan='2'></td>"
            f"</tr></tfoot>"
            f"</table>"
        )
        return format_html(html)
