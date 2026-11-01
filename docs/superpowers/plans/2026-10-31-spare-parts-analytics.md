# Вкладка «Запчасти» (Аналитика) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Четвёртая вкладка раздела «Аналитика» — «Запчасти»: текущий склад, движение V1/V2, закупки и себестоимость отгрузок V2, оценочная стоимость остатка, сроки годности, неликвиды, пополнение и контроль данных.

**Architecture:** Вкладка повторяет устройство «Оборудования». `SparePartSet.load()` один раз загружает и нормализует справочник, остатки и движения V1/V2; чистые функции виджетов получают `source` и работают в Python. `SparePartsView` добавляет ссылки и спецификации существующих графиков, шаблон разделён на четыре include.

**Tech Stack:** Python 3.11, Django 4.2.16, Decimal, Django TestCase на SQLite (`ebase_site.test_settings`), Chart.js 4.5.1 через существующие `charts.py` и `charts.js`. Новых зависимостей нет.

**Spec:** `docs/superpowers/specs/2026-10-31-spare-parts-analytics-design.md`. Исполнитель читает описание и план вместе.

## Global Constraints

- Текст интерфейса, комментарии и docstring — по-русски. Названия показателей и корзин берутся из описания.
- Новых зависимостей нет. Графики создаются только через `analytics.charts.chart_spec`; `charts.js` и Chart.js не меняются.
- Модели `spare_part`, их сигналы, FIFO и складские списки админки не меняются. Миграция нужна только для права новой вкладки.
- Все виджеты используют один `SparePartSet`, загруженный в начале запроса. Запросов в циклах и обращений к related-объектам, не загруженным в `load()`, нет.
- Количества и деньги — `Decimal`; float из моделей преобразуется через `Decimal(str(value))`. Даты, корзины и группировки считаются в Python.
- Общие количества разных запчастей не суммируются. Денежные графики используют только V2; архивные V1 участвуют только в количествах и истории расхода.
- Нулевая цена считается неизвестной. Стоимость остатка всегда подписана как «Оценочная стоимость остатка»; полнота цен видна рядом.
- Снимки склада не зависят от периода. Спрос использует последние 365 календарных дней: `today - 364 … today`; будущие отгрузки исключены.
- Ссылка `?id__in=` содержит не больше `MAX_LINK_IDS = 90` id. Иначе — документированный фильтр-надмножество или отсутствие ссылки.
- Тесты запускаются из `ebase_site/` после `source ../.venv/bin/activate`: `python manage.py test <label> --settings=ebase_site.test_settings`.
- В полном наборе сейчас пять известных падений в старых тестах `ebase` и `contracts`; новых падений быть не должно. В рабочую БД не ходить, `.env` не читать.
- `black` применяется только к изменённым Python-файлам. Работа идёт в ветке `feature/analytics-spare-parts`, в main не сливается.

## Review Focus

1. **Неизвестные и нулевые цены, архив без стоимости.** Они не превращаются в бесплатные запчасти и не завышают полноту оценки. Тесты в Задачах 2–4.
2. **Отрицательные, нулевые и отсутствующие остатки.** Отрицательные не уменьшают стоимость, нулевые могут быть кандидатами на пополнение, отсутствие `SparePartCount` трактуется как ноль. Тесты в Задачах 3 и 5.
3. **Границы дат.** Первый и последний день периода включены; сегодняшний срок годности не просрочен; 180/365-дневные окна не имеют ошибки на один день; будущие отгрузки не создают спрос. Тесты в Задачах 3–5.
4. **Удалённые запчасти, отгрузки без ремонта и модели без названия.** Страница отвечает 200, не выводит «None», не теряет общую себестоимость из-за строк без оборудования. Тесты в Задачах 2, 4 и 6.
5. **Большие списки и рост данных.** Число запросов постоянно; длинные `id__in` не создаются; таблица ограничена 100 строками с указанием общего числа отобранных. Тесты в Задачах 3, 5 и 6.

---

### Task 1: Право, фильтры и каркас вкладки

**Files:**
- Modify: `ebase_site/analytics/models.py`, `navigation.py`, `urls.py`, `filters.py`
- Create: `ebase_site/analytics/migrations/0006_spare_parts_tab.py`
- Create: `ebase_site/analytics/views_spare_parts.py`
- Create: `ebase_site/analytics/templates/analytics/spare_parts.html`
- Create: `ebase_site/analytics/templates/analytics/spare_parts/{overview,movement,expiration,control}.html`
- Test: `ebase_site/analytics/tests/test_migrations.py`, `test_filters.py`, `test_views.py`

