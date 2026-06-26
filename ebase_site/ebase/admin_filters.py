from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from contracts.models import Contract


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


class ContractFilter(admin.SimpleListFilter):
    title = _('По Контракту')
    parameter_name = 'contract'

    def lookups(self, request, model_admin):
        choices = [
            ('none', _('Без контракта')),
            ('all', _('С контрактом')),
        ]
        for contract in Contract.objects.all().order_by('contract_number'):
            choices.append((str(contract.pk), contract.contract_number))
        return choices

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'none':
            return queryset.filter(contract__isnull=True)
        if value == 'all':
            return queryset.filter(contract__isnull=False)
        if value:
            return queryset.filter(contract_id=value)
        return queryset
