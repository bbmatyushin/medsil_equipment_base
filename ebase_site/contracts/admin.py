from django.contrib import admin

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
        "comment",
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
        "create_dt",
    )
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "contract_number",
                    "order_number_1c",
                    "client",
                    ("conclusion_date", "service_end_date"),
                    "period",
                    "documentation_link",
                ),
            },
        ),
        (
            "Финансы",
            {
                "fields": (
                    "contract_amount",
                    ("payment_amount", "expenses_amount"),
                    ("debt", "profit"),
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
            "Служебная информация",
            {
                "fields": ("create_dt",),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("client", "client__city")
