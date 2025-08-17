import re
import logging
import json
from django.utils.safestring import mark_safe
from django.db.models import Prefetch

from spare_part.models import SparePart, SparePartCount
from directory.models import Position
from .forms import *
from .admin_filters import *
from .docx_create import CreateServiceAkt

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
        return super().get_queryset(request).select_related(
            'med_direction', 'manufacturer', 'supplier'
        ).prefetch_related('spare_part')

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
        return instance.department

    @admin.display(description='Инженер')
    def engineer(self, obj):
        instance = self.get_instance(obj)
        if isinstance(instance, list):
            instance = instance[0]
        return instance.engineer

    @admin.display(description='Дата монтажа')
    def install_dt(self, obj):
        instance = self.get_instance(obj)
        if isinstance(instance, list):
            instance = instance[0]
        return instance.install_dt.strftime('%d.%m.%Y г.') if instance.install_dt else '-'

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
    add_form_template = 'ebase/admin/service_change_form.html'
    # autocomplete_fields = ('equipment_accounting',)
    date_hierarchy = 'beg_dt'
    filter_horizontal = ('spare_part',)
    inlines = (ServicePhotosInline, )
    list_display = ('equipment_accounting', 'dept_name', 'service_type',
                    'photos',
                    'description_short', 'spare_part_used',
                    'reason_short', 'job_content_short', 'akt',
                    'beg_dt', 'end_dt',)
    list_select_related = ('equipment_accounting', 'service_type',)
    readonly_fields = ('service_akt_url',)
    search_fields = ('equipment_accounting__equipment__full_name',
                     'equipment_accounting__equipment__short_name',
                     'equipment_accounting__serial_number',)
    search_help_text = 'Поиск по полному/краткому наименованию оборудования или по серийному номеру'
    ordering = ('-beg_dt', 'equipment_accounting',)

    fieldsets = (
        (
            'Данные на оборудование', {'fields':
                                           ('equipment_accounting', 'service_type', 'spare_part', )
                                       }
        ),
        (
            'Описание работ', {
                'classes': ('collapse',),
                'fields': ('reason', 'description', 'job_content',),
            }
        ),
        ('Дата работ', {'fields': (('beg_dt', 'end_dt'),)}),
        ('Документы по ремонту', {'fields': ('service_akt_url',),})
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
                    'department__client',
                    'department__client__city'
                ).filter(is_active=True)
            ),
            Prefetch(
                "service_photos",
                queryset=ServicePhotos.objects.all()
            )
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
        # dept_id_list = obj.equipment_accounting.equipment_acc_department_equipment_accounting \
        #     .prefetch_related(Prefetch(
        #                           'equipment_accounting__equipment_acc_department_equipment_accounting__department',
        #                           queryset=Department.objects.all()
        #                       )) \
        #     .filter(is_active=True)\
        #     .values_list('department', flat=True)
        # dept = Department.objects.filter(id__in=dept_id_list).values_list('name', flat=True)
        # return "; ".join(dept) if dept else '-'
        # Используем предзагруженные данные из get_queryset

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
            return mark_safe(f'<span class="akt-span"><a href="{url}">{akt_name}</a></span>'
                             f'<input type="button" id="akt-create-btn" value="Обновить">')
        if obj.pk:
            return mark_safe('<span class="akt-span">Акт не создан</span>'
                             '<input type="button" id="akt-create-btn" value="Создать">')
        # При создании новой записи направит сюда
        return mark_safe('<span class="akt-span">-------</span>')

    @admin.action(description='Создать - Акт о проведении работ')
    def create_service_akt_by_action(self, request, queryset) -> None:
        """Формирование актов о проделаной работе для выбранных случаев"""
        equipments_list: list = []
        for qs in queryset:
            create_akt = self.create_service_atk(obj=qs)
            equipments_list.append(f"{create_akt[0]} (s/n {create_akt[1]})")
        if len(equipments_list) > 1:
            msg = f"Акты сформированы для: {', '.join(equipments_list)}."
        else:
            msg = f"Акт сформирован для {', '.join(equipments_list)}."

        self.message_user(request, message=msg)

    @staticmethod
    def create_service_atk(obj: Service):
        """Создание акта для преданного объекта из модели Service"""
        dept = obj.equipment_accounting.equipment_acc_department_equipment_accounting.first().department
        client_city = dept.client.city.name if dept.client.city.name != 'Не указан' else ''
        address = f"{client_city} {dept.client.address if dept.client.address else ''}"
        client = {
            '{{ CLIENT }}': dept.client.name,
            '{{ ADDRESS }}': address,
            '{{ PHONE }}': dept.client.phone if dept.client.phone else '',
            '{{ EMAIL }}': dept.client.email if dept.client.email else '',
            '{{ INN }}': f"ИНН {dept.client.inn if dept.client.inn else ''}",
            '{{ KPP }}': f"КПП {dept.client.kpp}" if dept.client.kpp else 'КПП',
            '{{ EQUIPMENT }}': obj.equipment_accounting.equipment.full_name
            if obj.equipment_accounting.equipment.full_name else '',
            '{{ SERIAL_NUM }}': obj.equipment_accounting.serial_number,
            '{{ DATE }}': obj.end_dt.strftime('%d.%m.%Y') if obj.end_dt else '________________',
            'equipment_short_name': obj.equipment_accounting.equipment.short_name
            if obj.equipment_accounting.equipment.short_name else obj.equipment_accounting.equipment.full_name,
        }
        description = obj.description if obj.description else ''
        job_content = obj.job_content if obj.job_content else ''
        spare_parts = list(obj.spare_part.values_list('name', 'article'))
        create_akt = CreateServiceAkt(client, job_content, description, spare_parts)
        create_akt.update_tables()
        obj.service_akt = create_akt.save_file_path
        obj.save()

        return client['equipment_short_name'], client['{{ SERIAL_NUM }}']

    def get_form(self, request, obj=None, change=False, **kwargs):
        """В карточке по ремонту есть кнопка по созданию акта. Чтобы отследить её
        нажатие, через JS в GET передается параметр akt"""
        if re.search(r'(akt=create)', request.META['QUERY_STRING']):
            if obj:
                create_akt = self.create_service_atk(obj)
                self.message_user(request,
                                  message=f"Акт сформирован для "
                                          f"{create_akt[0]} (s/n {create_akt[1]})")
        return super().get_form(request, obj=None, change=False, **kwargs)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)

    #     response.context_data['cl'].list_display = [
    #         f'<div style="width:200px">{col}</div>' for col in response.context_data['cl'].list_display
    #     ]
        return response

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Формируем список оборудования с серийными номера на основе
        id полученного из get-запроса"""
        eq_id: list = []
        if db_field.name == 'equipment_accounting':
            if re.search(r'\/service\/add\/', request.path):  # Проверяем, что это страница с добавлением новой записи
                eq_id = request.GET.getlist('eq_select')
            if eq_id:
                kwargs["queryset"] = EquipmentAccounting.objects.filter(equipment__id__in=eq_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """Формируем список запчастей для оборудования на основе
        его id полученного из get-запроса"""
        eq_id: list = []
        if db_field.name =='spare_part':
            if re.search(r'\/service\/add\/', request.path):  # Проверяем, что это страница с добавлением новой записи
                eq_id = request.GET.getlist('eq_select')
            elif re.search(r'\/service\/.*\/change\/', request.path):
                # Фильтруем запчасти на странице изменения по ремонту оборудования
                service_id = request.path.strip().split('/')[-3]
                eq_id.append(Service.objects.get(pk=service_id).equipment_accounting.equipment.pk)
            if eq_id:
                kwargs["queryset"] = SparePart.objects.filter(equipment__id__in=eq_id)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        elif not obj.pk:
            obj.user = request.user
        super().save_model(request, obj, form, change)

        spare_parts_data = []

        # Извлекаем данные из POST параметров
        for key, value in request.POST.items():
            if key.startswith('spare_part_quantities['):
                try:
                    data = json.loads(value)
                    spare_parts_data.append(data)
                except json.JSONDecodeError:
                    continue

        #TODO: отгружать с худшим сроком

        # Обновляем количества запчастей
        for spare_part_info in spare_parts_data:
            spare_part_id = spare_part_info['id']
            new_quantity = spare_part_info['quantity']
            original_quantity = spare_part_info['originalQuantity']

            try:
                spare_part_count = SparePartCount.objects.get(spare_part_id=spare_part_id)

                # Рассчитываем изменение
                quantity_change = new_quantity - original_quantity

                # Обновляем доступное количество
                spare_part_count.amount -= quantity_change
                spare_part_count.amount = max(0, spare_part_count.amount)
                spare_part_count.save()

            except SparePartCount.DoesNotExist:
                # Если записи не существует, создаем её
                SparePartCount.objects.create(
                    spare_part_id=spare_part_id,
                    amount=max(0, -new_quantity)
                )


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
