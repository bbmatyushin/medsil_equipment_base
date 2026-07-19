from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from ebase.models import EbaseModel

company = '"medsil"'  # название схемы для таблиц

# Ставка суточных, руб/день. При изменении ставки уже сохранённые записи
# пересчитываются только при их редактировании.
DAILY_ALLOWANCE_RATE = 700


class ExpenseType(models.Model):
    """Справочник видов затрат на командировку (такси, гостиница, транспорт…)."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Наименование",
        db_comment="Наименование вида затрат",
    )

    class Meta:
        db_table = f'{company}."business_trip_expense_type"'
        db_table_comment = "Справочник видов затрат на командировку. \n\n-- Generated"
        verbose_name = "Вид затрат"
        verbose_name_plural = "Виды затрат"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<ExpenseType {self.name=!r}>"


class BusinessTrip(EbaseModel):
    """Командировка сотрудника."""

    employee = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.RESTRICT,
        related_name="business_trip_employee",
        verbose_name="Сотрудник",
        db_comment="ID сотрудника, который был в командировке",
    )
    user = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="business_trip_creator",
        verbose_name="Кем внесена запись",
        db_comment="ID пользователя, создавшего запись",
    )
    doc_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name="Номер документа",
        db_comment="Номер документа (для приказа о командировке)",
        help_text="Заполняется автоматически (max+1). Можно изменить вручную.",
    )
    beg_dt = models.DateField(
        verbose_name="Дата выезда", db_comment="Дата выезда в командировку"
    )
    end_dt = models.DateField(
        verbose_name="Дата возвращения", db_comment="Дата возвращения из командировки"
    )
    allowance_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        verbose_name="Сумма командировочных",
        db_comment="Сумма командировочных (суточные = дни × ставка)",
        help_text="Считается автоматически: дни × 700 руб.",
    )
    service_type = models.ManyToManyField(
        "directory.ServiceType",
        blank=True,
        related_name="business_trip_service_type",
        verbose_name="Виды работ",
        help_text="Можно выбрать несколько (например, ТО и ремонт)",
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_trip",
        verbose_name="Договор",
        db_comment="ID связанного договора",
    )
    task = models.TextField(blank=True, verbose_name="Задание на командировку")
    take_with = models.TextField(blank=True, verbose_name="Взять с собой")
    comment = models.TextField(blank=True, verbose_name="Примечание")
    report = models.TextField(blank=True, verbose_name="Отчёт")

    class Meta:
        db_table = f'{company}."business_trip"'
        db_table_comment = "Командировки сотрудников. \n\n-- Generated"
        verbose_name = "Командировка"
        verbose_name_plural = "Командировки"
        ordering = ("-beg_dt",)
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["beg_dt"]),
            models.Index(fields=["end_dt"]),
        ]

    def __str__(self):
        return f"№{self.doc_number} {self.employee} ({self.beg_dt} — {self.end_dt})"

    @property
    def days_count(self):
        """Количество дней командировки (граничные даты включаются)."""
        if self.beg_dt is None or self.end_dt is None:
            return None
        return (self.end_dt - self.beg_dt).days + 1

    def _calc_allowance(self):
        days = self.days_count
        if not days or days < 1:
            return Decimal("0")
        return Decimal(days) * Decimal(DAILY_ALLOWANCE_RATE)

    def _assign_doc_number(self):
        # max+1 без блокировки: допустимо для внутренней админки с единичными
        # одновременными пользователями; уникальность гарантирует constraint.
        if self.doc_number is None:
            max_num = (
                BusinessTrip.objects.aggregate(max_num=models.Max("doc_number"))[
                    "max_num"
                ]
                or 0
            )
            self.doc_number = max_num + 1

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.beg_dt and self.end_dt and self.end_dt < self.beg_dt:
            raise ValidationError({"end_dt": "Дата возвращения раньше даты выезда."})

    def save(self, *args, **kwargs):
        self._assign_doc_number()
        self.allowance_amount = self._calc_allowance()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "doc_number",
                "allowance_amount",
            }
        super().save(*args, **kwargs)


class BusinessTripDestination(EbaseModel):
    """Пункт командировки: подразделение клиента и даты пребывания.

    Город НЕ хранится — подтягивается из department.city. В одной командировке
    может быть несколько пунктов (например, несколько больниц в одном городе).
    """

    business_trip = models.ForeignKey(
        BusinessTrip,
        on_delete=models.CASCADE,
        related_name="destinations",
        verbose_name="Командировка",
        db_comment="ID командировки",
    )
    department = models.ForeignKey(
        "clients.Department",
        on_delete=models.RESTRICT,
        related_name="business_trip_destination",
        verbose_name="Подразделение",
        db_comment="ID подразделения клиента",
    )
    beg_dt = models.DateField(
        verbose_name="Дата прибытия (с)", db_comment="Дата прибытия в пункт"
    )
    end_dt = models.DateField(
        verbose_name="Дата выбытия (по)", db_comment="Дата выбытия из пункта"
    )

    class Meta:
        db_table = f'{company}."business_trip_destination"'
        db_table_comment = (
            "Пункты командировки (подразделения и даты). \n\n-- Generated"
        )
        verbose_name = "Пункт командировки"
        verbose_name_plural = "Пункты командировки"
        ordering = ("beg_dt",)

    def __str__(self):
        return f"{self.department} ({self.beg_dt} — {self.end_dt})"

    @property
    def city(self):
        """Город подразделения (не хранится, подтягивается из department.city)."""
        return self.department.city if self.department_id else None

    @property
    def client(self):
        """Клиент подразделения (подтягивается из department.client)."""
        return self.department.client if self.department_id else None

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.beg_dt and self.end_dt and self.end_dt < self.beg_dt:
            errors["end_dt"] = "Дата выбытия раньше даты прибытия."
        # Даты пункта должны быть в пределах дат командировки (если она задана)
        if self.business_trip_id and self.beg_dt and self.end_dt:
            trip = self.business_trip
            if self.beg_dt < trip.beg_dt or self.end_dt > trip.end_dt:
                errors.setdefault("__all__", []).append(
                    "Даты пункта должны быть в пределах дат командировки "
                    f"({trip.beg_dt} — {trip.end_dt})."
                )
        if errors:
            raise ValidationError(errors)


class BusinessTripExpense(EbaseModel):
    """Затрата по командировке (чек).

    Привязка к городу НЕ хранится — определяется по дате затраты через пункты
    командировки (см. спеку, раздел «Атрибуция затрат к городам»).
    """

    business_trip = models.ForeignKey(
        BusinessTrip,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name="Командировка",
        db_comment="ID командировки",
    )
    expense_type = models.ForeignKey(
        ExpenseType,
        on_delete=models.RESTRICT,
        related_name="business_trip_expense",
        verbose_name="Вид затрат",
        db_comment="ID вида затрат",
    )
    date = models.DateField(verbose_name="Дата", db_comment="Дата затраты")
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Сумма",
        db_comment="Сумма затрат",
    )
    comment = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Комментарий",
        db_comment="На что потрачено",
    )

    class Meta:
        db_table = f'{company}."business_trip_expense"'
        db_table_comment = "Затраты по командировкам. \n\n-- Generated"
        verbose_name = "Затрата"
        verbose_name_plural = "Затраты на поездку"
        ordering = ("date",)

    def __str__(self):
        return f"{self.date} {self.expense_type} — {self.amount} руб."


class BusinessTripPhoto(EbaseModel):
    """Фото чека по командировке."""

    business_trip = models.ForeignKey(
        BusinessTrip,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Командировка",
        db_comment="ID командировки",
    )
    photo = models.ImageField(
        upload_to="business_trip/%Y/",
        verbose_name="Фото чека",
        db_comment="Ссылка на фото чека",
    )
    user = models.ForeignKey(
        "users.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_trip_photo_user",
        verbose_name="Кто добавил",
        db_comment="ID пользователя, добавившего фото",
    )
    create_dt = models.DateTimeField(
        auto_now_add=True, verbose_name="Когда было добавлено фото"
    )

    class Meta:
        db_table = f'{company}."business_trip_photo"'
        db_table_comment = "Фото чеков по командировкам. \n\n-- Generated"
        verbose_name = "Фото чека"
        verbose_name_plural = "Фото чеков"

    def delete(self, using=None, keep_parents=False):
        # Удаляем файл с диска перед удалением записи
        self.photo.delete(save=False)
        super().delete(using=None, keep_parents=False)

    def __str__(self):
        return f"{self.business_trip} — {self.photo}"
