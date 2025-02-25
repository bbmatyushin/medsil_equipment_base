import uuid
from pathlib import Path

from django.db import models
from django.conf import settings
from django.core import validators
# from django.contrib.postgres.fields import ArrayField
from django.utils.timezone import now
from directory.models import get_instance_city


company = '"medsil"'  # название схемы для таблиц


class EbaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='ID', db_comment='ID записи', help_text='ID записи')
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        abstract = True


class Client(EbaseModel):
    """Модель для перечьня клиентов."""
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Наименование',
        db_comment='Наименование клиента', help_text='Название учреждения'
    )
    inn = models.CharField(
        max_length=12, null=True, blank=False, verbose_name='ИНН',
        db_comment='ИНН клиента', unique=True
    )
    kpp = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='КПП',
        db_comment='КПП клиента',
    )
    phone = models.CharField(
        max_length=60, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон клиента'
    )
    email = models.EmailField(
        max_length=50, null=True, blank=True,
        verbose_name='Email', db_comment='Почта клиента'
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес клиента'
    )
    city = models.ForeignKey(
        'directory.City', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="client_city", verbose_name='Город',
        db_comment='Город клиента', help_text='Город клиента',
    )

    class Meta:
        db_table = f'{company}."client"'
        db_table_comment = 'Таблица с перечнем клиентов. \n\n-- BMatyushin'
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        unique_together = ('name', 'city')

    def __str__(self):
        return f"{self.name}, {f'ИНН {self.inn}' if self.inn else ''}"

    def __repr__(self):
        return f"<Client {self.name=!r}, {self.inn=!r}>"


class Department(EbaseModel):
    """Подразделения, филиалы клиентов"""
    name = models.CharField(
        max_length=200, null=False, blank=False, verbose_name='Наименование',
        db_comment='Наименование подразделения', help_text='Наименование подразделения / филиала'
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес подразделения', help_text='Адрес подразделения / филиала без указания города'
    )
    client = models.ForeignKey(
        "Client", on_delete=models.SET_NULL, null=True,
        related_name="department_client", verbose_name='Клиент',
        db_comment='Клиент подразделения', help_text='Клиент, к которому относится подразделение',
    )
    city = models.ForeignKey(
        'directory.City', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="department_city", verbose_name='Город',
        db_comment='ID Города подразделения',
        help_text='Города в котором расположено подразделение',
    )

    class Meta:
        db_table = f'{company}."department"'
        db_table_comment = 'Подразделения, филиаы клиентов.\n\n-- BMatyushin'
        verbose_name = 'Подразделение / Филиал'
        verbose_name_plural = 'Подразделения / Филиалы'
        unique_together = ('name', 'address',)
        ordering = ('city',)
        indexes = [
            models.Index(models.F('name'), models.F('city'), name='department_name_city')
        ]

    def __str__(self):
        return f"{self.name} ({self.city.name})"  # сильно замедляет выдачу на странице
        # return f"{self.name}"

    def __repr__(self):
        return f"<Department {self.name=!r}"


class DeptContactPers(EbaseModel):
    """Контактные лица подразделения"""
    department = models.ForeignKey(
        "Department", on_delete=models.SET_NULL, null=True, blank=False,
        related_name="dept_contactpers_department", verbose_name='Подразделение',
        db_comment='ID Подразделения',
    )
    patron = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Отчество',
        db_comment='Отчество контактного лица',
    )
    surname = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='Фамилия',
        db_comment='Фамилия контактного лица',
    )
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Имя',
        db_comment='Имя контактного лица',
    )
    position = models.ForeignKey(
        'directory.Position', on_delete=models.SET_NULL, null=True,
        related_name="dept_contactpers_position", verbose_name='Должность',
        db_comment='Должность контактного лица',
    )
    mob_phone = models.CharField(
        max_length=60, null=True, blank=True, verbose_name='Моб.Телефон',
        db_comment='Мобильный телефон контактного лица',
        help_text='Можно указать несколько'
    )
    work_phone = models.CharField(
        max_length=60, null=True, blank=True, verbose_name='Раб.Телефон',
        db_comment='Можно указать несколько', help_text='Можно указать несколько'
    )
    email = models.CharField(
        max_length=50, null=True, blank=True, verbose_name='E-mail',
        db_comment='E-mail контактного лица',
    )
    comment = models.CharField(
        max_length=300, null=True, blank=True, verbose_name='Комментарий',
        db_comment='Комментарий контактного лица',
    )
    is_active = models.BooleanField(blank=False, null=True,
        default=True, verbose_name='Работает',
        db_comment='Для отметки работает ли ещё контактное лицо',
        help_text='Для отметки работает ли ещё контактное лицо'
    )

    class Meta:
        db_table = f'{company}."dept_contact_pers"'
        db_table_comment = 'Контактные лица подразделения.\n\n-- BMatyushin'
        verbose_name = 'Контактное лицо подразделения'
        verbose_name_plural = 'Контактные лица подразделений'

    def __str__(self):
        return f"{self.name if self.name else ''} " \
            + f"{self.patron if self.patron else ''} " \
            + f"{self.surname if self.surname else ''}"

    def __repr__(self):
        return f"<DeptContactPers {self.name=!r}>"


