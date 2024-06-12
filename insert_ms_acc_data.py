import json
import asyncio
import aiofiles

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from models import *
from database import async_session, async_engine
from logger import get_logger


logger = get_logger('INSERT_ACC')


async def insert_cities():
    """Добавление городов из БД MS Access в новую БД"""
    # TODO: После вставки проверить на дубли (Гатчина была 2 раза)
    async with aiofiles.open('accembler_db/tables_json/города.json', mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        new_row = Cities(name=data.get('Город'),
                                         region=data.get('Область'))
                        session.add(new_row)
                except IntegrityError as err:
                    logger.error(err.orig)


async def insert_med_direction():
    """Добавление Направления"""
    file_path = 'accembler_db/tables_json/направление.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async with session.begin():
                async for line in f:
                    data = json.loads(line)
                    name = MedDirectory(name=data.get('НаименованиеНаправления'))
                    session.add(name)


async def insert_manufacturer():
    """Добавляем производителей"""
    file_path = 'accembler_db/tables_json/список_оборудования.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        name = Manufacturer(name=data.get('Производитель'))
                        session.add(name)
                except IntegrityError as err:
                    logger.error(err.orig)


async def insert_equipment():
    """Добавление оборудования из БД MS Access в новую БД"""
    file_path = 'accembler_db/tables_json/список_оборудования.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async with session.begin():
                async for line in f:
                    equipment_data = json.loads(line)
                    new_equipment = Equipment(fullname=equipment_data.get('Название полное'),
                                              shortname=equipment_data.get('Краткое название'),
                                              )
                    session.add(new_equipment)
                await session.commit()


async def delete_data():
    """Удаление данных из таблицы"""
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(Cities))
            await session.execute(delete(MedDirectory))
            await session.execute(delete(Manufacturer))
            await session.commit()


async def main():
    task_delete_data = asyncio.create_task(delete_data())
    task1_insert_cities = asyncio.create_task(insert_cities())
    task2_insert_med_direction = asyncio.create_task(insert_med_direction())
    task3_insert_manufacturer = asyncio.create_task(insert_manufacturer())
    # task4_insert_equipment = asyncio.create_task(insert_equipment())

    await asyncio.gather(task_delete_data,
                         task1_insert_cities,
                         task2_insert_med_direction,
                         task3_insert_manufacturer,
                         )


if __name__ == '__main__':
    # asyncio.run(delete_data())
    asyncio.run(main())
    # asyncio.run(insert_cities())
