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
