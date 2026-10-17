# «Аналитика»: вкладка «Командировки» — план реализации

> **Для исполнителя-агента:** используй скилл `superpowers:subagent-driven-development` (рекомендуется) или `superpowers:executing-plans` для пошагового выполнения. Шаги помечены чекбоксами `- [ ]`.

**Цель:** вкладка «Командировки» в разделе «Аналитика». Главное — сколько в среднем за год тратится на каждое направление (город / регион).
Плюс блоки «Сотрудники», «Командировки и деньги», «Экономия и контроль», «Нормативы для бюджета».

**Архитектура:** как у вкладки «Финансы».
- Расчёты — чистые функции в `analytics/services/trips.py`, на входе `Period` и фильтры.
- Стоимость командировки разносится по пунктам одним ядром атрибуции (`trip_shares`), из него строятся города, регионы и клиенты.
- `analytics/views_trips.py` собирает плитки, таблицы и спецификации графиков (`chart_spec`). Шаблон `analytics/trips.html` рисует их как `finance.html`.

**Тех-стек:** Django 4.2.16, Python 3.11, PostgreSQL (в тестах SQLite `:memory:`, миграции выключены), Chart.js 4.5.1 (vendored), Black 24.8.0.

**Спека:** `docs/superpowers/specs/2026-10-17-analytics-trips-design.md`. Перед стартом прочитать её целиком: решения пользователя, решения исполнителя, таблицы виджетов.
Образцы кода: `analytics/views.py`, `analytics/services/finance.py`, `analytics/templates/analytics/finance.html`, `analytics/tests/test_views.py`.

**Тесты (из `ebase_site/`):**

```bash
source ../.venv/bin/activate
python manage.py test analytics business_trip --settings=ebase_site.test_settings   # по ходу задач
python manage.py test --settings=ebase_site.test_settings                          # полный прогон
```

**Black:** только по своим файлам, например `black analytics/services/trips.py analytics/views_trips.py analytics/tests/test_trips.py …`. Не запускать `black ebase_site` целиком: он переформатирует чужие миграции.

**Коммиты:** на русском, стиль репозитория: `feat(analytics): …`, `test(analytics): …`, `docs(analytics): …`. Ветка `feature/analytics-trips` уже создана от `main`. В `main` не сливать.

## Global Constraints

- **Падения до начала работ.** Базовый прогон: `Ran 268 tests … FAILED (failures=2, errors=3)`. Эти пять тестов падали до нас и не чинятся:
  - `ebase.tests.ServiceContractTests` (три теста, ERROR);
  - `contracts.tests.ContractAdminFormTests.test_payment_status_included_on_change_form`;
  - `contracts.tests.ContractModelTests.test_payment_status_updates_when_contract_amount_changes`.

  Критерий: новых падений нет.
> **Изменено после реализации (2026-10-17, по просьбе пользователя):** остаются только права существующих вкладок — `view_finance` и `view_trips`. Миграция `0004` удаляет `view_warehouse_trips`, `view_service`, `view_park` вместо переименования; права новых вкладок добавляются вместе с вкладками. Список ниже и тесты задачи 1 описывают первоначальный вариант.

- Права `AnalyticsAccess` после задачи 1 (`codename` → название):
  - `view_finance` → «Аналитика: Финансы»;
  - `view_trips` → «Аналитика: Командировки» (новое);
  - `view_warehouse` → «Аналитика: Склад» (переименовано из `view_warehouse_trips`);
  - `view_service` → «Аналитика: Сервис и надёжность»;
  - `view_park` → «Аналитика: Парк и продажи».
- Группа «Аналитика» получает `view_trips`.
- Вкладка: `Tab("trips", "Командировки", "analytics.view_trips", "analytics:trips")`, URL `/admin/analytics/trips/`, вторая в `TABS` после «Финансов».
- Новых pip-зависимостей нет. Сигналы (`*/signals.py`) и модели `business_trip` не меняются.
- Тексты интерфейса на русском. Деньги — фильтр `money` («20 000,00 ₽»), счётчики — новый фильтр `number` («1 234»), пусто — «—».
- Арифметика дат и группировка по месяцам — в Python, не функциями БД.
- **Не вызывать `str(department)`**: `Department.__str__` падает при `city=None`. Брать `department.name`.
- Деньги — `Decimal`, в графики только через `chart_spec` (он переводит во float).
- Палитра графиков — не больше 6 серий (`charts.js` берёт цвета строго по порядку).
- `?id__in=` в ссылках — не больше `MAX_LINK_IDS` (90) id. Если id больше, ссылки нет.
- Имена GET-параметров ссылок в список командировок — те, что читает `list_filter`:
  - `employee=<pk>` (`EmployeeUsedInTripsFilter`);
  - `service_type__id__exact=<id>`, без вида работ — `service_type__isnull=True`;
  - даты — `beg_dt__gte` / `beg_dt__lte`;
  - поступления ДС — `employee=<pk>` (`ReceiptEmployeeFilter`).
- Подписи «вся история» / «на сегодня» на виджетах, где период не действует.

## Review Focus

1. **Пустая БД или период без командировок.** Ожидание:
   - страница 200;
   - плитки «0,00 ₽» и «0»;
   - средние и дельты «—»;
   - графики «Нет данных»;
   - таблицы с подписью «Нет данных»;
   - «В среднем за год» без строк и без подписи окна.

   Деления на ноль нет. Тесты: задача 4 `test_kpis_empty_period`, задача 9 `test_trips_page_empty_db`.
2. **Неполные справочники:** подразделение без города, город без региона, пункт без клиента, командировка без пунктов. Ожидание: подписанные корзины, без 500. Тесты: задача 3 `test_direction_*`, задача 9 `test_trips_page_with_incomplete_directory`.
3. **Затраты вне дат пунктов** (билет до выезда, дата вне командировки) и суммы, которые не делятся нацело. Ожидание: затрата делится по дням пунктов, сумма долей равна сумме затраты до копейки. Тесты: задача 3 `test_split_*`, `test_trip_shares_sum_equals_trip_total`.
4. **Мусор в GET:** неизвестный UUID сотрудника, `group=foo`, плохие даты. Ожидание: откат к «все сотрудники», «города», текущий год. Тесты: задача 2 `test_trips_form_*`, задача 9 `test_trips_page_bad_params`.
5. **Будущая командировка** (`beg_dt > сегодня`, суточные уже посчитаны). Ожидание: входит в виджеты периода, если попадает в период, но не входит в «вся история», «на сегодня» и окно «в среднем за год». Тесты: задача 5 `test_annual_ignores_future_trips`, задача 6 `test_balance_ignores_future_trips`.

