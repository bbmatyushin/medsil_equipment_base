import uuid

from django.db import models
from django.core.validators import MinValueValidator

# from directory.models import get_instance_unit


company = '"medsil"'  # название схемы для таблиц


class SparePartAbs(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
                          verbose_name='ID', db_comment='ID записи', help_text='ID записи')
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        abstract = True


class SparePart(SparePartAbs):
    """Запчасти."""
    article = models.CharField(
        max_length=50, null=True, blank=False, verbose_name='Артикул', db_comment='Артикул',
    )
    name = models.CharField(
        max_length=300, null=False, blank=False,verbose_name='Наименование',
        db_comment='Наименование запчасти',
    )
    unit = models.ForeignKey(
        "directory.Unit", on_delete=models.RESTRICT, null=False, blank=False,
        related_name="spare_part_unit", verbose_name='Ед.изм.', db_comment='Ед.изм.',
        # default=get_instance_unit
    )
    comment = models.TextField(
        null=True, blank=True, verbose_name='Примечание',
        db_comment='Примечание к запчасти', help_text='Примечание к запчасти'
    )
    is_expiration = models.BooleanField(
        default=False, verbose_name='Срок годности', blank=False,
        db_comment='Отмечаются запчасти со сроками годности',
        help_text='Флаг указывающий, что у запчасти должен быть срок годности'
    )
    equipment = models.ManyToManyField(
        "ebase.Equipment", related_name="spare_part_equipment", verbose_name='Оборудование',
        help_text="Оборудование, для которого предназначена эта запчасть. ", blank=False,
    )
    service = models.ManyToManyField(
        "ebase.Service", related_name="spare_part_service", verbose_name='ID Ремонта',
        help_text="В каком ремонте использовалась эта запчасть"
    )

    class Meta:
        db_table = f'{company}."spare_part"'
        db_table_comment = 'Справочник запчастей. \n\n-- BMatyushin'
        verbose_name = 'Справочник запчастей'
        verbose_name_plural = 'Справочник запчастей'
        unique_together = ('article', 'name',)

    def __str__(self):
        return f'{self.name} {f"(арт. {self.article})"if self.article else ""}'

    def __repr__(self):
        return f'<SparePart {self.name=!r}>'


class SparePartCount(SparePartAbs):
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


class SparePartShipment(SparePartAbs):
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


class SparePartSupply(SparePartAbs):
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
