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
    list_filter = (
        "services_provided",
        "payment_status",
        "conclusion_date",
        "client",
    )
    search_fields = ("contract_number", "order_number_1c")
    search_help_text = "Поиск по номеру контракта или номеру заказа 1С"
    readonly_fields = (
        "payment_amount",
        "expenses_amount",
        "debt",
        "profit",
        "service_expenses_display",
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
                "fields": ("service_expenses_display",),
                "description": "Запчасти, списанные на ремонт, связанный с этим контрактом.",
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

    @admin.display(description="Расходы по запчастям")
    def service_expenses_display(self, obj):
        """Отображает запчасти, списанные на связанный ремонт."""
        service = obj.service.first()
        if not service:
            return "Нет связанного ремонта."

        expenses = service.service_expenses.select_related("spare_part").all()
        if not expenses:
            service_url = reverse(
                "admin:ebase_service_change", args=[service.id]
            )
            return format_html(
                "Ремонт <a href='{}'>привязан</a>, но запчасти ещё не добавлены.",
                service_url,
            )

        service_url = reverse("admin:ebase_service_change", args=[service.id])
        rows = []
        for exp in expenses:
            part_name = exp.spare_part.name if exp.spare_part else "—"
            rows.append(
                format_html(
                    "<tr>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "</tr>",
                    part_name,
                    exp.unit,
                    exp.quantity,
                    f"{exp.price:.2f}",
                    f"{exp.sum:.2f}",
                )
            )

        total = sum(e.sum for e in expenses)
        html = (
            f"<table style='border-collapse: collapse; width: 100%;'>"
            f"<thead><tr>"
            f"<th style='text-align: left; padding: 4px 8px;'>Наименование</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Ед. изм.</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Кол-во</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Цена</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Сумма</th>"
            f"</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"<tfoot><tr>"
            f"<td colspan='4' style='text-align: right; padding: 4px 8px;'><b>Итого:</b></td>"
            f"<td style='text-align: right; padding: 4px 8px;'><b>{total:.2f}</b></td>"
            f"</tr></tfoot>"
            f"</table>"
            f"<p style='margin-top: 8px;'><a href='{service_url}'>Перейти к ремонту →</a></p>"
        )
        return format_html(html)
