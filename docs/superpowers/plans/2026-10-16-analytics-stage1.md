# «Статистика», этап 1: исправление долга, каркас и вкладка «Деньги» — план реализации

> **Для исполнителя-агента:** используй скилл `superpowers:subagent-driven-development` (рекомендуется) или `superpowers:executing-plans` для пошагового выполнения. Шаги помечены чекбоксами `- [ ]`.

**Цель:** исправить пересчёт `Contract.debt` и запустить раздел «Статистика» (приложение `analytics`) с первой вкладкой «Деньги».

**Архитектура:** новое приложение `analytics` со страницами внутри админки (`/admin/analytics/…`, обёртка `admin.site.admin_view`).
- Права вкладок задаются неуправляемой моделью без таблицы.
- Расчёты лежат в чистых функциях `analytics/services/finance.py`, на входе — `Period` и фильтры.
- View собирает из них спецификации графиков. Спецификации уходят в шаблон через `json_script`, `charts.js` рисует их Chart.js.
- Плитки и таблицы рендерятся на сервере.

**Тех-стек:** Django 4.2.16, Python 3.11, PostgreSQL (в тестах SQLite `:memory:`), Chart.js 4.5.1 (vendored), Black 24.8.0.

**Спека:** `docs/superpowers/specs/2026-10-16-analytics-design.md`. Перед стартом читать разделы «Принятые решения», «Решения исполнителя», «Архитектура», «Вкладка „Деньги“».

**Тесты (из `ebase_site/`):**

```bash
source ../.venv/bin/activate
python manage.py test analytics contracts --settings=ebase_site.test_settings   # по ходу задач
python manage.py test --settings=ebase_site.test_settings                       # полный прогон
```

**Black:** `black ebase_site/analytics ebase_site/contracts` после каждого изменения `.py`.

**Коммиты:** на русском, стиль репозитория: `fix(contracts): …`, `feat(analytics): …`, `test(analytics): …`. Ветка `feature/analytics` уже создана.

## Global Constraints

- **Падения до начала работ.** Базовый прогон: `Ran 84 tests … FAILED (failures=2, errors=3)`. Эти пять тестов падали до нас и не чинятся:
  - `ebase.tests.ServiceContractTests` (три теста, ERROR);
  - `contracts.tests.ContractAdminFormTests.test_payment_status_included_on_change_form`;
  - `contracts.tests.ContractModelTests.test_payment_status_updates_when_contract_amount_changes`.

  Критерий: новых падений нет.
- Имя приложения `analytics`, `verbose_name="Статистика"`. Имя `statistics` запрещено: оно затеняет stdlib.
- Права (`codename` → название), модель-носитель `AnalyticsAccess`:
  - `view_finance` → «Статистика: Деньги»;
  - `view_warehouse_trips` → «Статистика: Склад и командировки»;
  - `view_service` → «Статистика: Сервис и надёжность»;
  - `view_park` → «Статистика: Парк и продажи».
- Группа «Статистика» получает все четыре права и всех активных `is_staff` пользователей.
- URL-префикс `admin/analytics/` подключается в `ebase_site/urls.py` **до** `path("admin/", …)`, `app_name = "analytics"`.
- Chart.js 4.5.1 лежит файлом `ebase_site/analytics/static/analytics/vendor/chart.umd.min.js`, без CDN в шаблонах.
- Новых pip-зависимостей нет.
- Не менять сигналы (`contracts/signals.py`, `ebase/signals.py`, `business_trip/signals.py`, `spare_part/signals.py`).
- Все тексты интерфейса на русском. Деньги показываются в формате `contracts.admin.format_money` («20 000,00») с « ₽».
- Арифметику дат и группировку по месяцам делаем в Python, а не функциями БД: SQLite и PG ведут себя по-разному.
- Фильтр «клиент» действует на всё, кроме «Топ клиентов» и «Рентабельности клиентов». Эти два виджета сравнивают клиентов между собой, поэтому показывают всех; у виджета есть подпись об этом.
- «Возраст долга» считается на сегодня и период не учитывает. На виджете подпись «на сегодня, период не учитывается».

## Review Focus

1. **Пустая БД или период без контрактов.** Ожидание: страница 200, плитки «0,00 ₽», графики «Нет данных», маржа и дельта «—» (нет деления на ноль). Тесты: Task 6 `test_kpis_empty_period`, Task 9 `test_finance_page_empty_db`.
2. **Мусор в GET-параметрах:**
   - неизвестный `preset`;
   - `date_from > date_to`;
   - нераспознаваемые даты;
   - неверный UUID клиента.

   Ожидание: не 500, откат к умолчанию (текущий год, без клиента). Тесты: Task 3 `test_invalid_*`, Task 9 `test_finance_page_bad_params`.
3. **Период с 29 февраля** при сравнении с прошлым годом. Ожидание: 28 февраля, без исключения. Тест: Task 3 `test_previous_year_leap_day`.
4. **Контракт с `service_end_date` в будущем и контракт без неё.** Ожидание: корзина «срок не наступил»; без даты возраст считается от даты заключения. Тесты: Task 7 `test_debt_aging_future_end_date`, `test_debt_aging_falls_back_to_conclusion_date`.
5. **Сотрудник с `is_staff` без прав `analytics`.** Ожидание: нет ссылки «Статистика», 403 на вкладке и на корне. С правом только на одну вкладку корень ведёт на неё. Тесты: Task 4 `test_*_permission*`.