---

## Структура файлов

```
ebase_site/analytics/
├── models.py                    # (изм.) права view_trips, view_warehouse
├── migrations/0004_trips_tab.py # (нов.) переименование права, view_trips, выдача группе
├── navigation.py                # (изм.) Tab("trips", …) в TABS
├── urls.py                      # (изм.) trips/
├── filters.py                   # (изм.) TRIP_GROUPS, TripsFilterForm
├── services/trips.py            # (нов.) атрибуция и расчёты вкладки
├── views_trips.py               # (нов.) TripsView, плитки, ссылки, графики
├── templatetags/analytics_tags.py  # (изм.) фильтр number
├── templates/analytics/trips.html  # (нов.)
├── static/analytics/css/analytics.css  # (изм.) тон an-tone-load
└── tests/
    ├── factories.py             # (изм.) фабрики командировок
    ├── test_trips.py            # (нов.) расчёты
    ├── test_views.py            # (изм.) страница, доступ, ссылки
    ├── test_filters.py          # (изм.) TripsFilterForm
    ├── test_migrations.py       # (изм.) 0004 и состояние прав до неё
    └── test_tags.py             # (нов., если нет тестов фильтров) number
AGENTS.md                        # (изм.) раздел «Аналитика»
```

---

### Task 1: Права, миграция 0004, вкладка и пустая страница

**Files:**
- Modify: `ebase_site/analytics/models.py`, `ebase_site/analytics/navigation.py`, `ebase_site/analytics/urls.py`
- Create: `ebase_site/analytics/migrations/0004_trips_tab.py`, `ebase_site/analytics/views_trips.py`, `ebase_site/analytics/templates/analytics/trips.html`
- Test: `ebase_site/analytics/tests/test_migrations.py`, `ebase_site/analytics/tests/test_views.py`

**Interfaces:**
- Produces:
  - `analytics.views_trips.TripsView(AnalyticsTabView)` с `tab_key = "trips"` и `template_name = "analytics/trips.html"`;
  - URL `analytics:trips`;
  - функции миграции `add_trips_tab(apps, schema_editor)` / `remove_trips_tab(apps, schema_editor)`.

- [ ] **Step 1: Тесты миграций.** В тестах права создаются по текущей модели (миграции выключены), поэтому тестам `0002` и `0003` нужно состояние «до 0004». Добавить в `test_migrations.py` хелпер:

```python
def _permissions_before_0004():
    """Права как до миграции 0004: view_warehouse_trips вместо view_warehouse, без view_trips."""
    analytics = Permission.objects.filter(content_type__app_label="analytics")
    analytics.filter(codename="view_warehouse").update(
        codename="view_warehouse_trips", name="Аналитика: Склад и командировки"
    )
    analytics.filter(codename="view_trips").delete()
```

  Вызывать его в начале тестов `StatisticsGroupMigrationTests` (кроме `test_permissions_exist`) и в `RenameToAnalyticsMigrationTests.setUp` до обновления имён. Ожидания этих тестов не меняются.
  `test_permissions_exist` ожидает `{"view_finance", "view_trips", "view_warehouse", "view_service", "view_park"}`.
  Новый класс `TripsTabMigrationTests`, в `setUp` — `_permissions_before_0004()`:
  - `test_renames_warehouse_permission_and_keeps_grants`: пользователю выдано `view_warehouse_trips` напрямую, группе «Аналитика» тоже. После `add_trips_tab(django_apps, None)`:
    - у права `codename == "view_warehouse"`, `name == "Аналитика: Склад"`, тот же `pk`;
    - `User.objects.get(pk=…).has_perm("analytics.view_warehouse")` — True.
  - `test_creates_trips_permission_and_grants_group`: группа «Аналитика» с пользователем; после миграции право `view_trips` («Аналитика: Командировки») есть в группе, у пользователя `has_perm("analytics.view_trips")`.
  - `test_without_group_creates_permission_only`: групп нет → право создано, `Group.objects.count() == 0`.
  - `test_is_idempotent`: два вызова подряд → одно право `view_trips`, ошибок нет.
  - `test_reverse_restores_previous_state`: `add_trips_tab`, затем `remove_trips_tab` → codename `view_warehouse_trips` с прежним названием, `view_trips` нет.

- [ ] **Step 2: Тесты страницы** в `test_views.py` (`AnalyticsViewsTests`):
  - `test_superuser_sees_trips_tab`: GET `analytics:trips` → 200, есть «Командировки».
  - `test_staff_without_trips_permission_gets_403`.
  - `test_index_redirects_to_trips_when_only_trips_permitted`: только `view_trips` → редирект на `/admin/analytics/trips/`.
  - `test_sidebar_lists_trips_tab_with_permission`: пункт «Командировки» в списке приложений по образцу `test_sidebar_lists_analytics_tabs_with_permission`.

- [ ] **Step 3: Прогнать — падают** (`python manage.py test analytics.tests.test_migrations analytics.tests.test_views --settings=ebase_site.test_settings`), ожидаются ошибки отсутствия URL, миграции и прав.

- [ ] **Step 4: Реализовать.**
  - `models.py`: `permissions` в порядке finance, trips, warehouse, service, park, названия из Global Constraints.
  - `0004_trips_tab.py`: `AlterModelOptions` (полный набор опций, как в `0003`) + `RunPython(add_trips_tab, remove_trips_tab)`. Константы зафиксированы в файле миграции, не импортируются из `models.py`. Права ищутся по `content_type__app_label="analytics", content_type__model="analyticsaccess"`.
    1. Переименовать `view_warehouse_trips` → `view_warehouse` с новым названием (`update` по той же строке), только если `view_warehouse` ещё нет.
    2. `ContentType.objects.get_or_create(app_label="analytics", model="analyticsaccess")`, затем `Permission.objects.get_or_create(codename="view_trips", content_type=…, defaults={"name": …})`. Приём с `create_permissions` из `0002` не нужен.
    3. Если есть группа «Аналитика», `group.permissions.add(view_trips)`.

    Обратная функция: `view_trips` удалить; `view_warehouse` → `view_warehouse_trips` с названием «Аналитика: Склад и командировки», если старого codename нет.
    Зависимости: `("analytics", "0003_rename_to_analytics")`, `("auth", "0012_alter_user_first_name_max_length")`, `("contenttypes", "0002_remove_content_type_name")`.
  - `navigation.py`: вкладка в `TABS` после `finance`.
  - `views_trips.py`: `TripsView` с `form_class = PeriodForm` (заменится в задаче 2).
  - `urls.py`: `path("trips/", admin.site.admin_view(TripsView.as_view()), name="trips")`.
  - `trips.html`: `{% extends "analytics/base.html" %}` и пустой `analytics_content`.

