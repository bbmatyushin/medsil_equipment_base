from datetime import datetime
from decimal import Decimal
import logging

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Sum
from utils import MainModelAdmin
from ebase.models import Service, EquipmentAccDepartment

# from ebase_site.ebase.models import Service, EquipmentAccDepartment

from .models import (
    SparePartAccessories,
    SparePart,
    SparePartCount,
    SparePartSupply,
    SparePartShipment,
    SparePartShipmentV2,
    SparePartPhoto,
    SparePartSupplyV2,
    SparePartSupplyItem,
)
from .forms import *
from .admin_filters import WhoShipment

logger = logging.getLogger("spare_part")


@admin.register(SparePartAccessories)
class SparePartAccessoriesAdmin(MainModelAdmin):
    list_display = (
        "id",
        "name",
        "create_dt",
    )
    list_display_links = ("name",)
    search_fields = ("name",)
    search_help_text = "Поиск по названию комплектующего"
    ordering = ("name",)

    fieldsets = (
        (
            "Комплектующие к прибору",
            {
                "fields": (
                    "name",
                    "description",
                ),
            },
        ),
    )


class SparePartPhotoInline(admin.StackedInline):
    model = SparePartPhoto
    # classes = ['wide',]
    fk_name = "spare_part"
    extra = 1
    readonly_fields = ("s_part_photo",)
    verbose_name = "ФОТО ЗАПЧАСТИ"
    verbose_name_plural = "ФОТО ЗАПЧАСТИ"

    fieldsets = (
        (
            "",
            {
                # 'classes': ('collapse',),
                "fields": (("photo", "s_part_photo"),)
            },
        ),
    )

    @admin.display(description="Изображение")
    def s_part_photo(self, obj):
        if obj.photo:
            return mark_safe(
                f"<a href='{obj.photo.url}' target='_blank'>"
                f"<img src='{obj.photo.url}' width=50>"
                f"</a>"
            )
        return f"Нет изображения"


@admin.register(SparePart)
class SparePartAdmin(MainModelAdmin):
    form = SparePartForm

    autocomplete_fields = ("unit",)
    inlines = (SparePartPhotoInline,)
    list_display = (
        "article",
        "name",
        "photo",
        "amount",
        "unit",
        "is_expiration",
        "equipment_name",
    )
    list_display_links = (
        "article",
        "name",
    )
    search_fields = (
        "name",
        "article",
        "equipment__full_name",
    )
    search_help_text = "Поиск по названию, артикулу запчасти или по оборудованию"
    ordering = ("name", "article")
    filter_horizontal = ("equipment",)
    # list_select_related = ('unit',)
    list_select_related = True
    list_filter = ("is_expiration",)

    fieldsets = (
        (
            "Новая запчасть",
            {
                "fields": (
                    "article",
                    ("name", "unit"),
                    "is_expiration",
                    "equipment",
                )
            },
        ),
    )

    class Media:
        js = ("admin/js/jquery.init.js",)

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/get_expiration_dates/",
                self.admin_site.admin_view(self.get_expiration_dates),
                name="spare_part_get_expiration_dates",
            ),
        ]
        return custom_urls + urls

    def get_expiration_dates(self, request, object_id):
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        from django.utils.dateformat import format

        spare_part = get_object_or_404(SparePart, pk=object_id)

        # Get available expiration dates from SparePartCount where amount > 0
        available_dates = (
            spare_part.spare_part_count_spare_part.filter(amount__gt=0)
            .values("expiration_dt", "amount")
            .order_by("expiration_dt")
        )

        # Format dates for display
        formatted_dates = []
        for date_info in available_dates:
            if date_info["expiration_dt"]:
                display_date = format(date_info["expiration_dt"], "d E Y")
                formatted_dates.append(
                    {
                        "date": date_info["expiration_dt"].isoformat(),
                        "display": display_date,
                        "amount": (
                            int(date_info["amount"])
                            if date_info["amount"] % 1 == 0
                            else date_info["amount"]
                        ),
                    }
                )

        return JsonResponse(
            {
                "is_expiration": spare_part.is_expiration,
                "available_dates": formatted_dates,
                "unit": spare_part.unit.short_name if spare_part.unit else None,
            }
        )

    @admin.display(description="Оборудование")
    def equipment_name(self, obj):
        equipment_list = obj.equipment.values_list("full_name", flat=True)
        return ", ".join(equipment_list)

    @admin.display(description="Кол-во")
    def amount(self, obj):
        amount = (
            obj.spare_part_count_spare_part.aggregate(Sum("amount"))["amount__sum"] or 0
        )
        amount = amount if amount % 1 else int(amount)
        return amount

    @admin.display(description="Фото", boolean=True)
    def photo(self, obj):
        return True if obj.spare_part_photo.values() else False


