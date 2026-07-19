# Раздел «Командировки» — план реализации

> **Для исполнителя-агента:** используй скилл `superpowers:subagent-driven-development` (рекомендуется) или `superpowers:executing-plans` для пошагового выполнения. Шаги помечены чекбоксами `- [ ]`.

**Цель:** создать Django-приложение `business_trip` для учёта командировок сотрудников: поездки с датами, пунктами назначения (подразделения клиентов), затратами по видам, фото чеков и автоматическим расчётом суточных (дни × 700 руб).

**Архитектура:** новое приложение `business_trip` в `ebase_site/`, наследует существующие паттерны проекта — `EbaseModel` (UUID PK, схема `medsil`), `MainModelAdmin` (экспорт в Excel), inline-фото по образцу `SparePartPhoto`. Сигналов нет: суточные считаются в `save()` модели, суммы затрат — аннотацией в админке. Структура данных покрывает будущие «Приказ Т-9» и «Месячный отчёт», которые в этом задании НЕ реализуются.

**Тех-стек:** Django 4.2.16, Python 3.11, PostgreSQL (в тестах — SQLite `:memory:` через `test_settings.py`), openpyxl (уже в зависимостях), Black 24.8.0.

**Спека:** `docs/superpowers/specs/2026-07-19-business-trip-design.md` — читать обязательно перед стартом.

**Запуск тестов (одна команда для всех задач):**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

**Black (после каждого изменения .py):**

```bash
black ebase_site/business_trip
```

**Стиль коммитов (как в репозитории):** `feat(business_trip): русское описание`, `test(business_trip): ...`, `docs(business_trip): ...`. Коммитить на русском.

**Важные ограничения:**
- Не трогать сигналы `contracts/signals.py` и `ebase/signals.py` — командировки на них не влияют.
- Не менять поведение существующих админок (правка `DepartmentAdmin` не нужна — у него уже есть `search_fields`).
- Все `db_table` — со схемой `medsil`: `db_table = f'{company}."business_trip"'` и т.п. Константу `company = '"medsil"'` объявить вверху `models.py`.
- Модели наследуют `EbaseModel` из `ebase.models` (импорт: `from ebase.models import EbaseModel`).
- Полям давать `verbose_name` + `db_comment` на русском — как в соседних моделях.

---

## Структура файлов

```
ebase_site/business_trip/
├── __init__.py            # пустой
├── apps.py                # BusinessTripConfig, verbose_name="Командировки"
├── models.py              # ExpenseType, BusinessTrip, BusinessTripDestination,
│                          #   BusinessTripExpense, BusinessTripPhoto
├── admin.py               # BusinessTripAdmin, 4 inline, ExpenseTypeAdmin
├── tests.py               # все тесты в одном файле
├── migrations/
│   └── __init__.py        # пустой
└── (миграция 0001 генерируется makemigrations)
```

Изменяемые существующие файлы:
- `ebase_site/ebase_site/settings.py` — добавить приложение в `INSTALLED_APPS`.
- `AGENTS.md` — описать новое приложение.

---

## Task 1: Каркас приложения

**Files:**
- Create: `ebase_site/business_trip/__init__.py` (пустой)
- Create: `ebase_site/business_trip/apps.py`
- Create: `ebase_site/business_trip/migrations/__init__.py` (пустой)
- Modify: `ebase_site/ebase_site/settings.py:37-53` (`INSTALLED_APPS`)

- [ ] **Step 1: Создать пустые `__init__.py`**

`ebase_site/business_trip/__init__.py` и `ebase_site/business_trip/migrations/__init__.py` — пустые файлы (чтобы Python и Django распознали пакет).

- [ ] **Step 2: Создать `apps.py`**

```python
from django.apps import AppConfig


class BusinessTripConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "business_trip"
    verbose_name = "Командировки"
```

- [ ] **Step 3: Зарегистрировать приложение в `INSTALLED_APPS`**