- [ ] **Step 5: Прогнать — проходят** (та же команда).
  Затем проверить, что миграция совпадает с моделью. `test_settings` отключает миграции, рабочая БД не нужна, поэтому в scratchpad создать `mig_check_settings.py`:
  `from ebase_site.test_settings import *` и `MIGRATION_MODULES = {}`.
  Выполнить `PYTHONPATH=<scratchpad> python manage.py makemigrations analytics --check --dry-run --settings=mig_check_settings`.
  Ожидается `No changes detected`.

- [ ] **Step 6: Commit** — `feat(analytics): вкладка «Командировки», право view_trips и переименование права склада`.

---

### Task 2: Фильтры вкладки и фильтр `number`

**Files:**
- Modify: `ebase_site/analytics/filters.py`, `ebase_site/analytics/templatetags/analytics_tags.py`, `ebase_site/analytics/views_trips.py`
- Test: `ebase_site/analytics/tests/test_filters.py`; тест фильтра `number` — рядом с тестами `money`/`pct`, если они есть (`grep -rn "def test.*money" analytics/tests`), иначе новый `analytics/tests/test_tags.py`

**Interfaces:**
- Produces:
  - `TRIP_GROUPS = [("city", "Города"), ("region", "Регионы")]`, `DEFAULT_GROUP = "city"`;
  - `TripsFilterForm(PeriodForm)` с полями `employee` и `group`, методами `get_employee() -> CompanyUser | None` и `get_group() -> str`;
  - фильтр шаблона `number(value) -> str`.

- [ ] **Step 1: Тесты** (`test_filters.py`, фабрика `make_employee` из задачи 3 пока не нужна — сотрудник создаётся через `User.objects.create_user` + `BusinessTrip.objects.create`):
  - `test_trips_form_defaults`: пустой GET → `get_employee() is None`, `get_group() == "city"`, период — текущий год.
  - `test_trips_form_employee_and_group`: `{"employee": pk, "group": "region"}` → этот сотрудник и `"region"`.
  - `test_trips_form_garbage_falls_back`: `{"employee": "not-a-uuid", "group": "foo"}` → `None` и `"city"`.
  - `test_trips_form_lists_only_employees_with_trips`: пользователь без командировок отсутствует в `form.fields["employee"].queryset`.
  - `test_trips_form_employee_label_is_fio`: подпись варианта — «Иванов Иван Иванович» (`employee_fio`), без ФИО — `username`.
  - `number`: `number(1234) == "1 234"`, `number(None) == "—"`, `number(Decimal("12.5")) == "12,5"`, `number(Decimal("12.0")) == "12"`.

- [ ] **Step 2: Прогнать — падают.**

- [ ] **Step 3: Реализовать.**
  - `TripsFilterForm.employee`: `ModelChoiceField(CompanyUser.objects.filter(business_trip_employee__isnull=False).distinct().order_by("last_name", "first_name", "patron"), required=False, label="Сотрудник", empty_label="Все сотрудники")`. Подпись через `label_from_instance` = `employee_fio(user) or user.username` (`business_trip.xlsx_report.employee_fio`).
  - `TripsFilterForm.group`: `ChoiceField(choices=TRIP_GROUPS, required=False, label="Направления")`. Мусор → `DEFAULT_GROUP`, через `_cleaned()`, как `get_client`.
  - `number`: целое без дробной части; иначе один знак после запятой, у целого значения без «,0». Разряды через `_number`.
  - `TripsView.form_class = TripsFilterForm`.

- [ ] **Step 4: Прогнать — проходят.**

- [ ] **Step 5: Commit** — `feat(analytics): фильтры вкладки «Командировки» и формат чисел`.

---

### Task 3: Фабрики и ядро атрибуции

**Files:**
- Modify: `ebase_site/analytics/tests/factories.py`
- Create: `ebase_site/analytics/services/trips.py`, `ebase_site/analytics/tests/test_trips.py`

**Interfaces:**
- Produces (фабрики):
  - `make_employee(username="ivanov", last_name="Иванов", first_name="Иван", patron="Иванович") -> CompanyUser`;
  - `make_city(name="Казань", region="Татарстан") -> City` — через `get_or_create`;
  - `make_department(name, client=None, city=<make_city()>, address=None) -> Department` — `address` по умолчанию `f"адрес {name}"`; `city=None` допустим;
  - `make_trip(employee, beg, end, *, destinations=(), expenses=(), service_types=(), contracts=()) -> BusinessTrip`:
    - `destinations` — кортежи `(department, beg, end)`;
    - `expenses` — кортежи `(type_name, date, amount)`, `ExpenseType` через `get_or_create`;
    - `service_types` — имена `ServiceType` (`get_or_create`);
    - `contracts` — объекты `Contract` (добавляются последними, сигналы пересчитают доли);
  - `make_receipt(employee, receipt_date, amount) -> MoneyReceipt`.
- Produces (`services/trips.py`):
  - константы: `ALLOWANCE_LABEL = "Суточные"`, `NO_DESTINATIONS_LABEL = "Пункты не указаны"`, `NO_CITY_LABEL = "Город не указан"`, `NO_REGION_SUFFIX = " (регион не указан)"`, `NO_CLIENT_LABEL = "Клиент не указан"`;
  - `@dataclass(frozen=True) class Share: trip: BusinessTrip; destination: BusinessTripDestination | None; kind: str; amount: Decimal` (`kind` — `ExpenseType.name` или `ALLOWANCE_LABEL`);
  - `split_proportional(total: Decimal, weights: list[int]) -> list[Decimal]`;
  - `destination_days(dest) -> int` (`end_dt − beg_dt + 1`);
  - `trip_total(trip) -> Decimal` (все затраты + `allowance_amount`);
  - `trip_shares(trip) -> list[Share]`;
  - `direction_of(dest: BusinessTripDestination | None, group: str) -> tuple[str, str]` (ключ, подпись);
  - `client_of(dest: BusinessTripDestination | None) -> tuple[str, str]`;
  - `load_trips(queryset) -> list[BusinessTrip]` — `select_related("employee")` + `prefetch_related("destinations__department__city", "destinations__department__client", "expenses__expense_type", "service_type", "contract")`;
  - `trips_in_period(period, employee=None) -> list[BusinessTrip]` — `beg_dt` в периоде;
  - `trips_until(today, employee=None) -> list[BusinessTrip]` — `beg_dt ≤ today`.

  Функции принимают командировки после `load_trips`: в цикле нет запросов.

