from decimal import Decimal

from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.db import models
from django.db.models import Sum
from django.forms import Textarea
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from utils import MainModelAdmin
from .models import Contract, Payment, ContractExpense


class ClientNameOnlyAutocompleteSelect(AutocompleteSelect):
    """Autocomplete-виджет клиента, отображающий только наименование без ИНН."""

    def get_result_label(self, result):
        return result.name

    def label_from_instance(self, obj):
        return obj.name


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


def format_money(value):
    """Форматирует сумму: 20000.00 -> 20 000,00"""
    if value is None:
        return "—"
    # Python format with comma thousands separator and dot decimal
    formatted = f"{value:,.2f}"
    # Convert to Russian style: space thousands, comma decimal
    return formatted.replace(",", " ").replace(".", ",")


@admin.register(Contract)
class ContractAdmin(MainModelAdmin):
    inlines = (PaymentInline, ContractExpenseInline)
    autocomplete_fields = ("client",)
    date_hierarchy = "conclusion_date"
    list_display = (
        "contract_number",
        "client_display",
        "conclusion_date",
        "contract_amount",
        "payment_amount",
        "expenses_amount",
        "debt",
        "profit",
        "services_provided",
        "payment_status_colored",
    )
    list_filter = ("payment_status",)
    search_fields = (
        "contract_number",
        "order_number_1c",
        "client__name",
        "client__inn",
    )
    search_help_text = "Поиск по номеру контракта, номеру заказа 1С, наименованию клиента или ИНН"

    class Media:
        css = {"all": ("contracts/css/contract_changelist.css", "contracts/css/contract_spare_parts.css",)}

    formfield_overrides = {
        models.TextField: {"widget": Textarea(attrs={"rows": 3})},
    }

    readonly_fields = (
        "payment_amount_display",
        "expenses_amount_display",
        "debt_display",
        "profit_display",
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
                "fields": ("services_provided", "note"),
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
                    ("payment_amount_display", "expenses_amount_display", "debt_display", "profit_display"),
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

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            cl = response.context_data["cl"]
        except (AttributeError, KeyError):
            return response

        totals = cl.queryset.aggregate(
            contract_amount=Sum("contract_amount"),
            payment_amount=Sum("payment_amount"),
            expenses_amount=Sum("expenses_amount"),
            debt=Sum("debt"),
            profit=Sum("profit"),
        )
        response.context_data["totals"] = {
            "contract_amount": format_money(totals.get("contract_amount")),
            "payment_amount": format_money(totals.get("payment_amount")),
            "expenses_amount": format_money(totals.get("expenses_amount")),
            "debt": format_money(totals.get("debt")),
            "profit": format_money(totals.get("profit")),
        }
        return response

    @admin.display(description="Оплата?", ordering="payment_status")
    def payment_status_colored(self, obj):
        status = obj.payment_status
        label = obj.get_payment_status_display()
        return format_html(
            '<span class="payment-status-{}">{}</span>',
            status,
            label,
        )

    @admin.display(description="Клиент")
    def client_display(self, obj):
        return obj.client.name if obj.client else "—"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "client":
            kwargs["widget"] = ClientNameOnlyAutocompleteSelect(
                db_field,
                self.admin_site,
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Запчасти по контракту")
    def spare_part_shipments_display(self, obj):
        """Отображает все запчасти из отгрузок по контракту."""
        from django.db.models import Prefetch
        from spare_part.models import SparePartShipmentM2M

        lines = (
            obj.spare_part_shipments
            .prefetch_related(
                Prefetch(
                    "shipment_m2m",
                    queryset=SparePartShipmentM2M.objects.select_related(
                        "spare_part__unit"
                    ).order_by("create_dt"),
                ),
            )
            .order_by("shipment_dt")
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
                        "<td class='num'>{}</td>"
                        "<td class='num'>{}</td>"
                        "<td class='num'>{}</td>"
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
            "<div class='spare-parts-contract-wrapper'>"
            "<table class='spare-parts-contract-table'>"
            "<thead><tr>"
            "<th>Наименование</th>"
            "<th>Ед. изм.</th>"
            "<th class='num'>Кол-во</th>"
            "<th class='num'>Цена</th>"
            "<th class='num'>Сумма</th>"
            "<th>Отгрузка</th>"
            "<th>Дата</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "<tfoot><tr>"
            "<td colspan='4' class='num'>Итого:</td>"
            f"<td class='num'>{total:.2f}</td>"
            "<td colspan='2'></td>"
            "</tr></tfoot>"
            "</table>"
            "</div>"
        )
        return mark_safe(html)

    @admin.display(description="Сумма оплат")
    def payment_amount_display(self, obj):
        return mark_safe(f"<span class='finance-value'>{format_money(obj.payment_amount)}</span>")

    @admin.display(description="Затраты")
    def expenses_amount_display(self, obj):
        return mark_safe(f"<span class='finance-value'>{format_money(obj.expenses_amount)}</span>")

    @admin.display(description="Долг")
    def debt_display(self, obj):
        return mark_safe(f"<span class='finance-value'>{format_money(obj.debt)}</span>")

    @admin.display(description="Прибыль")
    def profit_display(self, obj):
        return mark_safe(f"<span class='finance-value'>{format_money(obj.profit)}</span>")
