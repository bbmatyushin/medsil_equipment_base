from datetime import datetime

from django.contrib import admin
from django.utils import timezone
from django.db.models import Sum

from .models import *
from .forms import *


@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    autocomplete_fields = ('unit',)
    list_display = ('article', 'name', 'amount', 'unit', 'is_expiration', 'equipment_name',)
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

    @admin.display(description='Оборудование')
    def equipment_name(self, obj):
        equipment_list = obj.equipment.values_list('full_name', flat=True)
        return ", ".join(equipment_list)

    @admin.display(description='Кол-во')
    def amount(self, obj):
        amount = obj.spare_part_count_spare_part.aggregate(Sum('amount'))['amount__sum'] or 0
        amount = amount if amount % 1 else int(amount)
        return amount


@admin.register(SparePartCount)
class SparePartCountAdmin(admin.ModelAdmin):
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
class SparePartSupplyAdmin(admin.ModelAdmin):
    autocomplete_fields = ('spare_part',)
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


@admin.register(SparePartShipment)
class SparePartShipmentAdmin(admin.ModelAdmin):
    form = SparePartShipmentForm

    autocomplete_fields = ('spare_part_count',)
    list_display = ('spare_part_name', 'count_shipment_part', 'exp_dt', 'doc_num', 'shipment_dt', 'user',)
    search_fields = ('spare_part_count__spare_part__name', 'spare_part_count__spare_part__article',)
    search_help_text = 'Поиск по названию запчасти или её артикулу'
    ordering = ('-shipment_dt', 'spare_part_count__spare_part__name',)
    list_select_related = True

    fieldsets = (
        ('Новая отгрузка', {'fields': ('spare_part_count', ('doc_num', 'shipment_dt'), 'count_shipment',)}),

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
