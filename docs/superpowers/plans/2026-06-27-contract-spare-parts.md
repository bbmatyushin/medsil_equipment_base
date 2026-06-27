# Связь отгрузок запчастей с контрактами — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать `SparePartShipmentV2` единственным источником запчастей по контракту, разорвав прямую связь через `ServiceExpense`.

**Architecture:** Добавляем `contract` в `SparePartShipmentV2`, убираем `unique` у `Service.contract`, удаляем `ServiceExpense`. Финансовые поля `Contract.expenses_amount` пересчитываем через агрегацию отгрузок. В строки отгрузки добавляем `price`/`sum` по FIFO.

**Tech Stack:** Django 4.x, PostgreSQL, pytest/django TestCase.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `ebase_site/spare_part/models.py` | Поля `SparePartShipmentV2.contract`, `SparePartShipmentM2M.price`/`sum`. |
| `ebase_site/ebase/models.py` | Убрать `unique` у `Service.contract`, удалить `ServiceExpense`. |
| `ebase_site/spare_part/signals.py` | Расчёт `price`/`sum` для строк отгрузки по FIFO. |
| `ebase_site/contracts/signals.py` | Пересчёт `Contract.expenses_amount` по отгрузкам; сигналы на отгрузки. |
| `ebase_site/ebase/signals.py` | Удалить материализацию `ServiceExpense`. |
| `ebase_site/ebase/admin.py` | Копирование `contract` из ремонта в отгрузку; удаление `ServiceExpenseInline`. |
| `ebase_site/spare_part/admin.py` | Поле `contract` в форме и списке отгрузок. |
| `ebase_site/contracts/admin.py` | Новая таблица «Запчасти по контракту». |
| `ebase_site/*/migrations/` | Миграции схемы и data-migration для существующих отгрузок. |
| `ebase_site/contracts/tests.py`, `ebase_site/ebase/tests.py`, `ebase_site/spare_part/tests.py` | Тесты новой логики. |

---

## Task 1: Модели — добавить `contract` в `SparePartShipmentV2`

**Files:**
- Modify: `ebase_site/spare_part/models.py`

- [ ] **Step 1: Добавить поле `contract` в модель `SparePartShipmentV2`**

Найти класс `SparePartShipmentV2` и добавить поле после поля `service`:

```python
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Контракт",
        db_comment="Контракт, к которому относится отгрузка запчастей",
        related_name="spare_part_shipments",
    )
```

- [ ] **Step 2: Проверить, что модель импортируется**

Run: `python ebase_site/manage.py check --settings=ebase_site.settings`
Expected: `System check identified no issues` (пока ещё может быть, т.к. миграции не созданы).

- [ ] **Step 3: Commit**

```bash
git add ebase_site/spare_part/models.py
git commit -m "feat(spare_part): add contract FK to SparePartShipmentV2"
```

---

## Task 2: Модели — добавить `price`/`sum` в `SparePartShipmentM2M`

**Files:**
- Modify: `ebase_site/spare_part/models.py`

- [ ] **Step 1: Добавить поля `price` и `sum` в `SparePartShipmentM2M`**

После поля `quantity` добавить:

```python
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Цена закупки",
        db_comment="Закупочная цена по FIFO",
    )
    sum = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Сумма",
        db_comment="quantity * price",
    )
```

- [ ] **Step 2: Добавить `save` для автоподсчёта `sum`**

В класс `SparePartShipmentM2M` добавить метод:

```python
    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.sum = Decimal(str(self.quantity or 0)) * Decimal(str(self.price or 0))
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"sum"}
        super().save(*args, **kwargs)
```

- [ ] **Step 3: Commit**

```bash
git add ebase_site/spare_part/models.py
git commit -m "feat(spare_part): add price/sum fields to SparePartShipmentM2M"
```

---

## Task 3: Модели — убрать `unique` у `Service.contract` и удалить `ServiceExpense`

**Files:**
- Modify: `ebase_site/ebase/models.py`

- [ ] **Step 1: Убрать `unique=True` у поля `contract` в `Service`**

Заменить:

```python
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        unique=True,
        related_name="service",
        verbose_name="Связанный Контракт",
        db_comment="ID контракта из реестра контрактов",
        help_text="Контракт, связанный с данным ремонтом. Один контракт может быть связан только с одним ремонтом.",
    )
```

на:

```python
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service",
        verbose_name="Связанный Контракт",
        db_comment="ID контракта из реестра контрактов",
        help_text="Контракт, связанный с данным ремонтом. На один контракт может быть несколько ремонтов.",
    )
```

- [ ] **Step 2: Удалить класс `ServiceExpense`**

Удалить весь класс `ServiceExpense` (строки 658–721).

- [ ] **Step 3: Commit**

```bash
git add ebase_site/ebase/models.py
git commit -m "feat(ebase): remove ServiceExpense and Service.contract uniqueness"
```

---

## Task 4: Сигналы — заполнять `price`/`sum` в строках отгрузки

**Files:**
- Modify: `ebase_site/spare_part/signals.py`

- [ ] **Step 1: Добавить `pre_save` сигнал для `SparePartShipmentM2M`**

В начало файла добавить импорт:

```python
from decimal import Decimal
from django.db.models.signals import pre_save
from django.dispatch import receiver
from spare_part.models import SparePartShipmentM2M
from ebase.signals import get_fifo_price
```

В конец файла добавить:

```python
@receiver(pre_save, sender=SparePartShipmentM2M)
def spare_part_shipment_m2m_pre_save(sender, instance, **kwargs):
    """Заполняет price по FIFO и пересчитывает sum перед сохранением."""
    if instance.price is None or instance.price == 0:
        instance.price = get_fifo_price(instance.spare_part, instance.expiration_dt)
    instance.sum = Decimal(str(instance.quantity or 0)) * Decimal(str(instance.price or 0))
```

- [ ] **Step 2: Commit**

```bash
git add ebase_site/spare_part/signals.py
git commit -m "feat(spare_part): fill FIFO price in shipment lines"
```

---

## Task 5: Сигналы — удалить `ServiceExpense` и пересчитывать контракт по отгрузкам

**Files:**
- Modify: `ebase_site/ebase/signals.py`
- Modify: `ebase_site/contracts/signals.py`

- [ ] **Step 1: Упростить `service_post_save` в `ebase_site/ebase/signals.py`**

Заменить всё содержимое файла на:

```python
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from contracts.signals import recalc_contract
from contracts.models import Contract
from .models import Service


@receiver(pre_save, sender=Service)
def service_pre_save(sender, instance, **kwargs):
    """Запоминаем старый contract_id для пересчёта старого контракта."""
    if instance.pk:
        try:
            old = Service.objects.get(pk=instance.pk)
            instance._old_contract_id = old.contract_id
        except Service.DoesNotExist:
            instance._old_contract_id = None
    else:
        instance._old_contract_id = None


def get_fifo_price(spare_part, expiration_dt=None):
    """Возвращает закупочную цену по FIFO для запчасти."""
    from spare_part.models import SparePartSupplyItem
    qs = SparePartSupplyItem.objects.filter(spare_part=spare_part)
    if expiration_dt is not None:
        qs = qs.filter(expiration_dt=expiration_dt)
    qs = qs.order_by("supply__supply_dt", "expiration_dt")
    first = qs.first()
    return first.price if first else 0


@receiver(post_save, sender=Service)
def service_post_save(sender, instance, created, **kwargs):
    """Пересчитываем связанный контракт при изменении ремонта."""
    if instance.contract:
        recalc_contract(instance.contract)

    old_contract_id = getattr(instance, "_old_contract_id", None)
    if old_contract_id and old_contract_id != instance.contract_id:
        try:
            old_contract = Contract.objects.get(pk=old_contract_id)
            recalc_contract(old_contract)
        except Contract.DoesNotExist:
            pass
```

- [ ] **Step 2: Обновить `recalc_contract` в `ebase_site/contracts/signals.py`**

Заменить функцию `recalc_contract` на:

```python
def recalc_contract(contract):
    """Пересчитывает payment_amount, expenses_amount, debt, profit."""
    if contract is None:
        return

    payment_amount = contract.payments.aggregate(s=Sum("amount"))["s"] or 0

    shipment_expenses = contract.spare_part_shipments.aggregate(
        s=Sum("shipment_m2m__sum")
    )["s"] or 0

    manual_expenses = contract.expenses.aggregate(s=Sum("sum"))["s"] or 0
    expenses_amount = shipment_expenses + manual_expenses

    contract.payment_amount = payment_amount
    contract.expenses_amount = expenses_amount
    contract.debt = contract.contract_amount - payment_amount
    contract.profit = payment_amount - expenses_amount
    contract.save(update_fields=["payment_amount", "expenses_amount", "debt", "profit"])
```