В `ebase_site/ebase_site/settings.py` добавить `"business_trip.apps.BusinessTripConfig"` в блок своих приложений (после `contracts`, до `debug_toolbar`). Итоговый блок:

```python
INSTALLED_APPS = [
    "users.apps.UsersConfig",
    "ebase.apps.EbaseConfig",
    "clients.apps.ClientsConfig",
    "directory.apps.DirectoryConfig",
    "spare_part.apps.SparePartConfig",
    "contracts.apps.ContractsConfig",
    "business_trip.apps.BusinessTripConfig",
    "debug_toolbar",
    "django.contrib.admin",
    # ... остальное без изменений
]
```

- [ ] **Step 4: Проверить, что Django видит приложение**

```bash
cd ebase_site && python manage.py check
```

Ожидается: `System check identified no issues (0 silenced)`. Если `ModuleNotFoundError: No module named 'business_trip'` — не создан `__init__.py` или запуск не из `ebase_site/`.

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/ ebase_site/ebase_site/settings.py
git commit -m "feat(business_trip): каркас приложения business_trip"
```

---

## Task 2: Модель `ExpenseType` (справочник видов затрат)

**Files:**
- Create: `ebase_site/business_trip/models.py`
- Test: `ebase_site/business_trip/tests.py`

- [ ] **Step 1: Написать тест на создание вида затрат**

`ebase_site/business_trip/tests.py`:

```python
from django.test import TestCase

from business_trip.models import ExpenseType


class ExpenseTypeTests(TestCase):
    def test_create_expense_type(self):
        expense_type = ExpenseType.objects.create(name="Такси")
        self.assertEqual(expense_type.name, "Такси")
        self.assertEqual(str(expense_type), "Такси")

    def test_name_unique(self):
        ExpenseType.objects.create(name="Гостиница")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ExpenseType.objects.create(name="Гостиница")
```

- [ ] **Step 2: Запустить тест, убедиться, что падает**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

Ожидается: `ImportError: cannot import name 'ExpenseType' from 'business_trip.models'` (файла ещё нет / модель не объявлена).

- [ ] **Step 3: Создать `models.py` с константой ставки и моделью `ExpenseType`**

`ebase_site/business_trip/models.py`:

```python
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
```

- [ ] **Step 4: Запустить тест, убедиться, что проходит**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

Ожидается: `Ran 2 tests... OK`. (Таблицы создаются из моделей напрямую — `test_settings` отключает миграции.)

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/models.py ebase_site/business_trip/tests.py
git commit -m "feat(business_trip): модель ExpenseType (справочник видов затрат)"
```

---

## Task 3: Модель `BusinessTrip` — суточные

**Files:**
- Modify: `ebase_site/business_trip/models.py` (добавить `BusinessTrip`)
- Modify: `ebase_site/business_trip/tests.py`

- [ ] **Step 1: Добавить тесты на расчёт суточных**

Дополнить `tests.py`:

```python
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model

from business_trip.models import BusinessTrip

User = get_user_model()


class BusinessTripAllowanceTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def _make(self, beg, end, **kwargs):
        return BusinessTrip.objects.create(employee=self.employee, beg_dt=beg, end_dt=end, **kwargs)

    def test_allowance_four_days(self):
        # 16.03–19.03 — 4 дня включительно
        trip = self._make(date(2026, 3, 16), date(2026, 3, 19))
        self.assertEqual(trip.days_count, 4)
        self.assertEqual(trip.allowance_amount, Decimal("2800.00"))

    def test_allowance_one_day(self):
        # 26.03–26.03 — 1 день
        trip = self._make(date(2026, 3, 26), date(2026, 3, 26))
        self.assertEqual(trip.days_count, 1)
        self.assertEqual(trip.allowance_amount, Decimal("700.00"))

    def test_allowance_recalc_on_date_change(self):
        trip = self._make(date(2026, 3, 16), date(2026, 3, 19))
        self.assertEqual(trip.allowance_amount, Decimal("2800.00"))
        trip.end_dt = date(2026, 3, 20)
        trip.save(update_fields=["end_dt"])
        trip.refresh_from_db()
        self.assertEqual(trip.allowance_amount, Decimal("3500.00"))
```

