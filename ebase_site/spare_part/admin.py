from datetime import datetime

from django.contrib import admin
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.db.models import Sum, Prefetch, F
from django.db import transaction
from ebase.admin import MainAdmin
from ebase.models import Service, EquipmentAccDepartment
# from ebase_site.ebase.models import Service, EquipmentAccDepartment

from .models import *
from .forms import *
from .admin_filters import WhoShipment


class SparePartPhotoInline(admin.StackedInline):
    model = SparePartPhoto
    # classes = ['wide',]
    fk_name = 'spare_part'
    extra = 1
    readonly_fields = ('s_part_photo',)
    verbose_name = 'ФОТО ЗАПЧАСТИ'
    verbose_name_plural = 'ФОТО ЗАПЧАСТИ'

    fieldsets = (
        ('', {
            # 'classes': ('collapse',),
            'fields': (('photo', 's_part_photo'),)
        }),
    )

    @admin.display(description='Изображение')
    def s_part_photo(self, obj):
        if obj.photo:
            return mark_safe(f"<a href='{obj.photo.url}' target='_blank'>"
                             f"<img src='{obj.photo.url}' width=50>"
                             f"</a>")
        return f"Нет изображения"


@admin.register(SparePart)
class SparePartAdmin(MainAdmin):
    form = SparePartForm

    autocomplete_fields = ('unit',)
    inlines = (SparePartPhotoInline, )
    list_display = ('article', 'name', 'photo', 'amount', 'unit', 'is_expiration', 'equipment_name',)
    list_display_links = ('article', 'name',)
    search_fields = ('name', 'article', 'equipment__full_name',)
    search_help_text = 'Поиск по названию, артикулу запчасти или по оборудованию'
    ordering = ('name', 'article')
    filter_horizontal = ('equipment',)
    # list_select_related = ('unit',)
    list_select_related = True
    list_filter = ('is_expiration',)

    fieldsets = (
        ('Новая запчасть', {'fields': ('article', ('name', 'unit'), 'is_expiration', 'equipment',)}),

    )

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'spare_part/js/toggle_filter.js',
        )

    @admin.display(description='Оборудование')
    def equipment_name(self, obj):
        equipment_list = obj.equipment.values_list('full_name', flat=True)
        return ", ".join(equipment_list)

    @admin.display(description='Кол-во')
    def amount(self, obj):
        amount = obj.spare_part_count_spare_part.aggregate(Sum('amount'))['amount__sum'] or 0
        amount = amount if amount % 1 else int(amount)
        return amount

    @admin.display(description='Фото', boolean=True)
    def photo(self, obj):
        return True if obj.spare_part_photo.values() else False


@admin.register(SparePartCount)
class SparePartCountAdmin(MainAdmin):
    form = SparePartCountForm

    autocomplete_fields = ('spare_part',)
    list_display = ('spare_part', 'amount_field', 'expiration_dt', 'is_overdue',)
    list_filter = ('is_overdue',)
    search_fields = ('spare_part__name', 'spare_part__article',)
    search_help_text = 'Поиск по названию запчасти или её артикулу'
    ordering = ('spare_part__name', '-amount',)

    fieldsets = (
        ('Новый остаток', {'fields': ('spare_part', ('amount', 'expiration_dt'),)}),

    )

    @admin.display(description='Количество')
    def amount_field(self, obj):
        return obj.amount if obj.amount % 1 else int(obj.amount)

    def get_queryset(self, request):
        """Обноление состояни просроченности при отображение страницы"""
        today = timezone.now().date()
        qs = super().get_queryset(request)
        qs.filter(expiration_dt__lt=today).update(is_overdue=False)
        return qs

    def get_search_results(self, request, queryset, search_term):
        """Переопределяем выдачу для autocomplete_fields"""
        if request.GET.get('model_name') == 'sparepartshipment':
            # При добавлении отгрузки запчасти, покажется только список с кол-вом больше 0
            qs = queryset.filter(amount__gt=0)
            return qs, False
        return super().get_search_results(request, queryset, search_term)