**Interfaces:**
- Produces:
  - право `analytics.view_spare_parts` («Аналитика: Запчасти»);
  - `Tab("spare_parts", "Запчасти", "analytics.view_spare_parts", "analytics:spare_parts")` четвёртым в `TABS`;
  - URL `/admin/analytics/spare-parts/`;
  - `EXPIRATION_CHOICES`, `STOCK_CHOICES`, `NONMOVING_CHOICES` и значения по умолчанию `"all"`;
  - `@dataclass(frozen=True) class SparePartFilters` с полями `spare_part: SparePart | None = None`, `equipment: Equipment | None = None`, `expiration: str = "all"`, `stock: str = "all"`, `nonmoving: str = "all"` и `is_empty -> bool`;
  - `SparePartFilterForm(PeriodForm)` с одноимёнными полями и `get_filters() -> SparePartFilters`;
  - `SparePartsView(AnalyticsTabView)` с `tab_key = "spare_parts"`, `form_class = SparePartFilterForm`, `template_name = "analytics/spare_parts.html"`.

- [ ] **Step 1: Зафиксировать исходное состояние**

Run: `python manage.py test analytics spare_part --settings=ebase_site.test_settings`
Expected: OK. Если есть падения, записать их имена до изменений и не исправлять в рамках вкладки.

- [ ] **Step 2: Написать падающие тесты миграции**

В `test_migrations.py`:
- общий набор прав теперь включает `view_spare_parts`;
- хелперы состояния до 0006 удаляют это право, чтобы старые тесты 0002–0005 продолжали моделировать прошлое;
- новый `SparePartsTabMigrationTests` по образцу `EquipmentTabMigrationTests`:
  - `test_creates_permission_and_grants_group` — право создано с точным именем и выдано группе «Аналитика»;
  - `test_without_group_creates_permission_only`;
  - `test_is_idempotent` — два вызова `add_spare_parts_tab` не создают дубликатов;
  - `test_reverse_removes_permission` — остаются три прежних права;
  - `test_forward_after_reverse` — повторный прямой проход восстанавливает только новое право.

- [ ] **Step 3: Написать падающие тесты фильтров**

`SparePartFilterFormTests` в `test_filters.py`:
- `test_spare_part_form_defaults` — пустой `SparePartFilters`, `is_empty`, текущий год;
- `test_spare_part_form_values` — все пять фильтров возвращаются;
- `test_spare_part_form_garbage_falls_back` — неверные UUID и choice не ломают период и дают значения по умолчанию;
- `test_spare_part_form_lists_only_used_equipment` — модель без связанных запчастей отсутствует;
- `test_spare_part_labels` — запчасть выводится с артикулом, модель без `full_name` использует `short_name`, без обоих — «Модель без названия»;
- `test_spare_part_empty_labels` — «Все запчасти», «Все модели», «Все», без обязательного выбора.

- [ ] **Step 4: Написать падающие тесты доступа и каркаса**

В `AnalyticsViewsTests` добавить `_spare_parts_staff()` по образцу других вкладок:
- `test_superuser_sees_spare_parts_tab` — 200 и «Запчасти»;
- `test_staff_without_spare_parts_permission_gets_403`;
- `test_index_redirects_to_spare_parts_when_only_it_permitted` — точный URL;
- `test_sidebar_lists_spare_parts_tab_with_permission` — пункт в `available_apps` и `app_list`;
- `test_spare_parts_tab_follows_equipment_in_tabs` — порядок `finance, trips, equipment, spare_parts`;
- `test_spare_parts_page_has_sections` — заголовки «Склад», «Движение и расход», «Сроки годности», «Неликвиды и контроль данных».

- [ ] **Step 5: Запустить тесты и проверить причину падения**

Run: `python manage.py test analytics.tests.test_migrations analytics.tests.test_filters analytics.tests.test_views --settings=ebase_site.test_settings`
Expected: FAIL/ERROR только из-за отсутствующих права, миграции, формы, URL и view.

- [ ] **Step 6: Реализовать каркас**

- Добавить право в `AnalyticsAccess.Meta.permissions`.
- Написать `0006_spare_parts_tab` по образцу 0005: `AlterModelOptions` с четырьмя правами, идемпотентные `add_spare_parts_tab`/`remove_spare_parts_tab`, зависимость от `0005_equipment_tab`.
- Подключить четвёртый `Tab` и `path("spare-parts/", admin.site.admin_view(SparePartsView.as_view()), name="spare_parts")`.
- Объявить choices:
  - срок: `all`, `overdue`, `30`, `90`, `180`, `missing`;
  - остаток: `all`, `positive`, `zero`, `negative`;
  - движение: `all`, `180`, `365`.
