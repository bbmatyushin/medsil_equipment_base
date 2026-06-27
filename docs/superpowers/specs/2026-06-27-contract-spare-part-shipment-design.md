# Связь отгрузок запчастей с контрактами

## Цель

Сделать единственным источником запчастей по контракту модель `SparePartShipmentV2`.
При создании отгрузки запчастей пользователь должен иметь возможность указать связь с `Contract`.
Если отгрузка создана автоматически из ремонта (`Service`) и у ремонта указан контракт, связь с контрактом должна переноситься в отгрузку.
Запчасти, указанные в ремонте, больше не должны напрямую учитываться в затратах контракта.

## Текущее состояние

- `Service.contract` — `ForeignKey` с `unique=True` (один ремонт на контракт).
- `Service.spare_part` + `Service.spare_part_count` описывают запчасти, использованные в ремонте.
- `ServiceAdmin.save_model` автоматически создаёт/обновляет `SparePartShipmentV2` с `SparePartShipmentM2M` строками.
- Сигнал `service_post_save` материализует `ServiceExpense` из `spare_part_count`.
- `contracts.signals.recalc_contract` суммирует `ServiceExpense` связанного ремонта и записывает в `Contract.expenses_amount`.
- На странице контракта `ContractAdmin.service_expenses_display` показывает таблицу из `service.service_expenses`.

## Решения по уточняющим вопросам

1. **Модель `ServiceExpense`** — удалить полностью. Больше не нужна, так как затраты считаются через отгрузки.
2. **Уникальность `Service.contract`** — убрать. На один контракт может быть несколько ремонтов.
3. **Отображение запчастей на странице контракта** — общий плоский список всех строк отгрузок по контракту.
4. **Аналитика расходов** — агрегировать на лету из отгрузок. Дополнительная таблица под расходы не создаётся.

## Предлагаемые изменения

### 1. Модели и схема БД

#### `SparePartShipmentV2` (`ebase_site/spare_part/models.py`)

Добавить поле:

```python
contract = models.ForeignKey(
    "contracts.Contract",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    verbose_name="Контракт",
    related_name="spare_part_shipments",
)
```

#### `Service` (`ebase_site/ebase/models.py`)

Убрать `unique=True` у поля `contract`:

```python
contract = models.ForeignKey(
    "contracts.Contract",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    verbose_name="Контракт",
    related_name="service",
)
```

Удалить поле `service_expenses` (обратная связь к `ServiceExpense`).

#### `SparePartShipmentM2M`

Добавить вычисляемые поля для финансового учёта:

```python
price = models.DecimalField(
    "Цена",
    max_digits=12,
    decimal_places=2,
    null=True,
    blank=True,
)
sum = models.DecimalField(
    "Сумма",
    max_digits=12,
    decimal_places=2,
    null=True,
    blank=True,
)
```

Значения заполняются при сохранении строки отгрузки: `price` — FIFO-цена из `SparePartSupplyItem`, `sum = quantity * price`.

#### `ServiceExpense`

Удалить модель `ServiceExpense` и все ссылки на неё.

### 2. Логика сохранения ремонта

В `ServiceAdmin.save_model` (`ebase_site/ebase/admin.py`) при создании/обновлении связанной `SparePartShipmentV2`:

- если `service.contract` заполнен — записать `shipment.contract = service.contract`;
- если `service.contract` очищен — сбросить `shipment.contract = None`.

### 3. Пересчёт финансов контракта

Функция `recalc_contract` (`ebase_site/contracts/signals.py`) должна:

- суммировать `Payment`;
- суммировать ручные `ContractExpense`;
- суммировать запчасти из отгрузок:
  ```python
  contract.spare_part_shipments.filter(
      shipment_m2m__isnull=False
  ).aggregate(
      total=Sum("shipment_m2m__sum")
  )["total"] or Decimal("0.00")
  ```

Пересчёт запускается при изменении:
- `Payment` (`post_save`, `post_delete`);
- `ContractExpense` (`post_save`, `post_delete`);
- `SparePartShipmentV2` (`post_save`, `post_delete`);
- `SparePartShipmentM2M` (`post_save`, `post_delete`).

Сигнал `service_post_save` (`ebase_site/ebase/signals.py`) больше не создаёт `ServiceExpense`. Если после удаления `ServiceExpense` в нём не остаётся полезной логики, сигнал удаляется.

### 4. Admin / UI

#### `SparePartShipmentV2Admin`

- Добавить `contract` в `fields`/`fieldsets` формы.
- Добавить `contract` в `list_display` и `list_filter`.
- Для авто-отгрузок (`is_auto_comment=True` и `service` заполнен) поле `contract` отображается read-only.

#### `ContractAdmin`

- Удалить `service_expenses_display`.
- Добавить read-only метод `spare_part_shipments_display`, который формирует HTML-таблицу из всех строк `SparePartShipmentM2M` отгрузок контракта.
- Колонки таблицы: запчасть, количество, единица измерения, цена, сумма, номер отгрузки, дата отгрузки.

### 5. Миграции

Так как контрактов, связанных с ремонтами, ещё нет, миграции безопасны:

1. `ebase_site/ebase/migrations/` — удалить модель `ServiceExpense`.
2. `ebase_site/ebase/migrations/` — убрать `unique=True` у `Service.contract`.
3. `ebase_site/spare_part/migrations/` — добавить поле `contract` в `SparePartShipmentV2`.
4. `ebase_site/spare_part/migrations/` — добавить поля `price` и `sum` в `SparePartShipmentM2M`.
5. Опционально: data-migration, копирующая `service.contract` в существующие авто-отгрузки (актуально, если появятся такие данные до деплоя).

### 6. Тесты

- Создание отгрузки с указанием контракта увеличивает `Contract.expenses_amount`.
- Строка отгрузки получает `price` по FIFO и корректный `sum`.
- Авто-отгрузка из ремонта наследует `contract` из ремонта.
- Удаление связи ремонта с контрактом сбрасывает `contract` у отгрузки.
- Изменение количества/состава строк отгрузки пересчитывает `Contract.expenses_amount`.
- Удаление отгрузки пересчитывает `Contract.expenses_amount`.
- `ServiceExpense` отсутствует в БД после миграций.

## Исключённые альтернативы

- **Промежуточная модель `ContractSparePartShipment`**: отвергнута в пользу прямой связи `SparePartShipmentV2.contract` как более простой и достаточной для текущих требований.
- **Таблица `ContractSparePartExpense` для денормализации**: отвергнута в пользу агрегации на лету, так как объём данных пока невелик, а лишняя денормализация усложняет поддержку.

## Связанные файлы

- `ebase_site/contracts/models.py`
- `ebase_site/contracts/admin.py`
- `ebase_site/contracts/signals.py`
- `ebase_site/ebase/models.py`
- `ebase_site/ebase/admin.py`
- `ebase_site/ebase/signals.py`
- `ebase_site/spare_part/models.py`
- `ebase_site/spare_part/admin.py`
- `ebase_site/ebase/tests.py`
- `ebase_site/contracts/tests.py`
- `ebase_site/spare_part/tests.py`
