# Вкладка «Оборудование» (Аналитика) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Третья вкладка раздела «Аналитика» — «Оборудование»: парк у клиентов, ремонты и ТО, надёжность моделей, подменный фонд. Плюс флаг «Плановое ТО» у вида работ.

**Architecture:** Вкладка устроена по образцу «Командировок».
- `EquipmentSet.load()` (`analytics/services/equipment.py`) один раз на запрос загружает приборы с монтажами, ремонты и подменный фонд.
- Чистые функции-виджеты получают набор параметром `source` и возвращают dict или list.
- `views_equipment.py` добавляет ссылки в админку и спецификации графиков (`chart_spec`).
- Шаблон разбит на четыре include по блокам А–Г.
- ТО и поломки различаются по новому полю `ServiceType.is_planned_maintenance`.

**Tech Stack:** Python 3.11, Django 4.2.16, Chart.js 4.5.1 через существующие `charts.py` и `charts.js`, тесты Django TestCase на SQLite (`ebase_site.test_settings`).

**Spec:** `docs/superpowers/specs/2026-10-18-analytics-equipment-design.md`. Файл локальный: каталог specs в `.gitignore`. Исполнитель читает дизайн и план вместе.

## Global Constraints

- Новых зависимостей нет. Графики строятся только через `analytics.charts.chart_spec`. «Хронология выдач» и тепловая карта делаются на HTML/CSS, `charts.js` не меняется.
- Весь текст интерфейса, комментарии и docstring пишутся по-русски. Подписи берутся дословно из этого плана.
- Ссылка `?id__in=` содержит не больше `MAX_LINK_IDS = 90` id (`analytics/views.py`). Если id больше, ссылка ведёт на фильтр-надмножество или её нет.
- Данные вкладки загружаются один раз на запрос (`EquipmentSet.load()`). Страница делает не больше 30 запросов, и это число не растёт с объёмом данных.
- Арифметика дат и медианы считаются в Python (`statistics.median`), не функциями БД.
- В расчётах не вызывать `str(Department)` (падает без города), `str(ReplacementEquipment)` и `str(Service)` (делают лишние запросы). Подписи строятся функциями `*_label` из Задачи 3.
- Модели `ebase`, сигналы и списки админки не меняются. Исключение — `ServiceTypeAdmin`.
- Цвета серий:
  - «Поставлено нами» — `"c1"`;
  - «Поставлено не нами» — `"c2"`;
  - «Прибор не указан» — `"c4"`;
  - накопительная линия — `"c3"`;
  - «Прошлый год» — `"c5"`.
- Тесты запускаются из `ebase_site/` после `source ../.venv/bin/activate` командой `python manage.py test <label> --settings=ebase_site.test_settings`. Исходное состояние: 379 тестов, `FAILED (failures=2, errors=3)`. Новых падений быть не должно.
- `black` применяется только к изменённым файлам. В рабочую БД не ходить, `.env` не читать.
- Работа идёт в ветке `feature/analytics-equipment`, в main не сливается.

## Review Focus

1. **Ремонт без прибора** (`Service.equipment_accounting=None`, поле nullable). Страница не падает. Без фильтров такой ремонт входит в общие счётчики, при любом фильтре не входит. В виджеты по приборам и моделям не попадает. Тест в Задаче 3.
2. **Неполные справочники**: модель без названия, без направления и производителя; подразделение без города и без клиента; город без региона. Подписи без «None», страница отвечает 200. Тест в Задаче 4.
3. **Плохие даты**: `end_dt` раньше `beg_dt` даёт длительность 1 день, а не отрицательную. Ремонт с `beg_dt` в будущем не считается «в работе сейчас». Тесты в Задачах 3 и 5.
4. **Период целиком в будущем** (свой период 2027 года): частоты в год равны None или списки пустые, `ZeroDivisionError` нет, хронология пустая. Тесты в Задачах 6 и 7.
5. **Старые выдачи без отметки «Вернули в офис»** (поле появилось позже, по умолчанию False). Положение прибора определяет только последняя выдача. Ранние выдачи заканчиваются по `end_dt` или днём перед следующей выдачей и не тянутся до сегодня. Тест в Задаче 7.

---

### Task 1: Флаг «Плановое ТО» у вида работ

**Files:**
- Modify: `ebase_site/directory/models.py` (класс `ServiceType`)
- Create: `ebase_site/directory/migrations/0004_servicetype_is_planned_maintenance.py`
- Modify: `ebase_site/directory/admin.py` (`ServiceTypeAdmin`)
- Test: `ebase_site/directory/tests.py` (сейчас пустой)

**Interfaces:**
- Produces:
  - `ServiceType.is_planned_maintenance: bool` (default False);
  - `directory.admin.PLANNED_MAINTENANCE_HELP: str` — текст пояснения, в модели он же в `help_text`;
  - функция миграции `mark_planned_maintenance(apps, schema_editor)`;
  - константа миграции `PLANNED_MAINTENANCE_NAMES = ("Тех. обслуживание",)`.

- [ ] **Step 1: Исходное состояние тестов**

Run: `python manage.py test --settings=ebase_site.test_settings 2>&1 | tail -3`
Expected: `Ran 379 tests`, `FAILED (failures=2, errors=3)`.

- [ ] **Step 2: Падающие тесты в `directory/tests.py`**

```python
class PlannedMaintenanceFlagTests(TestCase):
    def test_default_is_false(self):
        self.assertFalse(ServiceType.objects.create(name="ремонт").is_planned_maintenance)

    def test_migration_marks_maintenance_only(self):
        to = ServiceType.objects.create(name="Тех. обслуживание")
        repair = ServiceType.objects.create(name="ремонт")
        migration = importlib.import_module(
            "directory.migrations.0004_servicetype_is_planned_maintenance"
        )
        migration.mark_planned_maintenance(django_apps, None)
        migration.mark_planned_maintenance(django_apps, None)  # идемпотентность
        to.refresh_from_db(); repair.refresh_from_db()
        self.assertTrue(to.is_planned_maintenance)
        self.assertFalse(repair.is_planned_maintenance)

    def test_migration_without_maintenance_type_does_nothing(self): ...
        # только «ремонт» в базе -> ни одного вида с флагом

class ServiceTypeAdminTests(TestCase):
    # setUp: superuser + force_login
    def test_change_form_explains_flag(self):
        # GET admin:directory_servicetype_change -> 200,
        # assertContains("Плановое ТО"), assertContains("не входят в надёжность моделей")
    def test_changelist_saves_flag_inline(self):
        # POST в admin:directory_servicetype_changelist:
        # {"form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-0-id": pk,
        #  "form-0-is_planned_maintenance": "on", "_save": "Сохранить"} -> 302, флаг True
```

