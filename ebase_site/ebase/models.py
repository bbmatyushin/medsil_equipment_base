import uuid
from enum import Enum

from django.db import models
from django.contrib.auth.models import User


class PositionType(Enum):
    """Тип должности."""
    EMPLOYEE = 'Сотрудник'
    CLIENT = 'Клиент'


class EbaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='UUID', db_comment='UUID записи', help_text='UUID записи')
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания записи',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        abstract = True


class City(EbaseModel):
    """Модель для перечьня городов."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Город',
        db_comment='Город', help_text='Город'
    )
    region = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Регион',
        db_comment='Регион', help_text='Регион, Область в которой расположен город'
    )

    class Meta:
        db_table = 'city'
        db_table_comment = 'Таблица с перечнем городов. \n\n-- BMatyushin'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'

    def __repr__(self):
        return f"<City {self.name=!r}, {self.region=!r}>"


class Client(EbaseModel):
    """Модель для перечьня клиентов."""
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Наименование',
        db_comment='Наименование клиента', help_text='Наименование клиента'
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН',
        db_comment='ИНН клиента', help_text='ИНН клиента'
    )
    country = models.CharField(
        max_length=20, null=True, blank=True, verbose_name='Страна',
        db_comment='Страна клиента', help_text='Страна клиента'
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес клиента', help_text='Адрес клиента'
    )
    city = models.ForeignKey(
        "City", on_delete=models.SET_NULL, null=True,
        related_name="client_city", verbose_name='Город',
        db_comment='Город клиента', help_text='Город клиента'
    )

    class Meta:
        db_table = 'client'
        db_table_comment = 'Таблица с перечнем клиентов. \n\n-- BMatyushin'
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'

    def __repr__(self):
        return f"<Client {self.name=!r}, {self.inn=!r}>"


class Department(EbaseModel):
    """Подразделения, филиалы клиентов"""
    name = models.CharField(
        max_length=200, null=False, blank=False, verbose_name='Наименование',
        db_comment='Наименование подразделения', help_text='Наименование подразделения'
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес подразделения', help_text='Адрес подразделения'
    )
    client = models.ForeignKey(
        "Client", on_delete=models.SET_NULL, null=True,
        related_name="department_client", verbose_name='Клиент',
        db_comment='Клиент подразделения', help_text='Клиент подразделения'
    )
    city = models.ForeignKey(
        "City", on_delete=models.SET_NULL, null=True,
        related_name="department_city", verbose_name='ID Города',
        db_comment='ID Города подразделения', help_text='ID города в котором расположено подразделение'
    )

    class Meta:
        db_table = 'department'
        db_table_comment = 'Подразделения, филиаы клиентов.\n\n-- BMatyushin'
        verbose_name = 'Подразделение / Филиал'
        verbose_name_plural = 'Подразделения / Филиалы'

    def __repr__(self):
        return f"<Department {self.name=!r}"


class DeptContactPers(EbaseModel):
    """Контактные лица подразделения"""
    department = models.ForeignKey(
        "Department", on_delete=models.SET_NULL, null=True,
        related_name="dept_contactpers_department", verbose_name='ID Подразделения',
        db_comment='ID Подразделения', help_text='ID Подразделения'
    )
    patron = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Отчество',
        db_comment='Отчество контактного лица', help_text='Отчество контактного лица'
    )
    surname = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Фамилия',
        db_comment='Фамилия контактного лица', help_text='Фамилия контактного лица'
    )
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Имя',
        db_comment='Имя контактного лица', help_text='Имя контактного лица'
    )
    position = models.ForeignKey(
        "Position", on_delete=models.SET_NULL, null=True,
        related_name="dept_contactpers_position", verbose_name='Должность',
        db_comment='Должность контактного лица', help_text='Должность контактного лица'
    )
    mod_phone = models.CharField(
        max_length=60, null=True, blank=True, verbose_name='Моб.Телефон',
        db_comment='Мобильный телефон контактного лица',
        help_text='Мобильный телефон контактного лица'
    )
    work_phone = models.CharField(
        max_length=60, null=True, blank=True, verbose_name='Раб.Телефон',
        db_comment='Рабочий телефон контактного лица',
        help_text='Рабочий телефон контактного лица'
    )
    mod_email = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='E-mail',
        db_comment='E-mail контактного лица', help_text='E-mail контактного лица'
    )
    comment = models.CharField(
        max_length=300, null=True, blank=True, verbose_name='Комментарий',
        db_comment='Комментарий контактного лица', help_text='Комментарий контактного лица'
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Работает',
        db_comment='Для отметки работает ли ещё контактное лицо',
        help_text='Для отметки работает ли ещё контактное лицо'
    )

    class Meta:
        db_table = 'dept_contact_pers'
        db_table_comment = 'Контактные лица подразделения.\n\n-- BMatyushin'
        verbose_name = 'Контактное лицо подразделения'
        verbose_name_plural = 'Контактные лица подразделения'

    def __repr__(self):
        return f"<DeptContactPers {self.name}>"


class Equipment(EbaseModel):
    """Модель для перечьня моделей медицинского оборудования.
    Для полей с автоматическим заполнением, обязательно editable=False"""
    full_name = models.CharField(
        max_length=256, null=False, blank=False,
        db_comment="Полное наименование оборудования", verbose_name="Полное наименование",
        help_text="Полное наименование оборудования"
    ),
    short_name = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Краткое наименование',
        db_comment="Краткое наименование оборудования", help_text="Краткое наименование оборудования"
    ),
    med_direction = models.ForeignKey(
        "MedDirection", on_delete=models.SET_NULL, null=True,
        related_name="equipment_med_equipment", verbose_name="UUID Направления",
        db_comment="UUID направления", help_text="UUID из таблицы Направления."
    )
    manufacturer = models.ForeignKey(
        "Manufacturer", on_delete=models.SET_NULL, null=True,
        related_name="equipment_manufacturer", verbose_name="UUID Производителя",
        db_comment="UUID производителя", help_text="UUID из таблицы Производителя."
    )
    supplier = models.ForeignKey(
        "Supplier", on_delete=models.SET_NULL, null=True,
        related_name="equipment_supplier", verbose_name="UUID Поставщика",
        db_comment="UUID поставщика", help_text="UUID из таблицы Поставщика."
    )

    class Meta:
        db_table = 'equipment'
        db_table_comment = "Перечень моделей медициского оборудования.\n\n-- BMatyushin"
        verbose_name = 'Медицинское оборудование'
        verbose_name_plural = 'Медицинских оборудований'

    def __repr__(self):
        return f'<Equipment {self.full_name=!r}>'


class EquipmentAccounting(EbaseModel):
    """Модель для учета оборудований.
    Для полей с автоматическим заполнением, обязательно editable=False"""
    equipment = models.ForeignKey(
        'Equipment', on_delete=models.RESTRICT, null=False, editable=False,
        related_name='equipment_accounting_equipment', verbose_name='UUID Оборудования',
        db_comment="UUID оборудования", help_text="UUID оборудования. Заполняется автоматически"
    )
    equipment_status = models.ForeignKey(
        'EquipmentStatus', on_delete=models.SET_NULL, null=True, editable=True,
        related_name='equipment_accounting_equipment_status',
        verbose_name='UUID Статус оборудования', db_comment="UUID статуса оборудования",
        help_text="UUID статуса оборудования"
    )
    # TODO: добавить модель Service
    # service = models.ForeignKey(
    #     'Service', on_delete=models.CASCADE, null=True,
    #     related_name='equipment_accounting_service', verbose_name='UUID Ремонта',
    #     db_comment='Заполняется, если оборудование было сдано в ремонт',
    #     help_text='Заполняется, если оборудование было сдано в ремонт'
    # )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='equipment_accounting_user', verbose_name='Пользователь',
        db_comment='Пользователь, который добавил запись в таблицу "Учёт оборудования"',
        help_text=('Пользователь, который добавил запись в таблицу "Учёт оборудования". '
                  'Заполняется автоматически')
    )
    serial_number = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Серийный номер',
        db_comment='Серийный номер оборудования', help_text='Серийный номер оборудования'
    )
    is_our_service = models.BooleanField(
        null=False, blank=False, default=False, verbose_name='Обслужан нами',
        db_comment='True, если оборудование обслуживалось нами',
        help_text='True, если оборудование обслуживалось нами'
    )
    is_our_supply = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Поставлен нами',
        db_comment='True, если оборудование было поставлено нами',
        help_text='True, если оборудование было поставлено нами'
    )
    row_update_dt = models.DateTimeField(
        auto_now=True, editable=False, verbose_name='Дата обновления строки',
        db_comment='Дата обновления строки.',
        help_text='Дата обновления строки. Заполняется автоматически'
    )

    class Meta:
        db_table = 'equipment_accounting'
        indexes = [
            models.Index(fields=['serial_number'], name='serial_number_idx'),
        ]
        db_table_comment = ('Таблица с учёт оборудования. Для отслеживаия оборудования по его серийному '
                            'номеру.\n\n-- BMatyushin')
        verbose_name = 'Учёт оборудования'
        verbose_name_plural = 'Учёт оборудований'

    def __repr__(self):
        return f'<EquipmentAccounting {self.serial_number=!r}>'


class EquipmentStatus(models.Model):
    """Модель для фиксированного набора статусов оборудования"""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Статус',
        db_comment='Статус оборудования', help_text='Статус оборудования'
    )

    class Meta:
        db_table = 'equipment_status'
        db_table_comment = 'Таблица с набором статусов оборудования. \n\n-- BMatyushin'
        verbose_name = 'Статус оборудования'
        verbose_name_plural = 'Статусы оборудований'

    def __repr__(self):
        return f'<EquipmentStatus {self.name=!r}>'


class Manufacturer(EbaseModel):
    """Модель для перечьня производителей оборудования"""
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Производитель',
        db_comment='Производитель оборудования', help_text='Производитель оборудования'
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН',
        db_comment='ИНН производителя', help_text='ИНН производителя'
    )
    country = models.CharField(
        max_length=20, null=True, blank=True, verbose_name='Страна',
        db_comment='Страна производителя', help_text='Страна производителя'
    )
    city = models.ForeignKey(
        "City", on_delete=models.SET_NULL, null=True,
        related_name="manufacturer_city", verbose_name='Город',
        db_comment='Город производителя', help_text='Город производителя'
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес производителя', help_text='Адрес производителя'
    )
    contact_person = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Контактное лицо',
        db_comment='Контактное лицо производителя', help_text='Контактное лицо производителя'
    )
    contact_phone = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон производителя', help_text='Контактные телефоны производителя'
    )
    is_active = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Активен',
        db_comment='True, если производитель активен',
        help_text='True, если активен. Для мягкого удаления производителя.'
    )

    class Meta:
        db_table = 'manufacturer'
        db_table_comment = 'Производители оборудования. \n\n-- BMatyushin'
        verbose_name = 'Производитель оборудования'
        verbose_name_plural = 'Производители оборудований'

    def __repr__(self):
        return f'<Manufacturer {self.name=!r}, {self.city=!r}>'


class MedDirection(models.Model):
    """Модель для перечьня направлений для оборудования: Гематологическое, Биохимическое и т.д."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Направление',
        db_comment='Направление медицинского оборудования (Гематологическое, Биохимическое и т.д.)',
        help_text='Направление медицинского оборудования (Гематологическое, Биохимическое и т.д.).'
    )

    class Meta:
        db_table = 'med_direction'
        db_table_comment = ('Направления медицинского оборудования (Гематологическое, Биохимическое и т.д.).'
                            '\n\n-- BMatyushin')
        verbose_name = 'Направление мед.оборудования'
        verbose_name_plural = 'Направления мед.оборудования'

    def __repr__(self):
        return f'<MedDirection {self.name=!r}>'