- [ ] **Step 1: Тесты** (`test_trips.py`, класс `AttributionTests`):
  - `test_split_proportional_kopecks`: `split_proportional(Decimal("100.00"), [1, 2]) == [Decimal("33.34"), Decimal("66.66")]`; `split_proportional(Decimal("0"), [3, 1]) == [Decimal("0"), Decimal("0")]`.
  - `test_split_proportional_sum_is_exact`: для `Decimal("1000.01")` и весов `[3, 3, 1]` сумма долей `== Decimal("1000.01")`.
  - `test_single_city_gets_everything`: командировка 3 дня, один пункт, затраты 1 000 и 500 → доли пункта: затраты 1 500, суточные 2 100.
  - `test_expense_goes_to_destination_by_date`: пункты Казань 01–02.03 и Самара 03–05.03, такси 02.03 на 900 → вся сумма Казани.
  - `test_overlapping_destinations_pick_earliest`: два пункта из разных городов накрывают дату затраты → затрата у пункта с меньшим `beg_dt`.
  - `test_ticket_before_departure_split_by_days`: пункты 2 и 3 дня, билет за день до выезда 5 000 → 2 000 и 3 000.
  - `test_allowance_split_by_days`: та же командировка, суточные 3 500 (5 дней) → 1 400 и 2 100.
  - `test_trip_without_destinations`: все доли с `destination is None`; `direction_of(None, "city") == ("none", "Пункты не указаны")`.
  - `test_trip_shares_sum_equals_trip_total`: для командировки с тремя пунктами и «неудобными» суммами `sum(s.amount for s in trip_shares(trip)) == trip_total(trip)`.
  - `test_direction_city_and_region_keys`: при `group="city"` подпись Казани «Казань (Татарстан)»; при `"region"` два города Татарстана дают один ключ `"region:Татарстан"` с подписью «Татарстан».
  - `test_direction_city_without_region`: в режиме `"region"` город без региона → подпись «Набережные Челны (регион не указан)».
  - `test_direction_department_without_city`: `("no_city", "Город не указан")`.
  - `test_client_of_buckets`: клиент → `(str(pk), name)`; без клиента → `("no_client", "Клиент не указан")`; `None` → `("none", "Пункты не указаны")`.
  - `test_load_trips_makes_no_queries_in_loop`: `assertNumQueries` на вызов `trip_shares` по всем загруженным командировкам — 0 запросов.

- [ ] **Step 2: Прогнать — падают.**

- [ ] **Step 3: Реализовать.**
  - `split_proportional`: доля `i` — `total × w_i / Σw` с округлением вниз до копеек, остаток прибавляется к первой доле (как `business_trip.services.split_amount`).
  - `trip_shares`: пункты сортируются по `(beg_dt, end_dt)`.
    - Затрата с датой внутри пункта уходит первому подходящему.
    - Иначе каждая такая затрата отдельно делится по `destination_days` между всеми пунктами (`kind` — её вид).
    - Суточные делятся так же.
    - Без пунктов — по одной доле на затрату и суточные с `destination=None`.
    - Доли с нулевой суммой не создаются.
  - `direction_of`:
    - `group="city"` → `(f"city:{city.pk}", str(city).strip())`;
    - `group="region"` → `(f"region:{region}", region)` при непустом `region.strip()`, иначе `(f"city:{city.pk}", f"{city.name}{NO_REGION_SUFFIX}")`.

- [ ] **Step 4: Прогнать — проходят.**

- [ ] **Step 5: Commit** — `feat(analytics): атрибуция затрат командировок к пунктам`.

---

### Task 4: Основа вкладки — плитки, затраты по месяцам, структура

**Files:**
- Modify: `ebase_site/analytics/services/trips.py`, `ebase_site/analytics/views_trips.py`, `ebase_site/analytics/templates/analytics/trips.html`
- Test: `ebase_site/analytics/tests/test_trips.py`, `ebase_site/analytics/tests/test_views.py`

**Interfaces:**
- Consumes: `trips_in_period`, `trip_total` (задача 3); `analytics.services.finance._delta_pct`.
- Produces:
  - `MAX_MONTH_SERIES = 6`, `OTHER_KINDS_LABEL = "Прочие виды"`;
  - `trips_kpis(period, employee=None) -> dict` с ключами `current`, `previous`, `delta_pct`; в каждом `total: Decimal`, `count: int`, `person_days: int`, `avg_trip: Decimal | None`, `avg_day: Decimal | None` (средние — до копеек, `None` при нуле в знаменателе);
  - `costs_by_month(period, employee=None) -> dict` вида `{"months": list[date], "series": list[{"label": str, "data": list[Decimal]}]}`;
  - `cost_structure(period, employee=None) -> list[dict]` вида `[{"label", "amount", "share_pct"}]`;
  - в `views_trips.py`:
    - `TRIPS = "business_trip_businesstrip"`;
    - `TRIPS_TILES = [("total", "Всего потрачено", "money", True), ("count", "Командировок", "count", False), ("person_days", "Человеко-дней", "count", False), ("avg_trip", "Средняя поездка", "money", True), ("avg_day", "Средний день", "money", True)]` — ключ, подпись, вид, «рост — плохо»;
    - `_trips_list_url(period, employee, **params) -> str` — список командировок с `beg_dt__gte` / `beg_dt__lte` и `employee`;
  - контекст: `employee`, `group`, `tiles`, `trips_list_url`, `charts` (ключи `by_month`, `structure`).

- [ ] **Step 1: Тесты расчётов** (`KpiTests`, `MonthTests`):
  - `test_kpis_empty_period`: `total == 0`, `count == 0`, `person_days == 0`, `avg_trip is None`, `avg_day is None`, все `delta_pct` — `None`.
  - `test_kpis_values_and_delta`:
    - 2026: две командировки (3 и 2 дня, затраты 1 000 и 500) → `total == 1000 + 2100 + 500 + 1400 == 5000`, `person_days == 5`, `avg_trip == 2500`, `avg_day == 1000`;
    - 2025: одна на 2 500 → `delta_pct["total"] == Decimal("100.0")`.
  - `test_kpis_employee_filter`: чужая командировка не входит.
  - `test_months_use_trip_start_month`: командировка 30.03–02.04 с затратой 02.04 → вся сумма в марте.
  - `test_month_sum_equals_total_tile`: сумма всех серий по всем месяцам == `trips_kpis(...)["current"]["total"]`.
  - `test_month_series_collapse_to_six`: 7 видов затрат → 6 серий: 4 крупнейших вида, «Прочие виды», «Суточные» (последней).
  - `test_structure_shares`: доли в сумме дают 100 % (±0,1), строки по убыванию суммы, «Суточные» — отдельная строка.