- [ ] **Step 3: Запустить и убедиться, что тесты падают**

Run: `python manage.py test directory --settings=ebase_site.test_settings`
Expected: ERROR/FAIL, у модели нет поля `is_planned_maintenance`, модуля миграции нет.

- [ ] **Step 4: Реализация**

Поле:
```python
is_planned_maintenance = models.BooleanField(
    default=False, verbose_name="Плановое ТО",
    db_comment="True — вид работ считается плановым ТО, а не поломкой (раздел «Аналитика»)",
    help_text=PLANNED_MAINTENANCE_HELP,
)
```

Текст `PLANNED_MAINTENANCE_HELP` дословно: «Отметьте, если это плановое техническое обслуживание. В разделе «Аналитика» → «Оборудование» такие работы считаются ТО (плитка «ТО проведено», график ТО по месяцам), а не поломками: они не входят в надёжность моделей и повторные ремонты. Виды работ без отметки считаются ремонтами.»

Константа объявляется в `directory/models.py`, `admin.py` её импортирует.

Миграция пишется вручную:
- `AddField`, параметры поля те же;
- `RunPython(mark_planned_maintenance, migrations.RunPython.noop)`; функция делает `filter(name__in=PLANNED_MAINTENANCE_NAMES).update(is_planned_maintenance=True)`;
- зависимость `("directory", "0003_supplier_manufacturer")`.

Админка:
- `list_display = ("id", "name", "is_planned_maintenance")`;
- `list_editable = ("is_planned_maintenance",)`;
- в fieldset добавляется поле `"is_planned_maintenance"` и `"description": PLANNED_MAINTENANCE_HELP`.

- [ ] **Step 5: Проверить, что состояние миграций совпадает с моделями**

Создать в scratchpad файл `migcheck_settings.py`:
```python
from ebase_site.test_settings import *  # noqa
MIGRATION_MODULES = {}
```

Run: `PYTHONPATH=<scratchpad> python manage.py makemigrations directory --check --dry-run --settings=migcheck_settings`
Expected: `No changes detected in app 'directory'`.

- [ ] **Step 6: Тесты зелёные**

Run: `python manage.py test directory --settings=ebase_site.test_settings`
Expected: OK.

- [ ] **Step 7: Commit**

`black` по изменённым файлам, затем
`git commit -m "feat(directory): флаг «Плановое ТО» у вида работ"`.

---

### Task 2: Право, вкладка, фильтры и пустая страница

**Files:**
- Modify: `ebase_site/analytics/models.py`, `navigation.py`, `urls.py`, `filters.py`
- Create: `ebase_site/analytics/migrations/0005_equipment_tab.py`, `views_equipment.py`, `templates/analytics/equipment.html`
- Test: `analytics/tests/test_migrations.py`, `test_filters.py`, `test_views.py`

**Interfaces:**
- Produces:
  - право `analytics.view_equipment` («Аналитика: Оборудование»);
  - `Tab("equipment", "Оборудование", "analytics.view_equipment", "analytics:equipment")` третьим в `TABS`;
  - URL `/admin/analytics/equipment/`;
  - `analytics.filters`:
    - `SUPPLY_CHOICES = [("all", "Все"), ("ours", "Поставлено нами"), ("others", "Поставлено не нами")]`, `DEFAULT_SUPPLY = "all"`;
    - `@dataclass(frozen=True) class EquipmentFilters: direction: MedDirection | None = None; manufacturer: Manufacturer | None = None; supply: str = "all"` со свойством `is_empty -> bool` (все значения по умолчанию);
    - `EquipmentFilterForm(PeriodForm)` с полями `direction`, `manufacturer`, `supply` и методом `get_filters() -> EquipmentFilters`;
  - `views_equipment.EquipmentView(AnalyticsTabView)` с `tab_key = "equipment"`, `form_class = EquipmentFilterForm`, `template_name = "analytics/equipment.html"`. Контекст: `filters`, `charts` (пока `{}`).
- Миграция: функции `add_equipment_tab` и `remove_equipment_tab`, константа `EQUIPMENT = ("view_equipment", "Аналитика: Оборудование")`.

- [ ] **Step 1: Падающие тесты**

Правки `test_migrations.py`:
- в `test_permissions_exist` ожидаются `{"view_finance", "view_trips", "view_equipment"}`;
- `_permissions_before_0004()` удаляет `view_trips` и `view_equipment`. В тестах права создаются по текущей модели, поэтому `view_equipment` до 0005 не было;
- новый класс `EquipmentTabMigrationTests`, в `setUp` удаляется `view_equipment`:

```python
def test_creates_permission_and_grants_group(self):
    group = Group.objects.create(name="Аналитика")
    self.migration.add_equipment_tab(django_apps, None)
    perm = Permission.objects.get(content_type__app_label="analytics", codename="view_equipment")
    self.assertEqual(perm.name, "Аналитика: Оборудование")
    self.assertTrue(group.permissions.filter(pk=perm.pk).exists())
def test_without_group_creates_permission_only(self): ...
def test_is_idempotent(self): ...  # два прохода -> одно право, группа с одним правом
def test_reverse_removes_permission(self): ...  # остаются view_finance, view_trips
```

`test_filters.py` — класс `EquipmentFilterFormTests`:
- `test_equipment_form_defaults`: `get_filters() == EquipmentFilters()`, `is_empty` истинно;
- `test_equipment_form_values`: направление, производитель и `supply="ours"` возвращаются;
- `test_equipment_form_garbage_falls_back`: `{"direction": "abc", "manufacturer": "not-a-uuid", "supply": "foo"}` даёт `EquipmentFilters()`;
- `test_equipment_form_lists_only_used_directories`: направление и производитель без моделей в списке выбора отсутствуют.

`test_views.py`, класс `AnalyticsViewsTests`, хелпер `_equipment_staff()` по образцу `_trips_staff()`:
- `test_superuser_sees_equipment_tab`: ответ 200, `assertContains("Оборудование")`;
- `test_staff_without_equipment_permission_gets_403`: пользователь `finance_staff`;
- `test_index_redirects_to_equipment_when_only_equipment_permitted`: путь `/admin/analytics/equipment/`;
- `test_sidebar_lists_equipment_tab_with_permission`: пункт «Оборудование» есть в `available_apps` и в `app_list` главной страницы;
- `test_equipment_tab_follows_trips_in_tabs`: `[tab.key for tab in TABS][:3] == ["finance", "trips", "equipment"]`.

