# Чек-лист переезда medsil_equipment_base на новый сервер

Обозначения: `OLD` — старый сервер, `NEW` — новый, `DB_NAME` / `DB_USER` — имя БД и роли из `.env`,
`PROJECT=/home/medsil/medsil_equipment_base`.

Главное правило: **во время финального дампа gunicorn на старом сервере остановлен** — данные не меняются,
значит ничего не потеряется.

---

## 0. Что переносим

Восстанавливается из git (`git clone`): код, `ebase_site/gunicorn_conf.py`, шаблон `gunicorn.service`.

Нет в git — переносить вручную:

- [ ] База Postgres: БД, роль, схема `medsil`, настройки роли/БД (`search_path` и т.п.)
- [ ] `.env` в корне проекта (`SECRET_KEY`, `DB_*`, `ALLOWED_HOSTS`, `STATIC_ROOT`)
- [ ] `ebase_site/media/` — фото ремонтов, фото чеков, акты, **шаблоны `media/docs/service_akt/*.docx`**
- [ ] `ebase_site/static/images/` (в `.gitignore`)
- [ ] `ebase_site/logs/` (по желанию)
- [ ] `/etc/systemd/system/gunicorn.service` (серверная версия может отличаться от репозитория)
- [ ] Конфиг Nginx `/etc/nginx/sites-available/<сайт>`
- [ ] SSL-сертификаты `/etc/letsencrypt/` (если есть HTTPS)
- [ ] Cron-задача с `pg_dump` и сам скрипт бэкапа
- [ ] Каталог со старыми дампами (если нужны)

---

## 1. Инвентаризация на OLD (сайт работает)

- [ ] Версия Postgres: `psql --version`
- [ ] Юнит: `sudo cat /etc/systemd/system/gunicorn.service`
- [ ] Nginx: `ls -l /etc/nginx/sites-enabled/` и содержимое конфига
- [ ] Cron:
  ```bash
  sudo crontab -l; sudo crontab -l -u medsil; sudo crontab -l -u postgres; ls /etc/cron.d/
  ```
- [ ] БД, роли и их настройки:
  ```bash
  sudo -u postgres psql -c '\l' -c '\du' -c '\drds'
  ```
  > `\drds` важен: служебные таблицы Django (`django_migrations`, `auth_*`, `django_session`) лежат там,
  > куда указывает `search_path`. Если он задан у роли/БД — повторить на новом сервере.
- [ ] Объём медиа: `du -sh $PROJECT/ebase_site/media`
- [ ] Записать домен, открытые порты, правила брандмауэра (`sudo ufw status`)

---

## 2. Подготовка NEW

- [ ] Пакеты (Postgres — **той же или более новой** major-версии):
  ```bash
  sudo apt install postgresql nginx git
  ```
- [ ] Пользователь: `sudo adduser medsil`
- [ ] `uv` (от имени medsil): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Код:
  ```bash
  sudo -u medsil git clone <repo> /home/medsil/medsil_equipment_base
  ```
- [ ] `.env`:
  ```bash
  scp OLD:$PROJECT/.env NEW:$PROJECT/.env
  ```
  Поправить `ALLOWED_HOSTS` / `DB_*` / `STATIC_ROOT`, если меняются домен, пути или параметры БД.
- [ ] Зависимости — **только через `uv sync`**:
  ```bash
  cd $PROJECT && uv sync
  ```
  > В `requirements.txt` нет `gunicorn` и `gevent` — через pip служба не запустится.

---

## 3. Пробный прогон (OLD продолжает работать)

### На OLD
- [ ] Роли:
  ```bash
  sudo -u postgres pg_dumpall --roles-only > roles.sql
  ```
- [ ] База:
  ```bash
  sudo -u postgres pg_dump -Fc -d DB_NAME -f medsil.dump
  ```
- [ ] Файлы:
  ```bash
  rsync -aH $PROJECT/ebase_site/media/         NEW:$PROJECT/ebase_site/media/
  rsync -aH $PROJECT/ebase_site/static/images/ NEW:$PROJECT/ebase_site/static/images/
  scp roles.sql medsil.dump NEW:~
  ```

### На NEW
- [ ] Восстановить роли (ошибка `role "postgres" already exists` — норма):
  ```bash
  sudo -u postgres psql -f roles.sql
  ```