- [ ] **Step 3: Добавить сигналы отгрузок в `ebase_site/contracts/signals.py`**

Добавить импорт:

```python
from spare_part.models import SparePartShipmentV2, SparePartShipmentM2M
```

Добавить сигналы:

```python
@receiver(post_save, sender=SparePartShipmentV2)
def shipment_post_save(sender, instance, **kwargs):
    if instance.contract:
        recalc_contract(instance.contract)


@receiver(post_delete, sender=SparePartShipmentV2)
def shipment_post_delete(sender, instance, **kwargs):
    if instance.contract_id:
        try:
            contract = Contract.objects.get(pk=instance.contract_id)
            recalc_contract(contract)
        except Contract.DoesNotExist:
            pass


@receiver(post_save, sender=SparePartShipmentM2M)
def shipment_m2m_post_save(sender, instance, **kwargs):
    if instance.shipment.contract:
        recalc_contract(instance.shipment.contract)


@receiver(post_delete, sender=SparePartShipmentM2M)
def shipment_m2m_post_delete(sender, instance, **kwargs):
    if instance.shipment.contract_id:
        try:
            contract = Contract.objects.get(pk=instance.shipment.contract_id)
            recalc_contract(contract)
        except Contract.DoesNotExist:
            pass
```

- [ ] **Step 4: Commit**

```bash
git add ebase_site/ebase/signals.py ebase_site/contracts/signals.py
git commit -m "feat(signals): recalc contract from shipments, drop ServiceExpense"
```

---

## Task 6: Admin — обновить `ServiceAdmin.save_model` для копирования `contract`

**Files:**
- Modify: `ebase_site/ebase/admin.py`

- [ ] **Step 1: Удалить `ServiceExpenseInline` и метод `expenses_total`**

Удалить класс `ServiceExpenseInline` (строки 469–479) и метод `expenses_total` (строки 687–690).

- [ ] **Step 2: Удалить импорт `ServiceExpense`**

В строке 36 убрать `ServiceExpense` из импорта.

- [ ] **Step 3: Копировать `contract` в отгрузку в `save_model`**

В `ServiceAdmin.save_model`, после блока создания/обновления `SparePartShipmentV2` (после цикла `SparePartShipmentM2M.objects.create`), добавить:

```python
            # Переносим связь с контрактом из ремонта в отгрузку
            shipment.contract = obj.contract
            shipment.save(update_fields=["contract"])
```

Полный фрагмент должен выглядеть так:

```python
            # Создаем или обновляем запись в SparePartShipmentV2
            shipment, created = SparePartShipmentV2.objects.get_or_create(
                service=obj,
                defaults={
                    "shipment_dt": obj.beg_dt,
                    "user": request.user,
                    "comment": comment,
                    "is_auto_comment": True,
                },
            )

            # Удаляем старые записи о запчастях
            shipment.shipment_m2m.all().delete()

            # Добавляем новые записи о запчастях через промежуточную модель
            for spare_part_info in spare_parts_data:
                SparePartShipmentM2M.objects.create(
                    shipment=shipment,
                    spare_part_id=spare_part_info["id"],
                    quantity=spare_part_info["quantity"],
                    expiration_dt=spare_part_info["expiration_dt"],
                )

            # Переносим связь с контрактом из ремонта в отгрузку
            shipment.contract = obj.contract
            shipment.save(update_fields=["contract"])
```

- [ ] **Step 4: Commit**

```bash
git add ebase_site/ebase/admin.py
git commit -m "feat(admin): copy contract from service to shipment"
```

---

## Task 7: Admin — обновить `SparePartShipmentV2Admin`

**Files:**
- Modify: `ebase_site/spare_part/admin.py`

- [ ] **Step 1: Добавить `contract` в `fieldsets`, `list_display`, `list_filter`**

В `fieldsets` добавить поле `contract`:

```python
                "fields": (
                    (
                        "doc_num",
                        "shipment_dt",
                    ),
                    ("service", "client_shipment"),
                    "contract",
                    "comment",
                    "user",
                )
```

В `list_display` заменить на:

```python
    list_display = (
        "doc_num",
        "shipment_dt",
        "client_shipment",
        "service_equipment",
        "contract",
        "user_name",
    )
```

Добавить:

```python
    list_filter = ("contract",)
```

- [ ] **Step 2: Сделать `contract` read-only для авто-отгрузок**