- [ ] **Step 2: Запустить, тесты падают**

Run: `python manage.py test analytics --settings=ebase_site.test_settings`
Expected: новые тесты FAIL или ERROR (нет права, URL и формы).

- [ ] **Step 3: Реализация**

- Право добавляется в `Meta.permissions` модели `AnalyticsAccess`.
- Миграция `0005_equipment_tab` копирует устройство `0004_trips_tab`: `AlterModelOptions` с тремя правами и идемпотентный `RunPython`. Удаления прав-заготовок в ней нет.
- `EquipmentFilterForm`:
  - `direction = ModelChoiceField(MedDirection.objects.filter(equipment_med_equipment__isnull=False).distinct().order_by("name"), required=False, label="Направление", empty_label="Все направления")`;
  - `manufacturer` — то же по `Manufacturer` и `equipment_manufacturer`, `label="Производитель"`, `empty_label="Все производители"`;
  - `supply = ChoiceField(choices=SUPPLY_CHOICES, required=False, label="Поставка")`; мусор в нём даёт `"all"`.
- `EquipmentFilters` объявляется в `filters.py`, а не в сервисе: иначе получится циклический импорт.
- `equipment.html` наследует `analytics/base.html` и выводит четыре заголовка `an-section-title`: «Парк оборудования», «Ремонты», «Надёжность моделей», «Подменный фонд». Каждый блок подключается через `{% include "analytics/equipment/<блок>.html" %}`. Include-файлы (`park.html`, `repairs.html`, `reliability.html`, `fund.html`) пока пустые.

- [ ] **Step 4: Проверка миграций и тестов**

Run: `PYTHONPATH=<scratchpad> python manage.py makemigrations analytics --check --dry-run --settings=migcheck_settings`. Expected: `No changes detected`.

Run: `python manage.py test analytics directory --settings=ebase_site.test_settings`. Expected: OK.

- [ ] **Step 5: Commit**

`git commit -m "feat(analytics): вкладка «Оборудование» — право, фильтры, каркас страницы"`

---

### Task 3: Набор данных и базовые правила (`services/equipment.py`)

**Files:**
- Create: `ebase_site/analytics/services/equipment.py`
- Modify: `ebase_site/analytics/tests/factories.py`
- Create: `ebase_site/analytics/tests/test_equipment.py`

**Interfaces:**
- Consumes: `EquipmentFilters` (Задача 2), `Period` (`analytics/filters.py`).
- Produces. Фабрики в `factories.py`:
  - `make_service_type(name, planned=False) -> ServiceType` (через `get_or_create`, флаг обновляется);
  - `make_equipment(full_name="Анализатор", short_name=None, direction="Гематология", manufacturer="Mindray") -> Equipment`; `direction=None` / `manufacturer=None` создают модель без них;
  - `make_device(equipment, serial, *, ours=True, our_service=False, status=None) -> EquipmentAccounting`; `status` — имя `EquipmentStatus`;
  - `make_install(device, department, install_dt=None, *, active=True, engineer=None) -> EquipmentAccDepartment`; `engineer` — имя `Engineer` (`get_or_create`, без пользователя);
  - `make_service(device, beg, end=None, *, service_type=None, engineer=None, replacement=None, returned=False) -> Service`; пользователь `test_service_user` создаётся через `get_or_create`;
  - `make_replacement(equipment, serial, *, state="working") -> ReplacementEquipment`.
- Produces. Сервис:
  - `STATE_AT_CLIENT = "client"`, `STATE_REMOVED = "removed"`, `STATE_NO_INSTALL = "none"`;
  - `WORK_PLANNED = "planned"`, `WORK_BREAKDOWN = "breakdown"`, `WORK_UNKNOWN = "unknown"`;
  - подписи: `NO_MODEL_NAME_LABEL = "Модель без названия"`, `NO_DIRECTION_LABEL = "Направление не указано"`, `NO_MANUFACTURER_LABEL = "Производитель не указан"`, `NO_STATUS_LABEL = "Статус не указан"`, `NO_ENGINEER_LABEL = "Инженер не указан"`, `NO_SERVICE_TYPE_LABEL = "Вид работ не указан"`, `OTHER_SERVICE_TYPES_LABEL = "Прочие виды работ"`, `NO_CLIENT_LABEL = "Клиент не указан"`, `NO_CITY_LABEL = "Город не указан"`, `NO_REGION_SUFFIX = " (регион не указан)"`, `NO_DEVICE_LABEL = "Прибор не указан"`.
  - функции:
    - `active_install(device) -> EquipmentAccDepartment | None` — активный монтаж с самой поздней `install_dt` (монтаж без даты считается раньше любого датированного, при равенстве берётся поздний `create_dt`);
    - `install_state(device) -> str`;
    - `work_kind(service) -> str`;
    - `repair_days(service) -> int | None` — `max((end_dt - beg_dt).days + 1, 1)`, None без `end_dt`;
    - `model_label(equipment) -> str` — `full_name`, иначе `short_name`, иначе `NO_MODEL_NAME_LABEL`;
    - `device_label(device) -> str` — `f"{model_label} [{serial_number.upper()}]"`;
    - `department_label(department) -> str` — «Название (Город)» или «Название»;
    - `client_label(department) -> str`;
    - `region_label(department) -> str` — регион, иначе «<город> (регион не указан)», без города — `NO_CITY_LABEL`;
    - `replacement_label(replacement) -> str` — `f"{model_label} [{serial_number}]"`.
  - `class EquipmentSet`:
    - атрибуты `devices`, `services`, `replacements` (списки) и `device_by_id: dict`;
    - `@classmethod load() -> EquipmentSet`;
    - `devices_of(filters) -> list[EquipmentAccounting]`;
    - `services_of(filters) -> list[Service]`;
    - `services_in(period, filters) -> list[Service]` — `beg_dt` в периоде, границы включаются;
    - `replacements_of(filters) -> list[ReplacementEquipment]` — только направление и производитель модели подменного;
    - `device_of(service) -> EquipmentAccounting | None`;
    - `issues_of(replacement) -> list[Service]` — ремонты с этим подменным по `(beg_dt, create_dt)` по возрастанию.
  - `_source(source) -> EquipmentSet` — переданный набор или свежая загрузка.

- [ ] **Step 1: Падающие тесты в `test_equipment.py`, класс `EquipmentRulesTests`**

