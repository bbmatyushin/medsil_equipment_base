import uuid

from django.db import models

from ebase.models import EbaseModel

company = '"medsil"'  # название схемы для таблиц


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
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['inn']),
            models.Index(fields=['city']),
        ]

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
            models.Index(models.F('name'), models.F('city'), name='department_name_city'),
            models.Index(fields=['name']),
            models.Index(fields=['client']),
            models.Index(fields=['city']),
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
