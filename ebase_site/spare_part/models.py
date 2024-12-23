from datetime import datetime
import uuid
import logging

from django.db import models
from django.core.validators import MinValueValidator

from directory.models import get_instance_unit


logger = logging.getLogger('SPARE_PART_SIGNALS')
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
        default=get_instance_unit
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
        verbose_name = 'Запчасть'
        verbose_name_plural = 'Запчасти'
        unique_together = ('article', 'name',)

    def __str__(self):
        return f'{self.name} {f"(арт. {self.article})" if self.article else ""}'

    def __repr__(self):
        return f'<SparePart {self.name=!r}>'


class SparePartCount(SparePartAbs):
    """Общее количество запчастей (чтобы не делать сложные запросы для вывода этой инфы)"""
    spare_part = models.ForeignKey(
        'SparePart', on_delete=models.RESTRICT, null=False, blank=False,
        related_name="spare_part_count_spare_part", verbose_name='Запчасть',
        db_comment="ID запчасти", help_text="ID запчасти"
    )
    amount = models.FloatField(
        verbose_name='Количество', db_comment='Кол-во запчастей',
        help_text='Кол-во запчастей. Заполняется автоматически',
        validators=[MinValueValidator(0)], null=False, blank=False,
    )
    expiration_dt = models.DateField(
        null=True, blank=True, verbose_name='Годен до',
        db_comment='Годен до. Срок годности для запчастей со сроком годности.',
        help_text='Годен до. Срок годности для запчастей со сроком годности.',
        # choices=(SparePartShipment.objects.)
    )
    is_overdue = models.BooleanField(
        default=True, verbose_name='Не просрочено',
        db_comment='Флаг указывающий, что запчасть просрочена',
        help_text='Флаг указывающий, что запчасть просрочена'
    )

    class Meta:
        db_table = f'{company}."spare_part_count"'
        db_table_comment = 'Общее количество запчастей на остатке.\n\n-- BMatyushin'
        verbose_name = 'Остаток запчастей'
        verbose_name_plural = 'Остаток запчастей'
        unique_together = ('spare_part', 'expiration_dt')

    def check_expiration(self):
        """Проверка окончания срока годности у запчасти"""
        today = datetime.today().date()
        if self.expiration_dt:
            self.is_overdue = self.expiration_dt < today
            self.save(update_fields=['is_overdue'])

    def __str__(self):
        exp_dt = self.expiration_dt.strftime("%d.%m.%Y") if self.expiration_dt else '-'
        sp_amount = self.amount if self.amount % 1 else int(self.amount)
        return f"{self.spare_part.name}{f' (до {exp_dt})' if self.expiration_dt else ''}, остаток - {sp_amount}"
        # return f"{self.amount if self.amount else '-'}"

    def __repr__(self):
        return f'<SparePartCount {self.spare_part=!r} {self.amount=!r}>'


class SparePartShipment(SparePartAbs):
    """Отслеживание отгрузок запчастей"""

    # TODO: Нужно связать с таблицей учетом количества запчастей

    # spare_part = models.ForeignKey(
    #     'SparePart', on_delete=models.SET_NULL, null=True, blank=False,
    #     related_name="spare_part_shipment_spare_part", verbose_name='Запчасть',
    #     db_comment="ID запчасти",
    # )
    spare_part_count = models.ForeignKey(
        'SparePartCount', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="spare_part_shipment_spare_part_count", verbose_name='Запчасть',
        db_comment="ID запчасти из таблицы spare_part_count",
    )
    doc_num = models.CharField(
        max_length=20, null=False, blank=False, verbose_name='Номер документа',
        db_comment='Номер документа отгрузки',
        help_text='Номер документа отгрузки или внутренний номер для учёта',
        default='б/н'
    )
    count_shipment = models.FloatField(
        verbose_name='Кол-во', db_comment='Кол-во отгруженной запчасти',
        help_text='Кол-во отгруженной запчасти', null=False, blank=False,
        validators=[MinValueValidator(0)]
    )
    # expiration_dt = models.DateField(
    #     null=True, blank=True, verbose_name='Годен до',
    #     db_comment='Годен до. Срок годности для запчастей со сроком годности.',
    #     help_text='Срок годности для запчастей со сроком годности.',
    # )
    shipment_dt = models.DateField(
        null=False, blank=False, verbose_name='Дата отгрузки',
        db_comment='Дата отгрузки', help_text='Дата отгрузки.'
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.RESTRICT, null=False, blank=False,
        related_name='spare_part_shipment_company_user', verbose_name='Кто отгрузил',
        db_comment="ID сотрудника, который оформил отгрузку",
    )

    class Meta:
        db_table = f'{company}."spare_part_shipment"'
        db_table_comment = 'Отслеживание отгрузок запчастей. \n\n-- BMatyushin'
        verbose_name = 'Отгрузка запчастей'
        verbose_name_plural = 'Отгрузки запчастей'

    def __str__(self):
        art = f" (арт. {self.spare_part_count.spare_part.article})" if self.spare_part_count.spare_part.article else ''
        return f'{self.spare_part_count.spare_part.name}{art}'

    def __repr__(self):
        return f"<SparePartShipment: {self.spare_part_count=!r}, {self.count_shipment=!r}>"


class SparePartSupply(SparePartAbs):
    """Отслеживание поставок запчастей"""
    spare_part = models.ForeignKey(
        'SparePart', on_delete=models.SET_NULL, null=True, blank=False,
        related_name="spare_part_supply_spare_part", verbose_name='Запчасть',
        db_comment="ID запчасти",
    )
    doc_num = models.CharField(
        max_length=20, null=False, blank=False, verbose_name='Номер документа',
        db_comment='Номер документа отгрузки',
        help_text='Номер документа отгрузки или внутренний номер для учёта',
        default='б/н',
    )
    count_supply = models.FloatField(
        verbose_name='Кол-во', db_comment='Кол-во поставленой запчасти',
        null=False, blank=False, validators=[MinValueValidator(0)],
    )
    expiration_dt = models.DateField(
        null=True, blank=True, verbose_name='Годен до',
        db_comment='Годен до. Срок годности для запчастей со сроком годности.',
        help_text='Срок годности для запчастей со сроком годности.',
    )
    supply_dt = models.DateField(
        null=False, blank=False, verbose_name='Дата поставки', db_comment='Дата поставки',
    )
    user = models.ForeignKey(
        'users.CompanyUser', on_delete=models.RESTRICT, null=False, blank=True,
        related_name='spare_part_supply_company_user', verbose_name='Кто добавил',
        db_comment="ID сотрудника, который оформил поставку",
    )

    class Meta:
        db_table = f'{company}."spare_part_supply"'
        db_table_comment = 'Отслеживание поставок запчастей. \n\n-- BMatyushin'
        verbose_name = 'Поставка запчастей'
        verbose_name_plural = 'Поставки запчастей'

    def __str__(self):
        return f'{self.spare_part.name} {f"(арт. {self.spare_part.article})" if self.spare_part.article else ""}'

    def __repr__(self):
        return f"<SparePartSupply: {self.spare_part=!r}, {self.count_supply=!r}>"