class Position(models.Model):
    """Справочник должностей."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Должность',
        db_comment='Должность', help_text='Должность'
    )
    type = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Тип',
        choices=[t.value for t in PositionType], db_comment='Тип должности',
        help_text='Тип должности. Cотрудник - для компании, организации. Клиент - для учреждений'
    )

    class Meta:
        db_table = 'position'
        db_table_comment = 'Должности сотрудников и клиентов. \n\n-- BMatyushin'
        verbose_name = 'Должность'
        verbose_name_plural = 'Должности'

    def __repr__(self):
        return f'<Position {self.name=!r}>'


class Supplier(EbaseModel):
    """Поставщики оборудования."""
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Поставщик',
        db_comment='Поставщик оборудования', help_text='Поставщик оборудования'
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН',
        db_comment='ИНН поставщика', help_text='ИНН поставщика'
    )
    country = models.CharField(
        max_length=20, null=True, blank=True, verbose_name='Страна',
        db_comment='Страна поставщика', help_text='Страна поставщика'
    )
    city = models.ForeignKey(
        "City", on_delete=models.SET_NULL, null=True,
        related_name="supplier_city", verbose_name='Город',
        db_comment='Город поставщика', help_text='Город поставщика'
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес поставщика', help_text='Адрес поставщика'
    )
    contact_persone = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Контактное лицо',
        db_comment='Контактное лицо поставщика', help_text='Контактное лицо поставщика'
    )
    contact_phone = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон поставщика', help_text='Контактные телефоны поставщика'
    )
    is_active = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Активен',
        db_comment='True, если поставщик активен',
        help_text='True, если активен. Для мягкого удаления поставщика.'
    )

    class Meta:
        db_table = 'supplier'
        db_table_comment = 'Поставщики оборудования. \n\n-- BMatyushin'
        verbose_name = 'Поставщик оборудования'
        verbose_name_plural = 'Поставщики оборудования'

    def __repr__(self):
        return f'<Supplier {self.name=!r}, {self.city=!r}>'