```python
def test_install_states(self):
    # dev_a: активный монтаж -> STATE_AT_CLIENT; dev_b: только неактивный -> STATE_REMOVED;
    # dev_c: без монтажей -> STATE_NO_INSTALL
def test_active_install_prefers_latest_date(self):
    # два активных: 2020-01-01 и 2023-05-01 (+ активный без даты) -> install_dt == 2023-05-01
def test_work_kind(self):
    # «Тех. обслуживание» planned=True -> WORK_PLANNED; «ремонт» -> WORK_BREAKDOWN; без вида -> WORK_UNKNOWN
def test_repair_days_inclusive_and_never_negative(self):
    # beg=end -> 1; 2026-03-01..2026-03-10 -> 10; end раньше beg -> 1; без end -> None
def test_labels_without_names(self):
    # модель без full_name и short_name -> "Модель без названия [SN1]";
    # подразделение без города: department_label == "Больница", region_label == "Город не указан";
    # город без региона -> "Казань (регион не указан)"; без клиента -> "Клиент не указан"
def test_filters_on_devices_services_and_fund(self):
    # direction / manufacturer / supply="ours" | "others" сужают devices_of и services_of;
    # supply не меняет replacements_of, direction меняет
def test_service_without_device(self):
    # make_service(None, ...) входит в services_of(EquipmentFilters()), не входит при supply="ours";
    # device_of(service) is None
def test_load_makes_constant_number_of_queries(self):
    # assertNumQueries(4): приборы, монтажи (prefetch), ремонты, подменные
```

- [ ] **Step 2: Запустить, тесты падают**

Run: `python manage.py test analytics.tests.test_equipment --settings=ebase_site.test_settings`
Expected: ImportError, модуля `analytics.services.equipment` нет.

- [ ] **Step 3: Реализация `services/equipment.py`**

Шапка модуля — docstring про правила из дизайна.

`load()` делает четыре запроса (первый пункт — два запроса: приборы и prefetch монтажей):
1. `EquipmentAccounting.objects.select_related("equipment__med_direction", "equipment__manufacturer", "equipment_status")` с `Prefetch("equipment_acc_department_equipment_accounting", queryset=EquipmentAccDepartment.objects.select_related("department__city", "department__client", "engineer"), to_attr="installs")`.
2. `Service.objects.select_related("service_type", "engineer", "replacement_equipment__equipment")`. Прибор ремонта берётся из `device_by_id`, а не через `select_related`.
3. `ReplacementEquipment.objects.select_related("equipment__med_direction", "equipment__manufacturer")`.

Фильтр по модели сравнивает `equipment.med_direction_id` и `equipment.manufacturer_id` с pk выбранных значений. `supply` сравнивается с `device.is_our_supply`.

- [ ] **Step 4: Тесты зелёные**

Run: тот же. Expected: OK.

- [ ] **Step 5: Commit**

`git commit -m "feat(analytics): набор данных вкладки «Оборудование» и базовые правила"`

---

### Task 4: Блок А «Парк оборудования»

**Files:**
- Modify: `analytics/services/equipment.py`, `analytics/views_equipment.py`
- Create: `analytics/templates/analytics/equipment/park.html`
- Test: `analytics/tests/test_equipment.py`, `analytics/tests/test_views.py`

**Interfaces:**
- Consumes: Задача 3.
- Produces. Сервис:
  - константы:
    - `AGE_BUCKETS = (("<1", 0, 1), ("1–3", 1, 3), ("3–5", 3, 5), ("5–10", 5, 10), ("10+ лет", 10, None))` — возраст в годах `(today − install_dt).days / 365.25`, корзина `lo ≤ age < hi`, отрицательный возраст попадает в «<1»;
    - `AGE_UNKNOWN_LABEL = "дата неизвестна"`;
    - `TOP_MANUFACTURERS = 10`, `OTHER_MANUFACTURERS_LABEL = "Прочие производители"`, `TOP_CLIENTS = 15`, `OPEN_REPAIR_DAYS = 365`;
  - `park_kpis(today, filters, source=None) -> dict`:
    - ключи `total`, `ours`, `others`, `at_client`, `no_install`, `removed`, `clients`, `our_service` (int) и `avg_age` (`Decimal`, шаг 0,1, или None);
    - `clients` — число разных `department.client_id` активных монтажей, None не считается;
  - `installs_by_year(filters, source=None) -> dict`:
    - ключи `years: list[int]` (без пропусков от min до max), `ours`, `others`, `cumulative: list[int]`, `no_date: int`;
    - считаются все монтажи, активные и снятые, отфильтрованных приборов;
  - `park_structure(filters, source=None) -> dict`:
    - ключи `directions`, `manufacturers`, `statuses`, `regions`; строка — `{"label", "key", "ours", "others", "total", "ids"}`;
    - считаются приборы у клиентов; `key` — pk направления или производителя, имя статуса или None;
    - сортировка по `total` по убыванию, затем по `label`;
    - у производителей первые 10 строк, остаток сливается в строку `OTHER_MANUFACTURERS_LABEL` с `key=None`;
  - `park_age(today, filters, source=None) -> list[dict]` — строки `{"label", "count", "ids"}` по порядку корзин, «дата неизвестна» последней;
  - `top_clients(filters, source=None) -> list[dict]`:
    - строки `{"name", "devices", "ours", "models", "ids"}`, не больше 15;
    - сортировка `devices` по убыванию, затем `name`;
  - `data_gaps(today, filters, source=None) -> list[dict]`:
    - строки `{"key", "label", "count", "ids", "target"}` в порядке ключей: `no_install` «Нет данных о монтаже», `no_install_date` «У клиента, без даты монтажа», `no_status` «Без статуса», `no_engineer` «Монтаж без инженера», `no_service_type` «Ремонты без вида работ», `old_open` «Ремонты без даты окончания старше 365 дней»;
    - `target` — `"accounting"` у первых четырёх, `"service"` у двух последних.
