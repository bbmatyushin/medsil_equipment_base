"""Наполнение таблиц Postgres данными полученными из MS Access."""

import os
import logging
import json
import django

from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ebase_site.settings")
django.setup()

from ebase.models import *

logger = logging.getLogger('INSERT_DATA')

json_dir = '/home/human/Coding/Sites/medsil_equipment_base/accembler_db/tables_json/'


def insert_cities() -> None:
    """Заполняем таблицу City."""
    with open(Path(json_dir + 'города.json'), 'r', encoding='utf-8') as f:
        for line in f:
            city = json.loads(line)
            try:
                City.objects.create(name=city['Город'], region=city['Область'])
                logger.info(f'Город {city["Город"]} добавлен.')
            except Exception as e:
                logger.error(e)


if __name__ == '__main__':
    insert_cities()
