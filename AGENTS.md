# Руководство для AI-агентов: medsil_equipment_base

## Общее описание проекта

`medsil_equipment_base` — веб-приложение на Django для учёта поставки и сервисного обслуживания медицинского оборудования. Основной интерфейс пользователя — кастомизированная админка Django, через которую ведутся справочники, учёт оборудования, ремонты, контракты, запчасти и пользователи.

Проект локализован на русский язык (`LANGUAGE_CODE = "ru-ru"`, `TIME_ZONE = "Europe/Moscow"`). Код, комментарии и документация внутри репозитория ведутся на русском.

## Стек технологий

- **Язык:** Python 3.11 (`.python-version`, `requires-python = ">=3.11"`)
- **Фреймворк:** Django 4.2.16
- **Управление зависимостями:** `uv` (`pyproject.toml`, `uv.lock`); дублируется `requirements.txt`
- **База данных:** PostgreSQL (`psycopg2-binary`) в продакшене; для тестов — SQLite in-memory
- **Схема БД:** все таблицы создаются в схеме `medsil` (например, `"medsil"."equipment"`)
- **Веб-сервер:** Gunicorn + Nginx (инструкции в `README.md` и `gunicorn.service`)
- **Форматирование:** Black 24.8.0
- **Генерация документов:** `python-docx` для актов о проведении работ
- **Экспорт:** `openpyxl` для выгрузки списков в Excel
- **Утилиты:** django-debug-toolbar, django-extensions, django-shell-plus, django-cleanup

## Структура репозитория

```
/home/human/Coding/Sites/medsil_equipment_base/
├── pyproject.toml              # метаданные проекта и зависимости
├── uv.lock                     # lock-файл uv
├── requirements.txt            # резервный список зависимостей
├── README.md                   # инструкции по развёртыванию
├── .env / .env.example         # переменные окружения
├── gunicorn.service            # unit-файл systemd
├── create_role.sql             # SQL для создания БД/роли Postgres
├── accembler_db/               # импорт из MS Access
│   ├── general_db.accdb
│   ├── get_accdb_data.py       # экспорт таблиц Access → JSON
│   └── tables_json/
├── ebase_site/                 # Django-проект
│   ├── manage.py
│   ├── ebase_site/             # настройки (settings.py, test_settings.py, urls.py, wsgi.py)
│   ├── users/                  # кастомная модель пользователя
│   ├── directory/              # справочники (города, статусы, единицы, инженеры и т.д.)
│   ├── clients/                # клиенты, подразделения, контактные лица
│   ├── ebase/                  # оборудование, учёт, ремонты, подменное оборудование
│   ├── spare_part/             # запчасти, поставки, отгрузки, остатки
│   ├── contracts/              # реестр контрактов, оплаты, расходы
│   ├── business_trip/          # командировки, пункты, затраты, фото чеков
│   ├── utils/                  # общие админ-классы и экспорт в Excel
│   ├── static/                 # общая статика
│   └── media/                  # загруженные файлы (фото, акты)
└── pg_medsil_backup/           # дампы PostgreSQL
```

## Django-приложения

| Приложение   | Назначение |
|--------------|------------|
| `users`      | Кастомная модель `CompanyUser` (UUID, расширенный `AbstractUser`). Связь с должностями и учётом оборудования. |
| `directory`  | Справочники: города, страны, производители, поставщики, направления оборудования, статусы, единицы измерения, должности, типы работ, инженеры. |
| `clients`    | Клиенты (`Client`), подразделения/филиалы (`Department`), контактные лица (`DeptContactPers`). |
| `ebase`      | Модели оборудования (`Equipment`), учёт по серийным номерам (`EquipmentAccounting`), установки у клиентов (`EquipmentAccDepartment`), ремонты (`Service`), фото ремонтов (`ServicePhotos`), подменное оборудование (`ReplacementEquipment`). |
| `spare_part` | Запчасти (`SparePart`), остатки (`SparePartCount`), поставки v1/v2 (`SparePartSupply`, `SparePartSupplyV2`, `SparePartSupplyItem`), отгрузки v1/v2 (`SparePartShipment`, `SparePartShipmentV2`, `SparePartShipmentM2M`), комплектующие (`SparePartAccessories`). |
| `contracts`  | Реестр контрактов (`Contract`), оплаты (`Payment`), расходы (`ContractExpense`). Автоматический пересчёт сумм через сигналы. |
| `business_trip` | Командировки сотрудников (`BusinessTrip`), пункты (`BusinessTripDestination`), затраты (`BusinessTripExpense`, справочник `ExpenseType`), фото чеков (`BusinessTripPhoto`). Авто-расчёт суточных: дни × 700 руб. |

Все модели используют явное указание `db_table` со схемой `"medsil"`. Базовые классы `EbaseModel`/`ContractModelBase`/`SparePartAbs` задают UUID-PK и `create_dt`.

## Конфигурация и переменные окружения

Настройки читаются из `.env` через `python-decouple`:

```dotenv
ALLOWED_HOSTS = []
DB_NAME = ''
DB_USER = ''
DB_PASSWORD = ''
DB_HOST = 'localhost'
DB_PORT = 5432
SECRET_KEY = ""
STATIC_ROOT = ''
```

Важные параметры в `ebase_site/ebase_site/settings.py`:

- `DEBUG = True` — по умолчанию включён дебаг!
- `ALLOWED_HOSTS = []` — заполняется через `.env`.
- `AUTH_USER_MODEL = "users.CompanyUser"`
- `STATIC_ROOT` берётся из `.env`, fallback — `BASE_DIR / "staticfiles"`
- `STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"`
- `MEDIA_ROOT = BASE_DIR / 'media'`, `MEDIA_URL = 'media/'`