- [ ] **Step 2: Тесты страницы** (новый класс `TripsPageTests` по образцу `FinancePageTests`, сегодня — `TODAY` через `_fixed_today()`):
  - `test_trips_page_empty_db`: 200, «Нет данных», `charts["by_month"]["empty"]` и `charts["structure"]["empty"]` — True, «—» у средних и дельт.
  - `test_trips_tiles_kinds`: у плиток «Командировок» и «Человеко-дней» значение без «₽».
  - `test_trips_list_link_filters_period_and_employee`:
    - GET по `trips_list_url` с выбранным сотрудником → 200;
    - `response.context["cl"].result_count` равен числу его командировок периода;
    - у `filter_specs` со `parameter_name == "employee"` `value() == str(pk)`.

- [ ] **Step 3: Прогнать — падают.**

- [ ] **Step 4: Реализовать** расчёты, `_trips_tiles(kpis) -> list[dict]` (`label`, `value`, `delta`, `inverse`, `kind`), графики и разметку.
  - Графики через `chart_spec`:
    - `by_month` — `"bar"`, `stacked=True`, подписи месяцев `month_label`;
    - `structure` — `"bar"`, `horizontal=True`, одна серия «Сумма».
  - Шаблон: плитки, как в `finance.html`; у `kind == "count"` значение `|number`.
  - Под плитками ссылка «Открыть список командировок» (`trips_list_url`).
  - Подпись карточки «Затраты по месяцам»: «Все затраты и суточные командировки относятся к месяцу её начала, как в отчёте по ДС».

- [ ] **Step 5: Прогнать — проходят.**

- [ ] **Step 6: Commit** — `feat(analytics): плитки и затраты по месяцам вкладки «Командировки»`.

---

### Task 5: Направления, «в среднем за год», нормативы и виды работ

**Files:**
- Modify: `ebase_site/analytics/services/trips.py`, `ebase_site/analytics/views_trips.py`, `ebase_site/analytics/templates/analytics/trips.html`
- Test: `ebase_site/analytics/tests/test_trips.py`, `ebase_site/analytics/tests/test_views.py`

**Interfaces:**
- Consumes: `trip_shares`, `direction_of`, `destination_days`, `trips_in_period`, `trips_until` (задача 3).
- Produces:
  - `DAYS_IN_YEAR = 365`, `NO_SERVICE_TYPE_LABEL = "Вид работ не указан"`;
  - `directions(period, employee=None, group="city") -> list[dict]`:
    - строки `{"key", "label", "amount": Decimal, "trips": int, "days": int, "trip_ids": list[str]}`;
    - порядок — по убыванию суммы, затем по подписи;
    - у корзины «Пункты не указаны» `days` = дни командировок;
  - `annual_by_direction(today, employee=None, group="city") -> dict`:
    - `{"start": date | None, "window_days": int, "months": int, "is_estimate": bool, "years": list[int], "rows": [...]}`;
    - строки `{"key", "label", "by_year": list[Decimal], "total": Decimal, "per_year": Decimal, "trips_per_year": Decimal}`;
  - `direction_norms(today, employee=None, group="city") -> dict`:
    - `{"kinds": list[str], "rows": [...]}`;
    - строки `{"key", "label", "trips", "avg_days": Decimal, "avg_trip": Decimal, "per_day": Decimal, "per_day_by_kind": list[Decimal]}`;
  - `by_service_type(period, employee=None) -> list[dict]` — строки `{"id": int | None, "label", "trips", "avg_trip", "avg_days", "per_day"}`;
  - в `views_trips.py`:
    - `TOP_DIRECTIONS = 15`;
    - `_ids_link(ids: list[str]) -> str | None` — `changelist_url(TRIPS, id__in=ids)` при `1 ≤ len(ids) ≤ MAX_LINK_IDS`, иначе `None`;
  - контекст: `charts["directions"]`, `annual`, `norms`, `service_types` (у строк ещё `url`).

- [ ] **Step 1: Тесты расчётов** (`DirectionTests`, `AnnualTests`, `NormsTests`, `ServiceTypeTests`):
  - `test_directions_sum_equals_total`: сумма `amount` всех строк (с «Пункты не указаны») == `trips_kpis(...)["current"]["total"]`.
  - `test_directions_count_trip_once_per_direction`: командировка с двумя пунктами в одном городе → `trips == 1`, `days` = сумма дней пунктов.
  - `test_directions_region_group_merges_cities`: Казань и Набережные Челны (оба «Татарстан») → одна строка «Татарстан».
  - `test_annual_window_estimate`: `TODAY = date(2026, 10, 16)`, единственная командировка начинается `TODAY − 99 дней` и стоит 10 000 →
    - `window_days == 100`;
    - `per_year == Decimal("36500.00")`;
    - `is_estimate` — True;
    - `start` — дата этой командировки;
    - `years == [2026]`.
  - `test_annual_by_year_columns`: командировки в 2025 и 2026 → `by_year` по двум годам, `total` — их сумма.
  - `test_annual_window_ignores_employee_filter`: самая ранняя командировка — другого сотрудника; с фильтром окно всё равно от неё.
  - `test_annual_ignores_future_trips`: командировка с `beg_dt > TODAY` не входит в суммы и не сдвигает `start`.
  - `test_annual_empty`: пустая БД → `start is None`, `rows == []`.
  - `test_norms_per_day_by_kind`: 2 поездки в Казань, всего 5 дней пунктов, гостиница 10 000 →
    - в колонке «Гостиница» `per_day == Decimal("2000.00")`;
    - `avg_days == Decimal("2.5")`;
    - `kinds[-1] == "Суточные"`;
    - сумма `per_day_by_kind` == `per_day` (±0,01 на округление).
  - `test_norms_skip_trips_without_destinations`: корзины «Пункты не указаны» в нормативах нет.
  - `test_service_type_counts_trip_in_each_type`: командировка «ТО» + «ремонт» на 6 000 → у обоих видов `trips == 1`, `avg_trip == 6000`; без вида — строка «Вид работ не указан» с `id is None`.