---

## Структура файлов

```
ebase_site/analytics/
├── __init__.py
├── apps.py                 # AnalyticsConfig, verbose_name="Статистика"
├── models.py               # AnalyticsAccess (managed=False) — только права
├── filters.py              # Period, PeriodForm, FinanceFilterForm, shift_year, month_label
├── charts.py               # chart_spec(), to_float()
├── links.py                # changelist_url(), change_url()
├── views.py                # Tab, TABS, visible_tabs(), index(), AnalyticsTabView, FinanceView
├── urls.py
├── services/
│   ├── __init__.py
│   └── finance.py          # все расчёты вкладки «Деньги»
├── templatetags/
│   ├── __init__.py
│   └── analytics_tags.py   # фильтры money, pct, delta
├── templates/analytics/
│   ├── base.html           # наследует admin/base_site.html: вкладки, форма фильтров, подключение js/css
│   ├── finance.html
│   └── includes/chart.html # canvas + json_script + «Нет данных»
├── static/analytics/
│   ├── vendor/chart.umd.min.js
│   ├── js/charts.js
│   └── css/analytics.css
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py     # makemigrations
│   └── 0002_statistics_group.py
└── tests/
    ├── __init__.py
    ├── factories.py        # make_client, make_contract, make_payment …
    ├── test_migrations.py
    ├── test_filters.py
    ├── test_charts.py
    ├── test_views.py
    └── test_finance.py
```

Изменяемые файлы:
- `ebase_site/contracts/models.py` (`Contract.save`);
- `ebase_site/contracts/migrations/0006_recalc_contract_totals.py` (новая);
- `ebase_site/contracts/tests.py`;
- `ebase_site/ebase_site/settings.py` (`INSTALLED_APPS`);
- `ebase_site/ebase_site/urls.py`;
- `ebase_site/ebase/templates/admin/base_site.html` (ссылка в шапке);
- `AGENTS.md`.

---

### Task 1: Пересчёт долга при сохранении контракта

**Files:**
- Modify: `ebase_site/contracts/models.py` (`Contract.save`, ~стр. 174)
- Create: `ebase_site/contracts/migrations/0006_recalc_contract_totals.py`
- Test: `ebase_site/contracts/tests.py` (новый класс `ContractDebtTests`)

**Interfaces:**
- Produces:
  - `Contract.save()` всегда выставляет `debt = contract_amount − payment_amount`.
  - Функция миграции `recalc_contract_totals(apps, schema_editor)` в `0006_recalc_contract_totals.py`.

- [ ] **Step 1: Write the failing tests** (setUp как в `ContractModelTests`: клиент, контракт `CNT-001` на 100000 от 2026-01-15)

```python
def test_new_contract_without_payments_has_full_debt(self):
    self.contract.refresh_from_db()
    self.assertEqual(self.contract.debt, Decimal("100000"))

def test_debt_recalculated_when_amount_changes(self):
    Payment.objects.create(contract=self.contract, date="2026-01-20", amount=Decimal("100000"))
    self.contract.refresh_from_db()
    self.contract.contract_amount = Decimal("150000")
    self.contract.save()
    self.contract.refresh_from_db()
    self.assertEqual(self.contract.debt, Decimal("50000"))
    self.assertEqual(self.contract.payment_status, "partial")

def test_save_with_update_fields_updates_debt(self):
    self.contract.contract_amount = Decimal("120000")
    self.contract.save(update_fields=["contract_amount"])
    self.contract.refresh_from_db()
    self.assertEqual(self.contract.debt, Decimal("120000"))

def test_recalc_migration_fixes_stale_totals(self):
    Payment.objects.create(contract=self.contract, date="2026-01-20", amount=Decimal("30000"))
    ContractExpense.objects.create(contract=self.contract, expense_type="other", quantity=1, cost=5000)
    Contract.objects.filter(pk=self.contract.pk).update(
        debt=0, payment_amount=0, expenses_amount=0, profit=0, payment_status="no_receipts"
    )
    migration = importlib.import_module("contracts.migrations.0006_recalc_contract_totals")
    migration.recalc_contract_totals(django_apps, None)  # from django.apps import apps as django_apps
    self.contract.refresh_from_db()
    self.assertEqual(self.contract.payment_amount, Decimal("30000"))
    self.assertEqual(self.contract.expenses_amount, Decimal("5000"))
    self.assertEqual(self.contract.debt, Decimal("70000"))
    self.assertEqual(self.contract.profit, Decimal("25000"))
    self.assertEqual(self.contract.payment_status, "partial")
```

- [ ] **Step 2: Run, expect FAIL**
  - Run: `python manage.py test contracts.tests.ContractDebtTests --settings=ebase_site.test_settings`
  - Expected: первые три теста падают на значении `debt`, четвёртый — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**
  - **`Contract.save()`.** Рядом с `update_payment_status()` выставить `self.debt = Decimal(str(self.contract_amount or 0)) − Decimal(str(self.payment_amount or 0))`. В расширение `update_fields` добавить `"debt"` вместе с `"payment_status"`.
  - **Миграция `0006_recalc_contract_totals`.** Тип `RunPython(recalc_contract_totals, migrations.RunPython.noop)`. Зависимости: `("contracts", "0005_alter_contract_payment_status")`, `("spare_part", "0008_sparepartshipmentm2m_price_sparepartshipmentm2m_sum_and_more")`, `("business_trip", "0008_money_receipt")`.
  - **Функция `recalc_contract_totals`.** Берёт модели через `apps.get_model` и для каждого контракта повторяет формулы `contracts/signals.py: recalc_contract`:
    - оплаты = `payments` Σ`amount`;
    - затраты = `spare_part_shipments` Σ`shipment_m2m__sum` + `expenses` Σ`sum` + `business_trip_expenses` Σ`amount`;
    - `debt`, `profit`;
    - `payment_status` по правилу `Contract.update_payment_status`. У исторической модели нет методов, поэтому правило дублируется в функции.

    Запись через `.filter(pk=…).update(…)`.