class Equipment(EbaseModel):
    """Модель для перечьня моделей медицинского оборудования.
    Для полей с автоматическим заполнением, обязательно editable=False"""
    full_name = models.CharField(
        max_length=256, null=True, blank=False,
        db_comment="Полное наименование оборудования", verbose_name="Полное наименование",
        help_text="Полное наименование + краткое должно быть уникальным сочетанием"
    )
    short_name = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name='Краткое наименование', db_comment="Краткое наименование оборудования",
        help_text="Полное наименование + краткое должно быть уникальным сочетанием"
    )
    med_direction = models.ForeignKey(
        'directory.MedDirection', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="equipment_med_equipment", verbose_name="Направление",
        db_comment="ID направления", help_text="ID из таблицы Направления."
    )
    manufacturer = models.ForeignKey(
        "Manufacturer", on_delete=models.SET_NULL, null=True, blank=False,
        related_name="equipment_manufacturer", verbose_name="Производитель",
        db_comment="ID производителя", help_text="ID из таблицы Производителя."
    )
    supplier = models.ForeignKey(
        "Supplier", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="equipment_supplier", verbose_name="Поставщик",
        db_comment="ID поставщика",
    )
    spare_part = models.ManyToManyField(
        "spare_part.SparePart", related_name="equipment_spare_part", verbose_name="ID Запасных частей",
        help_text="ID из таблицы Запасных частей."
    )

    class Meta:
        db_table = f'{company}."equipment"'
        db_table_comment = "Перечень моделей медициского оборудования.\n\n-- BMatyushin"
        verbose_name = 'Мед. оборудование'
        verbose_name_plural = 'Мед. оборудование'
        unique_together = ('full_name', 'short_name',)

    def __str__(self):
        return self.full_name

    def __repr__(self):
        return f'<Equipment {self.full_name=!r}>'


class EquipmentAccounting(EbaseModel):
    """Модель для учета оборудований.
    Для полей с автоматическим заполнением, обязательно editable=False"""
    equipment = models.ForeignKey(
        'Equipment', on_delete=models.RESTRICT, null=False, editable=True,
        related_name='equipment_accounting_equipment', verbose_name='Оборудования',
        db_comment="ID оборудования",
    )
    equipment_status = models.ForeignKey(
        'directory.EquipmentStatus', on_delete=models.SET_NULL, null=True, editable=True,
        related_name='equipment_accounting_equipment_status',
        verbose_name='Статус', db_comment="ID статуса оборудования"
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
    )
    is_our_supply = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Поставлен нами',
        db_comment='True, если оборудование было поставлено нами',
    )
    row_update_dt = models.DateTimeField(
        auto_now=True, editable=False, verbose_name='Дата обновления строки',
        db_comment='Дата обновления строки.',
        help_text='Дата обновления строки. Заполняется автоматически'
    )
    url_youjail = models.URLField(max_length=2000, verbose_name='Ссылка YouJail',
                                  null=True, blank=True, default=None,
                                  help_text='Ссылка для связи с сервисом YouJail',
                                  db_comment='Ссылка для связи с сервисом YouJail'
    )

    class Meta:
        db_table = f'{company}."equipment_accounting"'
        indexes = [
            models.Index(fields=['serial_number'], name='serial_number_idx'),
        ]
        db_table_comment = ('Таблица с учёт оборудования. Для отслеживаия оборудования по его серийному '
                            'номеру.\n\n-- BMatyushin')
        verbose_name = 'Учёт оборудования'
        verbose_name_plural = '1. Учёт оборудований'
        unique_together = ('serial_number', 'equipment')

    def get_absolute_url(self):
        return 'http://109.172.114.134/%s/' % self.pk
        # return reverse('equipment_accounting_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return f"{self.equipment} [{self.serial_number.upper()}]"

    def __repr__(self):
        return f'<EquipmentAccounting {self.serial_number=!r}>'


