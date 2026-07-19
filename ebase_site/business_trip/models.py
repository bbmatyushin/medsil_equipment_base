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