- [ ] **Step 2: Тесты страницы:**
  - `test_trips_direction_links`:
    - `_ids_link([])` → `None`;
    - `_ids_link` из 90 фиктивных UUID → ссылка с 90 id в `id__in`;
    - из 91 → `None`;
    - ссылка на реальную строку открывает список с её командировками (`cl.result_count`).
  - `test_trips_service_type_link_selects_sidebar_filter`:
    - у фильтра `service_type` в `cl.filter_specs` `lookup_val == str(id)`;
    - ссылка строки без вида содержит `service_type__isnull=True` и открывает 200.
  - `test_trips_group_switch`: `?group=region` → в `annual["rows"]` подписи регионов.

- [ ] **Step 3: Прогнать — падают.**

- [ ] **Step 4: Реализовать.**
  - Формулы:
    - `start` — `Min(beg_dt)` по **всей** базе среди `beg_dt ≤ today` (без фильтра сотрудника);
    - `window_days = (today − start).days + 1`;
    - `months = max(1, round(window_days / 30.4))`;
    - `is_estimate = window_days < 365`;
    - `per_year = total × 365 / window_days` (до копеек, `ROUND_HALF_UP`);
    - `trips_per_year` — до 0,1;
    - год строки — год `beg_dt` командировки.
  - В нормативах:
    - дни направления — Σ `destination_days`;
    - `kinds` — виды затрат по убыванию суммы за историю, затем «Суточные»;
    - строки по убыванию числа поездок.
  - График `directions`: топ-`TOP_DIRECTIONS`, `horizontal=True`, `links=[_ids_link(row["trip_ids"]) …]`, высота через `_horizontal_chart_height`.
  - Подписи карточек:
    - «В среднем за год»: «Вся история, период не учитывается. Оценка по данным с {start} ({months} мес.)», если `is_estimate`, иначе «По данным с {start}»;
    - «Нормативы»: «Вся история. ₽ в день — на день пребывания в пункте»;
    - «По видам работ»: «Командировка с несколькими видами работ считается в каждом».

- [ ] **Step 5: Прогнать — проходят.**

- [ ] **Step 6: Commit** — `feat(analytics): направления командировок, среднее за год и нормативы`.

---

### Task 6: Блок A — сотрудники и подотчёт

**Files:**
- Modify: `ebase_site/analytics/services/trips.py`, `ebase_site/analytics/views_trips.py`, `ebase_site/analytics/templates/analytics/trips.html`, `ebase_site/analytics/static/analytics/css/analytics.css`
- Test: `ebase_site/analytics/tests/test_trips.py`, `ebase_site/analytics/tests/test_views.py`

**Interfaces:**
- Consumes: `trips_in_period`, `trips_until`, `load_trips` (задача 3); `business_trip.xlsx_report.EXCLUDED_EXPENSE_TYPE_NAME`, `employee_fio`, `build_money_report`.
- Produces:
  - `employee_name(user) -> str` — `employee_fio(user) or user.username`;
  - `accountable_spent(trip) -> Decimal` — затраты без вида `EXCLUDED_EXPENSE_TYPE_NAME` + `allowance_amount`;
  - `employee_days(period, employee=None) -> list[dict]`:
    - строки `{"id", "name", "trips", "days", "amount", "per_day"}`;
    - порядок — по убыванию дней, затем по имени;
  - `employee_month_load(period, employee=None) -> dict`:
    - `{"months": list[date], "rows": [{"id", "name", "days": list[int], "total": int}], "max": int}`;
  - `accountable(period, today, employee=None) -> list[dict]`:
    - строки `{"id", "name", "received", "spent", "diff", "balance"}`;
  - в `views_trips.py`: `RECEIPTS = "business_trip_moneyreceipt"`, `_with_load_shades(load) -> dict` (каждой строке `cells = [{"days", "shade"}]`, `shade = round(sqrt(days / max), 2)`, при `max == 0` — 0);
  - контекст: `charts["employee_days"]`, `charts["balance"]`, `load`, `accountable`.

- [ ] **Step 1: Тесты расчётов** (`EmployeeTests`, `AccountableTests`):
  - `test_employee_days`: 2 командировки по 3 дня → `trips == 2`, `days == 6`.
  - `test_month_load_splits_and_clips`:
    - командировка 29.03–02.04 → март 3, апрель 2;
    - при периоде «март» только 3 (обрезка по периоду);
    - в выборку входят командировки, **пересекающие** период, даже если начались раньше.
  - `test_accountable_user_example`: получено 10 000, затраты 6 000, командировка 3 дня (суточные 2 100) → `received == 10000`, `spent == 8100`, `diff == 1900`, `balance == 1900`.
  - `test_accountable_excludes_yandex_trips`: затрата вида «Я.командировки» на 5 000 не входит в `spent`.
  - `test_balance_is_cumulative`: поступление и командировка прошлого года входят в `balance`, но не в `received` / `spent` текущего периода.
  - `test_balance_ignores_future_trips`: командировка с `beg_dt > today` не уменьшает `balance`.
  - `test_accountable_matches_money_report`:
    - для сотрудника и месяца строится `build_money_report(employee, year, month, trips, receipts)` (trips с prefetch, как в `business_trip/admin.py`);
    - сумма данных ячеек D7–D18 = `received`;
    - сумма G7–G44 + D24–D34 = `spent` за этот месяц (`Period` месяца);
    - ячейки с формулами (строки «ИТОГО») не суммировать, брать только числа.

- [ ] **Step 2: Тест страницы** `test_trips_balance_row_links_to_receipts`: ссылка строки подотчёта = `changelist_url(RECEIPTS, employee=pk)`. GET по ней — 200, у `filter_specs` с `parameter_name == "employee"` `value() == str(pk)`.

- [ ] **Step 3: Прогнать — падают.**

- [ ] **Step 4: Реализовать.**
  - Подотчёт:
    - строки — сотрудники с поступлениями или командировками до `today` (с учётом фильтра сотрудника);
    - строки, где все четыре числа нулевые, не выводятся;
    - порядок — по имени.
  - Графики:
    - `employee_days` — `horizontal=True`, `fmt="count"`, серия «Дней»;
    - `balance` — `horizontal=True`, серия «Остаток на сегодня» с `sign_colors=True`.
  - «Кто и когда в отъезде» — HTML-таблица с классами `an-table an-matrix`, ячейки `an-tone-load` со `style="--an-shade: …"`. В CSS: `.an-tone-load { --an-tone: var(--an-c1); --an-tone-max: 40%; }`.
  - Подпись карточки «Подотчёт»: «Остаток = получено − (затраты без „Я.командировки“ + суточные), накопительно на сегодня. Плюс — деньги у сотрудника, минус — компания должна сотруднику». Значения остатка через `money` с типографским минусом.

- [ ] **Step 5: Прогнать — проходят.**

- [ ] **Step 6: Commit** — `feat(analytics): сотрудники в командировках и подотчёт`.

