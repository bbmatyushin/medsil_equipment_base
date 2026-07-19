from django.contrib import admin
from django.db.models import Sum
from django.utils.html import mark_safe

from business_trip.models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
    BusinessTripPhoto,
    ExpenseType,
)
from utils import MainModelAdmin


@admin.register(ExpenseType)
class ExpenseTypeAdmin(MainModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    search_help_text = "Поиск по наименованию вида затрат"

    fieldsets = (("Новый вид затрат", {"fields": ("name",)}),)


class BusinessTripDestinationInline(admin.TabularInline):
    model = BusinessTripDestination
    extra = 1
    verbose_name = "Пункт командировки"
    verbose_name_plural = "Пункты командировки (подразделения)"
    autocomplete_fields = ("department",)

    fields = ("department", "beg_dt", "end_dt", "city_display")
    readonly_fields = ("city_display",)

    @admin.display(description="Город")
    def city_display(self, obj):
        return obj.city.name if obj.city else "—"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("department__city")


class BusinessTripExpenseInline(admin.TabularInline):
    model = BusinessTripExpense
    extra = 1
    verbose_name = "Затрата"
    verbose_name_plural = "Затраты на поездку"

    fields = ("date", "expense_type", "amount", "comment")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("expense_type")


class BusinessTripPhotoInline(admin.StackedInline):
    model = BusinessTripPhoto
    extra = 1
    verbose_name = "ФОТО ЧЕКА"
    verbose_name_plural = "ФОТО ЧЕКОВ"
    readonly_fields = ("photo_preview",)

    fieldsets = (("", {"fields": (("photo", "photo_preview"),)}),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("business_trip", "user")

    @admin.display(description="Изображение")
    def photo_preview(self, obj):
        if obj.photo:
            return mark_safe(
                f"<a href='{obj.photo.url}' target='_blank'>"
                f"<img src='{obj.photo.url}' width=50>"
                f"</a>"
            )
        return "Нет изображения"


@admin.register(BusinessTrip)
class BusinessTripAdmin(MainModelAdmin):
    date_hierarchy = "beg_dt"
    list_filter = ("employee", "service_type")
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "destinations__department__name",
        "destinations__department__city__name",
        "comment",
        "=doc_number",
    )
    search_help_text = (
        "Поиск по ФИО сотрудника, подразделению, городу, номеру документа"
    )
    filter_horizontal = ("service_type",)
    readonly_fields = ("allowance_amount",)

    fieldsets = (
        (
            "Командировка",
            {
                "fields": (
                    ("employee", "doc_number"),
                    ("beg_dt", "end_dt", "allowance_amount"),
                    ("service_type", "contract"),
                )
            },
        ),
        (
            "Дополнительно",
            {"fields": ("task", "take_with", "comment", "report")},
        ),
    )

    list_display = (
        "doc_number",
        "employee",
        "beg_dt",
        "end_dt",
        "days_count",
        "allowance_amount",
        "cities_display",
        "expenses_sum",
        "has_photos",
    )

    inlines = (
        BusinessTripDestinationInline,
        BusinessTripExpenseInline,
        BusinessTripPhotoInline,
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("employee", "contract")
            .prefetch_related(
                "destinations__department__city",
                "photos",
            )
            .annotate(_expenses_sum=Sum("expenses__amount"))
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # При создании новой записи подставляем текущего пользователя как сотрудника
        if obj is None and "employee" in form.base_fields:
            form.base_fields["employee"].initial = request.user.id
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Города")
    def cities_display(self, obj):
        # obj из prefetch_related destinations — без N+1
        cities = []
        for dest in obj.destinations.all():
            city_name = dest.city.name if dest.city else "—"
            if city_name not in cities:
                cities.append(city_name)
        return ", ".join(cities) if cities else "—"

    @admin.display(description="Затраты", ordering="_expenses_sum")
    def expenses_sum(self, obj):
        return obj._expenses_sum or 0

    @admin.display(boolean=True, description="Фото")
    def has_photos(self, obj):
        return obj.photos.exists()
