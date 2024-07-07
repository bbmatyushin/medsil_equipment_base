import uuid

from django.db import models
from django.contrib.auth.models import User


class EbaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


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
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата добавления',
        db_comment="Дата добавления записи",
        help_text="Дата добавления записи. Заполняется автоматически"
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
        User, on_delete=models.SET_NULL, null=False, editable=False,
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
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания записи',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
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
        max_length=50, null=False, blank=False, verbose_name='Статус оборудования',
        db_comment='Статус оборудования', help_text='Статус оборудования'
    )

    class Meta:
        db_table = 'equipment_status'
        db_table_comment = 'Таблица с набором статусов оборудования. \n\n-- BMatyushin'
        verbose_name = 'Статус оборудования'
        verbose_name_plural = 'Статусы оборудований'

    def __repr__(self):
        return f'<EquipmentStatus {self.name=!r}>'


class MedDirection(models.Model):
    """Модель для перечьня направлений для оборудования: Гематологическое, Биохимическое и т.д."""
    name = models.CharField(
        max_length=50, null=False, blank=False, verbose_name='Наименование направления',
        db_comment='Направление медицинского оборудования (Гематологическое, Биохимическое и т.д.)',
        help_text='Направление медицинского оборудования (Гематологическое, Биохимическое и т.д.).'
    )

    class Meta:
        db_table = 'med_direction'
        db_table_comment = ('Направления медицинского оборудования (Гематологическое, Биохимическое и т.д.).'
                            '\n\n-- BMatyushin')
        verbose_name = 'Направление медицинского оборудования'
        verbose_name_plural = 'Направления медицинского оборудования'

    def __repr__(self):
        return f'<MedDirection {self.name=!r}>'
