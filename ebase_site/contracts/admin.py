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
        """Временная заглушка до реализации отображения запчастей из отгрузок."""
        return "Запчасти по контракту будут отображены из отгрузок (в разработке)."