@admin.register(SparePartCount)
class SparePartCountAdmin(MainModelAdmin):
    form = SparePartCountForm

    autocomplete_fields = ("spare_part",)
    list_display = (
        "spare_part",
        "unit_field",
        "amount_field",
        "expiration_dt",
        "is_overdue",
    )
    list_filter = ("is_overdue",)
    search_fields = (
        "spare_part__name",
        "spare_part__article",
    )
    search_help_text = "Поиск по названию запчасти или её артикулу"
    ordering = (
        "spare_part__name",
        "-amount",
    )

    fieldsets = (
        (
            "Новый остаток",
            {
                "fields": (
                    "spare_part",
                    ("amount", "expiration_dt"),
                )
            },
        ),
    )

    @admin.display(description="Количество")
    def amount_field(self, obj):
        return obj.amount if obj.amount % 1 else int(obj.amount)

    @admin.display(description="Ед. изм.")
    def unit_field(self, obj):
        return obj.spare_part.unit.short_name if obj.spare_part.unit else "-"

    def get_queryset(self, request):
        """Обноление состояни просроченности при отображение страницы"""
        today = timezone.now().date()
        qs = super().get_queryset(request)
        qs = qs.select_related("spare_part__unit")
        qs.filter(expiration_dt__lt=today).update(is_overdue=False)
        return qs

    def get_search_results(self, request, queryset, search_term):
        """Переопределяем выдачу для autocomplete_fields"""
        if request.GET.get("model_name") == "sparepartshipment":
            # При добавлении отгрузки запчасти, покажется только список с кол-вом больше 0
            qs = queryset.filter(amount__gt=0)
            return qs, False
        return super().get_search_results(request, queryset, search_term)


