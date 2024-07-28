from django.contrib import admin
from django.db.models import Sum

from .models import *
from .forms import *


@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    list_display = ('article', 'name', 'amount', 'unit', 'is_expiration', 'equipment_name',)
    search_fields = ('name', 'article', 'equipment__full_name',)
    search_help_text = 'Поиск по названию, артикулу запчасти или по оборудованию'
    ordering = ('name', 'article')
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
    list_display = ('spare_part', 'amount_field', 'expiration_dt', 'is_overdue',)
    search_fields = ('spare_part__name',)
    search_help_text = 'Поиск по названию запчасти'
    ordering = ('spare_part__name',)

    fieldsets = (
        ('Новый остаток', {'fields': ('spare_part', ('amount', 'expiration_dt'),)}),

    )

    @admin.display(description='Количество')
    def amount_field(self, obj):
        return obj.amount if obj.amount % 1 else int(obj.amount)


@admin.register(SparePartSupply)
class SparePartSupplyAdmin(admin.ModelAdmin):
    list_display = ('spare_part', 'count_supply', 'doc_num', 'supply_dt', 'expiration_dt', 'user',)
    search_fields = ('spare_part__name',)
    search_help_text = 'Поиск по названию запчасти'
    ordering = ('-supply_dt',)

    fieldsets = (
        ('Новая поставка', {'fields': ('spare_part', 'doc_num', ('count_supply', 'expiration_dt',),
                                       'supply_dt',)}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(SparePartShipment)
class SparePartShipmentAdmin(admin.ModelAdmin):
    form = SparePartShipmentForm
    readonly_fields = ('spare_part_amount',)

    list_display = ('spare_part_name', 'count_shipment', 'exp_dt', 'doc_num', 'shipment_dt', 'user',)
    search_fields = ('spare_part_count__spare_part.name',)
    search_help_text = 'Поиск по названию запчасти'
    ordering = ('-shipment_dt',)
    list_select_related = True

    fieldsets = (
        ('Новая отгрузка', {'fields': ('spare_part_count', ('doc_num', 'shipment_dt'), 'count_shipment',)}),

    )

    @admin.display(description='Запчасть')
    def spare_part_name(self, obj):
        return obj.spare_part_count.spare_part.name

    @admin.display(description='Доступно')
    def spare_part_amount(self, obj):
        return obj.spare_part_count.spare_part.amount

    @admin.display(description='Годен до')
    def exp_dt(self, obj):
        return obj.spare_part_count.expiration_dt if obj.spare_part_count.expiration_dt else '-'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)