- Queryset запчастей: все, `select_related("unit")`, порядок `name, article`. Queryset моделей: только `Equipment.objects.filter(spare_part_equipment__isnull=False).distinct()`, порядок `full_name, short_name`.
- Label запчасти — существующий `str(SparePart)`; label модели строить через `full_name or short_name or "Модель без названия"`, не полагаться на `str(Equipment)`.
- View пока возвращает `filters` и пустой `charts`. Главный шаблон наследует `analytics/base.html` и подключает четыре include; каждый include пока содержит только пустой контейнер своего блока.

- [ ] **Step 7: Проверить миграции и тесты**

Создать вне репозитория `migcheck_settings.py` по образцу предыдущих планов (`from ebase_site.test_settings import *`, `MIGRATION_MODULES = {}`).

Run: `PYTHONPATH=<scratchpad> python manage.py makemigrations analytics --check --dry-run --settings=migcheck_settings`
Expected: `No changes detected in app 'analytics'`.

Run: `python manage.py test analytics --settings=ebase_site.test_settings`
Expected: OK.

- [ ] **Step 8: Commit**

```bash
git add ebase_site/analytics
git commit -m "feat(analytics): каркас вкладки «Запчасти» и право доступа"
```

---

### Task 2: Набор данных, архив V1/V2 и отбор запчастей

**Files:**
- Create: `ebase_site/analytics/services/spare_parts.py`
- Modify: `ebase_site/analytics/tests/factories.py`
- Create: `ebase_site/analytics/tests/test_spare_parts.py`

**Interfaces:**
- Consumes: `SparePartFilters` и `Period` из Задачи 1.
- Produces фабрики:
  - `make_spare_part(name="Датчик", article=None, unit="шт.", is_expiration=False, equipment=()) -> SparePart`;
  - `make_stock(part, amount, expiration_dt=None) -> SparePartCount`;
  - `make_supply(part, supply_dt, quantity, price=100, expiration_dt=None, archive=False) -> SparePartSupplyItem | SparePartSupply`;
  - `make_part_shipment(part, shipment_dt, quantity, price=100, expiration_dt=None, service=None, contract=None, archive=False) -> SparePartShipmentM2M | SparePartShipment`.
- Produces сервис:
  - `DEMAND_DAYS = 365`;
  - `window_start(today: date, days: int) -> date` — `today - timedelta(days=days - 1)`;
  - `@dataclass(frozen=True) SupplyRow`: `document_id`, `part_id`, `supply_dt`, `quantity: Decimal`, `amount: Decimal | None`, `price: Decimal | None`, `expiration_dt`, `is_archive: bool`;
  - `@dataclass(frozen=True) ShipmentRow`: `document_id`, `part_id`, `shipment_dt`, `quantity: Decimal`, `cost: Decimal | None`, `price: Decimal | None`, `expiration_dt`, `equipment_id`, `equipment_label: str | None`, `is_archive: bool`;
  - `class SparePartSet` с `parts`, `counts`, `supplies`, `shipments`, `part_by_id`;
  - `SparePartSet.load() -> SparePartSet`;
  - `parts_of(filters: SparePartFilters, today: date) -> list[SparePart]`;
  - `stock_total(part_id) -> Decimal` — отсутствие записей даёт 0;
  - `last_shipment(part_id, today) -> ShipmentRow | None`;
  - `supplies_in(part_ids, period) -> list[SupplyRow]`;
  - `shipments_in(part_ids, period) -> list[ShipmentRow]`;
  - `_source(source) -> SparePartSet`.

- [ ] **Step 1: Написать падающие тесты нормализации**

`SparePartSetTests` в `test_spare_parts.py`:
- `test_load_normalizes_v2_and_archive` — V2 сохраняет сумму/цену/оборудование, V1 даёт `is_archive=True`, `amount/cost=None`, количество обеих версий — Decimal;
- `test_load_ignores_movements_without_part` — архивная запись с `spare_part=None` не попадает в набор и не падает;
- `test_stock_total_without_count_is_zero` — справочная запчасть без `SparePartCount` имеет остаток 0;
- `test_last_shipment_uses_history_but_not_future` — V1 участвует, будущая V2 игнорируется, при равных датах детерминированный порядок;
- `test_period_movements_include_boundaries_and_both_versions` — первая/последняя дата включены, соседние дни исключены;
- `test_load_makes_constant_number_of_queries` — ровно 7 запросов: запчасти + prefetch моделей, остатки, поставки V2, поставки V1, отгрузки V2, отгрузки V1.

- [ ] **Step 2: Написать падающие тесты фильтров набора**

- `test_parts_of_spare_part_and_compatible_equipment` — фильтры каталога сужают список;
- `test_parts_of_stock_states` — положительный/нулевой/отрицательный по сумме всех записей; отсутствие остатка — ноль;
- `test_parts_of_expiration_selects_whole_part` — у части с двумя сроками фильтр `30` оставляет всю запчасть, если хотя бы одна положительная запись в окне; просроченная и нулевая записи не дают совпадения;
- `test_parts_of_nonmoving_boundaries` — для 180 дней отгрузка `today - 179` исключает неликвид, `today - 180` оставляет; отсутствие отгрузок — неликвид только при положительном остатке;
- `test_parts_of_combines_filters` — условия применяются через AND.