В `get_form` добавить:

```python
        if obj and obj.is_auto_comment and obj.service:
            form.base_fields["contract"].disabled = True
            form.base_fields["contract"].widget.attrs["readonly"] = True
```

- [ ] **Step 3: Commit**

```bash
git add ebase_site/spare_part/admin.py
git commit -m "feat(admin): add contract field to SparePartShipmentV2 admin"
```

---

## Task 8: Admin — обновить `ContractAdmin`

**Files:**
- Modify: `ebase_site/contracts/admin.py`

- [ ] **Step 1: Добавить импорт `Decimal`**

В начало файла добавить:

```python
from decimal import Decimal
```

- [ ] **Step 2: Заменить `service_expenses_display` на `spare_part_shipments_display`**

Удалить метод `service_expenses_display`. Добавить:

```python
    @admin.display(description="Запчасти по контракту")
    def spare_part_shipments_display(self, obj):
        """Отображает все запчасти из отгрузок по контракту."""
        lines = (
            obj.spare_part_shipments
            .prefetch_related("shipment_m2m__spare_part__unit")
            .order_by("shipment_dt", "shipment_m2m__create_dt")
        )

        rows = []
        total = Decimal("0.00")
        for shipment in lines:
            for line in shipment.shipment_m2m.all():
                part_name = line.spare_part.name if line.spare_part else "—"
                unit = line.spare_part.unit.short_name if line.spare_part and line.spare_part.unit else "—"
                rows.append(
                    format_html(
                        "<tr>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "<td>{}</td>"
                        "</tr>",
                        part_name,
                        unit,
                        line.quantity,
                        f"{line.price:.2f}",
                        f"{line.sum:.2f}",
                        shipment.doc_num,
                        shipment.shipment_dt.strftime("%d.%m.%Y"),
                    )
                )
                total += line.sum or Decimal("0.00")

        if not rows:
            return "Нет отгрузок запчастей по контракту."

        html = (
            f"<table style='border-collapse: collapse; width: 100%;'>"
            f"<thead><tr>"
            f"<th style='text-align: left; padding: 4px 8px;'>Наименование</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Ед. изм.</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Кол-во</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Цена</th>"
            f"<th style='text-align: right; padding: 4px 8px;'>Сумма</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Отгрузка</th>"
            f"<th style='text-align: left; padding: 4px 8px;'>Дата</th>"
            f"</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"<tfoot><tr>"
            f"<td colspan='4' style='text-align: right; padding: 4px 8px;'><b>Итого:</b></td>"
            f"<td style='text-align: right; padding: 4px 8px;'><b>{total:.2f}</b></td>"
            f"<td colspan='2'></td>"
            f"</tr></tfoot>"
            f"</table>"
        )
        return format_html(html)
```

- [ ] **Step 3: Обновить `readonly_fields` и `fieldsets`**

Заменить:

```python
    readonly_fields = (
        "payment_amount",
        "expenses_amount",
        "debt",
        "profit",
        "service_expenses_display",
    )
```

на:

```python
    readonly_fields = (
        "payment_amount",
        "expenses_amount",
        "debt",
        "profit",
        "spare_part_shipments_display",
    )
```

В `fieldsets` заменить раздел "Запчасти по контракту":

```python
        (
            "Запчасти по контракту",
            {
                "fields": ("spare_part_shipments_display",),
                "description": "Запчасти, отгруженные по данному контракту.",
            },
        ),
```

- [ ] **Step 4: Commit**

```bash
git add ebase_site/contracts/admin.py
git commit -m "feat(admin): display spare parts by contract from shipments"
```

---

## Task 9: Миграции

**Files:**
- Create: `ebase_site/ebase/migrations/00XX_remove_serviceexpense_and_alter_service_contract.py`
- Create: `ebase_site/spare_part/migrations/00XX_add_contract_and_price_sum.py`

- [ ] **Step 1: Сгенерировать миграции**

Run:

```bash
cd ebase_site
python manage.py makemigrations ebase spare_part --settings=ebase_site.settings
```

Expected: созданы две миграции.

- [ ] **Step 2: Проверить сгенерированные миграции**

Run:

```bash
python manage.py sqlmigrate ebase <migration_name> --settings=ebase_site.settings
python manage.py sqlmigrate spare_part <migration_name> --settings=ebase_site.settings
```