- Produces. View:
  - константы `ACCOUNTING = "ebase_equipmentaccounting"`, `SERVICES = "ebase_service"`, `REPLACEMENTS = "ebase_replacementequipment"`;
  - `ids_link(admin_name, ids, **fallback) -> str | None`:
    - пустые `ids` — None;
    - ≤ 90 id — `?id__in=`;
    - больше — `changelist_url(admin_name, **fallback)`, если `fallback` задан, иначе None;
  - `_park_context(source, filters, today) -> dict` — ключи `park`, `park_tiles`, `structure`, `top_clients`, `data_gaps` и `charts` с ключами `installs_by_year`, `structure_directions`, `structure_manufacturers`, `structure_statuses`, `structure_regions`, `park_age`.
  - запасные ссылки:
    - для направлений — `med_direction=<pk>`;
    - для статусов — `equipment_status__name=<имя>`, у пустого статуса `equipment_status__name__isnull="True"`;
    - `no_install` и `no_install_date` — `install_dt="nulldt"`;
    - `no_status` — `equipment_status__name__isnull="True"`;
    - `no_service_type` — `service_type__isnull="True"`;
    - `old_open` — `end_dt__isnull="True"` и `beg_dt__lt=(today − 365 дн.).isoformat()`.
  - у каждой строки `data_gaps` есть ключи `url` и `superset`. `superset=True`, когда ссылка ведёт на надмножество, и шаблон тогда пишет «(список шире: …)».

- [ ] **Step 1: Падающие тесты `ParkTests` (`test_equipment.py`)**

Фикстура: 4 прибора.
- A — у клиента с 2020-03-01, нами;
- B — у клиента без даты, не нами;
- C — монтаж снят;
- D — без монтажа.

`today = date(2026, 10, 16)`.

```python
def test_park_kpis(self):
    # total 4, ours 3, others 1, at_client 2, no_install 1, removed 1, clients 1,
    # avg_age == Decimal("6.6") (только A), our_service — по флагу is_our_service
def test_installs_by_year_fills_gaps_and_accumulates(self):
    # монтажи 2020 и 2022 -> years [2020, 2021, 2022], cumulative [1, 1, 2], no_date == 1
def test_park_structure_splits_supply_and_groups_rest(self):
    # 11 производителей -> 10 строк + "Прочие производители"; ours/others по is_our_supply;
    # region "Казань (регион не указан)" для города без региона
def test_park_age_buckets(self):
    # возраст 0.5, 2, 4, 7, 12 лет и без даты -> по одной в каждой корзине, порядок AGE_BUCKETS + "дата неизвестна"
def test_top_clients(self): ...   # devices / ours / models, сортировка
def test_data_gaps(self): ...     # count каждого ключа; old_open — beg_dt раньше today − 365, без end_dt
```

Падающие тесты `EquipmentPageTests` (`test_views.py`, новый класс по образцу `TripsPageTests`, `_get()` под `_fixed_today()`):

```python
def test_equipment_page_empty_db(self):
    # 200; все spec в charts пустые (spec["empty"]); assertContains("Нет данных"); assertNotContains("None")
def test_equipment_page_bad_params(self):
    # {"preset": "foo", "direction": "x", "manufacturer": "y", "supply": "z", "date_from": "abc"} -> 200
def test_equipment_page_with_incomplete_directory(self):
    # модель без названия/направления/производителя, подразделение без города и клиента -> 200, нет "None"
def test_park_structure_link_opens_accounting_list(self):
    # spec["links"][0] у structure_directions -> changelist 200, result_count == число приборов направления
def test_park_large_direction_links_to_sidebar_filter(self):
    # 91 прибор одного направления (bulk_create) -> ссылка med_direction=<pk>;
    # filter_spec "med_direction" в changelist имеет value() == str(pk)
def test_data_gap_link_uses_install_dt_filter(self):
    # >90 приборов без монтажа -> url содержит install_dt=nulldt, superset True,
    # filter_spec "install_dt".value() == "nulldt"
def test_ids_link_limits(self):
    # ids_link(ACCOUNTING, []) is None; 90 id -> id__in из 90; 91 без fallback -> None
def test_equipment_page_query_count_is_small_and_constant(self):
    # как test_trips_page_query_count_is_small_and_constant: before <= 30, before == after
    # после добавления 3 приборов с монтажами, ремонтами и подменным
```

- [ ] **Step 2: Запустить, тесты падают**

Run: `python manage.py test analytics.tests.test_equipment analytics.tests.test_views --settings=ebase_site.test_settings`
Expected: FAIL или ERROR в новых тестах.

- [ ] **Step 3: Сервисные функции блока А**

- [ ] **Step 4: View и шаблон `equipment/park.html`**

Плитки без дельты, разметка `an-tile`, `kind` у плиток `count` или `years`:
- «Учтено приборов», подпись «нами N · не нами M»;
- «У клиентов»;
- «Нет данных о монтаже», подпись «монтаж снят: K»;
- «Клиентов с приборами»;
- «Средний возраст парка», значение `{{ value|number }} лет`;
- «С отметкой «Проведено ТО»».

Под плитками подпись: «На сегодня, период не учитывается».

Графики:
- `installs_by_year`: `chart_spec("bar", years, [нами c1, не нами c2, {"label": "Всего установлено", "kind": "line", "axis": "y2", "fmt": "count", "color": "c3"}], fmt="count", stacked=True)`;
- четыре графика структуры: `horizontal=True, stacked=True, fmt="count"`, ссылки, высота `_horizontal_chart_height`;
- `park_age`: одна серия «Приборов» цвета `c1`.

Карточки:
- «Установки по годам», «Возраст парка», «Клиенты с наибольшим парком» (таблица, имя клиента — ссылка);
- «Полнота данных» во всю ширину: таблица «показатель · число · ссылка»;
- «Структура парка»: четыре графика внутри `an-split`, подзаголовки `h3.an-subtitle`.

`get_context_data` вызывает `EquipmentSet.load()` один раз и сливает `charts` блоков.

- [ ] **Step 5: Тесты зелёные**

Run: тот же. Expected: OK.

- [ ] **Step 6: Commit**

`git commit -m "feat(analytics): «Оборудование» — блок «Парк оборудования»"`

---

### Task 5: Блок Б «Ремонты»

**Files:**
- Modify: `analytics/services/equipment.py`, `analytics/views_equipment.py`
- Create: `analytics/templates/analytics/equipment/repairs.html`
- Test: `test_equipment.py`, `test_views.py`