- [ ] **Step 2: Запустить тесты — должны падать (`BusinessTrip` не существует)**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

- [ ] **Step 3: Реализовать модель `BusinessTrip`**

Добавить в `models.py` (после `ExpenseType`):

```python
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
    beg_dt = models.DateField(verbose_name="Дата выезда", db_comment="Дата выезда в командировку")
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
        if self.doc_number is None:
            max_num = (
                BusinessTrip.objects.aggregate(
                    max_num=models.Max("doc_number")
                )["max_num"]
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
            kwargs["update_fields"] = set(update_fields) | {"allowance_amount"}
        super().save(*args, **kwargs)
```

Вверху файла добавить импорт `Decimal`:

```python
from decimal import Decimal
```

- [ ] **Step 4: Запустить тесты — должны пройти**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

Ожидается: все тесты `BusinessTripAllowanceTests` + `ExpenseTypeTests` — PASS.

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/models.py ebase_site/business_trip/tests.py
git commit -m "feat(business_trip): модель BusinessTrip с авто-расчётом суточных"
```

---

## Task 4: `BusinessTrip` — автонумерация и валидация дат

**Files:**
- Modify: `ebase_site/business_trip/tests.py`

- [ ] **Step 1: Добавить тесты на автонумерацию и валидацию**

```python
from django.core.exceptions import ValidationError


class BusinessTripDocNumberTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def test_doc_number_auto_first(self):
        trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        self.assertEqual(trip.doc_number, 1)

    def test_doc_number_auto_increment(self):
        first = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        second = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 4, 1), end_dt=date(2026, 4, 3)
        )
        self.assertEqual(first.doc_number, 1)
        self.assertEqual(second.doc_number, 2)

    def test_doc_number_manual_not_overwritten(self):
        trip = BusinessTrip.objects.create(
            employee=self.employee,
            beg_dt=date(2026, 3, 16),
            end_dt=date(2026, 3, 19),
            doc_number=100,
        )
        self.assertEqual(trip.doc_number, 100)


class BusinessTripValidationTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")

    def test_end_before_beg_raises(self):
        trip = BusinessTrip(
            employee=self.employee, beg_dt=date(2026, 3, 19), end_dt=date(2026, 3, 16)
        )
        with self.assertRaises(ValidationError):
            trip.clean()
```

- [ ] **Step 2: Запустить — должны пройти (логика уже в модели из Task 3)**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

Ожидается: PASS. Если падает — проверить `_assign_doc_number` и `clean`.

- [ ] **Step 3: Коммит**

```bash
git add ebase_site/business_trip/tests.py
git commit -m "test(business_trip): автонумерация и валидация дат командировки"
```

---

## Task 5: Модель `BusinessTripDestination` (пункт командировки)

**Files:**
- Modify: `ebase_site/business_trip/models.py`
- Modify: `ebase_site/business_trip/tests.py`

- [ ] **Step 1: Написать тесты**

Добавить в `tests.py`:

```python
from clients.models import Client, Department
from directory.models import City


class BusinessTripDestinationTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.city, _ = City.objects.get_or_create(
            name="Смоленск", region=None, defaults={"region": None}
        )
        self.client_obj = Client.objects.create(name="СОДКБ", city=self.city, inn="111111111111")
        self.department = Department.objects.create(
            name="СОДКБ", client=self.client_obj, city=self.city, address="ул. Ленина, 1"
        )
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 4, 1), end_dt=date(2026, 4, 3)
        )

    def test_city_pulled_from_department(self):
        dest = BusinessTripDestination.objects.create(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 4, 1),
            end_dt=date(2026, 4, 2),
        )
        self.assertEqual(dest.city, self.city)
        self.assertEqual(dest.client, self.client_obj)

    def test_dest_dates_outside_trip_raises(self):
        dest = BusinessTripDestination(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 3, 30),  # до выезда
            end_dt=date(2026, 4, 2),
        )
        with self.assertRaises(ValidationError):
            dest.clean()

    def test_dest_end_before_beg_raises(self):
        dest = BusinessTripDestination(
            business_trip=self.trip,
            department=self.department,
            beg_dt=date(2026, 4, 2),
            end_dt=date(2026, 4, 1),
        )
        with self.assertRaises(ValidationError):
            dest.clean()