---

### Task 7: Блок B — командировки и деньги

**Files:**
- Modify: `ebase_site/analytics/services/trips.py`, `ebase_site/analytics/views_trips.py`, `ebase_site/analytics/templates/analytics/trips.html`
- Test: `ebase_site/analytics/tests/test_trips.py`, `ebase_site/analytics/tests/test_views.py`

**Interfaces:**
- Consumes: `trips_in_period`, `trip_total`, `trip_shares`, `client_of` (задача 3); фабрики `make_client`, `make_contract`, `make_payment`.
- Produces:
  - `contract_trip_shares(period, employee=None, limit=15) -> list[dict]`:
    - строки `{"id", "number", "client", "contract_amount", "trips_amount", "share_pct": Decimal | None, "profit"}`;
    - контракты — те, у которых есть `BusinessTripContractExpense` от командировок периода;
    - `trips_amount` — **все** доли контракта;
    - `share_pct` — до 0,1, `None` при нулевой сумме контракта;
    - порядок — по убыванию `share_pct` (`None` в конце), затем по убыванию `trips_amount`;
  - `clients_trips_vs_payments(period, employee=None, limit=15) -> list[dict]`:
    - строки `{"key", "name", "trips_amount", "payments": Decimal | None, "per_100": Decimal | None}`;
    - оплаты — `Payment.date` в периоде по контрактам клиента, фильтр сотрудника на них не действует;
    - у корзин без клиента `payments` — `None`;
    - `per_100 = trips × 100 / payments` до копеек;
  - `unallocated_trips(period, employee=None) -> dict`:
    - `{"total": Decimal, "rows": [...], "ids": list[str]}`;
    - строки `{"id", "doc_number", "employee", "beg_dt", "end_dt", "amount", "has_contracts": bool}`;
  - контекст: `contracts` (строки с `url` карточки), `charts["clients"]`, `clients`, `unallocated` (+ `unallocated_url` через `_ids_link`).

- [ ] **Step 1: Тесты расчётов** (`MoneyTests`):
  - `test_contract_share_pct`: контракт на 100 000, его клиент в пунктах командировки на 5 100 (затраты 3 000 + суточные 2 100) → `trips_amount == 5100`, `share_pct == Decimal("5.1")`.
  - `test_contract_trips_amount_includes_all_trips`: вторая командировка прошлого года по тому же контракту входит в `trips_amount`, контракт попал в выборку по командировке периода.
  - `test_clients_per_100`: выезды к клиенту 5 000, оплаты клиента за период 100 000 → `per_100 == Decimal("5.00")`.
  - `test_clients_without_payments`: `payments` равен 0 или `None` → `per_100 is None`.
  - `test_unallocated_trips`:
    - командировка без контрактов → в `rows`, `has_contracts` — False;
    - командировка с контрактом, клиента которого нет в пунктах (долей нет) → в `rows`, `has_contracts` — True;
    - командировка с долями не попадает;
    - `total` — сумма двух первых.

- [ ] **Step 2: Тест страницы** `test_trips_contract_rows_link_to_contract`: `url` строки = `change_url(CONTRACTS, pk)`.

- [ ] **Step 3: Прогнать — падают.**

- [ ] **Step 4: Реализовать.**
  - График `clients` — `horizontal=True`, серия «Затраты на выезды»; рядом таблица с оплатами и «₽ выездов на 100 ₽ оплат».
  - Подписи карточек:
    - «Контракты»: «Контракты, по которым были командировки в периоде; „на командировки“ — за всё время контракта»;
    - «Клиенты»: «Затраты отнесены к клиенту по пунктам командировки; оплаты — по датам оплат периода, фильтр сотрудника на них не действует».

- [ ] **Step 5: Прогнать — проходят.**

- [ ] **Step 6: Commit** — `feat(analytics): командировки в контрактах и по клиентам`.

---

### Task 8: Блок C — экономия и контроль

**Files:**
- Modify: `ebase_site/analytics/services/trips.py`, `ebase_site/analytics/views_trips.py`, `ebase_site/analytics/templates/analytics/trips.html`
- Test: `ebase_site/analytics/tests/test_trips.py`

**Interfaces:**
- Consumes: `trips_in_period`, `trips_until`, `trip_total`, `direction_of`, `destination_days`, `employee_name`.
- Produces:
  - константы: `REPEAT_WINDOW_DAYS = 30`, `MERGE_WINDOW_DAYS = 14`, `EXPENSIVE_RATIO = Decimal("1.5")`, `MIN_TRIPS_FOR_REGION_MEDIAN = 3`;
  - `repeat_visits(period, employee=None) -> list[dict]`:
    - строки `{"department", "client", "city", "previous_trip_id", "previous_beg", "previous_end", "trip_id", "beg", "end", "gap": int, "service_types": str, "amount": Decimal}`;
    - порядок — по убыванию `beg`;
  - `merge_candidates(period, employee=None) -> list[dict]`:
    - строки `{"region": str, "first": dict, "second": dict, "gap": int, "amount": Decimal}`;
    - `first` / `second` — `{"id", "doc_number", "employee", "beg", "end", "amount"}`;
    - порядок — по `gap`, затем по `first["beg"]`;
  - `expensive_trips(period, today, employee=None, limit=10) -> list[dict]`:
    - строки `{"id", "doc_number", "employee", "beg", "end", "region", "per_day", "baseline", "baseline_kind": "region" | "all", "ratio": Decimal}`;
  - контекст: `repeats`, `merges`, `expensive` (у строк ещё `url` / `first_url` / `second_url` на карточки командировок).

- [ ] **Step 1: Тесты** (`ControlTests`):
  - `test_repeat_visit_within_30_days`: пункт того же подразделения закончился 01.03, новый начался 31.03 → строка с `gap == 30`.
  - `test_repeat_visit_31_days_is_not_repeat`: новый начался 01.04 → строк нет.
  - `test_repeat_ignores_same_trip`: два пункта одного подразделения в одной командировке → строк нет.
  - `test_repeat_previous_may_be_before_period`: прошлый выезд в декабре прошлого года, повторный в январе → строка есть.
  - `test_merge_candidates_gap`:
    - две командировки в регион «Татарстан» с разрывом 14 дней → пара;
    - с разрывом 15 → нет;
    - пересекающиеся по датам → нет;
    - разные регионы → нет.
  - `test_expensive_trip_against_region_median`: в регионе 3 поездки по 1 000 ₽/день (без суточных) + проверяемая 2 000 ₽/день → `ratio == Decimal("2.0")`, `baseline_kind == "region"`; поездка 1 400 ₽/день не выводится.
  - `test_expensive_trip_falls_back_to_overall_median`: в регионе меньше 3 поездок → `baseline_kind == "all"`.
  - `test_expensive_per_day_excludes_allowance`: `per_day` = затраты / дни, без суточных.