**Interfaces:**
- Consumes: Задачи 3 и 4; `_bucket_by_month` и `_delta_pct` (`services/finance.py`); `_with_load_shades` (`views_trips.py`).
- Produces. Сервис:
  - константы:
    - `DURATION_BUCKETS = (("1–3", 1, 3), ("4–7", 4, 7), ("8–14", 8, 14), ("15–30", 15, 30), ("31+", 31, None))` — границы включаются;
    - `MAX_MONTH_SERIES = 6`;
    - `REPAIR_KPI_KEYS = ("total", "planned", "breakdowns", "median_days", "replacement_share")`;
  - `repairs_kpis(period, today, filters, source=None) -> dict`:
    - ключи `current`, `previous`, `delta_pct` (dict по `REPAIR_KPI_KEYS`), `open_now: int`, `unknown_type: int`;
    - `median_days` — медиана `repair_days` закрытых поломок периода, `Decimal` с шагом 0,1, или None;
    - `replacement_share` — поломки с подменой / поломки × 100, шаг 0,1, или None;
    - `delta_pct["replacement_share"]` — разность в п.п. (current − previous, шаг 0,1), у остальных ключей `_delta_pct`;
  - `open_repairs(today, filters, source=None) -> dict`:
    - ключи `rows`, `old_count: int`, `old_before: date`;
    - строка — `{"id", "device", "department", "service_type", "beg_dt", "days", "replacement"}`;
    - `old_before = today − 365 дн.`; открытый ремонт: `end_dt is None` и `old_before ≤ beg_dt ≤ today`;
    - `days = (today − beg_dt).days + 1`; сортировка `days` по убыванию;
  - `works_by_month(period, filters, source=None) -> dict`:
    - ключи `months: list[date]` и `series: [{"label", "data": list[int]}]`;
    - серии — виды работ по убыванию итога; если видов больше 6, первые 5 и `OTHER_SERVICE_TYPES_LABEL`;
  - `planned_by_month(period, filters, source=None) -> dict`:
    - ключи `months`, `ours`, `others`, `no_device`, `previous` (int);
    - `previous[i]` — ТО в i-м месяце `period.previous_year()`;
  - `duration_stats(period, filters, source=None) -> dict`:
    - ключи `buckets` (`[{"label", "count", "ids"}]` — закрытые поломки периода), `by_type` (`[{"label", "count", "median", "max"}]` — все закрытые работы периода по виду, по убыванию `count`) и `open: int` (работы периода без `end_dt`);
  - `engineer_load(period, filters, source=None) -> dict`:
    - ключи `months`, `rows: [{"name", "days": list[int], "total"}]` (число работ по месяцам; ключ `days` нужен ради `_with_load_shades`), `max: int`;
    - сортировка `total` по убыванию, затем `name`.
- Produces. View: `_repairs_context(source, filters, period, today) -> dict` — ключи `repairs`, `repairs_tiles`, `open_repairs`, `old_open_url`, `durations`, `engineer_load` и `charts` с ключами `works_by_month`, `planned_by_month`, `durations`.

- [ ] **Step 1: Падающие тесты `RepairsTests` (`test_equipment.py`)**

Период — 2026 год, `today = date(2026, 10, 16)`.

```python
def test_repairs_kpis_counts_and_deltas(self):
    # 2026: 2 ТО, 3 поломки (одна с подменой), 1 без вида; 2025: 1 ТО, 1 поломка
    # current total 6, planned 2, breakdowns 3, replacement_share Decimal("33.3"), unknown_type 1
    # delta_pct["planned"] == Decimal("100.0"); delta_pct["replacement_share"] — в п.п.
def test_median_days_only_closed_breakdowns(self): ...  # ТО и открытые не входят
def test_open_repairs_window_and_future(self):
    # открытый 2026-10-01 -> days 16; 2025-10-16 (= old_before) -> в rows; 2025-10-15 -> old_count;
    # beg_dt 2026-11-01 (будущее) -> ни в rows, ни в old_count, не в open_now
def test_works_by_month_groups_extra_types(self):
    # 7 видов -> 6 серий, последняя "Прочие виды работ"; без вида -> "Вид работ не указан"
def test_planned_by_month_splits_supply_and_previous_year(self): ...
def test_duration_buckets_and_by_type(self):
    # длительности 1, 3, 4, 14, 15, 31 -> [2, 1, 1, 1, 1]; by_type median/max
def test_engineer_load(self): ...  # пустой инженер -> "Инженер не указан", max
```

`test_views.py`, класс `EquipmentPageTests`:
- `test_repairs_tiles`: «ТО проведено» — kind `count`; «Поломок с подменой» выводит дельту в п.п.; у «В работе сейчас» дельты нет;
- `test_open_repair_row_links_to_service`: `change_url(SERVICES, id)`;
- `test_old_open_link_filters_service_list`: ссылка открывает список ремонтов, `result_count` равен `old_count`.

- [ ] **Step 2: Запустить, тесты падают**

- [ ] **Step 3: Сервисные функции блока Б**

- [ ] **Step 4: View и `equipment/repairs.html`**

Плитки:
- «Всего работ»;
- «ТО проведено»;
- «Поломок» (`inverse`);
- «Медиана ремонта, дней» (`inverse`);
- «Поломок с подменой» (`pct`, дельта `delta:"pp"`);
- «В работе сейчас» с подписью «на сегодня» вместо дельты.

Подпись «без вида работ: N», если N > 0.

Графики:
- `works_by_month`: stacked, `fmt="count"`;
- `planned_by_month`: нами `c1`, не нами `c2`, «Прибор не указан» `c4` (только если сумма > 0), линия «Прошлый год» `kind="line"` `c5`, `stacked=True`, `fmt="count"`;
- `durations`: столбцы «Поломок» и справа таблица `by_type` в `an-split an-split--even`. Подписи «Корзины — поломки; таблица — все виды работ» и «без даты окончания: N».

Таблица открытых ремонтов во всю ширину, внизу «Старые незакрытые (начаты раньше ДД.ММ.ГГГГ): N» со ссылкой. Тепловая карта «Нагрузка инженеров» повторяет разметку «Кто и когда в отъезде» (`an-matrix`, `an-tone-load`).

- [ ] **Step 5: Тесты зелёные, commit**

`git commit -m "feat(analytics): «Оборудование» — блок «Ремонты»"`

---

### Task 6: Блок В «Надёжность моделей»

**Files:** те же модули, `equipment/reliability.html`, тесты.

