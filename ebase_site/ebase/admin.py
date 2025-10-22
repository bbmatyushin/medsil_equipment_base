import datetime
import re
import logging
import json
import time
from typing import Optional
from datetime import date

from django.utils.safestring import mark_safe
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.urls import path
from django.http import JsonResponse

from spare_part.models import SparePart, SparePartCount, SparePartShipment, SparePartShipmentV2, SparePartShipmentM2M
from directory.models import Position
from .forms import *
from .admin_filters import *
from .docx_create import CreateServiceAkt, create_service_atk

logger = logging.getLogger('ebase')


class MainAdmin(admin.ModelAdmin):
    list_per_page = 20


@admin.register(Client)
class ClientAdmin(MainAdmin):
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
class DepartmentAdmin(MainAdmin):
    list_display = ('name', 'client_name', 'city_name', 'address', 'create_dt')
    search_fields = ('name', 'client__name')
    search_help_text = 'Поиск по подразделению или клиенту'
    ordering = ('name',)

    fieldsets = (
        ('Новое подразделение', {'fields': ('name', 'client', 'address', 'city')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('client', 'city')

    @admin.display(description='Клиент')
    def client_name(self, obj):
        return obj.client.name if obj.client else '-'

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.client else '-'


@admin.register(DeptContactPers)
class DeptContactPersAdmin(MainAdmin):
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
class EquipmentAdmin(MainAdmin):
    autocomplete_fields = ('manufacturer','supplier',)
    list_display = ('full_name', 'short_name', 'med_direction_name',
                    'manufacturer_name', 'supplier_name',)
    list_filter = ('med_direction__name',)
    search_fields = ('short_name', 'full_name')
    search_help_text = 'Поиск по полному/краткому наименованию оборудования'
    ordering = ('full_name',)

    fieldsets = (
        ('Новое оборудование', {'fields': ('full_name', 'short_name', 'med_direction')}),
        ('Производитель и поставщик', {'fields': ('manufacturer', 'supplier',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .select_related('med_direction', 'manufacturer', 'supplier',) \
            .prefetch_related('spare_part')

    @admin.display(description='Направление')
    def med_direction_name(self, obj):
        return f"{obj.med_direction.name if obj.med_direction else '-'}"

    @admin.display(description='Производитель')
    def manufacturer_name(self, obj):
        return f"{obj.manufacturer.name if obj.manufacturer else '-'}"

    @admin.display(description='Поставщик')
    def supplier_name(self, obj):
        return f"{obj.supplier.name if obj.supplier else '-'}"


class EquipmentAccDepartmentInline(admin.StackedInline):
    model = EquipmentAccDepartment
    fk_name = 'equipment_accounting'
    extra = 0
    # autocomplete_fields = ('department',)  # С ним не отрабатывает def formfield_for_foreignkey
    # max_num = 1  # Не ограничивать, т.к. есть возможность снимать галочку "У клиента"
    verbose_name = 'ИНФОРМАЦИЯ О МОНТАЖЕ ОБОРУДОВАНИЯ'
    verbose_name_plural = 'ИНФОРМАЦИЯ О МОНТАЖЕ ОБОРУДОВАНИЯ'

    fieldsets = (
        (None, {'fields': (('department', 'is_active',), ('engineer', 'install_dt',),),}),
        # ('Монтаж', {'fields': (('engineer', 'install_dt',),),}),
    )

    # Модно переопределить get_formsets_with_inlines или get_formset для вывода поля город
    # def get_formset(self, request, obj=None, **kwargs):
    #     formset = super().get_formset(request, obj, **kwargs)
    #     # formset.form.base_fields['department'].queryset = Department.objects.filter(client=obj.client)
    #     return formset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "department":
            city = request.GET.get('city')
            if city:
                kwargs["queryset"] = Department.objects.filter(city__name__iexact=city)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(EquipmentAccounting)
class EquipmentAccountingAdmin(MainAdmin):
    form = EquipmentAccountingForm

    actions = ('set_is_our_service',)
    date_hierarchy = 'equipment_acc_department_equipment_accounting__install_dt'
    # подставляет в шаблон ссылку на сайт
    add_form_template = 'ebase/admin/equipment_acc_change_form.html'
    # autocomplete_fields = ('equipment',)  # С ним не отрабатывает def formfield_for_foreignkey

    inlines = (EquipmentAccDepartmentInline,)
    list_display = ('equipment', 'serial_number', 'dept_name', 'engineer', 'install_dt', 'equipment_status',
                    'is_our_service', 'is_our_supply', 'user_name', )
    search_fields = ('equipment__full_name', 'equipment__short_name', 'serial_number',
                     'equipment_acc_department_equipment_accounting__department__name',)  # поиск по названию подразделения
                     # 'equipment_acc_department_equipment_accounting__department__city__name',)  # поиск по городу подразделения
    search_help_text = ('Поиск по полному и краткому наименованию оборудования, по его серийному номеру или '
                        'по названию Подразделения клиента (где установлено)')
    ordering = ('-equipment_acc_department_equipment_accounting__install_dt',
                'equipment', 'serial_number', 'user',)
    list_select_related = True
    list_filter = (InstallDtFilter, 'equipment_status__name', 'is_our_supply',)
#
    fieldsets = (
        ('НОВОЕ ОБОРУДОВАНИЕ ДЛЯ УЧЁТА', {'fields': ('equipment', ('serial_number', 'equipment_status'),
                                                     ('is_our_supply', 'is_our_service',),
                                                     ('comment',),)}),
        ('YOUJAIL', {'fields': ('url_youjail',)}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Проверяем, что у сотрудника установлена должность менеджер
        user_position = request.user.position.filter(type='employee', name__iexact='менеджер')
        if user_position:
            # Для менеджреров не отображаем оборудование посталенное не нами
            queryset = queryset.filter(is_our_supply__exact=1)

        queryset = queryset.select_related(
            'equipment',
            'equipment_status',
            'user'
        ).prefetch_related(
            Prefetch(
                'equipment_acc_department_equipment_accounting',
                queryset=EquipmentAccDepartment.objects.select_related(
                    'department',
                    'engineer'
                )
            ),
            "service_equipment_accounting"
        )

        return queryset

    def get_instance(self, obj):
        # try:
        #     instance = obj.equipment_acc_department_equipment_accounting.get(equipment_accounting=obj.pk)
        # except Exception as e:  #TODO: заглушка, чтобы не падала с ошибкой. Исправить.
        #     logger.warning("get_instance WARNING:", exc_info=e)
        #     instance = list(obj.equipment_acc_department_equipment_accounting.filter(equipment_accounting=obj.pk))
        # return instance

        # Используем уже предзагруженные данные из prefetch_related -- Claude
        try:
            return obj.equipment_acc_department_equipment_accounting.all()[0]
        except (IndexError, AttributeError):
            logger.warning(f"get_instance WARNING: No department found for equipment_accounting {obj.pk}")
            return None

    @admin.display(description='Установлено')
    def dept_name(self, obj):
        instance = self.get_instance(obj)
        if isinstance(instance, list):
            instance = instance[0]
        return instance.department if instance else "--"

    @admin.display(description='Инженер')
    def engineer(self, obj):
        instance = self.get_instance(obj)
        if isinstance(instance, list):
            instance = instance[0]
        return instance.engineer if instance else "--"

    @admin.display(description='Дата монтажа')
    def install_dt(self, obj):
        instance = self.get_instance(obj)
        if isinstance(instance, list):
            instance = instance[0]
        if instance:
            return instance.install_dt.strftime('%d.%m.%Y г.') if instance.install_dt else '--'
        return "--"

    @admin.display(description='Добавил')
    def user_name(self, obj):
        return obj.user.username if obj.user else '-'

    @admin.action(description='Установить - Проведено ТО')
    def set_is_our_service(self, request, queryset):
        count_set = queryset.update(is_our_service=True)
        self.message_user(request, message=f'Успешно изменено {count_set} записей')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        elif not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'equipment':
            condition = request.GET.get('med_direction')
            if condition:
                kwargs["queryset"] = Equipment.objects.filter(med_direction__name=condition)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request)
        user_position = request.user.position.filter(type='employee', name__iexact='менеджер')
        if user_position:
            list_filter = (InstallDtFilter, 'equipment_status__name',)
        return list_filter


@admin.register(Manufacturer)
class ManufacturerAdmin(MainAdmin):
    autocomplete_fields = ('city',)
    list_display = ('name', 'inn', 'contact_person', 'contact_phone', 'email',
                    'country_name', 'city_name', 'address',)
    search_fields = ('name', 'inn')
    search_help_text = 'Поиск по Производителю или ИНН'
    ordering = ('name',)

    fieldsets = (
        ('Новый производитель', {'fields': ('name', 'inn',)}),
        ('Адрес', {'fields': ('country', 'city', 'address')}),
        ('Контакты производителя', {'fields': ('contact_person', 'contact_phone', 'email')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('city', 'country')

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.city else '-'

    @admin.display(description='Страна')
    def country_name(self, obj):
        return obj.country.name if obj.country else '-'


class ServicePhotosInline(admin.StackedInline):
    model = ServicePhotos
    # classes = ['wide',]
    fk_name = 'service'
    extra = 1
    readonly_fields = ('eq_service_photo',)
    verbose_name = 'ФОТО РЕМОНТА'
    verbose_name_plural = 'ФОТО РЕМОНТА'

    fieldsets = (
        ('', {
            # 'classes': ('collapse',),
            'fields': (('photo', 'eq_service_photo'),)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("service", "user")

    @admin.display(description='Изображение')
    def eq_service_photo(self, obj):
        if obj.photo:
            return mark_safe(f"<a href='{obj.photo.url}' target='_blank'>"
                             f"<img src='{obj.photo.url}' width=50>"
                             f"</a>")
        return f"Нет изображения"


@admin.register(Service)
class ServiceAdmin(MainAdmin):
    actions = ('create_service_akt_by_action',)
    # add_form_template = 'ebase/admin/service_change_form.html'
    # autocomplete_fields = ('equipment_accounting',)
    form = ServiceForm
    date_hierarchy = 'beg_dt'
    filter_horizontal = ('spare_part',)
    inlines = (ServicePhotosInline, )
    list_display = ('equipment_accounting', 'dept_name', 'service_type',
                    'photos',
                    'description_short', 'spare_part_used',
                    'reason_short', 'job_content_short', 'akt',
                    'beg_dt', 'end_dt',)
    list_select_related = ('equipment_accounting', 'service_type',)
    readonly_fields = ('service_akt_url', 'accept_in_akt_url', 'accept_from_akt_url',)
    search_fields = ('equipment_accounting__equipment__full_name',
                     'equipment_accounting__equipment__short_name',
                     'equipment_accounting__serial_number',)
    search_help_text = 'Поиск по полному/краткому наименованию оборудования или по серийному номеру'
    ordering = ('-beg_dt', 'equipment_accounting',)

    fieldsets = (
        (
            'Данные на оборудование', {'fields': ()}  # задается через get_fieldsets
        ),
        (
            'Описание работ', {
                'classes': ('collapse',),
                'fields': ('reason', 'description', 'job_content',),
            }
        ),
        ('Дата работ', {'fields': (('beg_dt', 'end_dt'),)}),
        ('Документы по ремонту', {'fields': ('accept_in_akt_url', 'service_akt_url', 'accept_from_akt_url',),})
    )

    class Media:
        css = {
            "all": ("ebase/admin/css/custom_form.css",)
        }
        js = (
            "ebase/js/part_to_service_grok.js",
            "ebase/js/scripts.js",
        )

    def get_queryset(self, request):
        # Максимально оптимизированный queryset с предзагрузкой всех необходимых связей
        return super().get_queryset(request).select_related(
            "equipment_accounting",
            "equipment_accounting__equipment",
            "service_type",
            "user"
        ).prefetch_related(
            "spare_part",
            Prefetch(
                'equipment_accounting__equipment_acc_department_equipment_accounting',
                queryset=EquipmentAccDepartment.objects.select_related(
                    'department',
                    # 'department__сity',
                    'department__client',
                    'department__client__city'
                ).filter(is_active=True)
            ),
            Prefetch(
                "service_photos",
                queryset=ServicePhotos.objects.all()
            ),
        )

    @admin.display(description='Содержание работ')
    def job_content_short(self, obj):
        job_content = obj.job_content
        content = '-' if not job_content else job_content if len(job_content) < 50 \
            else f"{job_content[:50]}..."
        return f"{content}" if len(content) < 50 \
                else mark_safe(f"<p title='{job_content}'>{content}</p>")

    @admin.display(description='Описание неисправности')
    def description_short(self, obj):
        description = obj.description
        descr = '-' if not description else description if len(description) < 50 \
            else f"{description[:50]}..."
        return f"{descr}" if len(descr) < 50 \
                else mark_safe(f"<p title='{description}'>{descr}</p>")

    @admin.display(description='Причина')
    def reason_short(self, obj):
        service_reason = obj.reason
        reason = '-' if not service_reason else service_reason if len(service_reason) < 50 \
            else f"{service_reason[:50]}..."
        return f"{reason}" if len(reason) < 50 \
                else mark_safe(f"<p title='{service_reason}'>{reason}</p>")

    @admin.display(description='Запчасти')
    def spare_part_used(self, obj):
        # Используем предзагруженные данные
        spare_parts_list = [sp.name for sp in obj.spare_part.all()]
        return "; ".join(spare_parts_list) if spare_parts_list else '-'

    @admin.display(description='Подразделение')
    def dept_name(self, obj):
        departments = [
            acc_dept.department.name
            for acc_dept in obj.equipment_accounting.equipment_acc_department_equipment_accounting.all()
            if acc_dept.is_active
        ]
        return "; ".join(departments) if departments else '-'

    @admin.display(description='Фото', boolean=True)
    def photos(self, obj):
        return True if obj.service_photos.values() else False

    @admin.display(description='Акт', boolean=True)
    def akt(self, obj):
        return True if obj.service_akt else False

    @admin.display(description='Акт о проведении работ')
    def service_akt_url(self, obj):
        if obj.service_akt:
            url = re.sub(r'.*/docs', '/media/docs', obj.service_akt)
            akt_name = obj.service_akt.split('/')[-1]
            return self._akt_mark_safe(url=url, akt_name=akt_name,
                                       tag_id="akt-create-btn", action="update")
        if obj.pk:
            return self._akt_mark_safe(tag_id="akt-create-btn", action="create")
        # При создании новой записи направит сюда
        return self._akt_mark_safe()

    @admin.display(description='Акт приёма-передачи в ремонт')
    def accept_in_akt_url(self, obj):
        if obj.accept_in_akt:
            url = re.sub(r'.*/docs', '/media/docs', obj.accept_in_akt)
            akt_name = obj.accept_in_akt.split('/')[-1]
            return self._akt_mark_safe(url=url, akt_name=akt_name,
                                       tag_id="accept-akt-create-btn", action="update")
        if obj.pk:
            return self._akt_mark_safe(tag_id="accept-akt-create-btn", action="create")
        # При создании новой записи направит сюда
        return self._akt_mark_safe()

    @admin.display(description='Акт приёма-передачи из ремонта')
    def accept_from_akt_url(self, obj):
        if obj.accept_from_akt:
            url = re.sub(r'.*/docs', '/media/docs', obj.accept_from_akt)
            akt_name = obj.accept_from_akt.split('/')[-1]
            return self._akt_mark_safe(url=url, akt_name=akt_name,
                                       tag_id="accept-akt-from-create-btn", action="update")
        if obj.pk:
            return self._akt_mark_safe(tag_id="accept-akt-from-create-btn", action="create")
        # При создании новой записи направит сюда
        return self._akt_mark_safe()

    @staticmethod
    def _akt_mark_safe(url: Optional[str] = None, akt_name: Optional[str] = None,
                       tag_id: Optional[str] = None, action: Optional[str] = None):
        """Возвращает mark_safe для актов"""
        if action == "create":
            return mark_safe(f'<span class="akt-span">Акт не создан</span>'
                             f'<input type="button" id="{tag_id}" value="Создать">')
        elif action == "update":
            time_version = int(time.time())
            return mark_safe(f'<span class="akt-span"><a href="{url}?v={time_version}">{akt_name}</a></span>'
                             f'<input type="button" id="{tag_id}" value="Обновить">')
        else:
            return mark_safe('<span class="akt-span">-------</span>')

    @admin.action(description='Создать - Акт о проведении работ')
    def create_service_akt_by_action(self, request, queryset) -> None:
        """Формирование актов о проделаной работе для выбранных случаев"""
        equipments_list: list = []
        for qs in queryset:
            create_akt = create_service_atk(obj=qs)
            equipments_list.append(f"{create_akt[0]} (s/n {create_akt[1]})")
        if len(equipments_list) > 1:
            msg = f"Акты сформированы для: {', '.join(equipments_list)}."
        else:
            msg = f"Акт сформирован для {', '.join(equipments_list)}."

        self.message_user(request, message=msg)

    @staticmethod
    def get_equipment_ids(search_str: str) -> QuerySet:
        """Получаем список из id оборудований в названии или серийный номер, которых
        совпадает с search_str

        :param search_str - значение параметра search_equipment_form"""
        eq_acc = \
            EquipmentAccounting.objects \
                .filter(Q(equipment__short_name__icontains=search_str) |
                        Q(equipment__short_name__icontains=search_str) |
                        Q(serial_number__icontains=search_str)) \
                .distinct()

        return eq_acc

    def get_fieldsets(self, request, obj=None):
        fieldsets: tuple = super().get_fieldsets(request, obj)
        if obj is not None:  # для страницы редактирования убираем поля для поиска оборудования
            fieldsets[0][1]['fields'] = ('equipment_accounting', 'service_type', 'spare_part')
        else:
            fieldsets[0][1]['fields'] = (("search_equipment", "search_button",),
                                         'equipment_accounting', 'service_type', 'spare_part')

        return fieldsets

    def get_form(self, request, obj=None, change=False, **kwargs):
        """В карточке по ремонту есть кнопка по созданию акта. Чтобы отследить её
        нажатие, через JS в GET передается параметр akt со значенем serviceAkt или
        acceptAkt или acceptFromAkt.

        serviceAkt - Акт о проведении работ
        acceptInAkt - Акт приема-передачи оборудования в ремонт
        acceptFromAkt - Акт приема-передачи оборудования из ремонт
        """
        if request.GET.get("akt"):
            akt_name = request.GET["akt"]
            start_msg_text = ''
            if obj:
                create_akt = create_service_atk(obj, akt_name)

                if akt_name == 'serviceAkt':
                    start_msg_text = 'Акт о проведении работ'
                elif akt_name == 'acceptInAkt':
                    start_msg_text = 'Акт приема-передачи оборудования в ремонт'
                elif akt_name == 'acceptFromAkt':
                    start_msg_text = 'Акт приема-передачи оборудования из ремонт'

                self.message_user(request,
                                  message=f"{start_msg_text} сформирован для "
                                          f"{create_akt[0]} (s/n {create_akt[1]})")
        return super().get_form(request, obj=None, change=False, **kwargs)
    
    def get_changeform_initial_data(self, request):
        """использовалось для отработки подставления значений оборудования при фильтрации
        через JavaScript"""
        initial = super().get_changeform_initial_data(request)
        eq_acc_id = request.GET.get("choice_eq_acc")  # выбранное оборудование из таблицы учета
        eq_search = request.GET.get("search_equipment_form")  # из поля поиска

        if eq_acc_id:
            try:
                eq_acc = EquipmentAccounting.objects.get(pk=eq_acc_id)
                initial["equipment_accounting"] = eq_acc
            except EquipmentAccounting.DoesNotExists as e:
                logger.warning(f"get_changeform_initial_data: {e}")
        elif eq_search:
            eq_acc: QuerySet = self.get_equipment_ids(search_str=eq_search)
            if len(eq_acc) == 1:  # если нашелся один, то сразу его подставляем
                initial["equipment_accounting"] = eq_acc.first()

        return initial

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)

    #     response.context_data['cl'].list_display = [
    #         f'<div style="width:200px">{col}</div>' for col in response.context_data['cl'].list_display
    #     ]
        return response

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Формируем список оборудования в формах с серийными номера на основе
            id полученного из get-запроса"""
        eq_acc = None
        eq_search = request.GET.get("search_equipment_form")

        if eq_search:  # по GET параметру получаем список id оборудований
            eq_acc: QuerySet = self.get_equipment_ids(search_str=eq_search)

        if db_field.name == 'equipment_accounting':
            # Для страницы добавления новой записи
            if re.search(r'\/service\/add\/', request.path):
                if eq_acc:
                    # Предзагружаем все необходимые связи для оборудования
                    eq_acc_ids = eq_acc.values_list("pk", flat=True)
                    eq_acc_queryset: QuerySet = EquipmentAccounting.objects \
                        .filter(pk__in=eq_acc_ids)
                else:
                    eq_acc_queryset: QuerySet = EquipmentAccounting.objects.all()

                kwargs["queryset"] = eq_acc_queryset \
                    .select_related(
                    "equipment",
                    "equipment__manufacturer",
                    "equipment__supplier",
                    "equipment__med_direction",
                    "equipment_status",
                    "user"
                ).prefetch_related(
                    Prefetch(
                        'equipment_acc_department_equipment_accounting',
                        queryset=EquipmentAccDepartment.objects.select_related(
                            'department',
                            'department__client',
                            'department__city',
                            'engineer'
                        )
                    )
                )

            # Для страницы изменения записи - ограничиваем queryset только текущим оборудованием
            elif re.search(r'\/service\/.*\/change\/', request.path):
                try:
                    service_id = request.path.strip().split('/')[-3]
                    service_obj = Service.objects.select_related(
                        'equipment_accounting__equipment'
                    ).get(pk=service_id)

                    kwargs["queryset"] = EquipmentAccounting.objects.filter(
                        pk=service_obj.equipment_accounting.pk
                    ).select_related(
                        "equipment",
                        "equipment__manufacturer",
                        "equipment__supplier",
                        "equipment__med_direction",
                        "equipment_status",
                        "user"
                    )
                except (Service.DoesNotExist, IndexError, ValueError):
                    # Fallback к базовому queryset
                    pass

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Оптимизированный метод для ManyToMany полей
        Формируем список запчастей для оборудования на основе
        полученного значения из get-запроса"""
        eq_ids = None
        eq_search = request.GET.get("search_equipment_form")
        eq_acc_id = request.GET.get("choice_eq_acc")  # выбранное оборудование из таблицы учета

        if db_field.name == 'spare_part':
            # Для страницы добавления
            if re.search(r'\/service\/add\/', request.path):
                if eq_acc_id:
                    eq_ids = EquipmentAccounting.objects \
                        .filter(pk=eq_acc_id) \
                        .values_list("equipment__pk", flat=True)
                elif eq_search:  # по GET параметру получаем список id оборудований
                    eq_acc = self.get_equipment_ids(search_str=eq_search)
                    eq_ids: QuerySet = eq_acc.values_list("equipment__pk", flat=True)

                    # Для страницы изменения
            elif re.search(r'\/service\/.*\/change\/', request.path):
                try:
                    service_id = request.path.strip().split('/')[-3]
                    service_obj = Service.objects.select_related(
                        'equipment_accounting__equipment'
                    ).get(pk=service_id)
                    eq_ids = [service_obj.equipment_accounting.equipment.pk]
                except (Service.DoesNotExist, IndexError, ValueError):
                    pass

            if eq_ids:
                # Предзагружаем запчасти с их оборудованием
                kwargs["queryset"] = SparePart.objects.filter(equipment__id__in=eq_ids) \
                    .prefetch_related("equipment", "service",)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if obj.beg_dt < date(2025, 10, 22):
            # Если дата начала ремонта меньше указанной даты, то ничего не делаем.
            # Иначе переходим на сохранение в SparePartShipmentV2
            return super().save_model(request, obj, form, change)

        with transaction.atomic():
            if not change:
                obj.user = request.user
            elif not obj.pk:
                obj.user = request.user

            spare_parts_data = []
            spare_part_count_json = {}

            # Извлекаем данные о запчастях из POST
            for key, value in request.POST.items():
                if key.startswith('spare_part_quantities['):
                    try:
                        data = json.loads(value)
                        spare_parts_data.append(data)
                    except json.JSONDecodeError:
                        continue

            if not spare_parts_data:
                # Если запчастей нет, то в отгрузку ничего не добавдляем
                return super().save_model(request, obj, form, change)

            # Обновляем данные в формате JSON для поля spare_part_count
            for spare_part_info in spare_parts_data:
                spare_part_id = spare_part_info['id']
                new_quantity = spare_part_info['quantity']
                expiration_dt = spare_part_info['expiration_dt']

                if spare_part_id in spare_part_count_json:
                    spare_part_count_json[spare_part_id].append({
                        "expiration_dt": expiration_dt,
                        "service_part_count": new_quantity
                    })
                else:
                    spare_part_count_json[spare_part_id] = [{
                        "expiration_dt": expiration_dt,
                        "service_part_count": new_quantity
                    }]

            comment = (
                f"Отгружено в {obj.equipment_accounting.equipment_acc_department_equipment_accounting.first().department.name}\n"
                f"Дата проведения работ: {obj.beg_dt.strftime('%d.%m.%Y')}г.\n"
                f"Анализатор: {obj.equipment_accounting.equipment.short_name} "
                f"(s/n {obj.equipment_accounting.serial_number.upper()})"
            )

            # Сохраняем JSON с информацией о запчастях
            obj.spare_part_count = spare_part_count_json

            # Вызываем оригинальный метод сохранения
            super().save_model(request, obj, form, change)

            # Создаем или обновляем запись в SparePartShipmentV2
            shipment, created = SparePartShipmentV2.objects.get_or_create(
                service=obj,
                defaults={
                    'shipment_dt': obj.beg_dt,
                    'user': request.user,
                    'comment': comment,
                    'is_auto_comment': True,
                }
            )

            # Удаляем старые записи о запчастях
            shipment.shipment_m2m.all().delete()

            # Добавляем новые записи о запчастях через промежуточную модель
            for spare_part_info in spare_parts_data:
                SparePartShipmentM2M.objects.create(
                    shipment=shipment,
                    spare_part_id=spare_part_info["id"],
                    quantity=spare_part_info["quantity"],
                    expiration_dt=spare_part_info["expiration_dt"]
                )

        #TODO: включить, если нужно учитывать количество запчастей из SparePartCount
        # def delete_model(self, request, obj):
        #     """
        #     Переопределяем удаление для возврата запчастей
        #     """
        #     # Перед удалением возвращаем запчасти в наличие
        #     if hasattr(obj, 'spare_part') and obj.spare_part.all().exists():
        #         for spare_part in obj.spare_part.all():
        #             try:
        #                 spare_part_count = SparePartCount.objects.get(spare_part_id=spare_part.id)
        #                 # Здесь нужно знать, сколько запчастей использовалось в данной записи
        #                 # Это значение должно храниться в связанной модели
        #                 used_quantity = self.get_used_quantity(obj, spare_part.id)
        #                 spare_part_count.available_quantity += used_quantity
        #                 spare_part_count.save()
        #             except SparePartCount.DoesNotExist:
        #                 pass
        #
        #     super().delete_model(request, obj)


@admin.register(Supplier)
class SupplierAdmin(MainAdmin):
    autocomplete_fields = ('city',)
    list_display = ('name', 'inn', 'contact_person', 'contact_phone', 'email',
                    'country_name', 'city_name', 'address',)
    search_fields = ('name', 'inn')
    search_help_text = 'Поиск по Поставщику или ИНН'
    ordering = ('name',)

    fieldsets = (
        ('Новый поставщик', { 'fields': ('name', 'inn')}),
        ('Адрес', {'fields': ('country', 'city', 'address',)}),
        ('Контакты поставщика', {'fields': ('contact_person', 'contact_phone', 'email')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('city', 'country')

    @admin.display(description='Город')
    def city_name(self, obj):
        return obj.city.name if obj.city else '-'

    @admin.display(description='Страна')
    def country_name(self, obj):
        return obj.country.name if obj.country else '-'