```

- [ ] **Step 2: Запустить — падает (модели нет)**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

- [ ] **Step 3: Реализовать модель**

Добавить в `models.py` (после `BusinessTrip`):

```python
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
    beg_dt = models.DateField(verbose_name="Дата прибытия (с)", db_comment="Дата прибытия в пункт")
    end_dt = models.DateField(verbose_name="Дата выбытия (по)", db_comment="Дата выбытия из пункта")

    class Meta:
        db_table = f'{company}."business_trip_destination"'
        db_table_comment = "Пункты командировки (подразделения и даты). \n\n-- Generated"
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
```

- [ ] **Step 4: Запустить — должны пройти**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/models.py ebase_site/business_trip/tests.py
git commit -m "feat(business_trip): модель BusinessTripDestination (пункт командировки)"
```

---

## Task 6: Модель `BusinessTripExpense` (затрата)

**Files:**
- Modify: `ebase_site/business_trip/models.py`
- Modify: `ebase_site/business_trip/tests.py`

- [ ] **Step 1: Написать тесты**

```python
class BusinessTripExpenseTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )
        self.expense_type = ExpenseType.objects.create(name="Такси")

    def test_create_expense(self):
        expense = BusinessTripExpense.objects.create(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 16),
            amount=Decimal("500.00"),
            comment="Такси до гостиницы",
        )
        self.assertEqual(expense.amount, Decimal("500.00"))
        self.assertEqual(str(self.trip.expenses.first()), str(expense))

    def test_negative_amount_raises(self):
        expense = BusinessTripExpense(
            business_trip=self.trip,
            expense_type=self.expense_type,
            date=date(2026, 3, 16),
            amount=Decimal("-100.00"),
        )
        with self.assertRaises(ValidationError):
            expense.full_clean()
```

- [ ] **Step 2: Запустить — падает**

- [ ] **Step 3: Реализовать модель**

Добавить в `models.py` (после `BusinessTripDestination`):

```python
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
        max_length=255, blank=True, verbose_name="Комментарий", db_comment="На что потрачено"
    )

    class Meta:
        db_table = f'{company}."business_trip_expense"'
        db_table_comment = "Затраты по командировкам. \n\n-- Generated"
        verbose_name = "Затрата"
        verbose_name_plural = "Затраты на поездку"
        ordering = ("date",)

    def __str__(self):
        return f"{self.date} {self.expense_type} — {self.amount} руб."
```

- [ ] **Step 4: Запустить — должны пройти**

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/models.py ebase_site/business_trip/tests.py
git commit -m "feat(business_trip): модель BusinessTripExpense (затрата)"
```

---

## Task 7: Модель `BusinessTripPhoto` (фото чека)

**Files:**
- Modify: `ebase_site/business_trip/models.py`
- Modify: `ebase_site/business_trip/tests.py`

- [ ] **Step 1: Написать тест**

```python
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BusinessTripPhotoTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(username="ivanov", password="pass")
        self.trip = BusinessTrip.objects.create(
            employee=self.employee, beg_dt=date(2026, 3, 16), end_dt=date(2026, 3, 19)
        )

    def test_photo_linked_and_deleted_with_record(self):
        photo_file = SimpleUploadedFile(
            "check.jpg", b"\x47\x49\x46\x38\x39\x61", content_type="image/jpeg"
        )
        photo = BusinessTripPhoto.objects.create(business_trip=self.trip, photo=photo_file)
        self.assertIn(photo, self.trip.photos.all())
        self.assertTrue(photo.photo.storage.exists(photo.photo.name))
        photo.delete()
        self.assertFalse(photo.photo.storage.exists(photo.photo.name))