**Interfaces:**
- Produces. Сервис:
  - константы `REPEAT_WINDOWS = (30, 90)`, `MIN_UNITS_FOR_RELIABILITY = 3`, `TOP_RELIABILITY = 15`, `TOP_PROBLEM_DEVICES = 10`, `DAYS_IN_YEAR = 365`;
  - `effective_days(period, today) -> int` — `(min(date_to, today) − date_from).days + 1`, отрицательное значение заменяется на 0;
  - `reliability(period, today, filters, source=None) -> list[dict]`:
    - строки `{"equipment_id", "label", "units", "breakdowns", "per_unit_year": Decimal (шаг 0,01), "service_ids"}`;
    - считаются поломки периода с `beg_dt ≤ today`;
    - в рейтинг входят модели с `units ≥ 3` и `breakdowns > 0`;
    - сортировка `per_unit_year` по убыванию, затем `breakdowns` по убыванию, затем `label`; не больше 15 строк;
    - при `effective_days == 0` — `[]`;
  - `repeat_repairs(period, filters, source=None) -> dict`:
    - ключи `counts: {30: int, 90: int}` и `rows`;
    - строка — `{"device", "department", "previous_id", "previous_date", "current_id", "current_date", "gap_days"}`;
    - `previous` — поломка того же прибора с наибольшим `(beg_dt, create_dt)` среди меньших, по всей истории; `previous_date = end_dt or beg_dt`;
    - `gap = max((current.beg_dt − previous_date).days, 0)`; в строки попадают разрывы ≤ 90; сортировка `gap` по возрастанию;
  - `problem_devices(period, filters, source=None) -> list[dict]`:
    - строки `{"device_id", "device", "department", "total", "in_period", "last_date"}`;
    - приборы с `total ≥ 2`, сортировка `total` по убыванию, затем `last_date` по убыванию; не больше 10;
  - `models_summary(period, today, filters, source=None) -> list[dict]`:
    - строки `{"equipment_id", "label", "manufacturer", "direction", "at_client", "ours", "others", "planned", "breakdowns", "per_unit_year", "median_days", "fund_working", "fund_total"}`;
    - модель входит, если у неё есть `at_client`, работы в периоде или `fund_total > 0`;
    - `per_unit_year` равен None при `at_client == 0` или `effective_days == 0`;
    - сортировка `breakdowns` по убыванию, затем `at_client` по убыванию, затем `label`.
- Produces. View: `_reliability_context(...) -> dict` — ключи `repeats` (`counts` и строки со ссылками на обе карточки ремонта), `problem_devices` (ссылка `change_url(ACCOUNTING, device_id)`), `models_summary` и `charts["reliability"]`. В графике ссылки — `ids_link(SERVICES, service_ids)`.

- [ ] **Step 1: Падающие тесты `ReliabilityTests`**

```python
def test_reliability_rate_and_min_units(self):
    # модель M: 4 прибора у клиента, 2 поломки за 2026, today 2026-10-16
    # per_unit_year == (Decimal(2) / 4 * 365 / 289).quantize(Decimal("0.01"))  # 289 дней с 01.01 по 16.10
    # модель с 2 приборами в рейтинг не входит; ТО и работы без вида не считаются
def test_reliability_future_period_is_empty(self):
    # Period(date(2027,1,1), date(2027,12,31)) -> []
def test_repeat_repairs_boundaries(self):
    # три прибора, у каждого прошлая поломка закончилась 2026-03-01:
    # X — следующая 2026-03-31 (gap 30), Y — 2026-05-30 (gap 90), Z — 2026-05-31 (gap 91)
    # counts == {30: 1, 90: 2}; Z не в rows
def test_repeat_repairs_previous_rules(self):
    # прошлая поломка без end_dt -> previous_date == её beg_dt;
    # прошлая поломка в 2025 (вне периода) учитывается;
    # ТО между двумя поломками не считается «прошлой поломкой»
def test_problem_devices(self): ...
def test_models_summary_columns(self):
    # at_client ours/others, planned, breakdowns, median_days, fund_working (рабочие подменные той же модели)
```

`test_views.py`: `test_reliability_chart_links_to_services` — ссылка открывает список ремонтов, `result_count` равен числу поломок модели.

- [ ] **Step 2: Запустить, тесты падают**

- [ ] **Step 3: Сервис**

- [ ] **Step 4: View и `equipment/reliability.html`**

- График `reliability`: horizontal, `fmt="count"`, серия «Поломок на прибор в год» цвета `c1`. Подпись: «Поломки периода на прибор модели у клиентов сейчас, пересчёт на год; модели с 3 и более приборами. Истории парка нет, поэтому знаменатель — текущий парк».
- Плитки повторов: «Повтор за 30 дн.», «Повтор за 90 дн.».
- Таблицы: повторы, проблемные приборы (подпись «Вся история»), сводная по моделям (`an-card--wide`).

- [ ] **Step 5: Тесты зелёные, commit**

`git commit -m "feat(analytics): «Оборудование» — блок «Надёжность моделей»"`

---

### Task 7: Блок Г «Подменный фонд»

**Files:** те же модули, `equipment/fund.html`, `analytics/static/analytics/css/analytics.css`, тесты.

**Interfaces:**
- Produces. Сервис:
  - `replacement_location(replacement, source) -> dict`:
    - ключи `at_client: bool`, `service: Service | None`, `department: str | None`;
    - последняя выдача — max `(beg_dt, create_dt)`;
    - `at_client` — выдача есть, `returned_to_office` False и у ремонтируемого прибора есть активный монтаж. Это то же правило, что `ReplacementEquipmentAdmin.transferred_to`;
  - `fund_kpis(period, today, filters, source=None) -> dict`:
    - ключи `total`, `working`, `not_working`, `at_client`, `in_office` и `issues: {"current", "previous", "delta_pct"}`;
    - `issues` — ремонты периода с подменным, подменный проходит фильтры;
  - `replacements_at_clients(today, filters, source=None) -> list[dict]`:
    - строки `{"replacement_id", "label", "department", "since", "days", "service_id", "repair_closed", "end_dt", "overdue"}`;
    - `overdue = end_dt is not None`; `days = max((today − since).days + 1, 1)`;
    - сортировка: сначала `overdue`, затем `days` по убыванию;
  - `issue_interval(service, next_issue, today) -> tuple[date, date]` — алгоритм ниже;
  - `issue_timeline(period, today, filters, source=None) -> dict`:
    - ключи `months: list[date]` и `rows`; строка — `{"replacement_id", "label", "bars": [{"service_id", "start", "end", "left_pct", "width_pct"}], "days": int}`;
    - строки идут по всем подменным из `replacements_of(filters)`, сортировка по `label`;
  - `replacement_shortage(period, filters, source=None) -> list[dict]`:
    - строки `{"equipment_id", "label", "without", "with", "median_days", "fund_model", "fund_direction"}`;
    - считаются поломки периода по модели ремонтируемого прибора;
    - `fund_*` — рабочие подменные той же модели и того же направления, без фильтров; у модели без направления `fund_direction` равен None;
    - сортировка `without` по убыванию, затем `with` по убыванию, затем `label`.