- [ ] Создать БД и восстановить дамп:
  ```bash
  sudo -u postgres createdb -O DB_USER DB_NAME
  sudo -u postgres pg_restore -d DB_NAME -j 4 medsil.dump
  ```
- [ ] Если в `\drds` был `search_path` на уровне БД:
  ```bash
  sudo -u postgres psql -c "ALTER DATABASE DB_NAME SET search_path = ..."
  ```
- [ ] Проверка Django:
  ```bash
  cd $PROJECT/ebase_site
  sudo -u medsil ../.venv/bin/python manage.py showmigrations | grep '\[ \]'   # должно быть пусто
  sudo -u medsil ../.venv/bin/python manage.py check --deploy
  sudo -u medsil ../.venv/bin/python manage.py collectstatic --noinput
  sudo chown -R medsil:medsil $PROJECT
  ```
- [ ] Скопировать `gunicorn.service` в `/etc/systemd/system/`
- [ ] Скопировать конфиг Nginx, проверить пути `alias` для `/static/` и `/media/`, сделать симлинк в `sites-enabled`
- [ ] Запуск:
  ```bash
  sudo nginx -t
  sudo systemctl daemon-reload
  sudo systemctl enable --now gunicorn nginx
  sudo systemctl status gunicorn
  ```
- [ ] Открыть сайт по IP (временно добавить IP в `ALLOWED_HOSTS` или прописать домен в `/etc/hosts` на своей машине)

### Ручная проверка
- [ ] Вход в админку
- [ ] Списки: оборудование, ремонты, контракты, запчасти, командировки
- [ ] Фото ремонтов и чеков открываются
- [ ] Генерация акта ремонта (проверяет шаблоны `.docx`)
- [ ] Приказ на командировку
- [ ] Экспорт в Excel и «Отчет по денежным средствам»
- [ ] Создание/изменение записи сохраняется, пересчёт контракта срабатывает

---

## 4. Переезд (простой ~10–30 минут)

- [ ] **За сутки** уменьшить TTL DNS-записи до 300 с
- [ ] Предупредить пользователей о времени простоя
- [ ] **OLD:** остановить приложение
  ```bash
  sudo systemctl stop gunicorn
  ```
- [ ] **OLD:** финальный дамп и докачка файлов
  ```bash
  sudo -u postgres pg_dump -Fc -d DB_NAME -f medsil_final.dump
  rsync -aH $PROJECT/ebase_site/media/ NEW:$PROJECT/ebase_site/media/
  scp medsil_final.dump NEW:~
  ```
- [ ] **NEW:** заменить пробную базу финальной
  ```bash
  sudo systemctl stop gunicorn
  sudo -u postgres dropdb DB_NAME
  sudo -u postgres createdb -O DB_USER DB_NAME
  sudo -u postgres pg_restore -d DB_NAME -j 4 medsil_final.dump
  sudo systemctl start gunicorn
  ```
- [ ] **Сверка данных** — выполнить на OLD и NEW, результаты должны совпасть:
  ```sql
  SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname='medsil' ORDER BY 1;
  ```
  Плюс точный `count(*)` по ключевым таблицам: оборудование, ремонты, контракты, оплаты.
- [ ] Переключить DNS (или IP) на NEW
- [ ] SSL: скопировать `/etc/letsencrypt` целиком **или** после переключения DNS:
  ```bash
  sudo certbot --nginx -d <домен>
  ```
- [ ] Повторить ручную проверку из п. 3 уже по домену
- [ ] Убрать временный IP из `ALLOWED_HOSTS`, если добавляли

---

## 5. После переезда

- [ ] Настроить cron с `pg_dump` на NEW
- [ ] **На следующий день убедиться, что дамп реально создан** и не пустой
- [ ] Хранить копию дампов вне сервера (другая машина / облако)
- [ ] Перенести старые дампы, если нужны
- [ ] Брандмауэр: открыть 80/443, порт 5432 наружу **не** открывать
- [ ] Вернуть TTL DNS в обычное значение

---

## Откат

**Старый сервер не выключать 1–2 недели** (gunicorn на нём остановлен).

1. Если на NEW уже вносили данные — снять с NEW дамп и восстановить его на OLD.
2. Вернуть DNS на OLD.
3. На OLD: `sudo systemctl start gunicorn`.