- [ ] **Step 3: Запустить и убедиться, что модуль отсутствует**

Run: `python manage.py test analytics.tests.test_spare_parts --settings=ebase_site.test_settings`
Expected: ImportError `analytics.services.spare_parts`.

- [ ] **Step 4: Реализовать фабрики и `SparePartSet`**

Фабрики создают реальные записи ORM и не отключают сигналы. `make_stock` использует `get_or_create(part, expiration_dt)` и обновляет `amount`. Для V1 создаётся связанный `SparePartCount`; документы получают уникальные номера через существующие счётчики или новые.

`load()`:
1. Запчасти: `select_related("unit")` + `prefetch_related("equipment")`.
2. Все `SparePartCount` без lazy-обращений к запчасти: связи разрешаются через `part_by_id`.
3. Поставки V2: `SparePartSupplyItem.objects.select_related("supply")`.
4. Поставки V1: только поля, нужные для `SupplyRow`; записи без запчасти пропускаются.
5. Отгрузки V2: `SparePartShipmentM2M.objects.select_related("shipment__service__equipment_accounting__equipment")`.
6. Отгрузки V1: `select_related("spare_part_count")`; удалённые запчасти пропускаются.

`equipment_id` у V2 — `shipment.service.equipment_accounting.equipment_id`, если вся цепочка существует, иначе None. `equipment_label` сразу заполняется из `equipment.full_name or equipment.short_name or "Модель без названия"`; у V1 оба значения None. В `parts_of` нет ORM-запросов: состояние остатка, срок и неликвид вычисляются по уже загруженным спискам.

- [ ] **Step 5: Запустить тесты набора**

