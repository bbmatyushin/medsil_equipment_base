from django.contrib import admin
from django.db.models import Max
from django.utils.html import mark_safe

from business_trip.forms import BusinessTripForm
from business_trip.models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
    BusinessTripPhoto,
    ExpenseType,
)
from users.models import CompanyUser
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
    verbose_name = "Подразделение"
    verbose_name_plural = "Подразделения"
    autocomplete_fields = ("department",)

    fields = ("department", "city_display", "beg_dt", "end_dt")
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

    fields = ("expense_type", "amount", "date", "comment")

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


class EmployeeUsedInTripsFilter(admin.SimpleListFilter):
    """Фильтр по сотруднику: только те, кто фигурирует в карточках командировок."""

    title = "Сотрудник"
    parameter_name = "employee"

    def lookups(self, request, model_admin):
        employees = (
            CompanyUser.objects.filter(business_trip_employee__isnull=False)
            .distinct()
            .order_by("last_name", "first_name", "patron")
        )
        return [(e.pk, str(e)) for e in employees]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(employee_id=self.value())
        return queryset


@admin.register(BusinessTrip)
class BusinessTripAdmin(MainModelAdmin):
    date_hierarchy = "beg_dt"
    list_filter = (EmployeeUsedInTripsFilter, "service_type")
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
    autocomplete_fields = ("service_type",)
    readonly_fields = ("allowance_amount_display",)
    form = BusinessTripForm

    fieldsets = (
        (
            "Командировка",
            {
                "fields": (
                    ("doc_number", "creation_date"),
                    ("employee",),
                    ("beg_dt", "end_dt"),
                    ("allowance_amount_display",),
                    ("service_type",),
                    ("contract",),
                )
            },
        ),
        (
            "Дополнительно",
            {"fields": ("task", "take_with", "comment", "report")},
        ),
    )

    class Media:
        css = {"all": ("business_trip/css/business_trip.css",)}
        js = (
            "admin/js/jquery.init.js",
            "business_trip/js/business_trip.js",
        )

    @admin.display(description="Командировочные")
    def allowance_amount_display(self, obj):
        """Командировочные (суточные).

        Рендерится как readonly-поле с <input disabled>, чтобы значение нельзя
        было изменить вручную, но JavaScript мог обновлять сумму на лету при
        изменении дат выезда/возвращения.
        """
        from django.utils.html import format_html

        value = obj.allowance_amount if obj and obj.pk else 0
        return format_html(
            '<input type="text" id="id_allowance_amount" value="{}" disabled>'
            '<span class="help" '
            'style="display:block; font-size:0.6875rem; color:var(--body-quiet-color, #666);">'
            "Дни × 700 руб.</span>",
            value,
        )

    list_display = (
        "doc_number",
        "employee",
        "departments_display",
        "cities_display",
        "beg_dt",
        "end_dt",
        "days_count",
        "allowance_amount_column",
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
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            if "employee" in form.base_fields:
                form.base_fields["employee"].initial = request.user.id
            if "doc_number" in form.base_fields:
                max_num = (
                    BusinessTrip.objects.aggregate(max_num=Max("doc_number"))["max_num"]
                    or 0
                )
                form.base_fields["doc_number"].initial = max_num + 1
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Подразделение")
    def departments_display(self, obj):
        # obj из prefetch_related destinations — без N+1
        departments = []
        for dest in obj.destinations.all():
            name = dest.department.name if dest.department else "—"
            if name not in departments:
                departments.append(name)
        return ", ".join(departments) if departments else "—"

    @admin.display(description="Города")
    def cities_display(self, obj):
        # obj из prefetch_related destinations — без N+1
        cities = []
        for dest in obj.destinations.all():
            city_name = dest.city.name if dest.city else "—"
            if city_name not in cities:
                cities.append(city_name)
        return ", ".join(cities) if cities else "—"

    @admin.display(description="Кол-во дней")
    def days_count(self, obj):
        return obj.days_count

    @admin.display(description="Сумма", ordering="allowance_amount")
    def allowance_amount_column(self, obj):
        return obj.allowance_amount

    @admin.display(boolean=True, description="Фото")
    def has_photos(self, obj):
        return obj.photos.exists()