- [ ] **Step 4: Run, expect PASS**
  - Тот же запуск плюс `python manage.py test contracts --settings=ebase_site.test_settings`.
  - Expected: новые тесты зелёные. В `contracts` падают только два базовых теста из Global Constraints.

- [ ] **Step 5: Commit** — `fix(contracts): долг пересчитывается при сохранении контракта + миграция пересчёта`

---

### Task 2: Приложение `analytics`, права и группа «Статистика»

**Files:**
- Create: `analytics/__init__.py`, `apps.py`, `models.py`, `migrations/0001_initial.py` (через `python manage.py makemigrations analytics` с обычными настройками), `migrations/0002_statistics_group.py`, `tests/__init__.py`, `tests/test_migrations.py`
- Modify: `ebase_site/ebase_site/settings.py` (добавить `"analytics.apps.AnalyticsConfig"` после `business_trip`)

**Interfaces:**
- Produces:
  - модель `analytics.models.AnalyticsAccess` (`managed = False`, `default_permissions = ()`, `permissions` — четыре пары из Global Constraints, `verbose_name = "Доступ к статистике"`);
  - константа `analytics.models.STATISTICS_GROUP_NAME = "Статистика"`;
  - функция миграции `create_statistics_group(apps, schema_editor)`.

- [ ] **Step 1: Write the failing tests** (`tests/test_migrations.py`)

```python
class StatisticsGroupMigrationTests(TestCase):
    def test_permissions_exist(self):
        codenames = set(Permission.objects.filter(content_type__app_label="analytics")
                        .values_list("codename", flat=True))
        self.assertEqual(codenames, {"view_finance", "view_warehouse_trips", "view_service", "view_park"})

    def test_group_gets_all_permissions_and_active_staff_only(self):
        staff = User.objects.create_user("staff", password="p", is_staff=True)
        User.objects.create_user("inactive", password="p", is_staff=True, is_active=False)
        User.objects.create_user("plain", password="p")
        migration = importlib.import_module("analytics.migrations.0002_statistics_group")
        migration.create_statistics_group(django_apps, None)
        migration.create_statistics_group(django_apps, None)  # идемпотентность
        group = Group.objects.get(name="Статистика")
        self.assertEqual(group.permissions.count(), 4)
        self.assertEqual(list(group.user_set.all()), [staff])
        self.assertTrue(User.objects.get(pk=staff.pk).has_perm("analytics.view_finance"))
```

- [ ] **Step 2: Run, expect FAIL**
  - Run: `python manage.py test analytics --settings=ebase_site.test_settings`
  - Expected: ошибка импорта, приложения нет.

- [ ] **Step 3: Implement** приложение, модель и `0001` (`makemigrations`), затем `0002`:
  - `RunPython(create_statistics_group, noop)`.
  - Сначала создать права через `django.contrib.auth.management.create_permissions(apps.get_app_config("analytics"), apps=apps, verbosity=0)`. Для исторического реестра на время вызова выставить `app_config.models_module = True` (стандартный приём).
  - Затем `Group.get_or_create(name="Статистика")`, `permissions.set(...)`, `user_set.add(*active staff)`.
  - Зависимости: `("analytics", "0001_initial")`, `("users", "0001_initial")`, `("auth", "0012_alter_user_first_name_max_length")`, `("contenttypes", "0002_remove_content_type_name")`.

- [ ] **Step 4: Run, expect PASS** (та же команда). Плюс `python manage.py makemigrations --check --dry-run` → `No changes detected`.

- [ ] **Step 5: Commit** — `feat(analytics): приложение «Статистика», права вкладок и группа`

---

### Task 3: Период и формы фильтров

**Files:**
- Create: `analytics/filters.py`, `analytics/tests/test_filters.py`

**Interfaces:**
- Produces (`analytics/filters.py`):
  - `@dataclass(frozen=True) class Period: date_from: date; date_to: date`.
    - `previous_year() -> Period`: обе даты через `shift_year(d, -1)`.
    - `months() -> list[date]`: первые числа месяцев от `date_from` до `date_to` включительно.
  - `shift_year(d: date, years: int) -> date`: 29.02 → 28.02.
  - `month_label(d: date) -> str`: `"янв 2026"`. Сокращения: янв фев мар апр май июн июл авг сен окт ноя дек.
  - `PRESETS = [("year", "Текущий год"), ("prev_year", "Прошлый год"), ("quarter", "Текущий квартал"), ("month", "Текущий месяц"), ("custom", "Свой период")]`.
  - `class PeriodForm(forms.Form)`.
    - Поля: `preset` (ChoiceField, required=False), `date_from`, `date_to` (DateField, required=False, `DateInput(attrs={"type": "date"})`).
    - Метод `get_period(today: date) -> Period` берёт только прошедшие очистку значения из `cleaned_data`. Форма вызывается с `data=request.GET`.
    - Порядок: нет `preset` или он невалиден → `"year"`. `"custom"` без одной из дат → `"year"`. `date_from > date_to` → даты меняются местами.
  - `class FinanceFilterForm(PeriodForm)`: поле `client = ModelChoiceField(Client.objects.filter(contract_client__isnull=False).distinct().order_by("name"), required=False, label="Клиент")`, метод `get_client() -> Client | None` (невалидное значение → `None`).