@admin.register(SparePartSupply)
class SparePartSupplyAdmin(MainAdmin):
    form = SparePartSupplyForm

    autocomplete_fields = ('spare_part',)
    date_hierarchy = 'supply_dt'
    list_display = ('spare_part', 'count_part', 'doc_num', 'supply_dt', 'expiration_dt', 'user',)
    search_fields = ('spare_part__name', 'spare_part__article',)
    search_help_text = 'Поиск по названию запчасти или её артикулу'
    ordering = ('-supply_dt', 'spare_part__name')

    fieldsets = (
        (
            'Новая поставка', {
                # 'classes': ('wide',),
                'fields': ('spare_part', 'doc_num', ('count_supply', 'expiration_dt',),
                           'supply_dt',)
            }),
    )

    @admin.display(description='КОЛ-ВО')
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
    extra = 1
    autocomplete_fields = ("spare_part",)
    fields = ("spare_part", "quantity", "expiration_dt")
    readonly_fields = ("create_dt",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['expiration_dt'].required = False

        # Если объект существует и связан с Service, делаем поля недоступными для редактирования
        if obj and obj.service:
            for field_name in formset.form.base_fields:
                formset.form.base_fields[field_name].disabled = True
                formset.form.base_fields[field_name].widget.attrs['readonly'] = True
                # if field_name == "expiration_dt":
                #     formset.form.base_fields[field_name].widget.attrs.pop("today", None)
                #     formset.form.base_fields[field_name].widget.attrs.pop("calendar", None)


        return formset

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('spare_part', 'shipment',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "spare_part":
            kwargs["queryset"] = SparePart.objects.select_related("unit")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SparePartShipmentV2)
class SparePartShipmentV2Admin(admin.ModelAdmin):
    form = SparePartShipmentV2Form
    inlines = [SparePartShipmentM2MInline,]

    list_display = ("doc_num", "shipment_dt", "client_shipment", "service_equipment", "user_name")
    readonly_fields = ("client_shipment",)
    search_fields = ("service__equipment_accounting__equipment__short_name",
                     "service__equipment_accounting__equipment_acc_department_equipment_accounting__department__name")
    search_help_text = "Поиск по клиенту или названию оборудования"

    fieldsets = (
        (
            "ИНФОРМАЦИЯ ПО ОТГРУЗКЕ", {
                "fields": (("doc_num", "shipment_dt",),
                           ("service",
                            "client_shipment"),
                           "comment", "user",)
            },
        ),
    )

    class Media:
        css = {
            'all': ('spare_part/css/hide_datetime_shortcuts.css',)
        }
        js = (
            'admin/js/jquery.init.js',
            'spare_part/js/remove_datetime_shortcuts.js',
            'spare_part/js/toggle_filter.js',
        )

    @admin.display(description="Создал")
    def user_name(self, obj):
        return obj.user if obj.user else "-"

    @admin.display(description="Клиент")
    def client_shipment(self, obj):
        client = "--"
        if obj.service:
            client = obj.service.equipment_accounting \
                .equipment_acc_department_equipment_accounting \
                .values_list("department__name", flat=True)[0]

        return client

    @admin.display(description="Оборудование")
    def service_equipment(self, obj):
        equipment = "--"
        if obj.service:
            equipment = obj.service.equipment_accounting.equipment.short_name

        return equipment

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # оптимизация: подгружаем связанные объекты и инлайн-запчасти
        return qs.select_related(
            "user",
            "service__equipment_accounting__equipment", # Добавляем связи для департаментов
        ).prefetch_related("spare_part", "service")

    def get_changeform_initial_data(self, request):
        """Устанавливает начальные значения при открытии формы"""
        return {
            'user': request.user,
            "shipment_dt": datetime.now(),
        }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service":
            kwargs["queryset"] = Service.objects \
                .select_related("service_type", "equipment_accounting__equipment", "user")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            # Сохраняем оригинальные значения перед сохранением
            original_spare_parts = {}
            if change and obj.pk:
                original = SparePartShipmentV2.objects.get(pk=obj.pk)
                original_spare_parts = {
                    str(item.spare_part.id): {
                        'quantity': item.quantity,
                        'expiration_dt': item.expiration_dt
                    }
                    for item in original.shipment_m2m.all()
                }

            # Сохраняем основную модель
            super().save_model(request, obj, form, change)
            
            # Обрабатываем изменения количества для каждой запчасти через inline формы
            # Используем form.forms для доступа к inline формам
            for i, inline_form in enumerate(form.forms):
                if hasattr(inline_form, 'cleaned_data') and inline_form.cleaned_data:
                    data = inline_form.cleaned_data
                    # Пропускаем удаленные записи
                    if data and not data.get('DELETE', False):
                        spare_part = data.get('spare_part')
                        quantity = data.get('quantity', 0)
                        expiration_dt = data.get('expiration_dt')
                        
                        if spare_part and quantity > 0:
                            try:
                                # Получаем оригинальное количество
                                original_data = original_spare_parts.get(str(spare_part.id), {})
                                original_qty = original_data.get('quantity', 0)
                                delta = quantity - original_qty
                                
                                if delta != 0:
                                    # Обновляем остаток с учетом срока годности
                                    SparePartCount.objects.filter(
                                        spare_part=spare_part,
                                        expiration_dt=expiration_dt
                                    ).update(amount=F('amount') - delta)

                                    logger.info(
                                        f"Обновление остатка для запчасти {spare_part.name}: "
                                        f"изменение на {delta} (было {original_qty}, стало {quantity}), "
                                        f"срок годности: {expiration_dt}"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"Ошибка обновления остатка для запчасти {spare_part.name}: {str(e)}"
                                )


@admin.register(SparePartShipment)
class SparePartShipmentAdmin(MainAdmin):
    form = SparePartShipmentForm

    autocomplete_fields = ('spare_part_count',)
    date_hierarchy = 'shipment_dt'
    list_display = ('spare_part_name', 'count_shipment_part', 'exp_dt',
                    'doc_num', 'shipment_dt', 'user',)
    search_fields = ('spare_part_count__spare_part__name', 'spare_part_count__spare_part__article',)
    search_help_text = 'Поиск по названию запчасти или её артикулу'
    ordering = ('-shipment_dt', 'spare_part_count__spare_part__name',)
    list_select_related = True
    list_filter = (WhoShipment, )

    fieldsets = (
        ('Новая отгрузка', {'fields': ('spare_part_count', ('doc_num', 'shipment_dt'),
                                       'count_shipment', 'comment',)}),

    )

    @admin.display(description='Запчасть')
    def spare_part_name(self, obj):
        return obj.spare_part_count.spare_part.name

    @admin.display(description='Кол-во')
    def count_shipment_part(self, obj):
        return obj.count_shipment if obj.count_shipment % 1 else int(obj.count_shipment)

    @admin.display(description='Годен до')
    def exp_dt(self, obj):
        return obj.spare_part_count.expiration_dt if obj.spare_part_count.expiration_dt else '-'

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