Run: `python manage.py test analytics.tests.test_spare_parts --settings=ebase_site.test_settings`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add ebase_site/analytics/services/spare_parts.py ebase_site/analytics/tests
git commit -m "feat(analytics): набор данных склада запчастей V1/V2"
```

---

### Task 3: Остатки, оценка и основная складская таблица

**Files:**
- Modify: `ebase_site/analytics/services/spare_parts.py`
- Modify: `ebase_site/analytics/views_spare_parts.py`
- Modify: `ebase_site/analytics/templates/analytics/spare_parts/overview.html`
- Test: `ebase_site/analytics/tests/test_spare_parts.py`, `test_views.py`

**Interfaces:**
- Consumes: Задача 2.
- Produces сервис:
  - `known_price(part_id, expiration_dt, source=None) -> Decimal | None` — сначала точная пара запчасть/срок, затем вся запчасть; только V2 с `quantity > 0`, `price > 0`;
  - `stock_value(count, source=None) -> Decimal | None` — None для неположительного остатка или неизвестной цены;
  - `overview_kpis(period, today, filters, source=None) -> dict` — `positive_count`, `stock_value`, `priced_count`, `priced_total`, `purchase_amount`, `shipment_cost`;
  - `stock_rows(period, today, filters, source=None) -> list[dict]`; строка содержит `id`, `label`, `article`, `unit`, `stock`, `average_price`, `stock_value`, `value_complete`, `received`, `shipped`, `average_monthly`, `days_stock`, `last_shipment`, `nonmoving_180`, `nonmoving_365`.
- Produces view:
  - `SPARE_PARTS = "spare_part_sparepart"`;
  - `_overview_context(source, filters, period, today) -> dict` — `tiles`, `stock_rows`, `stock_rows_total`, `stock_rows_limit=100`, `kpis`;
  - каждая строка получает `url = change_url(SPARE_PARTS, row["id"])`.

- [ ] **Step 1: Написать падающие тесты цен и оценки**

`StockValuationTests`:
- `test_known_price_weighted_by_expiration_then_part_fallback` — поставки 5×100 и 5×200 дают 150; для другого срока используется fallback; нулевая цена и нулевое количество исключены;
- `test_stock_value_positive_only` — положительный остаток оценивается, ноль и отрицательный дают None;
- `test_overview_kpis_and_price_coverage` — одна полностью оценённая и одна неоценённая позиция: `priced_count=1`, `priced_total=2`; частично оценённая запчасть не входит в `priced_count`, её известная часть входит в `stock_value`;
- `test_overview_money_uses_v2_and_all_shipments` — V1 не меняет деньги, V2 без контракта входит, границы периода включены;
- `test_stock_value_does_not_depend_on_period` — два разных периода дают одинаковый снимок.

- [ ] **Step 2: Написать падающие тесты строк склада**

`StockRowsTests`:
- `test_stock_rows_quantities_demand_and_days` — V1+V2 входят в `received/shipped`; спрос за `today-364…today` даёт среднемесячный расход с двумя знаками; запас округляется вверх; будущая отгрузка не участвует;
- `test_stock_rows_without_demand_or_with_zero_stock` — `average_monthly=0`, `days_stock=None`, нулевой остаток не даёт деления на ноль;
- `test_stock_rows_partial_price_is_marked` — `value_complete=False`, известная часть стоимости сохранена;
- `test_stock_rows_sorting` — сначала большая оценённая стоимость, затем неоценённые, внутри — название/артикул;
- `test_stock_rows_respect_selected_parts` — все фильтры применяются через `parts_of`.

- [ ] **Step 3: Написать падающие page-тесты**

Новый `SparePartsPageTests` в `test_views.py` с `_fixed_today()`:
- `test_spare_parts_overview_tiles` — точные подписи, деньги и примечание «цена известна: N из M позиций»;
- `test_spare_parts_stock_row_links_to_part` — карточка запчасти открывается;
- `test_spare_parts_stock_table_limits_to_100` — 101 позиция: 100 строк, `stock_rows_total=101`, текст «Показаны 100 из 101»;
- `test_spare_parts_snapshot_note` — «на сегодня, период не учитывается»;
- `test_spare_parts_estimated_value_wording` — есть «Оценочная стоимость», нет «Себестоимость склада».

- [ ] **Step 4: Запустить новые тесты**

Run: `python manage.py test analytics.tests.test_spare_parts analytics.tests.test_views.SparePartsPageTests --settings=ebase_site.test_settings`
Expected: FAIL/ERROR по отсутствующим функциям и контексту.

- [ ] **Step 5: Реализовать расчёты**

- Построить индексы известных поставок по `(part_id, expiration_dt)` и `part_id`; сумма/количество только при положительных цене и количестве.
- `average_price` строки — общая средневзвешенная цена запчасти (`known_price(part_id, None)`), независимо от оценки отдельных сроков.
- `stock_value` строки — сумма известных оценок положительных `SparePartCount`; `value_complete=True`, только если все положительные записи оценены и хотя бы одна есть.
- `positive_count`, `priced_count`, `priced_total` считаются по разным запчастям, не по записям сроков.
- Поступления и отгрузки строки суммируют количество V1/V2 только этой запчасти. Деньги плиток — только `amount/cost` V2.
- Спрос: `quantity / Decimal(12)` за `DEMAND_DAYS`; `days_stock = ceil(stock / (demand / 365))` только при положительных остатке и спросе.
- `last_shipment` и признаки неликвида используют `window_start`; без отгрузок при положительном остатке оба признака True.

- [ ] **Step 6: Реализовать view и шаблон**

Плитки первой версии: «Позиций с остатком», «Оценочная стоимость остатка», «Закуплено за период», «Отгружено за период». Для снимков — примечание «на сегодня», для денег — выбранный период.

`overview.html` использует существующие `an-tiles`, `an-card--wide`, `an-table-wrap`, `an-table`. Неизвестная цена/стоимость — «—», частичная оценка отмечена «частично». Запас в днях и последняя отгрузка без значения — «—». Внизу пояснение: «Количества включают архив V1 и текущие записи V2; деньги — только V2».

`SparePartsView.get_context_data` теперь один раз вызывает `SparePartSet.load()` и объединяет контекст блоков.

- [ ] **Step 7: Проверить тесты и commit**

Run: `python manage.py test analytics --settings=ebase_site.test_settings`
Expected: OK.

`git commit -m "feat(analytics): остатки и оценочная стоимость запчастей"`.

---

### Task 4: Движение денег и топы расхода

**Files:**
- Modify: `ebase_site/analytics/services/spare_parts.py`
- Modify: `ebase_site/analytics/views_spare_parts.py`
- Modify: `ebase_site/analytics/templates/analytics/spare_parts/movement.html`
- Test: `ebase_site/analytics/tests/test_spare_parts.py`, `test_views.py`

**Interfaces:**
- Produces сервис:
  - `money_by_month(period, filters, source=None) -> dict` — `months`, `purchases`, `shipments`, `balance`, все серии по длине равны `period.months()`;
  - `top_parts(period, filters, source=None, limit=15) -> list[dict]` — `id`, `label`, `cost`, `shipment_ids`;
  - `top_equipment(period, filters, source=None, limit=15) -> dict` — `rows` (`equipment_id`, `label`, `cost`, `shipment_ids`) и `without_equipment_cost`.
- Produces view:
  - `SHIPMENTS = "spare_part_sparepartshipmentv2"`;
  - `_ids_link(admin_name, ids) -> str | None` — пусто/больше 90: None, иначе `changelist_url(..., id__in=ids)`;
  - `_movement_context(...) -> dict` — `top_parts`, `top_equipment`, `without_equipment_cost`, `charts` с `money_by_month`, `top_parts`, `top_equipment`.

- [ ] **Step 1: Написать падающие сервисные тесты**

`MovementTests`:
- `test_money_by_month_fills_gaps_and_balance` — покупки/отгрузки в разных месяцах, пустые месяцы нулевые, `balance=purchases-shipments`;
- `test_money_by_month_ignores_archive_money` — V1 влияет только на количества из Задачи 3;
- `test_top_parts_sorts_limits_and_collects_document_ids` — 16 запчастей дают 15 строк, порядок по cost и label, id документов без дублей;
- `test_top_equipment_uses_actual_service_device` — совместимость справочника не заменяет `shipment.service.equipment_accounting.equipment`;
- `test_top_equipment_without_device_is_separate` — отгрузка без ремонта/прибора остаётся в общей себестоимости и `without_equipment_cost`, но не искажает строки моделей;
- `test_top_equipment_nameless_model_has_safe_label` — «Модель без названия», без «None».

- [ ] **Step 2: Написать падающие page-тесты**

- `test_spare_parts_money_chart` — три серии, линия «Сальдо», 12 месяцев для года, формат money;
- `test_spare_parts_top_charts_are_horizontal_with_links` — не больше 15 строк, ссылка ведёт на список отгрузок и открывается с 200;
- `test_spare_parts_top_shipment_link_limit` — `_ids_link` для 0/90/91 id;
- `test_spare_parts_archive_money_note` — пояснение про V1/V2 видно;
- `test_spare_parts_unassigned_equipment_cost_note` — сумма без модели показана отдельно, не подписана как модель.

- [ ] **Step 3: Запустить новые тесты**

Run: `python manage.py test analytics.tests.test_spare_parts.MovementTests analytics.tests.test_views.SparePartsPageTests --settings=ebase_site.test_settings`
Expected: FAIL/ERROR.

- [ ] **Step 4: Реализовать сервисные функции**

- Для месячных серий использовать существующий `_bucket_by_month` из `services/finance.py`; вход — даты и `amount/cost` только V2 отобранных запчастей.
- Топ запчастей группирует V2-отгрузки по `part_id`; топ моделей — по `equipment_id`. Нулевые суммы не создают строки. Сортировка: cost по убыванию, затем label.
- Подпись модели берётся из `ShipmentRow.equipment_label`, заполненной при загрузке фактической модели ремонта; совместимые модели из справочника запчасти для этого блока не используются.
- `shipment_ids` — UUID документов V2, не UUID строк M2M, чтобы ссылка открывала реестр отгрузок.

- [ ] **Step 5: Реализовать графики и шаблон**

- `money_by_month`: столбцы «Закуплено» (`c1`) и «Отгружено» (`c2`), линия «Сальдо» (`c3`), без стекирования.
- Топы: горизонтальные денежные графики, `links` из `_ids_link(SHIPMENTS, shipment_ids)`, высота через `_horizontal_chart_height`.
- `movement.html`: карточка «Движение денег», рядом топы «Запчасти по себестоимости отгрузок» и «Модели оборудования по расходу запчастей»; подсказка о деньгах V2 и отдельная сумма «Без указания модели: N ₽».

- [ ] **Step 6: Проверить тесты и commit**

Run: `python manage.py test analytics --settings=ebase_site.test_settings`
Expected: OK.

`git commit -m "feat(analytics): движение денег и расход запчастей"`.

---

### Task 5: Сроки годности, неликвиды, пополнение и качество данных

**Files:**
- Modify: `ebase_site/analytics/services/spare_parts.py`
- Modify: `ebase_site/analytics/views_spare_parts.py`
- Modify: `ebase_site/analytics/templates/analytics/spare_parts/{overview,expiration,control}.html`
- Test: `ebase_site/analytics/tests/test_spare_parts.py`, `test_views.py`

**Interfaces:**
- Produces сервис:
  - `EXPIRATION_BUCKETS` с ключами `overdue`, `0_30`, `31_90`, `91_180`, `181_plus`, `missing`;
  - `expiration_rows(today, filters, source=None) -> list[dict]` — `key`, `label`, `count`, `parts`, `value`, `count_ids`;
  - `nonmoving_rows(today, filters, source=None) -> dict` — ключи `180`, `365`; каждая строка содержит `id`, `label`, `unit`, `stock`, `stock_value`, `last_shipment`, `demand`;
  - `restock_rows(today, filters, source=None) -> list[dict]` — `id`, `label`, `unit`, `last_shipment`, `demand`;
  - `data_quality(today, filters, source=None) -> list[dict]` — `key`, `label`, `count`, `ids`, `target`, `info`;
  - `overview_kpis` дополняется `expired_value` и `nonmoving_value`.
- Produces view:
  - `COUNTS = "spare_part_sparepartcount"`, `SUPPLIES = "spare_part_sparepartsupplyv2"`;
  - `ARCHIVE_SUPPLIES = "spare_part_sparepartsupply"`, `ARCHIVE_SHIPMENTS = "spare_part_sparepartshipment"`;
  - `_expiration_context`, `_control_context` и `charts["expiration"]`;
  - ссылки по `target`: `counts`, `supplies`, `shipments`, `archive_supplies`, `archive_shipments`; при >90 id ссылка None, строка остаётся видимой.

- [ ] **Step 1: Написать падающие тесты сроков годности**

`ExpirationTests` при `today=2026-10-16`:
- `test_expiration_bucket_boundaries` — вчера → overdue; сегодня и +30 → `0_30`; +31 и +90 → `31_90`; +91 и +180 → `91_180`; +181 → `181_plus`;
- `test_expiration_missing_only_when_required` — пустая дата попадает в `missing` только при `is_expiration=True`;
- `test_expiration_ignores_zero_negative_and_uses_date_not_flag` — нулевые/отрицательные исключены, противоречивый `is_overdue` не влияет;
- `test_expiration_values_and_ids` — count/part считаются без дублей, стоимость использует правила Задачи 3, ids принадлежат `SparePartCount`;
- `test_expiration_kpi_and_nonmoving_kpi` — плитки получают суммы просрочки и неликвида 365, неизвестные цены не мешают суммировать известные.

- [ ] **Step 2: Написать падающие тесты неликвидов и пополнения**

`StockControlTests`:
- `test_nonmoving_180_and_365_boundaries` — отгрузка на первый день окна исключает неликвид, отгрузка днём раньше — нет; никогда не отгружавшаяся позиция входит при положительном остатке;
- `test_restock_zero_stock_and_recent_demand` — нулевой остаток и отгрузка в окне 365 даёт строку; положительный/отрицательный остаток, отсутствие спроса и будущая отгрузка — нет;
- `test_restock_without_count_record` — справочная запчасть без `SparePartCount`, но с недавней отгрузкой включается;
- `test_data_quality_categories` — отдельно negative stock, unknown price, zero supply price, zero shipment price, missing expiration, archive supplies/shipments;
- `test_data_quality_ids_point_to_parent_documents` — нулевые цены дают id поставки/отгрузки, не inline-строки; дубликаты устранены;
- `test_data_quality_archive_is_informational` — `info=True`, остальные категории `info=False`.

- [ ] **Step 3: Написать падающие page-тесты**

- `test_spare_parts_expiration_chart_and_links` — шесть корзин в порядке спецификации, горизонтальный график, ссылка на остатки открывается;
- `test_spare_parts_expiration_large_bucket_has_no_long_url` — 91 запись: счётчик есть, `url=None`, в URL нет `id__in`;
- `test_spare_parts_nonmoving_and_restock_tables` — заголовки, пороги и строки видны;
- `test_spare_parts_data_quality_links` — ссылки ведут на правильные модели админки и возвращают 200;
- `test_spare_parts_overview_all_six_tiles` — добавлены «Просрочено» и «Неликвиды».

- [ ] **Step 4: Запустить новые тесты**

Run: `python manage.py test analytics.tests.test_spare_parts analytics.tests.test_views.SparePartsPageTests --settings=ebase_site.test_settings`
Expected: FAIL/ERROR.

- [ ] **Step 5: Реализовать расчёты**

- Корзины получают только `count.amount > 0` отобранных запчастей. `parts` — число разных part_id, `count` — число записей остатков.
- `expired_value` — сумма известных оценок корзины `overdue`; `nonmoving_value` — известная оценка позиций с `nonmoving_365=True`.
- Неликвиды используют весь спрос V1/V2 и правила `window_start`; вывод ограничить 50 строками в каждом блоке, показывая общее число.
- Кандидаты на пополнение сортируются по убыванию спроса, затем по label; вывод ограничен 50 строками.
- Качество данных считается по отобранным запчастям. Для архивных V1 показывать два информационных счётчика, не прибавляя их к ошибкам.
- Для положительного остатка цена неизвестна, если хотя бы одна положительная запись не получила оценку; ids включают только неоценённые записи.

- [ ] **Step 6: Реализовать view и шаблоны**

- `expiration`: горизонтальный денежный график с шестью корзинами и таблица «корзина · записей · запчастей · оценка»; клик возможен только при наличии URL.
- `control.html`: две карточки неликвидов, «Кандидаты на пополнение» и «Контроль качества данных». У архивных строк пометка «информационно», у отсутствующей ссылки из-за >90 id — «список слишком большой для прямой ссылки».
- `overview.html` получает шесть плиток из описания.

- [ ] **Step 7: Проверить тесты и commit**

Run: `python manage.py test analytics --settings=ebase_site.test_settings`
Expected: OK.

`git commit -m "feat(analytics): сроки годности и контроль склада запчастей"`.

---

### Task 6: Сквозная проверка, производительность и документация

**Files:**
- Modify: `ebase_site/analytics/tests/test_views.py`
- Modify: `ebase_site/analytics/tests/test_spare_parts.py` (только если сквозная проверка выявит пробел)
- Modify: `AGENTS.md` (разделы приложений, аналитики, тестов и правил расчёта)
- Modify: `docs/superpowers/specs/2026-10-31-spare-parts-analytics-design.md` (только если реализация уточнила правило)

**Interfaces:**
- Consumes: все предыдущие задачи.
- Produces: готовая вкладка `/admin/analytics/spare-parts/` и актуальная проектная документация; новых runtime-интерфейсов нет.

- [ ] **Step 1: Добавить сквозные page-тесты**

В `SparePartsPageTests`:
- `test_spare_parts_page_empty_db` — 200, четыре блока, все четыре графика пустые, нули/«—», нет «None» и исключений;
- `test_spare_parts_page_bad_params` — мусор всех фильтров и дат даёт 200, текущий год и значения по умолчанию;
- `test_spare_parts_page_with_mixed_real_data` — V1/V2, контрактная и бесконтрактная отгрузка, два срока годности, неизвестная цена, ремонт с моделью и без него; страница содержит согласованные суммы всех плиток и графиков;
- `test_spare_parts_period_does_not_change_snapshot` — два запроса с разными периодами меняют движение, но не остатки, сроки, неликвиды и пополнение;
- `test_spare_parts_contract_shipments_match_finance_subset` — при одинаковом периоде сумма контрактных V2-отгрузок в наборе равна `finance.money_flow()["spare_parts"]`, а итог вкладки больше или равен ей за счёт бесконтрактных;
- `test_spare_parts_page_query_count_is_small_and_constant` — до/после добавления запчастей, поставок и отгрузок: `before <= 35`, `before == after`.

- [ ] **Step 2: Запустить сквозные тесты и исправить только подтверждённые дефекты вкладки**

Run: `python manage.py test analytics.tests.test_views.SparePartsPageTests --settings=ebase_site.test_settings`
Expected: OK после устранения дефектов. Если тест выявил неправильное правило, сначала добавить узкий падающий тест в `test_spare_parts.py`, затем исправить сервис.

- [ ] **Step 3: Обновить проектную документацию**

В `AGENTS.md` зафиксировать:
- вкладку «Запчасти», право `view_spare_parts`, миграцию 0006 и URL;
- `services/spare_parts.py`, `views_spare_parts.py`, `test_spare_parts.py`;
- правила V1/V2, оценочной стоимости, 365-дневного спроса, снимков на сегодня и ограничения ссылок;
- новые тесты в описании набора `analytics/tests/`.

Если фактическая реализация сознательно отличается от описания, синхронизировать spec; не менять правила молча только в коде.

- [ ] **Step 4: Форматирование и Django check**

Run: `black <только изменённые Python-файлы>`
Expected: без ошибок.

Run: `python manage.py check --settings=ebase_site.test_settings`
Expected: `System check identified no issues`.

- [ ] **Step 5: Профильные и полный наборы тестов**

Run: `python manage.py test analytics spare_part --settings=ebase_site.test_settings`
Expected: OK.

Run: `python manage.py test --settings=ebase_site.test_settings`
Expected: новые тесты проходят; остаются только пять известных падений в старых `ebase/tests.py` и `contracts/tests.py`. Если исходный baseline отличался, допустимы только зарегистрированные в Задаче 1 старые падения.

- [ ] **Step 6: Проверить рабочее дерево и commit**

Run: `git status --short`
Expected: только предусмотренные файлы; тестовых БД, логов и scratchpad-файлов в репозитории нет.

```bash
git add AGENTS.md docs/superpowers ebase_site/analytics
git commit -m "docs(analytics): правила и проверка вкладки «Запчасти»"
```

---

## Итоговая приёмка

- Суперпользователь и пользователь с `view_spare_parts` видят вкладку; остальные получают 403 и не видят пункт меню.
- На контрольном наборе шесть плиток, четыре графика, складская таблица, сроки, неликвиды, пополнение и качество данных согласованы между собой.
- Оценочная стоимость не выдаётся за точную себестоимость; неизвестные цены и архив явно обозначены.
- Все переходы в админку работают, длинных URL сверх лимита нет.
- Число запросов не растёт с данными; `analytics` и `spare_part` зелёные; старых падений не прибавилось.