@admin.register(SparePartSupply)
class SparePartSupplyAdmin(MainModelAdmin):
    form = SparePartSupplyForm

    autocomplete_fields = ("spare_part",)
    date_hierarchy = "supply_dt"
    list_display = (
        "spare_part",
        "count_part",
        "doc_num",
        "supply_dt",
        "expiration_dt",
        "user",
    )
    search_fields = (
        "spare_part__name",
        "spare_part__article",
    )
    search_help_text = "Поиск по названию запчасти или её артикулу"
    ordering = ("-supply_dt", "spare_part__name")

    fieldsets = (
        (
            "Новая поставка",
            {
                # 'classes': ('wide',),
                "fields": (
                    "spare_part",
                    "doc_num",
                    (
                        "count_supply",
                        "expiration_dt",
                    ),
                    "supply_dt",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_archive_notice"] = True
        return super().changelist_view(request, extra_context=extra_context)

    @admin.display(description="КОЛ-ВО")
    def count_part(self, obj):
        return obj.count_supply if obj.count_supply % 1 else int(obj.count_supply)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        elif not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)


class SparePartShipmentM2MInline(admin.TabularInline):
    model = SparePartShipmentM2M
    form = SparePartShipmentM2MForm
    extra = 1
    autocomplete_fields = ("spare_part",)
    fields = ("spare_part", "unit_display", "quantity", "expiration_dt")
    readonly_fields = ("create_dt", "unit_display")

    def get_extra(self, request, obj=None, **kwargs):
        # Если отгрузка создана из Ремонта оборудования — не даём добавлять новые строки
        if obj and obj.service:
            return 0
        return super().get_extra(request, obj, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        # Если объект существует и связан с Service, делаем поля недоступными для редактирования
        if obj and obj.service:
            for field_name in formset.form.base_fields:
                formset.form.base_fields[field_name].disabled = True
                formset.form.base_fields[field_name].widget.attrs["readonly"] = True

        return formset

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "spare_part__unit",
            "shipment",
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "spare_part":
            kwargs["queryset"] = SparePart.objects.select_related("unit")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Ед. изм.")
    def unit_display(self, obj):
        return obj.spare_part.unit.short_name if obj.spare_part.unit else "-"


@admin.register(SparePartShipmentV2)
class SparePartShipmentV2Admin(admin.ModelAdmin):
    form = SparePartShipmentV2Form
    inlines = [
        SparePartShipmentM2MInline,
    ]

    list_display = (
        "doc_num",
        "shipment_dt",
        "client_shipment",
        "service_equipment",
        "contract_link",
        "user_name",
    )
    readonly_fields = ("client_shipment",)
    autocomplete_fields = ("contract",)
    ordering = ("-shipment_dt",)
    search_fields = (
        "service__equipment_accounting__equipment__short_name",
        "service__equipment_accounting__equipment_acc_department_equipment_accounting__department__name",
    )
    search_help_text = "Поиск по клиенту или названию оборудования"

    fieldsets = (
        (
            "ИНФОРМАЦИЯ ПО ОТГРУЗКЕ",
            {
                "fields": (
                    (
                        "doc_num",
                        "shipment_dt",
                    ),
                    ("service", "client_shipment"),
                    "contract",
                    "comment",
                    "user",
                )
            },
        ),
    )

    class Media:
        css = {"all": ("spare_part/css/hide_datetime_shortcuts.css",)}
        js = (
            "admin/js/jquery.init.js",
            "spare_part/js/remove_datetime_shortcuts.js",
            "spare_part/js/expiration_dt_control.js",
        )

    @admin.display(description="Создал")
    def user_name(self, obj):
        return obj.user if obj.user else "-"

    @admin.display(description="Клиент")
    def client_shipment(self, obj):
        client = "--"
        if obj.service:
            client = obj.service.equipment_accounting.equipment_acc_department_equipment_accounting.values_list(
                "department__name", flat=True
            )[
                0
            ]

        return client

    @admin.display(description="Оборудование")
    def service_equipment(self, obj):
        equipment = "--"
        if obj.service:
            equipment = obj.service.equipment_accounting.equipment.short_name

        return equipment

    @admin.display(description="Контракт")
    def contract_link(self, obj):
        if obj.contract:
            url = reverse("admin:contracts_contract_change", args=[obj.contract.id])
            return format_html('<a href="{}">{}</a>', url, obj.contract.contract_number)
        return "--"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # оптимизация: подгружаем связанные объекты и инлайн-запчасти
        return qs.select_related(
            "user",
            "service__equipment_accounting__equipment",  # Добавляем связи для департаментов
            "contract",
        ).prefetch_related("spare_part", "service")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Поле «Ремонт оборудования» неактивно:
        #   — при создании новой отгрузки вручную (obj is None)
        #   — при редактировании отгрузки, созданной пользователем (is_auto_comment != True)
        # Заполняется автоматически только при создании из карточки Ремонта.
        if obj is None:
            form.base_fields["service"].disabled = True
        elif obj and not obj.is_auto_comment:
            form.base_fields["service"].disabled = True
        elif obj and obj.is_auto_comment and obj.service:
            # Авто-отгрузка со связью: убираем пустой выбор «---------»
            form.base_fields["service"].empty_label = None
            form.base_fields["service"].required = True
        if obj and obj.is_auto_comment and obj.service:
            form.base_fields["contract"].disabled = True
            form.base_fields["contract"].widget.attrs["readonly"] = True
        return form

    def get_changeform_initial_data(self, request):
        """Устанавливает начальные значения при открытии формы"""
        return {
            "user": request.user,
            "shipment_dt": datetime.now(),
        }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service":
            qs = Service.objects.select_related(
                "service_type", "equipment_accounting__equipment", "user"
            )

            # Для авто-отгрузки (is_auto_comment=True) — сужаем queryset до текущего ремонта,
            # чтобы нельзя было переключиться на другой.
            object_id = request.resolver_match.kwargs.get("object_id")
            if object_id:
                try:
                    obj = self.get_object(request, object_id)
                    if obj and obj.is_auto_comment and obj.service:
                        qs = qs.filter(pk=obj.service.pk)
                except self.model.DoesNotExist:
                    pass

            kwargs["queryset"] = qs
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        """Учёт остатков полностью обслуживается сигналами модели SparePartShipmentM2M."""
        super().save_related(request, form, formsets, change)

    def save_model(self, request, obj, form, change):
        # Сохраняем основную модель
        super().save_model(request, obj, form, change)


class SparePartSupplyItemInline(admin.TabularInline):
    model = SparePartSupplyItem
    extra = 1
    verbose_name = "Запчасть поставки"
    verbose_name_plural = "Запчасти поставки"
    autocomplete_fields = ("spare_part",)
    fields = ("spare_part", "unit_display", "quantity", "price", "sum", "expiration_dt")
    readonly_fields = ("unit_display", "sum")

    def unit_display(self, obj):
        return (
            obj.spare_part.unit.short_name
            if obj.spare_part and obj.spare_part.unit
            else "-"
        )

    unit_display.short_description = "Ед. изм."


@admin.register(SparePartSupplyV2)
class SparePartSupplyV2Admin(MainModelAdmin):
    form = SparePartSupplyV2Form
    inlines = [SparePartSupplyItemInline]
    list_display = ("doc_num", "supply_dt", "total_sum", "user")
    readonly_fields = ("user",)
    ordering = ("-supply_dt",)
    search_fields = ("doc_num", "items__spare_part__name", "items__spare_part__article")
    search_help_text = "Поиск по номеру документа, названию или артикулу запчасти"
    date_hierarchy = "supply_dt"
    list_select_related = ("user",)

    fieldsets = (
        (
            "Информация о поставке",
            {
                "fields": (("doc_num", "supply_dt"), "note"),
            },
        ),
    )

    class Media:
        css = {"all": ("spare_part/css/hide_datetime_shortcuts.css",)}
        js = (
            "admin/js/jquery.init.js",
            "spare_part/js/remove_datetime_shortcuts.js",
            "spare_part/js/supply_expiration_control.js",
        )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items__spare_part__unit")

    def get_search_results(self, request, queryset, search_term):
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        if not use_distinct:
            qs = qs.distinct()
        return qs, True

    @admin.display(description="Сумма поставки")
    def total_sum(self, obj):
        return sum((item.sum or Decimal("0") for item in obj.items.all()), Decimal("0"))

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(SparePartShipment)
class SparePartShipmentAdmin(MainModelAdmin):
    form = SparePartShipmentForm

    autocomplete_fields = ("spare_part_count",)
    date_hierarchy = "shipment_dt"
    list_display = (
        "spare_part_name",
        "count_shipment_part",
        "exp_dt",
        "doc_num",
        "shipment_dt",
        "user",
    )
    search_fields = (
        "spare_part_count__spare_part__name",
        "spare_part_count__spare_part__article",
    )
    search_help_text = "Поиск по названию запчасти или её артикулу"
    ordering = (
        "-shipment_dt",
        "spare_part_count__spare_part__name",
    )
    list_select_related = True
    list_filter = (WhoShipment,)

    fieldsets = (
        (
            "Новая отгрузка",
            {
                "fields": (
                    "spare_part_count",
                    ("doc_num", "shipment_dt"),
                    "count_shipment",
                    "comment",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_archive_notice"] = True
        return super().changelist_view(request, extra_context=extra_context)

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "spare_part/js/remove_shipment_add_link.js",
        )

    @admin.display(description="Запчасть")
    def spare_part_name(self, obj):
        if obj.spare_part_count is None:
            return "—"
        return obj.spare_part_count.spare_part.name

    @admin.display(description="Кол-во")
    def count_shipment_part(self, obj):
        return obj.count_shipment if obj.count_shipment % 1 else int(obj.count_shipment)

    @admin.display(description="Годен до")
    def exp_dt(self, obj):
        if obj.spare_part_count is None:
            return "—"
        return (
            obj.spare_part_count.expiration_dt
            if obj.spare_part_count.expiration_dt
            else "-"
        )

    # def get_search_results(self, request, queryset, search_term):
    #     """Переопределяем выдачу для autocomplete_fields"""
    #     if search_term:
    #         qs = queryset.filter(spare_part_count__spare_part__name='CaTr')
    #         return qs, False
    #     return super().get_search_results(request, queryset, search_term)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        elif not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)
