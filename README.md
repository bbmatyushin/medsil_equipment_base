# medsil_equipment_base
Веб-приложение для ведения учета поставки и обслуживания медицинского оборудования.

Для работы с базами MS Access необходимо установить mdbtools:
```shell
sudo apt install mdbtools
```
1. Файл БД (*.accdb) переместить в директорию accembler_db;
2. Создать директорию tables_json `mkdir accembler_db/tables_json`;
3. Выполнить скрипт python3 accembler_db/get_accdb_data.py. После чего в директории tables_json таблице будут представленны в виде json-файлов.