```

- [ ] **Step 2: Запустить — падает**

- [ ] **Step 3: Реализовать модель**

Добавить в `models.py` (после `BusinessTripExpense`):

```python
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
```

- [ ] **Step 4: Запустить — должны пройти**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/models.py ebase_site/business_trip/tests.py
git commit -m "feat(business_trip): модель BusinessTripPhoto (фото чека)"
```

---

## Task 8: Миграции

**Files:**
- Create: `ebase_site/business_trip/migrations/0001_initial.py` (генерируется)

- [ ] **Step 1: Сгенерировать миграции**

```bash
cd ebase_site && python manage.py makemigrations business_trip
```

Ожидается: `Migrations for 'business_trip': 0001_initial.py ...`. В миграции должны быть все 5 моделей.

- [ ] **Step 2: Применить к БД (локально, с Postgres)**

```bash
cd ebase_site && python manage.py migrate business_trip
```

Если Postgres не настроен локально — пропустить; миграция проверится в тестах (там `DisableMigrations`, таблицы создаются напрямую из моделей).

- [ ] **Step 3: Коммит**

```bash
git add ebase_site/business_trip/migrations/
git commit -m "feat(business_trip): миграция 0001_initial"
```

---

## Task 9: Админка — `ExpenseTypeAdmin`

**Files:**
- Create: `ebase_site/business_trip/admin.py`

- [ ] **Step 1: Создать `admin.py` с `ExpenseTypeAdmin`**

```python
from django.contrib import admin

from business_trip.models import ExpenseType
from utils import MainModelAdmin


@admin.register(ExpenseType)
class ExpenseTypeAdmin(MainModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    search_help_text = "Поиск по наименованию вида затрат"

    fieldsets = (
        ("Новый вид затрат", {"fields": ("name",)}),
    )
```

- [ ] **Step 2: Проверить, что админка грузится**

```bash
cd ebase_site && python manage.py check
```

- [ ] **Step 3: Коммит**

```bash
git add ebase_site/business_trip/admin.py
git commit -m "feat(business_trip): ExpenseTypeAdmin"
```

---

## Task 10: Админка — inline и `BusinessTripAdmin`

**Files:**
- Modify: `ebase_site/business_trip/admin.py`

- [ ] **Step 1: Реализовать inline'ы и `BusinessTripAdmin`**

Добавить в `admin.py` (под существующим импортом, сверху дополнить импорты моделей и `mark_safe`):

```python
from django.db.models import Sum
from django.utils.html import mark_safe

from business_trip.models import (
    BusinessTrip,
    BusinessTripDestination,
    BusinessTripExpense,
    BusinessTripPhoto,
)
```

Затем inline-классы:

```python
class BusinessTripDestinationInline(admin.TabularInline):
    model = BusinessTripDestination
    extra = 1
    verbose_name = "Пункт командировки"
    verbose_name_plural = "Пункты командировки (подразделения)"
    autocomplete_fields = ("department",)

    fields = ("department", "beg_dt", "end_dt", "city_display")
    readonly_fields = ("city_display",)

    @admin.display(description="Город")
    def city_display(self, obj):
        return obj.city.name if obj.city else "—"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("department__city")


class BusinessTripExpenseInline(admin.TabularInline):
    model = BusinessTripExpense
    extra = 1
    verbose_name = "Затрата"
    verbose_name_plural = "Затраты на поездку"

    fields = ("date", "expense_type", "amount", "comment")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("expense_type")


class BusinessTripPhotoInline(admin.StackedInline):
    model = BusinessTripPhoto
    extra = 1
    verbose_name = "ФОТО ЧЕКА"
    verbose_name_plural = "ФОТО ЧЕКОВ"
    readonly_fields = ("photo_preview",)

    fieldsets = (
        ("", {"fields": (("photo", "photo_preview"),)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("business_trip", "user")

    @admin.display(description="Изображение")
    def photo_preview(self, obj):
        if obj.photo:
            return mark_safe(
                f"<a href='{obj.photo.url}' target='_blank'>"
                f"<img src='{obj.photo.url}' width=50>"
                f"</a>"
            )
        return "Нет изображения"
```