- [ ] **Step 2: Прогнать — падают.**

- [ ] **Step 3: Реализовать.**
  - `repeat_visits`:
    - предыдущий пункт ищется среди пунктов того же `department_id` **других** командировок любых сотрудников за всю историю;
    - условие: `prev.end_dt < dest.beg_dt` и `(dest.beg_dt − prev.end_dt).days ≤ REPEAT_WINDOW_DAYS`;
    - берётся ближайший;
    - стоимость — `trip_total` повторной командировки.
  - `merge_candidates`:
    - ключи — `direction_of(dest, "region")` без `"none"` / `"no_city"`;
    - пары командировок периода с `a.end_dt < b.beg_dt`, разрыв `1…MERGE_WINDOW_DAYS` и общим ключом;
    - `region` — подписи общих ключей через запятую.
  - `expensive_trips`:
    - основной регион — пункт с наибольшими `destination_days` (при равенстве — более ранний);
    - медианы (`statistics.median`) по истории `trips_until(today)` **без** фильтра сотрудника;
    - региональная медиана — при ≥ `MIN_TRIPS_FOR_REGION_MEDIAN` поездках, иначе общая;
    - кандидаты — командировки периода с `per_day > 0` и `baseline > 0`;
    - `ratio` до 0,1, выводятся `ratio ≥ EXPENSIVE_RATIO`, по убыванию, `limit`.
  - Подписи карточек:
    - «Повторные выезды»: «То же подразделение через {REPEAT_WINDOW_DAYS} дней или раньше: возможно, проблему не решили с первого раза»;
    - «Можно было объединить»: «Командировки в один регион с разрывом до {MERGE_WINDOW_DAYS} дней»;
    - «Необычно дорогие»: «₽ в день без суточных против медианы региона за всю историю (при < 3 поездках — общей медианы); показаны от 1,5×».

- [ ] **Step 4: Прогнать — проходят.**

- [ ] **Step 5: Commit** — `feat(analytics): повторные выезды, объединяемые и дорогие командировки`.

---

### Task 9: Страница целиком — порядок секций, пустые состояния, неполные справочники

**Files:**
- Modify: `ebase_site/analytics/templates/analytics/trips.html`, `ebase_site/analytics/views_trips.py`
- Test: `ebase_site/analytics/tests/test_views.py`

**Interfaces:**
- Consumes: всё из задач 4–8. `TRIPS_CHART_KEYS = {"by_month", "structure", "directions", "employee_days", "balance", "clients"}` в тестах.

- [ ] **Step 1: Тесты:**
  - `test_trips_page_empty_db`:
    - 200;
    - `set(charts) == TRIPS_CHART_KEYS`, все `empty`;
    - таблицы показывают «Нет данных»;
    - нет подписи «Оценка по данным с»;
    - нет «None» в HTML.
  - `test_trips_page_with_data`: фикстура из 3 сотрудников, 6 командировок в двух регионах, поступлений и контракта; все секции заполнены, ключевые числа в HTML (через `money` / `number`).
  - `test_trips_page_with_incomplete_directory`: подразделение без города, город без региона, пункт без клиента, командировка без пунктов → 200, в HTML «Город не указан», «(регион не указан)», «Пункты не указаны».
  - `test_trips_page_bad_params`: `?employee=bad&group=foo&preset=zzz&date_from=31.31.2026` → 200, `context["employee"] is None`, `context["group"] == "city"`.
  - `test_trips_employee_filter_applies`: с `?employee=<pk>` в плитках только его командировки.

- [ ] **Step 2: Прогнать.** Ожидается, что падают только новые проверки, если секции ещё не доведены.

- [ ] **Step 3: Довести шаблон.** Секции в порядке спеки, у каждой заголовок `h2`:
  1. «Обзор» — плитки, по месяцам, структура;
  2. «Направления» — за период, «В среднем за год», «Нормативы», «По видам работ»;
  3. «Сотрудники» — дни, кто и когда в отъезде, подотчёт;
  4. «Командировки и деньги»;
  5. «Экономия и контроль».

  Широкие таблицы — в `an-table-wrap` (горизонтальная прокрутка на телефоне), карточки — `an-card` / `an-card--wide`. Пустые таблицы — `<p class="an-chart-empty">Нет данных…</p>`, как в «Платёжной дисциплине».

- [ ] **Step 4: Прогнать — проходят.**

- [ ] **Step 5: Commit** — `feat(analytics): страница вкладки «Командировки»`.

---

### Task 10: Документация, black, полный прогон, браузер

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: `AGENTS.md`**, раздел «Аналитика»:
  - права: пять кодов, `0004` переименовала `view_warehouse_trips` → `view_warehouse` и выдала `view_trips` группе «Аналитика»;
  - вкладка «Командировки», структура (`services/trips.py`, `views_trips.py`);
  - правила расчёта:
    - атрибуция к пунктам и деление по дням;
    - месяц — по `beg_dt`;
    - окно «в среднем за год»;
    - подотчёт и исключение «Я.командировки»;
    - пороги C;
  - в таблице приложений строку `analytics` («этап 1 — одна вкладка «Финансы»») дополнить вкладкой «Командировки»;
  - в «Наборы тестов» добавить `test_trips`;
  - в «Текущее состояние тестов» — новое общее число тестов из прогона Step 3.
- [ ] **Step 2: Black** по всем новым и изменённым `.py` файлам: `black --check` по ним — без изменений.
- [ ] **Step 3: Полный прогон** — `python manage.py test --settings=ebase_site.test_settings`: `FAILED (failures=2, errors=3)`, падают те же пять тестов.
- [ ] **Step 4: Браузер.**
  - Скриптом в scratchpad (не в репозитории) поднять тестовую БД с фикстурой из `test_trips_page_with_data` и сохранить HTML страницы, отрендеренной test client'ом, со статикой.
  - Открыть в headless Chromium и снять скриншоты:
    - светлая и тёмная темы;
    - ширина 1280 и 390 px.
  - Проверить:
    - графики рисуются;
    - таблицы не ломают ширину страницы;
    - заливка «сотрудник × месяц» видна в обеих темах.
  - В рабочую БД не ходить, `.env` не читать.
- [ ] **Step 5: Commit** — `docs(analytics): вкладка «Командировки» в AGENTS.md`.