- [ ] **Step 1: Write the failing tests** (`SimpleTestCase` для дат, `TestCase` для клиента; `TODAY = date(2026, 10, 16)`)

```python
def test_default_is_current_year(self):
    self.assertEqual(PeriodForm(data={}).get_period(TODAY), Period(date(2026, 1, 1), date(2026, 12, 31)))
def test_presets(self):  # prev_year → 2025-01-01..2025-12-31; quarter → 2026-10-01..2026-12-31; month → 2026-10-01..2026-10-31
def test_custom_range(self):  # {"preset": "custom", "date_from": "2026-02-01", "date_to": "2026-03-15"}
def test_invalid_preset_falls_back_to_year(self):  # {"preset": "zzz"}
def test_invalid_dates_fall_back_to_year(self):  # {"preset": "custom", "date_from": "abc", "date_to": "2026-03-15"}
def test_invalid_reversed_range_is_swapped(self):  # from 2026-05-01, to 2026-03-01 → 2026-03-01..2026-05-01
def test_previous_year_leap_day(self):
    self.assertEqual(Period(date(2024, 2, 1), date(2024, 2, 29)).previous_year(), Period(date(2023, 2, 1), date(2023, 2, 28)))
def test_months(self):  # Period(2026-01-15, 2026-03-02).months() == [2026-01-01, 2026-02-01, 2026-03-01]
def test_month_label(self):  # month_label(date(2026, 1, 1)) == "янв 2026"
def test_invalid_client_is_ignored(self):  # FinanceFilterForm(data={"client": "not-a-uuid"}).get_client() is None, get_period работает
```

- [ ] **Step 2: Run, expect FAIL**
  - Run: `python manage.py test analytics.tests.test_filters --settings=ebase_site.test_settings`
  - Expected: ImportError.
