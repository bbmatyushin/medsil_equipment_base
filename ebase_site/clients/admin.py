from django.contrib import admin

from clients.models import Client, Department, DeptContactPers
from directory.models import Position
from utils import MainModelAdmin


@admin.register(Client)
class ClientAdmin(MainModelAdmin):
    autocomplete_fields = ('city',)
    list_display = ('name', 'inn', 'city_name', 'address', 'create_dt')
    search_fields = ('name', 'inn')
    search_help_text = 'Поиск по Наименованию или ИНН'
    ordering = ('name',)

    fieldsets = (
        ('Клиент', {'fields': ('name',)}),
        ('Реквизиты', {'fields': (('inn', 'kpp',), ('phone', 'email',), ('city', 'address',))})
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('city')

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.city else '-'


@admin.register(Department)
class DepartmentAdmin(MainModelAdmin):
    list_display = ('name', 'client_name', 'city_name', 'address', 'create_dt')
    search_fields = ('name', 'client__name')
    search_help_text = 'Поиск по подразделению или клиенту'
    ordering = ('name',)

    fieldsets = (
        ('Новое подразделение', {'fields': ('name', 'client', 'address', 'city')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'city')

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/get_city/",
                self.admin_site.admin_view(self.get_city),
                name="department_get_city",
            ),
        ]
        return custom_urls + urls

    def get_city(self, request, object_id):
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404

        department = get_object_or_404(Department, pk=object_id)
        return JsonResponse(
            {"city": department.city.name if department.city else None}
        )

    @admin.display(description='Клиент')
    def client_name(self, obj):
        return obj.client.name if obj.client else '-'

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.client else '-'


@admin.register(DeptContactPers)
class DeptContactPersAdmin(MainModelAdmin):
    autocomplete_fields = ('department',)
    list_display = ('fio', 'position', 'department', 'phone', 'email', 'comment')
    list_filter = ('position',)
    search_fields = ('surname', 'name', 'patron', 'department__name')
    search_help_text = 'Поиск по фамилии/имени/отчеству или по подразделению'
    ordering = ('name',)

    fieldsets = (
        ('Новое контактное лицо', {
            'fields': ('surname', 'name', 'patron',
                       'department', 'position', 'mob_phone', 'work_phone',
                       'email', 'comment')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('department', 'position')

    # Переопределяет метод для выбора должностей. Будут видны только должности типа "Клиент"
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "position":
            kwargs["queryset"] = Position.objects.filter(type='client')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='ФИО')
    def fio(self, obj):
        # Формируем ФИО, исключая None и пустые строки
        fio_parts = []
        if obj.surname:
            fio_parts.append(obj.surname)
        if obj.name:
            fio_parts.append(obj.name)
        if obj.patron:
            fio_parts.append(obj.patron)

        return ' '.join(fio_parts).strip()

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