```python
def issue_interval(service, next_issue, today):
    """Даты выдачи подменного прибора в ремонт `service`.

    Последняя выдача: не вернули или ремонт не закрыт — до сегодня, иначе до end_dt.
    Ранняя выдача: до end_dt, но не позже дня перед следующей выдачей (старые
    ремонты без отметки «Вернули в офис» не тянутся до сегодня).
    """
    start = service.beg_dt
    if next_issue is None:
        closed = service.end_dt is not None and service.returned_to_office
        end = service.end_dt if closed else today
    else:
        cap = next_issue.beg_dt - timedelta(days=1)
        end = min(service.end_dt or cap, cap)
    return start, max(end, start)
```

Видимая часть полосы: `[max(start, date_from), min(end, date_to, today)]`, пустая полоса пропускается. Обозначим `period_days = (date_to − date_from).days + 1`. Тогда:
- `left_pct = round((vis_start − date_from).days / period_days * 100, 2)`;
- `width_pct = round(((vis_end − vis_start).days + 1) / period_days * 100, 2)`;
- `days` — число дней в объединении видимых интервалов строки.

- Produces. View: `_fund_context(...) -> dict` — ключи `fund`, `fund_tiles`, `fund_status` (ссылки на ремонт и на подменный), `timeline` (подписи месяцев через `month_label`; если месяцев больше 24, в шапке выводятся годы), `shortage`. Графиков в блоке нет.

- [ ] **Step 1: Падающие тесты `FundTests`**

```python
def test_location_matches_admin_transferred_to(self):
    # 3 подменных: последний ремонт без «вернули» и с монтажом -> у клиента; с «вернули» -> в офисе;
    # без активного монтажа ремонтируемого прибора -> в офисе.
    # сравнить с ReplacementEquipmentAdmin(ReplacementEquipment, admin.site).transferred_to(obj)
    # для obj из его get_queryset(request) — "В офисе" <=> not at_client
def test_overdue_first(self):
    # ремонт закрыт 2026-09-01, не вернули -> overdue True, первая строка
def test_issue_interval_rules(self):
    # последняя открытая -> до today; последняя закрыта и вернули -> до end_dt;
    # ранняя без «вернули», end_dt None, следующая с 2026-05-10 -> до 2026-05-09
def test_timeline_clipped_to_period_and_today(self):
    # выдача 2025-12-20..открыта, период 2026 -> left_pct 0.0, видимый конец today, days == 289
def test_timeline_future_period_empty(self): ...  # 2027 -> у всех строк bars == [], days == 0
def test_shortage(self): ...
def test_fund_kpis_supply_filter_ignored(self):
    # supply="ours" не меняет total/working; direction меняет
```

`test_views.py`:
- `test_fund_status_overdue_row_highlighted`: в HTML есть `an-tone-risk` и «прибор не вернули в офис»;
- `test_timeline_bar_links_to_service`.

- [ ] **Step 2: Запустить, тесты падают**

- [ ] **Step 3: Сервис**

- [ ] **Step 4: View, `equipment/fund.html` и CSS**

Плитки:
- «В фонде», «Рабочих», «Нерабочих», «У клиентов», «В офисе» — с подписью «на сегодня»;
- «Выдач за период» — с дельтой.

Подпись блока: «Фильтр «Поставка» на подменный фонд не действует».

CSS:
- `.an-timeline` — grid: колонки «прибор · дорожка · дней»;
- `.an-timeline-track` — `position: relative`, фон `var(--an-surface)` с рамкой;
- `.an-timeline-bar` — `position: absolute`, фон `var(--an-c1)`, `left` и `width` задаются inline-стилем в процентах, полоса — ссылка `<a>` с `title` «ДД.ММ — ДД.ММ».

Тёмная тема — через существующие переменные. На ширине меньше 768px колонка «дней» прячется под дорожку.

Строка overdue получает класс `an-tone-risk` и текст «ремонт закрыт ДД.ММ, прибор не вернули в офис».

- [ ] **Step 5: Тесты зелёные, commit**

`git commit -m "feat(analytics): «Оборудование» — блок «Подменный фонд»"`

---

### Task 8: Проверка страницы целиком и документация

**Files:**
- Modify: `AGENTS.md`, `analytics/tests/test_views.py`
- Modify: память `analytics-stages-2-4-lessons.md` (вне репозитория)

- [ ] **Step 1: Дополнить тест пустой базы**

`test_equipment_page_empty_db` проверяет, что `set(charts) == EQUIPMENT_CHART_KEYS`. Это ключи всех графиков из Задач 4–6, десять штук: `installs_by_year`, `structure_directions`, `structure_manufacturers`, `structure_statuses`, `structure_regions`, `park_age`, `works_by_month`, `planned_by_month`, `durations`, `reliability`. Все таблицы показывают «Нет данных».

- [ ] **Step 2: Полный прогон**

Run: `python manage.py test --settings=ebase_site.test_settings 2>&1 | tail -3`
Expected: `FAILED (failures=2, errors=3)` — те же пять тестов, что в исходном состоянии. Других падений нет.

- [ ] **Step 3: Ручная проверка в headless Chromium**

Скрипт в scratchpad:
- создаёт фикстуры через фабрики в тестовой БД;
- рендерит `/admin/analytics/equipment/` test client'ом;
- сохраняет HTML со статикой.

Снять скриншоты `/usr/bin/chromium --headless`:
- в светлой теме (`--blink-settings=preferredColorScheme=1`) и в тёмной;
- на ширине 1400 и 390 px.

Проверить:
- графики нарисованы;
- таблицы не обрезаны, в 4+ числовых колонки они во всю ширину;
- полосы хронологии видны;
- на телефоне нет горизонтальной прокрутки страницы.

- [ ] **Step 4: Документация**

`AGENTS.md`:
- в таблицу приложений и раздел «Аналитика» добавить вкладку «Оборудование», право `view_equipment`, миграцию `0005_equipment_tab`, `services/equipment.py` (`EquipmentSet.load()`), правила расчёта из дизайна, флаг «Плановое ТО» (`directory/0004`);
- в «Наборы тестов» добавить `test_equipment` и `directory/tests.py`;
- обновить число тестов в «Текущем состоянии».

Память `analytics-stages-2-4-lessons.md`: вкладка «Оборудование» в ветке `feature/analytics-equipment`, решения пользователя (ТО двумя показателями, менеджерам весь парк, флаг ТО).

- [ ] **Step 5: Commit**

`black` по изменённым файлам, затем `git commit -m "docs: AGENTS.md — вкладка «Оборудование» и флаг «Плановое ТО»"`.