- [ ] **Step 3: Implement** по интерфейсам выше.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(analytics): период и фильтры статистики`

---

### Task 4: Навигация, доступ и ссылка в шапке

**Files:**
- Create: `analytics/views.py`, `analytics/urls.py`, `analytics/templates/analytics/base.html`, `analytics/templates/analytics/finance.html` (пока только заголовок и форма), `analytics/tests/test_views.py`
- Modify: `ebase_site/ebase_site/urls.py`, `ebase_site/ebase/templates/admin/base_site.html`

**Interfaces:**
- Consumes: `PeriodForm`, `FinanceFilterForm`, `Period` (Task 3).
- Produces (`analytics/views.py`):
  - `@dataclass(frozen=True) class Tab: key: str; title: str; perm: str; url_name: str`.
  - `TABS = [Tab("finance", "Деньги", "analytics.view_finance", "analytics:finance")]`. Этапы 2–4 дописывают сюда свои вкладки.
  - `visible_tabs(user) -> list[Tab]`.
  - `index(request)` → редирект на первую видимую вкладку, иначе `PermissionDenied`.
  - `class AnalyticsTabView(TemplateView)`.
    - Атрибуты: `tab_key: str`, `form_class = PeriodForm`.
    - `dispatch` проверяет `request.user.has_perm(tab.perm)`, иначе `PermissionDenied`.
    - `get_context_data` возвращает `**admin.site.each_context(request)` и `tabs`, `active_tab`, `form`, `period`, `previous_period`, `today`, `title="Статистика — <tab.title>"`.
    - Атрибут `self.form` заполняется в `get_context_data`, наследники берут из него `get_client()`.
  - `class FinanceView(AnalyticsTabView)`: `tab_key = "finance"`, `form_class = FinanceFilterForm`, `template_name = "analytics/finance.html"`.
  - URL-имена: `analytics:index` (`""`) и `analytics:finance` (`"finance/"`). Обе view обёрнуты в `admin.site.admin_view`.
- Шаблон `analytics/base.html`:
  - наследует `admin/base_site.html`;
  - хлебные крошки «Начало › Статистика › <вкладка>»;
  - строка вкладок (только `tabs`) и GET-форма фильтров с кнопкой «Показать»;
  - блоки `analytics_content` и `extrahead` (`{{ block.super }}` плюс `chart.umd.min.js`, `charts.js`, `analytics.css`; статику добавит Task 5).
- В `ebase/templates/admin/base_site.html` переопределяется `{% block userlinks %}`: `{% if perms.analytics %}<a href="{% url 'analytics:index' %}">Статистика</a> / {% endif %}{{ block.super }}`.

- [ ] **Step 1: Write the failing tests** (`test_views.py`; пользователи: `superuser`; `staff` с `is_staff=True` без прав; `finance_staff` с `is_staff=True` и правом `view_finance`)

```python
def test_superuser_sees_finance_tab(self):  # GET analytics:finance → 200, contains "Деньги"
def test_staff_without_permission_gets_403_on_tab(self):  # staff → 403
def test_staff_without_permission_gets_403_on_index(self):
def test_index_redirects_to_first_permitted_tab(self):  # finance_staff → 302 на reverse("analytics:finance")
def test_anonymous_redirected_to_admin_login(self):  # 302, "/admin/login/" in response["Location"]
def test_header_link_shown_with_permission(self):  # finance_staff GET admin:index → contains reverse("analytics:index")
def test_header_link_hidden_without_permission(self):  # staff GET admin:index → not contains
```

- [ ] **Step 2: Run, expect FAIL** (`NoReverseMatch`).
- [ ] **Step 3: Implement** по интерфейсам. В `ebase_site/urls.py` вставить `path("admin/analytics/", include("analytics.urls"))` перед `path("admin/", admin.site.urls)`.
- [ ] **Step 4: Run, expect PASS**
  - Run: `python manage.py test analytics --settings=ebase_site.test_settings`
  - Expected: все тесты `analytics` зелёные.
- [ ] **Step 5: Commit** — `feat(analytics): раздел «Статистика» в админке, вкладки и права`

---

### Task 5: Графики: спецификация, Chart.js, `charts.js`, стили

Перед этим таском **загрузить скилл `dataviz`**: по нему подбираются палитра, разметка плиток и подписи осей.

**Files:**
- Create: `analytics/charts.py`, `analytics/links.py`, `analytics/templatetags/__init__.py`, `analytics/templatetags/analytics_tags.py`, `analytics/templates/analytics/includes/chart.html`, `analytics/static/analytics/vendor/chart.umd.min.js`, `analytics/static/analytics/js/charts.js`, `analytics/static/analytics/css/analytics.css`, `analytics/tests/test_charts.py`
- Modify: `analytics/templates/analytics/base.html` (подключить статику)

**Interfaces:**
- Produces:
  - `analytics.charts.to_float(value) -> float`: `None → 0.0`; Decimal/int → `round(float(value), 2)`.
  - `analytics.charts.chart_spec(kind: str, labels: list[str], datasets: list[dict], *, fmt: str = "money", horizontal: bool = False, stacked: bool = False, links: list[str | None] | None = None) -> dict`.
    - `kind`: `"bar"` | `"line"` | `"scatter"`.
    - Ключи датасета:
      - `label` — название серии;
      - `data` — числа, либо для scatter точки `{"x", "y", "label", "url"}`;
      - `kind` — тип отрисовки серии, необязательный, для смешанного bar+line;
      - `axis` — `"y"` | `"y2"`, необязательный: `y2` — шкала процентов справа;
      - `sign_colors` — `bool`, необязательный: окраска по знаку для расходящихся столбцов.
    - `fmt`: `"money"` | `"count"` | `"percent"`.
    - Возвращает JSON-совместимый dict с ключами `kind, labels, datasets, format, horizontal, stacked, links, empty`. Числа приводятся к float. `empty=True`, если нет меток или точек или все значения равны 0.
  - `analytics.links.changelist_url(admin_name: str, **params) -> str`. Пример: `changelist_url("contracts_contract", id__in=[uuid1, uuid2])` → `"/admin/contracts/contract/?id__in=uuid1%2Cuuid2"`. Списки склеиваются запятой, `None`-параметры отбрасываются.
  - `analytics.links.change_url(admin_name: str, pk) -> str`.
  - Фильтры шаблонов `{% load analytics_tags %}`:
    - `money` → `format_money(v) + " ₽"` (`None` → «—»);
    - `pct` → `"12,5 %"`, `None` → «—»;
    - `delta` → `"+12,5 %"` или `"−3,0 %"`, `None` → «—», с CSS-классом по знаку через `delta_class`.
  - `includes/chart.html` принимает `spec` и `chart_id`. Выводит `{{ spec|json_script:chart_id }}` и `<canvas data-chart="{{ chart_id }}">`; при `spec.empty` вместо canvas пишет «Нет данных за выбранный период».
  - `charts.js`:
    - на `DOMContentLoaded` строит графики для всех `canvas[data-chart]`;
    - форматирует числа через `Intl.NumberFormat("ru-RU")` (деньги без копеек + « ₽»);
    - клик по элементу ведёт на `links[index]`, а у scatter — на `point.url`;
    - цвета берёт из CSS-переменных `--an-c1…--an-c6`, `--an-positive`, `--an-negative`, `--an-grid`, `--an-text`;
    - пересоздаёт графики при смене `data-theme` на `<html>` (`MutationObserver`).
- `analytics.css`:
  - переменные для светлой и тёмной темы (`:root`, `@media (prefers-color-scheme: dark)`, `html[data-theme="dark"]`, `html[data-theme="light"]`, как в админке Django 4.2);
  - сетка плиток и карточек графиков, на ширине ≤ 767px в одну колонку;
  - стили вкладок и тепловой карты/таблиц.

- [ ] **Step 1: Write the failing tests** (`test_charts.py`)

```python
def test_chart_spec_converts_decimals(self):
    spec = chart_spec("bar", ["янв 2026"], [{"label": "Пришло", "data": [Decimal("10.505")]}])
    self.assertEqual(spec["datasets"][0]["data"], [10.51])
    self.assertFalse(spec["empty"])
def test_chart_spec_empty_when_all_zero(self):  # data [0, Decimal("0")] → empty True
def test_chart_spec_empty_without_labels(self):
def test_chart_spec_is_json_serializable(self):  # json.dumps(spec) не падает
def test_changelist_url_joins_lists(self):
    self.assertEqual(changelist_url("contracts_contract", id__in=["a", "b"], client=None),
                     "/admin/contracts/contract/?id__in=a%2Cb")
