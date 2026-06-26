import uuid
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator


company = '"medsil"'


class ContractModelBase(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
        verbose_name='ID', db_comment='ID записи', help_text='ID записи'
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name='Дата создания',
        db_comment='Дата создания записи.',
        help_text='Дата создания записи. Заполняется автоматически'
    )

    class Meta:
        abstract = True


class Contract(ContractModelBase):
    """Карточка контракта из реестра отдела Сервис."""

    SERVICES_PROVIDED_CHOICES = [
        ('not_yet', 'ещё нет'),
        ('partially', 'частично'),
        ('fully', 'полностью'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('no_receipts', 'поступлений нет'),
        ('paid', 'оплачено'),
        ('partial', 'частичная оплата'),
    ]

    client = models.ForeignKey(
        'clients.Department', on_delete=models.RESTRICT,
        related_name='contract_client', verbose_name='Клиент',
        db_comment='ID подразделения клиента',
        help_text='Подразделение клиента, для которого заключён контракт'
    )
    contract_number = models.CharField(
        max_length=255, unique=True, verbose_name='Номер контракта',
        db_comment='Номер контракта. Должен быть уникальным во всём реестре.'
    )
    order_number_1c = models.CharField(
        max_length=255, blank=True, verbose_name='Номер заказа 1С',
        db_comment='Номер заказа в учётной системе 1С'
    )
    conclusion_date = models.DateField(
        verbose_name='Дата заключения', db_comment='Дата заключения контракта'
    )
    service_end_date = models.DateField(
        null=True, blank=True, verbose_name='Дата окончания выполнения услуг',
        db_comment='Дата окончания выполнения услуг по контракту'
    )
    documentation_link = models.URLField(
        blank=True, verbose_name='Ссылка на документацию',
        db_comment='Внешняя ссылка на документы (OneDrive/SharePoint и т.п.)'
    )
    period = models.CharField(
        max_length=255, blank=True, verbose_name='Период',
        db_comment='Период действия/отчётности, произвольный текст'
    )
    contract_amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Сумма контракта',
        db_comment='Общая сумма контракта'
    )
    services_provided = models.CharField(
        max_length=20, choices=SERVICES_PROVIDED_CHOICES,
        default='not_yet', verbose_name='Услуги оказаны?',
        db_comment='Статус оказания услуг по контракту'
    )
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES,
        default='no_receipts', verbose_name='Оплата?',
        db_comment='Статус оплаты. Заполняется вручную, не выводится автоматически из суммы оплат.'
    )
    note = models.TextField(
        blank=True, verbose_name='Примечание',
        db_comment='Примечание к контракту'
    )

    # Вычисляемые поля
    payment_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='Сумма оплат',
        db_comment='Сумма всех оплат по контракту (авто)'
    )
    expenses_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='Затраты',
        db_comment='Общие затраты по контракту: запчасти + командировочные/прочие (авто)'
    )
    debt = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='Долг',
        db_comment='contract_amount - payment_amount (авто)'
    )
    profit = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='Прибыль',
        db_comment='payment_amount - expenses_amount (авто)'
    )

    class Meta:
        db_table = f'{company}."contracts_contract"'
        db_table_comment = 'Реестр контрактов отдела Сервис.\n\n-- Generated'
        verbose_name = 'Контракт'
        verbose_name_plural = 'Контракты'
        ordering = ['-conclusion_date', '-create_dt']
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['conclusion_date']),
            models.Index(fields=['services_provided']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return f"{self.contract_number} — {self.client.name}"

    def __repr__(self):
        return f'<Contract {self.contract_number=!r}>'


class Payment(ContractModelBase):
    """Поступления оплаты по контракту."""

    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE,
        related_name='payments', verbose_name='Контракт',
        db_comment='ID контракта'
    )
    date = models.DateField(
        verbose_name='Дата поступления', db_comment='Дата поступления оплаты'
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Сумма',
        db_comment='Сумма поступления'
    )
    note = models.CharField(
        max_length=500, blank=True, verbose_name='Примечание',
        db_comment='Примечание к оплате, например "Аванс" или номер счёта'
    )

    class Meta:
        db_table = f'{company}."contracts_payment"'
        db_table_comment = 'Оплаты по контрактам.\n\n-- Generated'
        verbose_name = 'Оплата'
        verbose_name_plural = 'Оплаты'
        ordering = ['-date', '-create_dt']

    def __str__(self):
        return f"{self.amount} от {self.date}"


class ContractExpense(ContractModelBase):
    """Командировочные и прочие расходы, вводимые в карточке контракта."""

    EXPENSE_TYPE_CHOICES = [
        ('business_trip', 'Командировочные'),
        ('other', 'Прочие расходы'),
    ]

    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE,
        related_name='expenses', verbose_name='Контракт',
        db_comment='ID контракта'
    )
    expense_type = models.CharField(
        max_length=20, choices=EXPENSE_TYPE_CHOICES,
        verbose_name='Тип расхода', db_comment='Тип расхода'
    )
    name = models.CharField(
        max_length=255, verbose_name='Наименование',
        db_comment='Наименование расхода. По умолчанию заполняется по типу.'
    )
    unit = models.CharField(
        max_length=50, default='шт.', verbose_name='Ед. изм.',
        db_comment='Единица измерения'
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=3, default=1,
        validators=[MinValueValidator(0)], verbose_name='Кол-во',
        db_comment='Количество'
    )
    cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        validators=[MinValueValidator(0)], verbose_name='Стоимость',
        db_comment='Стоимость за единицу'
    )
    # NB: Field name intentionally shadows the built-in sum() to match the
    # domain term "Сумма". Use the model instance attribute explicitly or
    # import builtins.sum when aggregation is needed.
    sum = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='Сумма', db_comment='quantity * cost (авто)'
    )
    date = models.DateField(
        null=True, blank=True, verbose_name='Дата расхода',
        db_comment='Дата, когда расход был понесён'
    )
    comment = models.TextField(
        blank=True, verbose_name='Примечание',
        db_comment='Комментарий по строке расхода'
    )

    class Meta:
        db_table = f'{company}."contracts_contractexpense"'
        db_table_comment = 'Ручные расходы по контрактам (командировочные, прочие).\n\n-- Generated'
        verbose_name = 'Расход контракта'
        verbose_name_plural = 'Расходы контракта'
        ordering = ['-date', '-create_dt']

    def __str__(self):
        return f"{self.name} — {self.sum}"

    def save(self, *args, **kwargs):
        self.sum = Decimal(self.quantity or 0) * (self.cost or 0)
        if not self.name:
            self.name = self.get_expense_type_display()
        super().save(*args, **kwargs)