class EquipmentAccDepartment(EbaseModel):
    """Учет поставленного оборудования в подразделения клиента"""
    equipment_accounting = models.ForeignKey(
        'EquipmentAccounting', on_delete=models.CASCADE, null=False, editable=True,
        related_name='equipment_acc_department_equipment_accounting',
        verbose_name='Оборудование', db_comment="ID Учёта оборудования",
        help_text="Поставленное оборудование"
    )
    department = models.ForeignKey(
        'Department', on_delete=models.RESTRICT, null=False, editable=True,
        related_name='equipment_accounting_department_department', verbose_name='Подразделение',
        db_comment="ID подразделения", help_text="Подразделение или филиал клиента"
    )
    engineer = models.ForeignKey(
        'directory.Engineer', on_delete=models.SET_NULL, null=True, blank=False,
        related_name='equipment_accounting_engineer', verbose_name='Инженер',
        help_text="Инженер, который запускал оборудование"
    )
    is_active = models.BooleanField(
        default=True, verbose_name='У клиента',
        db_comment='Флаг, указывающий на то, что прибор установлен в подразделении клиента',
        help_text='Флаг, указывающий на то, что прибор установлен в подразделении клиента'
    )
    install_dt = models.DateField(
        null=True, blank=False, verbose_name='Дата монтажа',
        db_comment='Дата установки оборудования в подразделении клиента',
        help_text='Дата установки оборудования в подразделении клиента'
    )

    class Meta:
        db_table = f'{company}."equipment_acc_department"'
        db_table_comment = 'Учет поставленного оборудования в подразделения клиента.\n\n-- BMatyushin'
        verbose_name = 'Оборудование по клиентам'
        verbose_name_plural = 'Оборудование по клиентам'

    def __str__(self):
        return f"{self.department} - {self.equipment_accounting}"

    def __repr__(self):
        return f"<EquipmentAccDepartment {self.id=!r}, {self.is_active=!r}>"


class Manufacturer(EbaseModel):
    """Модель для перечьня производителей оборудования"""
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Производитель',
        db_comment='Производитель оборудования', help_text='Производитель оборудования'
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН', unique=True,
        db_comment='ИНН производителя', help_text='ИНН производителя'
    )
    country = models.ForeignKey(
        'directory.Country', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="manufacturer_country", verbose_name='Страна',
        db_comment='Страна производителя',
    )
    city = models.ForeignKey(
        'directory.City', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="manufacturer_city", verbose_name='Город',
        db_comment='Город производителя', help_text='Город производителя',
        default=get_instance_city
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
    email = models.EmailField(
        max_length=100, null=True, blank=True, verbose_name='E-mail',
        db_comment='E-mail производителя'
    )
    is_active = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Действующий',
        db_comment='True, если производитель активен',
        help_text='True, если активен. Для мягкого удаления производителя.'
    )

    class Meta:
        db_table = f'{company}."manufacturer"'
        db_table_comment = 'Производители оборудования. \n\n-- BMatyushin'
        verbose_name = 'Производитель'
        verbose_name_plural = 'Производители'
        unique_together = ('name', 'city',)
        # unique_together = ('name', 'country',)

    def __str__(self):
        return f"{self.name}{f', ({self.city.name})' if self.city.name != 'Не указан' else ''}"

    def __repr__(self):
        return f'<Manufacturer {self.name=!r}, {self.city=!r}>'


class Service(EbaseModel):
    """Таблица для учета поступившего на ремонт оборудования."""
    service_type = models.ForeignKey(
        'directory.ServiceType', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="service_service_type", verbose_name='Типа ремонта',
        db_comment='ID Типа ремонта',
    )
    equipment_accounting = models.ForeignKey(
        "EquipmentAccounting", related_name="service_equipment_accounting",
        verbose_name='Оборудование для ремонта. ', null=True, blank=False, on_delete=models.RESTRICT,
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.RESTRICT, null=False, blank=False,
        related_name="service_company_user", verbose_name='ID Пользователя',
        db_comment='ID Пользователя (сотрудника)',
        help_text='Пользователь из таблицы "Пользователи"'
    )
    description = models.TextField(
        null=True, blank=True, verbose_name='Описание неисправности',
        db_comment='Описание неисправности',
    )
    reason = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Причина',
        db_comment='На основании чего делается ремонт',
        help_text='На основании чего делается ремонт'
    )
    job_content = models.TextField(
        null=True, blank=True, verbose_name='Содержание работ',
        db_comment='Содержание работ',
    )
    beg_dt = models.DateField(
        null=False, blank=False, editable=True, verbose_name='Дата начала',
        db_comment='Дата начала ремонта', help_text='Дата начала ремонта',
        default=now,
    )
    end_dt = models.DateField(
        null=True, blank=True, verbose_name='Дата окончания',
        db_comment='Дата окончания ремонта', help_text='Дата окончания ремонта'
    )
    comment = models.TextField(
        null=True, blank=True, verbose_name='Комментарии',
        db_comment='Примечание, комментарии по ремонту',
        help_text='Примечание, комментарии по ремонту'
    )
    spare_part = models.ManyToManyField(
        "spare_part.SparePart", related_name="service_spare_part",
        verbose_name='Запчасти',
        help_text='Запчасти, которые используются в ремонте. ', blank=True,
    )
    service_akt = models.CharField(
        max_length=2056, null=True, blank=True, verbose_name='Акт',
        db_comment='Акт о проведении работ', help_text='Акт о проведении работ',
        validators=[validators.RegexValidator(regex=r'\.docs$')]
    )

    class Meta:
        db_table = f'{company}."service"'
        db_table_comment = 'Учет ремонта оборудования. \n\n-- BMatyushin'
        verbose_name = 'Ремонт оборудования'
        verbose_name_plural = 'Ремонт оборудования'

    def __str__(self):
        return f"{self.equipment_accounting} - {self.service_type}"

    def __repr__(self):
        return f'<Service {self.id=!r}, {self.user=!r}>'