## Команды сборки и запуска

Активировать виртуальное окружение:

```bash
source /home/human/Coding/Sites/medsil_equipment_base/.venv/bin/activate
```

Установка зависимостей (один из вариантов):

```bash
# через uv
uv sync

# или pip
pip install -r requirements.txt
```

Применение миграций:

```bash
cd ebase_site
python manage.py migrate
```

Сбор статики:

```bash
python manage.py collectstatic
```

Создание суперпользователя:

```bash
python manage.py createsuperuser
```

Разработческий сервер:

```bash
python manage.py runserver
```

Продакшен (Gunicorn):

```bash
gunicorn --config gunicorn_conf.py ebase_site.wsgi:application
```

## Тестирование

Тестовые настройки расположены в `ebase_site/ebase_site/test_settings.py`. Они используют SQLite in-memory и отключают миграции, а также патчат SQL, вырезая префикс схемы `"medsil"."`.

Запуск тестов:

```bash
cd ebase_site
python manage.py test --settings=ebase_site.test_settings
```

Наборы тестов:

- `ebase/tests.py` — связь ремонтов с контрактами и отгрузками.
- `contracts/tests.py` — пересчёт оплат/расходов/прибыли по контракту, автокомплит клиента, итоги changelist.
- `spare_part/tests.py` — поставки V2 и пересчёт остатков.
- `business_trip/tests.py` — расчёт суточных, автонумерация документов, валидации дат, smoke-тесты админки.

**Текущее состояние тестов:** часть тестов падает. При последнем запуске из 27 тестов `FAILED (failures=2, errors=3)`. Основные проблемы:

- В `ebase/tests.py` в `setUp` контракту передаётся `Department` вместо `Client`.
- В `contracts/tests.py` ожидается поле `payment_status` в форме редактирования, но оно исключено.
- В `contracts/tests.py` расчёт `profit` не учитывает, что при обновлении `contract_amount` `payment_amount` остаётся равным сумме оплат.

## Стиль кода

- Форматер: **Black** (`black==24.8.0`). Перед коммитом рекомендуется запускать:

  ```bash
  black ebase_site
  ```

- Именование: Python/Django-стиль (`snake_case` для переменных/функций, `PascalCase` для классов).
- Комментарии и `verbose_name` — на русском языке.
- Модели содержат `db_comment`, `verbose_name`, `help_text`.

## Архитектурные особенности

### Сигналы

- `contracts/signals.py` — пересчёт `payment_amount`, `expenses_amount`, `debt`, `profit` и `payment_status` контракта при изменении оплат, расходов и отгрузок запчастей.
- `spare_part/signals.py` — управление остатками `SparePartCount` при поставках и отгрузках (V1 и V2), включая FIFO-цену закупки.
- `ebase/signals.py` — пересчёт связанного контракта при изменении ремонта `Service`.

### Админка

Интерфейс приложения построен вокруг Django Admin. В `utils/common_admin.py` определён `MainModelAdmin` с единым action — экспортом в Excel. Практически все модели регистрируются через кастомные `ModelAdmin` с:

- `list_display`, `search_fields`, `list_filter`;
- `select_related`/`prefetch_related` для оптимизации N+1;
- inline-формами;
- кастомными form-классами и валидацией.

### Генерация документов

`ebase/docx_create.py` создаёт Word-акты (`service_akt_MEDSIL.docx`, `Akt_in_service.docx`, `Akt_from_service.docx`) на основе шаблонов из `media/docs/service_akt/`. Шаблоны не хранятся в репозитории, их нужно разместить вручную на сервере.

### Импорт из MS Access

Для переноса данных из Access:

1. Установить `mdbtools`: `sudo apt install mdbtools`.
2. Поместить `.accdb` в `accembler_db/`.
3. Создать `accembler_db/tables_json/`.
4. Выполнить `python3 accembler_db/get_accdb_data.py`.

## Безопасность

- `DEBUG = True` в `settings.py` — обязательно переопределить в `.env`/`local_settings.py` для продакшена.
- `SECRET_KEY`, параметры БД и `ALLOWED_HOSTS` должны задаваться только через `.env`.
- CSRF и аутентификация Django включены стандартно.
- Файл `.env` добавлен в `.gitignore` и не должен попадать в репозиторий.
- Для продакшена настроен `systemd`-юнит `gunicorn.service`; запуск от пользователя `medsil`.

## Полезные ссылки и файлы

- `README.md` — подробная инструкция по развёртыванию на Linux и в Docker.
- `ebase_site/ebase_site/settings.py` — основные настройки.
- `ebase_site/ebase_site/test_settings.py` — тестовые настройки.
- `create_role-example.sql` — пример создания БД/схемы/роли Postgres.
- `gunicorn_conf.py` — конфигурация Gunicorn.

## Что нужно знать агенту перед правками

1. Все модели ожидают схему `medsil` в Postgres. При локальной разработке с SQLite используйте `test_settings.py`.
2. Не меняйте поведение сигналов без явной необходимости — от них зависят финансовые пересчёты контрактов и складские остатки.
3. В админке много кастомных `formfield_for_foreignkey`/`get_queryset` — изменения могут сломать фильтрацию/поиск.
4. Перед коммитом запускайте `black ebase_site` и `python manage.py test --settings=ebase_site.test_settings`.
5. Если добавляете новые зависимости, обновляйте `pyproject.toml` и `uv.lock` (`uv add <package>`), а также `requirements.txt`.
