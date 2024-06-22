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
    """Получаем id по имени из нашей БД"""
    async with async_session() as session:
        async with session.begin():
            result_id = await session.execute(select(table.id).filter_by(name=name))
            id_value = result_id.scalar()
        # print(f"{id_value=}")
        if table.__name__ == 'Manufacturer' and id_value is None:
            id_value = uuid.UUID('00000000-0000-0000-0000-000000000000')
        return id_value


async def get_name_by_code(code: int, file_path: str, ms_key: str) -> str:
    """Функция принимает код и возвращает значение ключа ms_key в файле file_path из БД MS Access"""
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async for line in f:
            data = json.loads(line)
            if data.get('Код') == code or data.get('КодКлиента') == code:
                return data.get(ms_key)


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

            async with session.begin():
                # Добавляет производителя заглушку
                null_name = Manufacturer(name='Не указано', is_active=True,
                                         id=uuid.UUID('00000000-0000-0000-0000-000000000000'))
                session.add(null_name)


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
            async for line in f:
                try:
                    async with session.begin():
                        equipment_data = json.loads(line)
                        fullname = equipment_data.get('Название полное')
                        shortname = equipment_data.get('Краткое название', None)
                        med_dir_code = equipment_data.get('Направление', None)
                        med_dir_name = data_med_dir.get(med_dir_code, None)
                        med_directory_id = await get_id(name=med_dir_name, table=MedDirectory)
                        manufacturer_id = await get_id(name=equipment_data.get('Производитель'),
                                                       table=Manufacturer)
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
                            logger.error(f"{err.orig=}")
                            logger.error(f"{fullname=}, {med_directory_id=}, {manufacturer_id=}, {supplier_id=}")
                except Exception as err:
                    logger.error(f"{err=}")
                    exit(1)


async def insert_client():
    """Добавляем клиентов из БД MS Access в новую БД"""
    file_path = 'accembler_db/tables_json/клиент.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        if data.get('Наименование'):
                            new_row = Client(name=data.get('Наименование'),
                                             inn=data.get('ИНН'))
                            session.add(new_row)
                except IntegrityError as err:
                    logger.error(err.orig)


async def insert_department():
    """Добавляем подразделения из БД MS Access в новую БД"""
    file_path = 'accembler_db/tables_json/подразделение.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        if data.get('Наименование'):
                            name = data['Наименование']
                            address = data.get('Адрес')
                            city_code = data.get('Город')
                            if city_code:
                                city_path = 'accembler_db/tables_json/города.json'
                                city_name = await get_name_by_code(code=city_code,
                                                                   file_path=city_path,
                                                                   ms_key='Город')
                                city_uuid = await get_id(name=city_name, table=Cities)
                            else:
                                city_uuid = None
                            client_code = data.get('Клиент')
                            if client_code:
                                client_path = 'accembler_db/tables_json/клиент.json'
                                client_name = await get_name_by_code(code=client_code,
                                                                     file_path=client_path,
                                                                     ms_key='Наименование')
                                client_uuid = await get_id(name=client_name, table=Client)
                            else:
                                client_uuid = None

                            new_row = Department(name=name, client_id=client_uuid,
                                                 city_id=city_uuid, address=address)
                            session.add(new_row)
                except IntegrityError as err:
                    logger.error(err.orig)


async def insert_position():
    """Наполняем таблицу с должностями КЛИЕНТОВ"""
    file_path = 'accembler_db/tables_json/контактные_лица.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        if data.get('Должность'):
                            new_row = Position(name=data.get('Должность'), type='client')
                            session.add(new_row)
                except IntegrityError as err:
                    logger.error(err.orig)
            async with session.begin():
                # Удаляем должность 'зав.лаб', т.к. она дублируется с 'зав.лаб.'
                await session.execute(delete(Position).filter_by(name='зав.лаб'))


async def insert_deptcontactpers():
    """Контактные лица подразделений"""
    file_path = 'accembler_db/tables_json/контактные_лица.json'
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        async with async_session() as session:
            async for line in f:
                data = json.loads(line)
                try:
                    async with session.begin():
                        surname = name = patron = mob_phone = work_phone = dept_uuid = None
                        if data.get('ФИО'):
                            fio = data['ФИО'].strip().split()
                            if len(fio) == 3:
                                surname, name, patron = map(str.strip, fio)
                            elif len(fio) == 2:
                                name, patron = map(str.strip, fio)
                            else:
                                name = fio[0].strip()
                            position = 'зав.лаб.' if data.get('Должность') == 'зав.лаб' else data.get('Должность')
                            position_uuid = await get_id(name=position, table=Position)
                            if data.get('Телефон'):
                                mob_phone = data['Телефон'] if data['Телефон'].startswith('+') \
                                    else data['Телефон'] if data['Телефон'].startswith('8') \
                                    else '+7' + data['Телефон']
                            if data.get('Второй номер'):
                                work_phone = data['Второй номер'] if data['Второй номер'].startswith('+') \
                                    else data['Второй номер'] if data['Второй номер'].startswith('8') \
                                    else '+7' + data['Второй номер']
                            if data.get('Больница'):
                                dept_path = 'accembler_db/tables_json/подразделение.json'
                                dept_name = await get_name_by_code(code=data['Больница'],
                                                                   file_path=dept_path,
                                                                   ms_key='Наименование')
                                dept_uuid = await get_id(name=dept_name, table=Department)
                            comment = data['Примечание'] if data.get('Примечание') else None
                            new_row = DeptContactPers(department_id=dept_uuid,
                                                      name=name, surname=surname, patron=patron,
                                                      position_id=position_uuid, mob_phone=mob_phone,
                                                      work_phone=work_phone, comment=comment)
                            session.add(new_row)
                except IntegrityError as err:
                    logger.error(err.orig)


async def insert_spare_parts():  # TODO Добавить запчасти
    pass


async def delete_data():
    """Удаление данных из таблицы"""
    async with async_session() as session:
        async with session.begin():
            # await session.execute(delete(Cities))
            # await session.execute(delete(MedDirectory))
            # await session.execute(delete(Manufacturer))
            # await session.execute(delete(Supplier))
            # await session.execute(delete(Client))
            # await session.execute(delete(Equipment))
            # await session.execute(delete(Department))
            # await session.execute(delete(Position))
            # await session.execute(delete(DeptContactPers))
            await session.execute(delete(SparePart))
            pass


async def main():
    # task_delete_data = asyncio.create_task(delete_data())
    await delete_data()  # сначало будет удаление данных

    # task1_insert_cities = asyncio.create_task(insert_cities())
    # task2_insert_med_direction = asyncio.create_task(insert_med_direction())
    # task3_insert_manufacturer = asyncio.create_task(insert_manufacturer())
    # task4_insert_supplier = asyncio.create_task(insert_supplier())
    # task5_insert_client = asyncio.create_task(insert_client())


    # await asyncio.gather(task1_insert_cities,
    #                      task2_insert_med_direction,
    #                      task3_insert_manufacturer,
    #                      task4_insert_supplier,
    #                      task5_insert_client
    #                      )
    # await insert_client()
    # await insert_equipment()
    # await insert_department()
    # await insert_position()
    # await insert_deptcontactpers()
    await insert_spare_parts()


if __name__ == '__main__':
    # asyncio.run(delete_data())
    # asyncio.run(get_id(name='Витал', table=Manufacturer))
    asyncio.run(main())
