"""Для работы нужно установить mdbtools: sudo apt install mdbtools"""

import subprocess
import re
from logger.logger import get_logger


logger = get_logger('ACCESS')

db_path = r'/home/human/Coding/Sites/medsil_equipment_base/accembler_db/general_db.accdb'


def get_all_tables(db_path: str) -> list:
    """ Получаем названия всех таблиц из MS Access
    :param db_path: The MS Access database file."""
    command = f'mdb-tables -d ";" {db_path}'
    output = subprocess.run(command, shell=True, capture_output=True, text=True)
    table_list = output.stdout.split(';')
    logger.info(table_list)
    return table_list[:-1]


def export_table(table_list: list) -> None:
    """Извлекаем данные из списка таблиц и сохраняем их в json-файлах"""
    for table in table_list:
        filename = re.sub(r'\s+', '_', table) + '.json'
        # -D, --date-format=format
        # -T, --time-format=format
        command = (f'mdb-json -D "%Y-%m-%d" -T "%Y-%m-%d %H:%M:%S" {db_path} "{table}" '
                   f'> tables_json/{filename.lower()}')
        subprocess.run(command, shell=True)
    logger.info("Done! Created json files.")


def main():
    table_list = get_all_tables(db_path)
    export_table(table_list)


if __name__ == '__main__':
    main()