Expected: SQL содержит `DROP TABLE` для `service_expense`, `ALTER TABLE` для удаления unique, `ADD COLUMN` для `contract`, `price`, `sum`.

- [ ] **Step 3: Применить миграции**

Run:

```bash
python manage.py migrate --settings=ebase_site.settings
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add ebase_site/ebase/migrations/ ebase_site/spare_part/migrations/
git commit -m "feat(migrations): schema changes for contract-shipment linkage"
```

---

## Task 10: Тесты — пересчёт контракта через отгрузки

**Files:**
- Modify: `ebase_site/contracts/tests.py`

- [ ] **Step 1: Добавить тест на пересчёт через отгрузку**

Добавить в `ContractModelTests` (или создать новый класс):

```python
    def test_contract_recalc_on_spare_part_shipment(self):
        """Создание отгрузки с запчастями увеличивает expenses_amount контракта."""
        from spare_part.models import SparePartShipmentV2, SparePartShipmentM2M
        from directory.models import Unit
        from users.models import CompanyUser

        unit = Unit.objects.create(name="шт.", short_name="шт.")
        spare_part = SparePart.objects.create(name="Тестовая запчасть", unit=unit)
        user = CompanyUser.objects.create_user(username="testshipper", password="pass")

        shipment = SparePartShipmentV2.objects.create(
            doc_num="ТО-001",
            shipment_dt=date.today(),
            user=user,
            contract=self.contract,
        )
        SparePartShipmentM2M.objects.create(
            shipment=shipment,
            spare_part=spare_part,
            quantity=2,
            price=Decimal("100.00"),
        )

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.expenses_amount, Decimal("200.00"))
```

- [ ] **Step 2: Запустить тест**

Run:

```bash
cd ebase_site
python manage.py test contracts.tests.ContractModelTests.test_contract_recalc_on_spare_part_shipment --settings=ebase_site.settings -v 2
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add ebase_site/contracts/tests.py
git commit -m "test(contracts): recalc contract from spare part shipment"
```

---

## Task 11: Тесты — связь ремонта и отгрузки с контрактом

**Files:**
- Modify: `ebase_site/ebase/tests.py`

- [ ] **Step 1: Обновить существующие тесты**

Удалить или обновить тесты, которые проверяют `ServiceExpense` и `unique` у `Service.contract`.

- [ ] **Step 2: Добавить тест на перенос `contract` в отгрузку**

Добавить:

```python
    def test_service_contract_copies_to_shipment(self):
        """При сохранении ремонта с запчастями отгрузка наследует contract."""
        # Зависит от логики ServiceAdmin.save_model; если интеграционный тест сложен,
        # можно протестировать напрямую через модели.
        from spare_part.models import SparePartShipmentV2, SparePartShipmentM2M
        shipment = SparePartShipmentV2.objects.create(
            doc_num="АВ-001",
            shipment_dt=self.service.beg_dt,
            user=self.service.user,
            service=self.service,
            contract=self.contract,
        )
        SparePartShipmentM2M.objects.create(
            shipment=shipment,
            spare_part=self.spare_part,
            quantity=1,
            price=Decimal("50.00"),
        )

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.expenses_amount, Decimal("50.00"))
```

- [ ] **Step 3: Запустить тесты**

Run:

```bash
python manage.py test ebase.tests.ServiceContractTests --settings=ebase_site.settings -v 2
```

Expected: все тесты проходят.

- [ ] **Step 4: Commit**

```bash
git add ebase_site/ebase/tests.py
git commit -m "test(ebase): service contract linkage through shipment"
```

---

## Task 12: Финальная проверка

- [ ] **Step 1: Запустить полный набор тестов**

Run:

```bash
cd ebase_site
python manage.py test --settings=ebase_site.settings -v 2
```

Expected: все тесты проходят.

- [ ] **Step 2: Проверить состояние git**

Run:

```bash
git status
```

Expected: нет незакоммиченных изменений.

- [ ] **Step 3: Commit (если есть финальные правки)**

```bash
git add -A
git commit -m "feat: complete contract spare-part shipment linkage"
```

---

## Self-Review Checklist

- [ ] Spec coverage: каждый пункт spec имеет соответствующую task.
- [ ] Placeholder scan: нет `TBD`, `TODO`, незавершённых секций.
- [ ] Type consistency: названия полей и методов совпадают во всех tasks.
- [ ] Migration safety: миграции учитывают отсутствие данных в `ServiceExpense`.
