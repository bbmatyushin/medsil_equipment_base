from django.contrib import admin
from .models import *


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'inn', 'city_name', 'address', 'create_dt')
    search_fields = ('name', 'inn')
    ordering = ('name',)

    fieldsets = (
        ('Новый клиент', {'fields': ('name', 'inn', 'city', 'address')}),
    )

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'region', 'create_dt')
    search_fields = ('name', 'region')
    ordering = ('name',)

    fieldsets = (
        ('Новый город', {'fields': ('name', 'region')}),
    )

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'client_name', 'city_name', 'address', 'create_dt')
    search_fields = ('name', 'client__name')
    ordering = ('name',)

    fieldsets = (
        ('Новое подразделение', {'fields': ('name', 'client', 'address', 'city')}),
    )

    @admin.display(description='Клиент')
    def client_name(self, obj):
        return obj.client.name

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name


@admin.register(DeptContactPers)
class DeptContactPersAdmin(admin.ModelAdmin):
    list_display = ('fio', 'position', 'department', 'phone', 'email', 'comment')
    search_fields = ('surname', 'name', 'patron')
    ordering = ('name',)

    fieldsets = (
        ('Новое контактное лицо', {
            'fields': ('surname', 'name', 'patron',
                       'position', 'department', 'mob_phone', 'work_phone',
                       'email', 'comment')
        }),
    )

    @admin.display(description='ФИО')
    def fio(self, obj):
        return (f"{obj.surname if obj.surname else ''} "
                f"{obj.name if obj.name else ''} "
                f"{obj.patron if obj.patron else ''}")

    @admin.display(description='Телефон')
    def phone(self, obj):
        if obj.mob_phone and obj.work_phone:
            return f"{obj.mob_phone}, {obj.work_phone}"
        elif obj.mob_phone:
            return obj.mob_phone
        elif obj.work_phone:
            return obj.work_phone
        else:
            return '-'


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'type',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новая должность', {'fields': ('name', 'type')}),
    )


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новый тип ремоната / вида работ', {'fields': ('name',)}),
    )


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'inn', 'country', 'city_name', 'address', 'contact_persone', 'contact_phone')
    search_fields = ('name', 'inn')
    ordering = ('name',)

    fieldsets = (
        ('Новый поставщик', {
            'fields':
            ('name', 'inn', 'country', 'city', 'address', 'contact_persone', 'contact_phone')
            }),
    )

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_name', 'full_name', )
    search_fields = ('short_name', 'full_name')
    ordering = ('short_name',)

    fieldsets = (
        ('Новая единица измерения', {'fields': ('short_name', 'full_name')}),
    )
