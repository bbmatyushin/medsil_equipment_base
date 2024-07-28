from django.contrib import admin
from .models import *
# from users.models import CompanyUser
from directory.models import Position, PositionType


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
        return obj.city.name if obj.city else '-'


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
        return obj.client.name if obj.client else '-'

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.client else '-'


@admin.register(DeptContactPers)
class DeptContactPersAdmin(admin.ModelAdmin):
    list_display = ('fio', 'position', 'department', 'phone', 'email', 'comment')
    search_fields = ('surname', 'name', 'patron')
    ordering = ('name',)

    fieldsets = (
        ('Новое контактное лицо', {
            'fields': ('surname', 'name', 'patron',
                       'department', 'position', 'mob_phone', 'work_phone',
                       'email', 'comment')
        }),
    )

    # Переопределяет метод для выбора должностей. Будут видны только должности типа "Клиент"
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "position":
            kwargs["queryset"] = Position.objects.filter(type=PositionType.client.name)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'short_name', 'med_direction_name',
                    'manufacturer_name', 'supplier_name',)
    search_fields = ('short_name', 'full_name')
    ordering = ('full_name',)

    fieldsets = (
        ('Новое оборудование', {'fields': ('full_name', 'short_name', 'med_direction')}),
        ('Производитель и поставщик', {'fields': ('manufacturer', 'supplier',)}),
    )

    @admin.display(description='Направление')
    def med_direction_name(self, obj):
        return f"{obj.med_direction.name if obj.med_direction else '-'}"

    @admin.display(description='Производитель')
    def manufacturer_name(self, obj):
        return f"{obj.manufacturer.name if obj.manufacturer else '-'}"

    @admin.display(description='Поставщик')
    def supplier_name(self, obj):
        return f"{obj.supplier.name if obj.supplier else '-'}"


class EquipmentAccDepartmentInline(admin.TabularInline):
    model = EquipmentAccDepartment
    fk_name = 'equipment_accounting'
    extra = 1
    # max_num = 1  # Не ограничивать, т.к. есть возможность снимать галочку "У клиента"
    verbose_name = 'ИНФОРМАЦИЯ О МОНТАЖЕ ОБОРУДОВАНИЯ'
    # fields = ('department', ('engineer', 'install_dt'), 'is_active')
    fieldsets = (
        ('Подразделение', {'fields': ('department',)}),
        ('Монтаж', {'fields': ('engineer', 'install_dt', 'is_active',)}),
    )


@admin.register(EquipmentAccounting)
class EquipmentAccountingAdmin(admin.ModelAdmin):
    inlines = (EquipmentAccDepartmentInline,)
    list_display = ('equipment', 'serial_number', 'dept_name', 'engineer', 'install_dt', 'equipment_status',
                    'is_our_service', 'is_our_supply', 'user_name', )
    search_fields = ('equipment__full_name', 'equipment__short_name', 'serial_number',)
    search_help_text = 'Поиск по полному и краткому наименованию оборудования или по серийному номеру'
    ordering = ('equipment', 'serial_number', 'user',)
    list_per_page = 50
    list_select_related = True
#
    fieldsets = (
        ('НОВОЕ ОБОРУДОВАНИЕ ДЛЯ УЧЁТА', {'fields': ('equipment', ('serial_number', 'equipment_status'),
                                               ('is_our_supply', 'is_our_service',),)}),
    )

    def get_instance(self, obj):
        instance = obj.equipment_acc_department_equipment_accounting.get(equipment_accounting=obj.pk)
        return instance

    @admin.display(description='Установлено')
    def dept_name(self, obj):
        instance = self.get_instance(obj)
        return instance.department

    @admin.display(description='Инженер')
    def engineer(self, obj):
        instance = self.get_instance(obj)
        return instance.engineer

    @admin.display(description='Дата монтажа')
    def install_dt(self, obj):
        instance = self.get_instance(obj)
        return instance.install_dt.strftime('%d.%m.%Y г.') if instance.install_dt else '-'

    @admin.display(description='Добавил')
    def user_name(self, obj):
        return obj.user.username if obj.user else '-'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        elif not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ('name', 'inn', 'contact_person', 'contact_phone', 'email',
                    'country_name', 'city_name', 'address',)
    search_fields = ('name', 'inn')
    ordering = ('name',)

    fieldsets = (
        ('Новый производитель', {'fields': ('name', 'inn',)}),
        ('Адрес', {'fields': ('country', 'city', 'address')}),
        ('Контакты производителя', {'fields': ('contact_person', 'contact_phone', 'email')}),
    )

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.city else '-'

    @admin.display(description='Страна')
    def country_name(self, obj):
        return obj.country.name if obj.country else '-'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('equipment_accounting', 'service_type', 'description',
                    'reason', 'job_content_short', 'beg_dt',)
    ordering = ('beg_dt',)
    list_select_related = ('equipment_accounting', 'service_type',)

    fieldsets = (
        ('Новый ремонт', {'fields': ('equipment_accounting', 'spare_part', 'service_type',
                                     'description', 'reason', 'job_content')}
        ),
        ('Дата работ', {'fields': (('beg_dt', 'end_dt'),)}),
    )

    @admin.display(description='Содержание работ')
    def job_content_short(self, obj):
        content = obj.job_content[:50] if obj.job_content else '-'
        return content if len(content) < 50 else f'{content}...'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        elif not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'inn', 'contact_person', 'contact_phone', 'email',
                    'country_name', 'city_name', 'address',)
    search_fields = ('name', 'inn')
    ordering = ('name',)

    fieldsets = (
        ('Новый поставщик', { 'fields': ('name', 'inn')}),
        ('Адрес', {'fields': ('country', 'city', 'address',)}),
        ('Контакты поставщика', {'fields': ('contact_person', 'contact_phone', 'email')}),
    )

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.city else '-'

    @admin.display(description='Страна')
    def country_name(self, obj):
        return obj.country.name if obj.country else '-'
