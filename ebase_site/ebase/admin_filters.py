from django.contrib import admin


class InstallDtFilter(admin.SimpleListFilter):
    title = 'Дата монтажа'
    parameter_name = 'install_dt'

    def lookups(self, request, model_admin):
        return [
            ('notnulldt', 'Заполнена',),
            ('nulldt', 'Не заполнена',),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'notnulldt':
            return queryset.filter(equipment_acc_department_equipment_accounting__install_dt__isnull=False)
        elif self.value() == 'nulldt':
            return queryset.filter(equipment_acc_department_equipment_accounting__install_dt__isnull=True)


class MedDirectionFilter(admin.SimpleListFilter):
    title = 'Направления'
    parameter_name = 'med_direction'

    def lookups(self, request, model_admin):
        from directory.models import MedDirection
        directions = MedDirection.objects.all().order_by('name')
        return [(direction.id, direction.name) for direction in directions]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(equipment__med_direction_id=self.value())
        return queryset