И сам `BusinessTripAdmin`:

```python
@admin.register(BusinessTrip)
class BusinessTripAdmin(MainModelAdmin):
    date_hierarchy = "beg_dt"
    list_filter = ("employee", "service_type")
    search_fields = (
        "employee__last_name",
        "employee__first_name",
        "destinations__department__name",
        "destinations__department__city__name",
        "comment",
        "=doc_number",
    )
    search_help_text = "Поиск по ФИО сотрудника, подразделению, городу, номеру документа"
    filter_horizontal = ("service_type",)
    readonly_fields = ("allowance_amount",)

    fieldsets = (
        (
            "Командировка",
            {
                "fields": (
                    ("employee", "doc_number"),
                    ("beg_dt", "end_dt", "allowance_amount"),
                    ("service_type", "contract"),
                )
            },
        ),
        (
            "Дополнительно",
            {"fields": ("task", "take_with", "comment", "report")},
        ),
    )

    list_display = (
        "doc_number",
        "employee",
        "beg_dt",
        "end_dt",
        "days_count",
        "allowance_amount",
        "cities_display",
        "expenses_sum",
        "has_photos",
    )

    inlines = (
        BusinessTripDestinationInline,
        BusinessTripExpenseInline,
        BusinessTripPhotoInline,
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("employee", "contract")
            .prefetch_related(
                "destinations__department__city",
                "photos",
            )
            .annotate(
                _expenses_sum=Sum("expenses__amount"),
            )
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # При создании новой записи подставляем текущего пользователя как сотрудника
        if obj is None and "employee" in form.base_fields:
            form.base_fields["employee"].initial = request.user.id
        return form

    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Города")
    def cities_display(self, obj):
        # obj из prefetch_related destinations — без N+1
        cities = []
        for dest in obj.destinations.all():
            city_name = dest.city.name if dest.city else "—"
            if city_name not in cities:
                cities.append(city_name)
        return ", ".join(cities) if cities else "—"

    @admin.display(description="Затраты", ordering="_expenses_sum")
    def expenses_sum(self, obj):
        return obj._expenses_sum or 0

    @admin.display(boolean=True, description="Фото")
    def has_photos(self, obj):
        return obj.photos.exists()
```

- [ ] **Step 2: Проверить загрузку страницы списка**

```bash
cd ebase_site && python manage.py check
```

И (если есть локальный Postgres с данными) — открыть `/admin/business_trip/businesstrip/` в браузере, убедиться, что список рендерится.

- [ ] **Step 3: Запустить тесты — ничего не должно сломаться**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

- [ ] **Step 4: Black**

```bash
black ebase_site/business_trip
```

- [ ] **Step 5: Коммит**

```bash
git add ebase_site/business_trip/admin.py
git commit -m "feat(business_trip): админка BusinessTripAdmin с inline (пункты, затраты, фото)"
```

---

## Task 11: Документация — обновить `AGENTS.md`

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Добавить приложение в таблицу приложений**

В таблице «Django-приложения» добавить строку (после `contracts`):

```markdown
| `business_trip` | Командировки сотрудников (`BusinessTrip`), пункты командировки (`BusinessTripDestination` — подразделения и даты), затраты (`BusinessTripExpense`, справочник видов `ExpenseType`), фото чеков (`BusinessTripPhoto`). Авто-расчёт суточных: дни × 700 руб. |
```

- [ ] **Step 2: Добавить в структуру репозитория**

В блоке `ebase_site/` добавить:

```
│   ├── business_trip/           # командировки сотрудников
```

(после `contracts/`)

- [ ] **Step 3: Коммит**

```bash
git add AGENTS.md
git commit -m "docs(business_trip): описание приложения в AGENTS.md"
```

---

## Task 12: Финальная проверка

- [ ] **Step 1: Полный прогон тестов приложения**

```bash
cd ebase_site && python manage.py test business_trip --settings=ebase_site.test_settings
```

Ожидается: все тесты PASS (минимум 12: 2 ExpenseType + 3 суточных + 3 автономер/валидация + 3 пункт + 2 затрата + 1 фото).

- [ ] **Step 2: Прогон всех тестов проекта (существующие не должны сломаться)**

```bash
cd ebase_site && python manage.py test --settings=ebase_site.test_settings
```

Ожидается: не больше падающих, чем было до изменений (известные 5 по `AGENTS.md`).

- [ ] **Step 3: Black по всему новому коду**

```bash
black ebase_site/business_trip
```

- [ ] **Step 4: Smoke-проверка в админке (если есть локальный сервер)**

- `/admin/business_trip/` — раздел «Командировки» присутствует.
- Добавить командировку: дата выезда/возвращения, `employee` подставился текущим пользователем, `doc_number` проставился автоматически, `allowance_amount` посчитан, сохранилась.
- Inline «Пункты» — выбор подразделения через autocomplete, после сохранения в столбце «Город» — город подразделения.
- Inline «Затраты» — добавление строки с датой/видом/суммой.
- Inline «Фото чеков» — загрузка картинки, превью-миниатюра со ссылкой.
- Список: фильтр по сотруднику, drill-down по месяцу через `date_hierarchy`, экспорт в Excel (action из `MainModelAdmin`).

- [ ] **Step 5: Финальный коммит (если были правки по smoke)**

```bash
git add -A
git commit -m "feat(business_trip): раздел командировок готов"
```

---

## Покрытие спеки (self-review)

| Раздел спеки | Задача |
|---|---|
| Приложение `business_trip`, `INSTALLED_APPS` | Task 1 |
| `EbaseModel`, `db_table` со схемой `medsil`, `company` константа | Task 3 |
| Константа `DAILY_ALLOWANCE_RATE = 700` | Task 2 (объявлена) + Task 3 (использована) |
| `ExpenseType` (name unique) | Task 2 |
| `BusinessTrip`: employee/user/doc_number/dates/allowance/service_type/contract/task/take_with/comment/report | Task 3 |
| `allowance_amount` пересчёт в `save()` + расширение `update_fields` | Task 3 (test_allowance_recalc_on_date_change) |
| Автонумерация `doc_number` (max+1, ручной ввод) | Task 4 |
| Валидация `end_dt ≥ beg_dt` | Task 4 |
| `days_count` property | Task 3 |
| `BusinessTripDestination`: department/dates, city из department, валидация | Task 5 |
| `BusinessTripExpense`: date/expense_type/amount/comment, без связи с городом | Task 6 |
| `BusinessTripPhoto`: фото + `delete()` удаляет файл | Task 7 |
| `BusinessTripAdmin`: list_display/date_hierarchy/list_filter/search/filter_horizontal/inlines/`save_model`/`get_form` | Task 10 |
| Inline: пункты (autocomplete department, город readonly), затраты, фото (превью) | Task 10 |
| `ExpenseTypeAdmin` | Task 9 |
| Миграции | Task 8 |
| Тесты (12+ кейсов) | Tasks 2–7 |
| `AGENTS.md` | Task 11 |
| Документы (приказ/отчёт) — НЕ реализуются, структура их покрывает | не задача (задел) |
| Правка `DepartmentAdmin.search_fields` — не нужна (уже есть) | Task 10 использует готовое |

Все пункты спеки покрыты. Мест для неопределённости («TBD», «добавь обработку ошибок») нет — каждый шаг содержит полный код.
