from django.contrib import admin
from .models import *
from ebase.admin import MainAdmin


@admin.register(City)
class CityAdmin(MainAdmin):
    list_display = ('id', 'name', 'region', 'create_dt')
    list_display_links = ('name',)
    search_fields = ('name', 'region')
    ordering = ('name',)

    fieldsets = (
        ('Новый город', {'fields': ('name', 'region')}),
    )


@admin.register(Country)
class CountryAdmin(MainAdmin):
    list_display = ('id', 'name', 'create_dt')
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новая страна', {'fields': ('name',)}),
    )


@admin.register(EquipmentStatus)
class EquipmentStatusAdmin(MainAdmin):
    list_display = ('id', 'name',)
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новый статус', {'fields': ('name',)}),
    )


@admin.register(Engineer)
class EngineerAdmin(MainAdmin):
    list_display = ('name', 'user')
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новый инженер', {'fields': ('name', 'user')}),
    )


@admin.register(MedDirection)
class MedDirectionAdmin(MainAdmin):
    list_display = ('id', 'name',)
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новое направление', {'fields': ('name',)}),
    )


@admin.register(Position)
class PositionAdmin(MainAdmin):
    list_display = ('id', 'name', 'type',)
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('type', 'name',)

    fieldsets = (
        ('Новая должность', {'fields': ('name', 'type')}),
    )


@admin.register(ServiceType)
class ServiceTypeAdmin(MainAdmin):
    list_display = ('id', 'name',)
    list_display_links = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

    fieldsets = (
        ('Новый тип ремоната / вида работ', {'fields': ('name',)}),
    )


@admin.register(Unit)
class UnitAdmin(MainAdmin):
    list_display = ('id', 'short_name', 'full_name', )
    list_display_links = ('short_name',)
    search_fields = ('short_name', 'full_name')
    ordering = ('short_name',)

    fieldsets = (
        ('Новая единица измерения', {'fields': ('short_name', 'full_name')}),
    )