class ServicePhotos(EbaseModel):
    """Набор фото связанных с ремонтом"""
    service = models.ForeignKey(
        'Service', on_delete=models.CASCADE, null=False, blank=False,
        related_name="service_photos", verbose_name='Ремонт',
        db_comment='ID Ремонта',
    )
    photo = models.ImageField(upload_to='service/%Y/', blank=True, null=True,
                              verbose_name='Фото ремонта',
                              db_comment='Ссылка на поле для фото связанных с ремонтом')
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.CASCADE, null=True, blank=True,
        related_name="service_photo_user", verbose_name='ID Пользователя',
        db_comment='ID Пользователя (сотрудника)',
        help_text='Пользователь из таблицы "Пользователи"'
    )
    create_dt = models.DateTimeField(auto_now_add=True, verbose_name='Когда было добавлено фото')

    class Meta:
        db_table = f'{company}."service_photos"'
        db_table_comment = 'Фотографии ремонта оборудования. \n\n-- BMatyushin'
        verbose_name = 'Фото ремонта'
        verbose_name_plural = 'Фото ремонта'

    def delete(self, using=None, keep_parents=False):
        self.photo.delete(save=False)
        super().delete(using=None, keep_parents=False)

    def __str__(self):
        return f"{self.service} - {self.photo}"

    def __repr__(self):
        return f'<ServicePhotos {self.id=!r}, {self.service=!r}>'


class Supplier(EbaseModel):
    """Поставщики оборудования."""
    name = models.CharField(
        max_length=150, null=False, blank=False, verbose_name='Поставщик',
    )
    inn = models.CharField(
        max_length=12, null=True, blank=True, verbose_name='ИНН', unique=True
    )
    country = models.ForeignKey(
        'directory.Country', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="supplier_country", verbose_name='Страна',
        db_comment='Страна производителя',
    )
    city = models.ForeignKey(
        'directory.City', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="supplier_city", verbose_name='Город',
        db_comment='Город поставщика', help_text='Город поставщика',
        default=get_instance_city
    )
    address = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Адрес',
        db_comment='Адрес поставщика', help_text='Адрес поставщика'
    )
    contact_person = models.CharField(
        max_length=200, null=True, blank=True, verbose_name='Контактное лицо',
        db_comment='Контактное лицо поставщика', help_text='Контактное лицо поставщика'
    )
    contact_phone = models.CharField(
        max_length=100, null=True, blank=True, verbose_name='Телефон',
        db_comment='Телефон поставщика', help_text='Контактные телефоны поставщика'
    )
    email = models.EmailField(
        max_length=100, null=True, blank=True, verbose_name='E-mail',
        db_comment='E-mail поставщика'
    )
    is_active = models.BooleanField(
        null=False, blank=False, default=True, verbose_name='Действующий',
        db_comment='True, если поставщик активен',
        help_text='True, если активен. Для мягкого удаления поставщика.'
    )

    class Meta:
        db_table = f'{company}."supplier"'
        db_table_comment = 'Поставщики оборудования. \n\n-- BMatyushin'
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        unique_together = ('name', 'city')

    def __str__(self):
        return f"{self.name}{f', ({self.city.name})' if self.city.name != 'Не указан' else ''}"

    def __repr__(self):
        return f'<Supplier {self.name=!r}, {self.city=!r}>'
