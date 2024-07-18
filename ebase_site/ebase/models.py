import uuid
from enum import Enum

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, EmailValidator
from django.contrib.postgres.fields import ArrayField
# from users.models import CompanyUser


company = '"medsil"'  # название схемы для таблиц


class PositionType(Enum):
    """Тип должности."""
    EMPLOYEE = 'Сотрудник'
    CLIENT = 'Клиент'


class EbaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='ID', db_comment='ID записи', help_text='ID записи')
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания записи',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        abstract = True


class City(models.Model):
    """Модель для перечьня городов."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Город',
        db_comment='Город', help_text='Город'
    )
    region = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Регион',
        db_comment='Регион', help_text='Регион, Область в которой расположен город'
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания записи',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        db_table = f'{company}."city"'
        db_table_comment = 'Таблица с перечнем городов. \n\n-- BMatyushin'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        unique_together = ('name', 'region')

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
        db_table = f'{company}."client"'
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
        db_table = f'{company}."department"'
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
        db_table = f'{company}."dept_contact_pers"'
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
        related_name="equipment_med_equipment", verbose_name="ID Направления",
        db_comment="ID направления", help_text="ID из таблицы Направления."
    )
    manufacturer = models.ForeignKey(
        "Manufacturer", on_delete=models.SET_NULL, null=True,
        related_name="equipment_manufacturer", verbose_name="ID Производителя",
        db_comment="ID производителя", help_text="ID из таблицы Производителя."
    )
    supplier = models.ForeignKey(
        "Supplier", on_delete=models.SET_NULL, null=True,
        related_name="equipment_supplier", verbose_name="ID Поставщика",
        db_comment="ID поставщика", help_text="ID из таблицы Поставщика."
    )
    spare_part = models.ManyToManyField(
        "SparePart", related_name="equipment_spare_part", verbose_name="ID Запасных частей",
        help_text="ID из таблицы Запасных частей."
    )

    class Meta:
        db_table = f'{company}."equipment"'
        db_table_comment = "Перечень моделей медициского оборудования.\n\n-- BMatyushin"
        verbose_name = 'Медицинское оборудование'
        verbose_name_plural = 'Медицинских оборудований'

    def __repr__(self):
        return f'<Equipment {self.full_name=!r}>'


class EquipmentAccDepartment(EbaseModel):
    """Учет поставленного оборудования в подразделения клиента.
    Для полей с автоматическим заполнением, обязательно editable=False"""
    equipment_accounting = models.ForeignKey(
        'EquipmentAccounting', on_delete=models.RESTRICT, null=False, editable=False,
        related_name='equipment_acc_department_equipment_accounting',
        verbose_name='ID Учёта оборудования', db_comment="ID Учёта оборудования",
        help_text="ID Учёта оборудования. Заполняется автоматически"
    )
    department = models.ForeignKey(
        'Department', on_delete=models.RESTRICT, null=False, editable=False,
        related_name='equipment_accounting_department_department', verbose_name='ID Подразделения',
        db_comment="ID подразделения", help_text="ID подразделения. Заполняется автоматически"
    )
    user = models.ManyToManyField(
        'users.CompanyUser', verbose_name='ID инженера',
        related_name='equipment_accounting_company_user',
        help_text="ID сотрудника-ИНЖНЕРА, который запускал оборудование. Заполняется автоматически"
    )
    is_active = models.BooleanField(
        default=True, verbose_name='У клиента',
        db_comment='Флаг, указывающий на то, что прибор установлен в подразделении клиента',
        help_text='Флаг, указывающий на то, что прибор установлен в подразделении клиента'
    )

    class Meta:
        db_table = f'{company}."equipment_acc_department"'
        db_table_comment = 'Учет поставленного оборудования в подразделения клиента.\n\n-- BMatyushin'
        verbose_name = 'Учет поставленного оборудования'
        verbose_name_plural = 'Учет поставленного оборудования'
        
    def __repr__(self):
        return f"<EquipmentAccDepartment {self.id=!r}, {self.is_active=!r}>"


class EquipmentAccounting(EbaseModel):
    """Модель для учета оборудований.
    Для полей с автоматическим заполнением, обязательно editable=False"""
    equipment = models.ForeignKey(
        'Equipment', on_delete=models.RESTRICT, null=False, editable=False,
        related_name='equipment_accounting_equipment', verbose_name='ID Оборудования',
        db_comment="ID оборудования", help_text="ID оборудования. Заполняется автоматически"
    )
    equipment_status = models.ForeignKey(
        'EquipmentStatus', on_delete=models.SET_NULL, null=True, editable=True,
        related_name='equipment_accounting_equipment_status',
        verbose_name='ID Статус оборудования', db_comment="ID статуса оборудования",
        help_text="ID статуса оборудования"
    )
    service = models.ManyToManyField(
        'Service', related_name='equipment_accounting_service', verbose_name='ID Ремонта',
        help_text='Заполняется, если оборудование было сдано в ремонт'
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.SET_NULL, null=True, editable=False,
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
        db_table = f'{company}."equipment_accounting"'
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
        db_table = f'{company}."equipment_status"'
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
        db_table = f'{company}."manufacturer"'
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
        db_table = f'{company}."med_direction"'
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
        choices=[(t.value, t.name) for t in PositionType], db_comment='Тип должности',
        help_text='Тип должности. Cотрудник - для компании, организации. Клиент - для учреждений'
    )

    class Meta:
        db_table = f'{company}."position"'
        db_table_comment = 'Должности сотрудников и клиентов. \n\n-- BMatyushin'
        verbose_name = 'Должность'
        verbose_name_plural = 'Должности'

    def __repr__(self):
        return f'<Position {self.name=!r}>'


class Service(EbaseModel):
    """Таблица для учета поступившего на ремонт оборудования."""
    service_type = models.ForeignKey(
        "ServiceType", on_delete=models.SET_NULL, null=True,
        related_name="service_service_type", verbose_name='ID Типа ремонта',
        db_comment='ID Типа ремонта', help_text='ID Типа ремонта из таблицы "Тип ремонта"'
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.RESTRICT, null=False,
        related_name="service_company_user", verbose_name='ID Пользователя',
        db_comment='ID Пользователя (сотрудника)',
        help_text='ID Пользователя (сотрудника) из таблицы "Пользователи"'
    )
    description = models.TextField(
        null=True, blank=True, verbose_name='Описание неисправности',
        db_comment='Описание неисправности', help_text='Описание неисправности'
    )
    reason = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Причина',
        db_comment='На основании чего делается ремонт',
        help_text='На основании чего делается ремонт'
    )
    job_content = models.TextField(
        null=True, blank=True, verbose_name='Содержание работ',
        db_comment='Содержание работ', help_text='Содержание работ'
    )
    beg_dt = models.DateField(
        auto_now_add=True, editable=False, verbose_name='Дата начала ремонта',
        db_comment='Дата начала ремонта', help_text='Дата начала ремонта'
    )
    end_dt = models.DateField(
        null=True, blank=True, verbose_name='Дата окончания ремонта',
        db_comment='Дата окончания ремонта', help_text='Дата окончания ремонта'
    )
    comment = models.TextField(
        null=True, blank=True, verbose_name='Комментарии',
        db_comment='Примечание, комментарии по ремонту',
        help_text='Примечание, комментарии по ремонту'
    )
    equipment_accounting = models.ManyToManyField(
        "EquipmentAccounting", related_name="service_equipment_accounting",
        verbose_name='ID учтённого оборудования',
        help_text="ID учтённого оборудования. Заполняется автоматически"
    )
    spare_part = models.ManyToManyField(
        "SparePart", related_name="service_spare_part", verbose_name='ID запчасти',
        help_text="ID запчасти"
    )

    class Meta:
        db_table = f'{company}."service"'
        db_table_comment = 'Учет ремонта оборудования. \n\n-- BMatyushin'
        verbose_name = 'Учет ремонта оборудования'
        verbose_name_plural = 'Учет ремонта оборудования'

    def __repr__(self):
        return f'<Service {self.id=!r}, {self.user=!r}>'


class ServiceType(models.Model):
    """Типы ремонта / Виды работ"""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Тип ремонта',
        db_comment='Тип ремонта', help_text='Тип ремонта'
    )

    class Meta:
        db_table = f'{company}."service_type"'
        db_table_comment = 'Типы ремонтов / Виды работ. \n\n-- BMatyushin'
        verbose_name = 'Тип ремонта'
        verbose_name_plural = 'Типы ремонтов'

    def __repr__(self):
        return f'<ServiceType {self.name=!r}>'


class SparePart(EbaseModel):
    """Запчасти."""
    article = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Артикул',
        db_comment='Артикул', help_text='Артикул'
    )
    name = models.CharField(
        max_length=100, null=False, blank=False,verbose_name='Наименование',
        db_comment='Наименование запчасти', help_text='Наименование запчасти'
    )
    unit = models.ForeignKey(
        "Unit", on_delete=models.RESTRICT, null=False, default=1,
        related_name="spare_part_unit", verbose_name='Единица измерения',
        db_comment='Единица измерения', help_text='Единица измерения'
    )
    comment = models.TextField(
        null=True, blank=True, verbose_name='Примечание',
        db_comment='Примечание к запчасти', help_text='Примечание к запчасти'
    )
    is_expiration = models.BooleanField(
        default=False, verbose_name='Срок годности',
        db_comment='Отмечаются запчасти со сроками годности',
        help_text='Флаг указывающий, что у запчасти должен быть срок годности'
    )
    equipment = models.ManyToManyField(
        "Equipment", related_name="spare_part_equipment", verbose_name='ID Оборудования',
        help_text="ID оборудования, для которого предназначена эта запчасть"
    )
    service = models.ManyToManyField(
        "Service", related_name="spare_part_service", verbose_name='ID Ремонта',
        help_text="ID ремонта, в котором использовалась запчасть"
    )

    class Meta:
        db_table = f'{company}."spare_part"'
        db_table_comment = 'Справочник запчастей. \n\n-- BMatyushin'
        verbose_name = 'Справочник запчастей'
        verbose_name_plural = 'Справочник запчастей'
        unique_together = ('article', 'name',)

    def __repr__(self):
        return f'<SparePart {self.name=!r}>'


class SparePartCount(EbaseModel):
    """Общее количество запчастей (чтобы не делать сложные запросы для вывода этой инфы)"""
    spare_part = models.ForeignKey(
        'SparePart', on_delete=models.RESTRICT, null=False, blank=False,
        related_name="spare_part_count_spare_part", verbose_name='ID запчасти',
        db_comment="ID запчасти", help_text="ID запчасти"
    )
    amount = models.FloatField(
        verbose_name='Кол-во', db_comment='Кол-во запчастей',
        help_text='Кол-во запчастей. Заполняется автоматически',
        validators=[MinValueValidator(0)], null=False, blank=False,
    )
    expiration_dt = models.DateField(
        null=True, blank=True, verbose_name='Годен до',
        db_comment='Годен до. Срок годности для запчастей со сроком годности.',
        help_text='Годен до. Срок годности для запчастей со сроком годности.',
    )
    is_overdue = models.BooleanField(
        default=False, verbose_name='Просрочено',
        db_comment='Флаг указывающий, что запчасть просрочена',
        help_text='Флаг указывающий, что запчасть просрочена'
    )

    class Meta:
        db_table = f'{company}."spare_part_count"'
        db_table_comment = 'Общее количество запчастей на остатке.\n\n-- BMatyushin'
        verbose_name = 'Количество запчастей'
        verbose_name_plural = 'Количество запчастей'
        unique_together = ('spare_part', 'expiration_dt')

    def __repr__(self):
        return f'<SparePartCount {self.spare_part=!r} {self.amount=!r}>'


class SparePartShipment(EbaseModel):
    """Отслеживание отгрузок запчастей"""
    spare_part = models.ForeignKey(
        'SparePart', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="spare_part_shipment_spare_part", verbose_name='ID запчасти',
        db_comment="ID запчасти", help_text="ID запчасти"
    )
    count_shipment = models.FloatField(
        verbose_name='Кол-во', db_comment='Кол-во отгруженной запчасти',
        help_text='Кол-во отгруженной запчасти', null=False, blank=False,
        validators=[MinValueValidator(0)]
    )
    expiration_dt = models.DateField(
        null=True, blank=True, verbose_name='Годен до',
        db_comment='Годен до. Срок годности для запчастей со сроком годности.',
        help_text='Годен до. Срок годности для запчастей со сроком годности.',
    )
    shipment_dt = models.DateField(
        null=False, blank=False, verbose_name='Дата отгрузки',
        db_comment='Дата отгрузки', help_text='Дата отгрузки.'
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.RESTRICT, null=False, blank=False,
        related_name='spare_part_shipment_company_user', verbose_name='ID сотрудника',
        db_comment="ID сотрудника, который оформил отгрузку",
        help_text="ID сотрудника, который оформил отгрузку. Заполняется автоматически"
    )

    class Meta:
        db_table = f'{company}."spare_part_shipment"'
        db_table_comment = 'Отслеживание отгрузок запчастей. \n\n-- BMatyushin'
        verbose_name = 'Отгрузка запчастей'
        verbose_name_plural = 'Отгрузки запчастей'

    def __repr__(self):
        return f"<SparePartShipment: {self.spare_part=!r}, {self.count_shipment=!r}>"


class SparePartSupply(EbaseModel):
    """Отслеживание поставок запчастей"""
    spare_part = models.ForeignKey(
        'SparePart', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="spare_part_supply_spare_part", verbose_name='ID запчасти',
        db_comment="ID запчасти", help_text="ID запчасти"
    )
    count_supply = models.FloatField(
        verbose_name='Кол-во', db_comment='Кол-во поставленой запчасти',
        help_text='Кол-во поставленой запчасти', null=False, blank=False,
        validators=[MinValueValidator(0)],
    )
    expiration_dt = models.DateField(
        null=True, blank=True, verbose_name='Годен до',
        db_comment='Годен до. Срок годности для запчастей со сроком годности.',
        help_text='Годен до. Срок годности для запчастей со сроком годности.',
    )
    supply_dt = models.DateField(
        null=False, blank=False, verbose_name='Дата поставки',
        db_comment='Дата поставки', help_text='Дата поставки.'
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.RESTRICT, null=False, blank=False,
        related_name='spare_part_supply_company_user', verbose_name='ID сотрудника',
        db_comment="ID сотрудника, который оформил поставку",
        help_text="ID сотрудника, который оформил поставку. Заполняется автоматически"
    )

    class Meta:
        db_table = f'{company}."spare_part_supply"'
        db_table_comment = 'Отслеживание поставок запчастей. \n\n-- BMatyushin'
        verbose_name = 'Поставка запчастей'
        verbose_name_plural = 'Поставки запчастей'

    def __repr__(self):
        return f"<SparePartSupply: {self.spare_part=!r}, {self.count_supply=!r}>"


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
        db_table = f'{company}."supplier"'
        db_table_comment = 'Поставщики оборудования. \n\n-- BMatyushin'
        verbose_name = 'Поставщик оборудования'
        verbose_name_plural = 'Поставщики оборудования'

    def __repr__(self):
        return f'<Supplier {self.name=!r}, {self.city=!r}>'


class Unit(models.Model):
    """Единицы измерения."""
    short_name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Сокращенное наименование',
        db_comment='Единица измерения', help_text='Единица измерения',
        unique=True,
    )
    full_name = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Полное наименование',
        db_comment='Полное наименование единицы измерения',
        help_text='Полное наименование единицы измерения'
    )

    class Meta:
        db_table = f'{company}."unit"'
        db_table_comment = 'Справочник с единицами измерения. \n\n-- BMatyushin'
        verbose_name = 'Единица измерения'
        verbose_name_plural = 'Единицы измерения'

    def __repr__(self):
        return f'<Unit {self.short_name=!r}>'

