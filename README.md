# medsil_equipment_base
Веб-приложение для ведения учета поставки и обслуживания медицинского оборудования.

Для работы с базами MS Access необходимо установить mdbtools:
```shell
sudo apt install mdbtools
```
1. Файл БД (*.accdb) переместить в директорию accembler_db;
2. Создать директорию tables_json `mkdir accembler_db/tables_json`;
3. Выполнить скрипт `python3 accembler_db/get_accdb_data.py`. После чего в директории tables_json таблицы будут представленны в виде json-файлов.

---

## Развертывания готового веб-приложения на Django на сервере Linux:

#### Шаг 1: Подготовка сервера
```shell
sudo apt update
sudo apt upgrade
```
#### Шаг 2: Установка необходимых компонентов
```shell
sudo apt install python3 python3-pip python3-venv
```
Установите PostgreSQL (или любую другую базу данных):
```shell
sudo apt install postgresql
```
#### Шаг 3: Подготовка приложения Django
**Скопируйте приложение:** Скопируйте ваше Django приложение на сервер.\
**Установите зависимости:** Перейдите в папку проекта и установите зависимости:
```shell
python3 -m venv venv && \
source bin/venv/activate && \
pip3 install -r requirements.txt
```
**Настройте базу данных:** Обновите настройки в settings.py вашего Django проекта для подключения к базе данных PostgreSQL.
#### Шаг 4: Настройка сервера
Создайте и примените миграции: Выполните миграции для создания таблиц в базе данных:
``` shell
python3 manage.py makemigrations
python3 manage.py migrate
```
Объедините все static файлы в одну директорию, указанную в STATIC_ROOT в **settings.py**:
```shell
python3 manage.py collectstatic
```
Создайте суперпользователя для управления админкой Django:
```shell
python3 manage.py createsuperuser
```
#### Шаг 5: Настройка веб-сервера
**Установите и настройте Gunicorn:** Установите Gunicorn и создайте файл конфигурации, например, gunicorn_config.py.
```shell
pip3 install gunicorn
pip3 install gevent  # для обработки соединений асинхронно
```
Файл конфигурации, для удобства, можно раположить, например, в корневой папке проекта.\
Пример файла gunicorn_config.py:
```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = 'gevent'
timeout = 30
loglevel = "info"
```
* Параметры `workers`, `timeout`, `loglevel` в файле конфигурации могут быть настроены в зависимости от ваших потребностей.


**Настройте Nginx:** Установите Nginx.
```shell
sudo apt install nginx
```
Создайте файл конфигурации для вашего сайта. Обычно эти файлы располагаются в директории /etc/nginx/sites-available/.
Назовите файл, например, myproject.\
Откройте файл конфигурации myproject в текстовом редакторе и добавьте следующий конфигурационный блок:
```conf
server {
    listen 80;
    server_name your_domain_or_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/your/static/files/;
    }
}
```
* `listen 80;` - указывает Nginx слушать входящие запросы на порту 80.
* `server_name your_domain_or_IP;` - замените your_domain_or_IP на ваш доменное имя или IP адрес сервера.
* `proxy_pass http://127.0.0.1:8000;` - указывает Nginx перенаправлять запросы на Gunicorn, который работает на 127.0.0.1:8000.
* Настройки `proxy_set_header` используются для передачи заголовков.
* `location /static/` путь до static файлов.\
Создайте символическую ссылку на ваш файл конфигурации в папке sites-enabled:
```shell
sudo ln -s /etc/nginx/sites-available/myproject /etc/nginx/sites-enabled/
```
Перезапустите Nginx для применения изменений:
``` shell
sudo systemctl restart nginx
```
После выполнения этих шагов, Nginx будет настроен для работы в связке с Gunicorn и веб-приложением Django будет доступно через Nginx по указанному доменному имени или IP адресу.

#### Шаг 6: Запуск приложения
**Запуск Gunicorn для Django приложения**\
Перейдите в директорию вашего проекта Django. Запустите Gunicorn:
```shell
gunicorn --config gunicorn_config.py ebase_site.wsgi:application
```

**Создание юнит-файла для запуска gunicorn:**
```shell
printf "[Unit]
Description=gunicorn daemon
After=network.target nginx.service

[Service]
User=$USER
WorkingDirectory=/home/medsil/medsil_equipment_base/ebase_site
ExecStart=/home/medsil/medsil_equipment_base/venv/bin/gunicorn --config gunicorn_conf.py ebase_site.wsgi:application

[Install]
WantedBy=multi-user.target" > /etc/systemd/system/gunicorn.service
```
Запускаем службу:
```shell
systemctl daemon-reload
systemctl enable gunicorn.service
systemctl restart gunicorn.service
```

#### Шаг 7: Настройка брандмауэра
**Настройте брандмауэр:** Если у вас есть брандмауэр, разрешите доступ к порту 80 (или другому порту, который использует Nginx) для входящих соединений.
После завершения этих шагов ваше веб-приложение Django должно быть развернуто на сервере Linux и готово к использованию через веб-браузер.

## Развертывания готового веб-приложения на Django в Docker:
#### Шаг 1: Установка Docker
Установите Docker на ваш виртуальный сервер. В большинстве случаев это можно сделать с помощью команд:
```shell
sudo apt update
sudo apt install docker.io
```
#### Шаг 2: Создание Docker образа для Django приложения
Создайте файл Dockerfile в корневой директории вашего Django проекта.
В Dockerfile определите образ базового контейнера, установите зависимости, скопируйте приложение и выполните команды для подготовки приложения. Пример Dockerfile:
```vim
FROM python:3.8

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
```
1. Необходимо создать конфигурационные файлы gunicorn_config.py и nginx.conf и поместить их в корневую директорию вашего проекта.
2. В gunicorn_config.py укажите параметры для Gunicorn (примеры выше), а в nginx.conf настройки для Nginx.\
```conf
events {}

http {
    server {
        listen 80;
        server_name your_domain_or_IP;

        location / {
            proxy_pass http://django:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /static/ {
            alias /path/to/your/static/files/;
        }
    }
}
```
#### Шаг 3: Docker-compose для Django, Gunicorn, Nginx и Postgres
Создайте файл docker-compose.yml в корневой директории вашего проекта.\
В файле docker-compose.yml определите сервисы для Django, Gunicorn, Nginx и Postgres. Пример docker-compose.yml:
```yml
version: '3'

services:
  django:
    build: .
    command: gunicorn --bind 0.0.0.0:8000 myproject.wsgi
    depends_on:
      - db
    environment:
      - DATABASE_URL=postgres://postgres:password@db:5432/mydatabase

  db:
    image: postgres
    environment:
      POSTGRES_DB: mydatabase
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password

  nginx:
    image: nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - django
```
##### Запустите Docker-Compose из корневой директории вашего проекта:
```shell
sudo docker-compose up
```