def test_money_filter(self):  # money(Decimal("20000")) == "20 000,00 ₽"; money(None) == "—"
def test_delta_filter(self):  # delta(Decimal("12.5")) == "+12,5 %"; delta(None) == "—"
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Download Chart.js и проверить**

```bash
curl -fsSL https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js -o ebase_site/analytics/static/analytics/vendor/chart.umd.min.js
head -c 120 ebase_site/analytics/static/analytics/vendor/chart.umd.min.js   # ожидается баннер "Chart.js v4.5.1"
```

- [ ] **Step 4: Implement** `charts.py`, `links.py`, теги, `includes/chart.html`, `charts.js`, `analytics.css`; подключить статику в `base.html`.
- [ ] **Step 5: Run, expect PASS.**
- [ ] **Step 6: Commit** — `feat(analytics): графики Chart.js, спецификации и стили`

---

### Task 6: Расчёты «Деньги» — плитки и помесячные ряды

**Files:**
- Create: `analytics/services/__init__.py`, `analytics/services/finance.py`, `analytics/tests/factories.py`, `analytics/tests/test_finance.py`

**Interfaces:**
- Consumes: `Period` (Task 3).
- Produces:
  - `analytics/tests/factories.py`:
    - `make_client(name="Клиент", inn=None) -> Client` (уникальный ИНН по счётчику);
    - `make_contract(client, number, conclusion_date, amount, **fields) -> Contract`;
    - `make_payment(contract, date, amount) -> Payment`;
    - `make_shipment(contract, shipment_dt, total) -> SparePartShipmentM2M`: одна строка, `quantity=1`, `price=total`; `Unit "шт."` и пользователь создаются по необходимости.
  - `analytics/services/finance.py`:
    - `contracts_in_period(period: Period, client: Client | None = None) -> QuerySet[Contract]` (`conclusion_date` в периоде).
    - `TOTAL_KEYS = ("contract_amount", "payment_amount", "expenses_amount", "debt", "profit")`.
    - `finance_kpis(period: Period, client=None) -> dict`. Возвращает `{"current": totals, "previous": totals, "delta_pct": {key: Decimal | None}}`.
      - `totals`: `{"count": int, **{k: Decimal}, "margin_pct": Decimal | None}`.
      - `margin_pct = profit / payment_amount × 100` с округлением до 0,1, при `payment_amount == 0` — `None`.
      - `delta_pct[k] = (cur − prev) / |prev| × 100` с округлением до 0,1, при `prev == 0` — `None`. Ключи — `TOTAL_KEYS`, `"count"` и `"margin_pct"`; для маржи дельта считается в процентных пунктах (`cur − prev`).
    - `money_flow(period: Period, client=None) -> dict` (фильтр клиента — через контракт). Возвращает `{"months": list[date], "inflow", "spare_parts", "trips", "other", "outflow", "balance"}`; значения — `list[Decimal]` той же длины, что `months`.
      - `inflow`: `Payment.amount` по `date`.
      - `spare_parts`: `SparePartShipmentM2M.sum` по `shipment.shipment_dt`, только если `shipment.contract` задан.
      - `other`: `ContractExpense.sum` по `date`, а при пустой дате по `timezone.localdate(create_dt)`.
      - `trips`: `BusinessTripContractExpense.amount` по `business_trip.end_dt`.
      - `outflow`: сумма трёх рядов затрат; `balance = inflow − outflow`.
    - `concluded_by_month(period: Period, client=None) -> dict`: `{"months", "amount", "cumulative"}`.

- [ ] **Step 1: Write the failing tests** (`test_finance.py`; `P = Period(date(2026, 1, 1), date(2026, 12, 31))`)

```python
def test_kpis_match_contract_totals(self):
    # 2 контракта в 2026 (100000 с оплатой 30000; 50000 без оплат) + 1 контракт в 2025 (80000)
    k = finance_kpis(P)
    self.assertEqual(k["current"]["count"], 2)
    self.assertEqual(k["current"]["contract_amount"], Decimal("150000"))
    self.assertEqual(k["current"]["debt"], Decimal("120000"))
    self.assertEqual(k["current"]["margin_pct"], Decimal("100.0"))  # profit 30000 / payment 30000
    self.assertEqual(k["previous"]["contract_amount"], Decimal("80000"))
    self.assertEqual(k["delta_pct"]["contract_amount"], Decimal("87.5"))
def test_kpis_client_filter(self):
def test_kpis_empty_period(self):  # все суммы 0, margin_pct None, delta_pct[*] None
def test_money_flow_by_actual_dates(self):
    # контракт 2025-12-20; оплата 2026-02-10 = 40000; отгрузка по контракту 2026-03-05 на 1000;
    # отгрузка без контракта 2026-03-06 на 999 — не учитывается;
    # ContractExpense без даты, create_dt в марте 2026 (выставить через .update()), sum 500;
    # доля командировки 300, командировка с end_dt 2026-04-02: создать командировку без контрактов,
    # затем BusinessTripContractExpense напрямую (иначе сигналы пересинхронизируют доли)
    f = money_flow(P)
    self.assertEqual(len(f["months"]), 12)
    self.assertEqual(f["inflow"][1], Decimal("40000"))
    self.assertEqual(f["spare_parts"][2], Decimal("1000"))
    self.assertEqual(f["other"][2], Decimal("500"))
    self.assertEqual(f["trips"][3], Decimal("300"))
    self.assertEqual(f["balance"][2], Decimal("-1500"))
def test_concluded_by_month_cumulative(self):  # 100000 в янв, 50000 в мар → cumulative[2] == 150000
```

- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** по интерфейсам. Группировка по месяцам — общий приватный хелпер `_bucket_by_month(pairs: Iterable[tuple[date, Decimal]], months: list[date]) -> list[Decimal]`.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(analytics): расчёт плиток и движения денег`

---

### Task 7: Расчёты «Деньги» — возраст долга и «оказано × оплачено»

**Files:**
- Modify: `analytics/services/finance.py`, `analytics/tests/test_finance.py`

**Interfaces:**
- Produces:
  - `AGING_BUCKETS = [("not_due", "Срок не наступил"), ("0_30", "0–30 дн."), ("31_90", "31–90 дн."), ("91_180", "91–180 дн."), ("180_plus", "Более 180 дн.")]`.
  - `debt_aging(today: date, client=None) -> list[dict]`.
    - Берутся все контракты с `debt > 0`, период не учитывается.
    - Возраст = `(today − (service_end_date or conclusion_date)).days`. Отрицательный → `not_due`; 0–30 → `0_30`, и так далее.
    - Результат — список в порядке `AGING_BUCKETS`, все корзины всегда присутствуют: `{"key", "label", "count": int, "amount": Decimal, "ids": list[str]}`.
  - `status_matrix(period: Period, client=None) -> dict`.
    - Возвращает `{"columns": [{"key", "label"}], "rows": [{"key", "label", "cells": [{"payment_status", "count", "amount"}]}]}`.
    - Строки — `Contract.SERVICES_PROVIDED_CHOICES`, столбцы — `Contract.PAYMENT_STATUS_CHOICES`, в их порядке. `amount = Σ contract_amount`.

- [ ] **Step 1: Write the failing tests**

```python
def test_debt_aging_buckets(self):  # today 2026-10-16; service_end_date 2026-10-01 (15 дн.), 2026-06-01 (137 дн.)
    a = {b["key"]: b for b in debt_aging(date(2026, 10, 16))}
    self.assertEqual(a["0_30"]["count"], 1); self.assertEqual(a["91_180"]["count"], 1)
def test_debt_aging_future_end_date(self):  # service_end_date 2026-12-31 → not_due
def test_debt_aging_falls_back_to_conclusion_date(self):  # service_end_date None, conclusion 2026-03-01 → 180_plus
def test_debt_aging_skips_paid(self):  # контракт с debt 0 не попадает никуда; ids содержат str(pk)
def test_status_matrix_counts(self):  # fully+no_receipts = 1 (100000); not_yet+paid = 1; остальные ячейки 0; 3×3
```

- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement.** **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(analytics): возраст долга и матрица «оказано × оплачено»`

---

### Task 8: Расчёты «Деньги» — клиенты и контракты

**Files:**
- Modify: `analytics/services/finance.py`, `analytics/tests/test_finance.py`

**Interfaces:**
- Produces:
  - `top_clients(period: Period, limit: int = 10) -> dict`.
    - Группировка `Σ payment_amount` по клиенту среди контрактов периода. Клиенты с нулевой суммой исключаются. Сортировка по убыванию.
    - Возвращает:
      - `"clients": [{"id", "name", "amount", "cumulative_pct"}]` — первые `limit`; `cumulative_pct` — накопленная доля от общей суммы, Decimal до 0,1;
      - `"total"`;
      - `"clients_total"`;
      - `"clients_for_80"` — минимальное N, при котором накопленная доля ≥ 80.
  - `client_profitability(period: Period, limit: int = 10) -> dict`: `{"best": [{"id", "name", "profit"}], "losers": [...]}`. В `best` первые `limit` с `profit > 0` по убыванию; в `losers` все с `profit < 0` по возрастанию.
  - `contracts_scatter(period: Period, client=None) -> list[dict]`: `[{"id", "label": "<номер> — <клиент>", "x": contract_amount, "y": margin_pct}]`, только при `payment_amount > 0`.
  - `payment_discipline(period: Period, client=None) -> list[dict]`.
    - Берутся контракты периода с `payment_status="paid"`. Дни = `max(payments.date) − (service_end_date or conclusion_date)`.
    - Возвращает `[{"client_id", "name", "avg_days": Decimal (0,1), "contracts": int}]` по убыванию `avg_days`.

- [ ] **Step 1: Write the failing tests**

```python
def test_top_clients_pareto(self):  # оплаты по клиентам 60/30/10 → cumulative_pct [60.0, 90.0, 100.0], clients_for_80 == 2
def test_top_clients_excludes_zero(self):
def test_client_profitability_split(self):  # прибыль +500, +100, −200 → best [500, 100], losers [−200]
def test_contracts_scatter_skips_unpaid(self):  # контракт без оплат не попадает; y = profit/payment*100
def test_payment_discipline_days(self):
    # оплачен: конец услуг 2026-03-01, последняя оплата 2026-03-31 → 30;
    # второй контракт того же клиента: предоплата за 10 дней → −10; avg_days 10.0, contracts 2
```

- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement.** **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(analytics): рейтинг и рентабельность клиентов, платёжная дисциплина`

---

### Task 9: Страница вкладки «Деньги»

**Files:**
- Modify: `analytics/views.py` (`FinanceView.get_context_data`), `analytics/templates/analytics/finance.html`, `analytics/tests/test_views.py`

**Interfaces:**
- Consumes:
  - всё из `services/finance.py` (Tasks 6–8);
  - `chart_spec`, `changelist_url`, `change_url` (Task 5);
  - `month_label` (Task 3).
- Produces: контекст шаблона.
  - `kpis`.
  - `charts`: dict спецификаций с ключами `money_flow`, `concluded`, `cost_structure`, `debt_aging`, `top_clients`, `profitability`, `scatter`.
  - `matrix`: `status_matrix` плюс `url` у каждой ячейки.
  - `aging`.
  - `discipline`.
  - `client`.

**Разметка страницы (сверху вниз), спецификации графиков:**
1. **Плитки.** Шесть штук: «Сумма контрактов», «Оплачено», «Затраты», «Долг», «Прибыль», «Маржа». Под значением дельта к прошлому году и подпись периода сравнения.
2. **«Движение денег».** `bar` по месяцам: «Пришло» и «Ушло», плюс `line` «Сальдо» (`kind: "line"`).
3. **«Заключено контрактов».** `bar` «Сумма» плюс `line` «Накопительно».
4. **«Структура затрат».** `bar`, `stacked`: «Запчасти», «Командировки», «Прочие».
5. **«Возраст долга».** `bar`, `horizontal`. `links` — `changelist_url("contracts_contract", id__in=ids)` у непустых корзин. Подпись «на сегодня, период не учитывается».
6. **«Оказано × оплачено».** Серверная таблица 3×3: количество и сумма. Ссылка ячейки — `changelist_url("contracts_contract", services_provided=…, payment_status=…, conclusion_date__gte=…, conclusion_date__lte=…, client=<pk или None>)`.
7. **«Топ клиентов».** `bar` «Оплачено» плюс `line` «Накопленная доля» (`axis: "y2"`, `fmt` линии percent). Подпись «N из M клиентов дают 80 % оплат», «все клиенты, фильтр клиента не применяется».
8. **«Рентабельность клиентов».** `bar`, `horizontal`, `sign_colors`. `best` и `losers` склеены, убыточные внизу.
9. **«Контракты: сумма и маржа».** `scatter`, точка с `url = change_url("contracts_contract", id)`.
10. **«Платёжная дисциплина».** Серверная таблица: клиент, средний срок оплаты (дн.), контрактов. Отрицательное значение подписано «предоплата».

- [ ] **Step 1: Write the failing tests**

```python
def test_finance_page_empty_db(self):  # superuser → 200; contains "Нет данных"; contains "—"
def test_finance_page_with_data(self):
    # контракт 2026 с оплатой → 200; contains format_money суммы контракта;
    # context["charts"]["money_flow"]["empty"] is False
def test_finance_page_bad_params(self):  # ?preset=zzz&date_from=abc&client=not-a-uuid → 200
def test_finance_matrix_links_filter_contract_changelist(self):
    # url ячейки ведёт на changelist с services_provided и payment_status;
    # GET по нему суперпользователем → 200 (админка принимает фильтр)
def test_finance_aging_link_opens_changelist(self):  # url корзины с id__in → GET 200, в выдаче номер контракта
```

- [ ] **Step 2: Run, expect FAIL.** **Step 3: Implement** view и шаблон. **Step 4: Run, expect PASS.**
- [ ] **Step 5: Ручная проверка в браузере** (`python manage.py runserver`, вход суперпользователем, `/admin/analytics/`):
  - графики рисуются;
  - переключатель темы перекрашивает графики;
  - при ширине 375px плитки и графики в одну колонку, без горизонтальной прокрутки страницы;
  - клик по корзине долга и по ячейке матрицы открывает отфильтрованный список контрактов;
  - смена периода и клиента меняет цифры;
  - плитки совпадают с «Итого» в списке контрактов, отфильтрованном по тем же датам заключения.
- [ ] **Step 6: Commit** — `feat(analytics): вкладка «Деньги»`

---

### Task 10: Документация и финальный прогон

**Files:**
- Modify: `AGENTS.md`:
  - строка `analytics` в таблице приложений;
  - абзац в «Архитектурных особенностях» про права, группу и `services/`;
  - `analytics/tests` в «Наборах тестов»;
  - строка про пересчёт `debt` в `Contract.save()` в разделе «Сигналы».

- [ ] **Step 1:** `black ebase_site` → без ошибок.
- [ ] **Step 2:** `python manage.py test --settings=ebase_site.test_settings`. Ожидание: падают только пять базовых тестов из Global Constraints, остальные (включая новые) проходят.
- [ ] **Step 3:** `python manage.py makemigrations --check --dry-run` → `No changes detected`.
- [ ] **Step 4:** `python manage.py collectstatic --dry-run --noinput` с обычными настройками. Новые файлы `analytics/…` находятся, ошибок `ManifestStaticFilesStorage` нет.
- [ ] **Step 5: Commit** — `docs(analytics): раздел «Статистика» в AGENTS.md`

---

## Вне этого плана

Этапы 2–4 (Склад и командировки, Сервис и надёжность, Парк и продажи) планируются отдельно после завершения этапа 1.

Открытый вопрос к этапу 2. В «Отчёте по денежным средствам» нет формулы сальдо: ячейки «остаток на начало/конец месяца» пустые. Поэтому формулу «получено − потрачено» для подотчёта надо согласовать с пользователем.
