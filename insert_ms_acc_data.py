import json
import asyncio
import aiofiles
import uuid
from typing import Union, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept

from models import *
from database import async_session, async_engine
from logger import get_logger


logger = get_logger('INSERT_ACC')


async def get_id(name: Optional[str], table: DeclarativeAttributeIntercept) -> Union[int, uuid.UUID]:
    async with async_session() as session:
        async with session.begin():
            result_id = await session.execute(select(table.id).filter_by(name=name))
            id_value = result_id.scalar()
        print(f"{id_value=}")
        return id_value


async def get_med_directory_name():
    """Получаем все Направления в виде словаря"""
    file_med_directory = 'accembler_db/tables_json/направление.json'
    data_med_dir = {}
    async with aiofiles.open(file_med_directory, mode='r', encoding='utf-8') as f:
        async for line in f:
            data = json.loads(line)
            data_med_dir[data['Код']] = data['НаименованиеНаправления']
    # print(data_med_dir)
    return data_med_dir


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


async def insert_supplier():
    """Добавляем поставщиков"""
    file_path = 'accembler_db/tables_json/список_оборудования.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        name = data.get('Поставщик')
                        if name:
                            add_supplier = Supplier(name=name)
                            session.add(add_supplier)
                except IntegrityError as err:
                    logger.error(err.orig)


async def insert_equipment():
    """Добавление оборудования из БД MS Access в новую БД"""
    file_path = 'accembler_db/tables_json/список_оборудования.json'
    data_med_dir = await get_med_directory_name()
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async with session.begin():
                async for line in f:
                    equipment_data = json.loads(line)
                    fullname = equipment_data.get('Название полное')
                    shortname = equipment_data.get('Краткое название', None)
                    med_dir_code = equipment_data.get('Направление', None)
                    med_dir_name = data_med_dir.get(med_dir_code, None)
                    med_directory_id = await get_id(name=med_dir_name, table=MedDirectory)
                    manufacturer_id = await get_id(name=equipment_data.get('Производитель'), table=Manufacturer)
                    supplier_id = await get_id(name=equipment_data.get('Поставщик'), table=Supplier)
                    try:
                        new_equipment = Equipment(fullname=fullname,
                                                  shortname=shortname,
                                                  med_directory_id=med_directory_id,
                                                  manufacturer_id=manufacturer_id,
                                                  supplier_id=supplier_id,
                                                  )
                        session.add(new_equipment)
                    except IntegrityError as err:
                        logger.error(err.orig)
                        logger.error(f"{fullname=}, {med_directory_id=}, {manufacturer_id=}, {supplier_id=}")
                await session.commit()


async def delete_data():
    """Удаление данных из таблицы"""
    async with async_session() as session:
        async with session.begin():
            # await session.execute(delete(Cities))
            # await session.execute(delete(MedDirectory))
            # await session.execute(delete(Manufacturer))
            # await session.execute(delete(Supplier))
            await session.execute(delete(Equipment))


async def main():
    # task_delete_data = asyncio.create_task(delete_data())
    # task1_insert_cities = asyncio.create_task(insert_cities())
    # task2_insert_med_direction = asyncio.create_task(insert_med_direction())
    # task3_insert_manufacturer = asyncio.create_task(insert_manufacturer())
    # task4_insert_supplier = asyncio.create_task(insert_supplier())

    await delete_data()  # сначало будет удаление данных

    # await asyncio.gather(task1_insert_cities,
    #                      task2_insert_med_direction,
    #                      task3_insert_manufacturer,
    #                      task4_insert_supplier
    #                      )

    await insert_equipment()



if __name__ == '__main__':
    # asyncio.run(delete_data())
    # asyncio.run(get_id(name='Витал', table=Manufacturer))
    asyncio.run(main())
