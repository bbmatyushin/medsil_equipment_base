"""Наполнение таблиц Postgres данными полученными из MS Access."""

import os
import logging
import json
import uuid
import django

from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ebase_site.settings")
django.setup()

from ebase.models import *

logger = logging.getLogger('INSERT_DATA')

json_dir = '/home/human/Coding/Sites/medsil_equipment_base/accembler_db/tables_json'


class InsertData:
    def get_instance_client(self, client_code_ms: int) -> django.db.models:
        """Получаем экземпляр клиента из нашей БД.
        :params client_code_ms: Код клиента из MS Access."""
        with open(Path(json_dir, 'клиент.json'), 'r', encoding='utf-8') as f:
            for line in f:
                client = json.loads(line)
                if client.get('КодКлиента') == client_code_ms:
                    dept_client = Client.objects.get(name=client.get('Наименование'),
                                                     inn=client.get('ИНН'))
                    return dept_client

    def get_instance_city(self, city_code_ms: int) -> django.db.models:
        """Получаем экземпляр города из нашей БД.
        :params city_code_ms: Код города из MS Access."""
        with open(Path(json_dir, 'города.json'), 'r', encoding='utf-8') as f:
            for line in f:
                city = json.loads(line)
                if city.get('Код') == city_code_ms:
                    dept_city = City.objects.get(name=city.get('Город'), region=city.get('Область'))
                    return dept_city

    def get_instance_department(self, department_code_ms: int) -> django.db.models:
        """Получаем экземпляр подразделения из нашей БД.
        :params department_code_ms: Код подразделения из MS Access."""
        with open(Path(json_dir, 'подразделение.json'), 'r', encoding='utf-8') as f:
            for line in f:
                department = json.loads(line)
                if department.get('Код') == department_code_ms:
                    dept_department = Department.objects.get(name=department.get('Наименование'),
                                                             address=department.get('Адрес'))
                    return dept_department
                
    def get_instance_manufacturer(self, manufacturer_name_ms: str) -> django.db.models:
        """Получаем экземпляр производителя из нашей БД.
        :params manufacturer_name_ms: Название производителя из MS Access."""
        manufacturer = Manufacturer.objects.get(name=manufacturer_name_ms)
        return manufacturer

    def get_instance_med_direction(self, med_direction_code_ms: int) -> django.db.models:
        """Получаем экземпляр мед. направления из нашей БД.
        :params med_direction_code_ms: Код мед. направления из MS Access."""
        with open(Path(json_dir, 'направление.json'), 'r', encoding='utf-8') as f:
            for line in f:
                med_direction = json.loads(line)
                if med_direction.get('Код') == med_direction_code_ms:
                    med_direction = MedDirection.objects.get(name=med_direction.get('НаименованиеНаправления'))
                    return med_direction

    def get_instance_post(self, post_name: str) -> django.db.models:
        """Получаем экземпляр должности из нашей БД.
        :params post_name: Название должности."""
        return Position.objects.get(name=post_name)
    
    def get_instance_supplier(self, supplier_name_ms: str) -> django.db.models:
        """Получаем экземпляр поставщика из нашей БД.
        :params supplier_name_ms: Название поставщика из MS Access."""
        supplier = Supplier.objects.get(name=supplier_name_ms)
        return supplier

    def cities(self) -> None:
        """Заполняем таблицу City."""
        City.objects.create(name='Не указан')
        with open(Path(json_dir, 'города.json'), 'r', encoding='utf-8') as f:
            for line in f:
                city = json.loads(line)
                try:
                    City.objects.create(name=city['Город'], region=city['Область'])
                    logger.info(f'Город {city["Город"]} добавлен.')
                except Exception as e:
                    logger.error(e)

    def clients(self) -> None:
        """Заполняем таблицу Client."""
        with open(Path(json_dir, 'клиент.json'), 'r', encoding='utf-8') as f:
            for line in f:
                client = json.loads(line)
                try:
                    Client.objects.create(name=client.get('Наименование'), inn=client.get('ИНН'),
                                          city=City.objects.get(name='Не указан'))
                    logger.info(f"Клиент {client.get('Наименование')} добавлен.")
                except Exception as e:
                    logger.error(e)

    def countries(self) -> None:
        """Добавляем страны"""
        country_list = [
            Country(name='Россия'),
            Country(name='Германия'),
        ]
        Country.objects.bulk_create(country_list)

    def dept_contact_pers(self) -> None:
        """Заполняем таблицу DeptContactPers."""
        with open(Path(json_dir, 'контактные_лица.json'), 'r', encoding='utf-8') as f:
            for line in f:
                contact_person = json.loads(line)
                post = contact_person.get('Должность')
                if post:
                    if post == 'зав.лаб':
                        post = 'зав.лаб.'
                    try:
                        Position.objects.create(name=post, type=PositionType.client.name)
                    except Exception as e:
                        logger.error(f"Add position {post} error: {e}")
                try:
                    position = self.get_instance_post(contact_person.get('Должность'))
                    department = self.get_instance_department(contact_person.get('Больница'))
                    surname = name = patron = mob_phone = work_phone = None
                    if contact_person.get('ФИО'):
                        fio = contact_person['ФИО'].strip().split()
                        if len(fio) == 3:
                            surname, name, patron = map(str.strip, fio)
                        elif len(fio) == 2:
                            name, patron = map(str.strip, fio)
                        else:
                            name = fio[0].strip()
                        if contact_person.get('Телефон'):
                            mob_phone = contact_person['Телефон'] if contact_person['Телефон'].startswith('+') \
                                else contact_person['Телефон'] if contact_person['Телефон'].startswith('8') \
                                else '+7' + contact_person['Телефон']
                        if contact_person.get('Второй номер'):
                            work_phone = contact_person['Второй номер'] if contact_person['Второй номер'].startswith('+') \
                                else contact_person['Второй номер'] if contact_person['Второй номер'].startswith('8') \
                                else '+7' + contact_person['Второй номер']
                        DeptContactPers.objects.create(surname=surname, name=name, patron=patron,
                                                       mob_phone=mob_phone, work_phone=work_phone,
                                                       position=position, department=department)
                        logger.info(f'Контактное лицо {contact_person.get("ФИО")} добавлено.')
                except Exception as e:
                    logger.error(e)

    def departments(self) -> None:
        """Заполняем таблицу Department."""
        with open(Path(json_dir, 'подразделение.json'), 'r', encoding='utf-8') as f:
            for line in f:
                department = json.loads(line)
                try:
                    client = self.get_instance_client(department.get('Клиент'))
                    city = self.get_instance_city(department['Город']) if department.get('Город') \
                        else City.objects.get(name='Не указан')
                    Department.objects.create(name=department.get('Наименование'),
                                              address=department.get('Адрес'),
                                              client=client, city=city)
                    logger.info(f'Подразделение {department.get("Наименование")} добавлено.')
                except Exception as e:
                    logger.error(e)

    def equipment(self) -> None:
        """Добовляем оборудование"""
        with open(Path(json_dir, 'список_оборудования.json'), 'r', encoding='utf-8') as f:
            for line in f:
                equipment = json.loads(line)
                try:
                    med_direction = self.get_instance_med_direction(equipment['Направление']) \
                        if equipment.get('Направление') else None
                    manufacturer = self.get_instance_manufacturer(equipment['Производитель']) \
                        if equipment.get('Производитель') else None
                    supplier = self.get_instance_supplier(equipment['Поставщик']) \
                        if equipment.get('Поставщик') else None
                    Equipment.objects.create(full_name=equipment.get('Название полное'),
                                             short_name=equipment.get('Краткое название'),
                                             med_direction=med_direction,
                                             manufacturer=manufacturer,
                                             supplier=supplier)
                    logger.info(f'Оборудование {equipment.get("Название полное")} добавлено.')
                except Exception as e:
                    logger.error(e)

    def equipment_status(self) -> None:
        """Добавляем фиксированные надоры статусов"""
        eqipment_status_list = [
            EquipmentStatus(name='В ремонте'),
            EquipmentStatus(name='Работает'),
            EquipmentStatus(name='Подменный'),
            EquipmentStatus(name='Апробация'),
            EquipmentStatus(name='Неисправен'),
            EquipmentStatus(name='Списание'),
        ]
        EquipmentStatus.objects.bulk_create(eqipment_status_list)

    def med_direction(self) -> None:
        """Добавляем направления"""
        med_dir_list = []
        with open(Path(json_dir, 'направление.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                med_dir_list.append(MedDirection(name=data.get('НаименованиеНаправления')))
        MedDirection.objects.bulk_create(med_dir_list)

    def manufacturer_supplier(self) -> None:
        """Добавляем поставщиков и производителей"""
        with open(Path(json_dir, 'список_оборудования.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                if data.get('Производитель'):
                    try:
                        Manufacturer.objects.create(name=data.get('Производитель'))
                        logger.info(f'Производитель {data.get("Производитель")} добавлен.')
                    except Exception as e:
                        logger.error(e)
                if data.get('Поставщик'):
                    try:
                        if data.get('Поставщик') == 'ЗАО Аналитика':
                            Supplier.objects.create(name=data.get('Поставщик'),
                                                    contact_person='Сервисный отдел',
                                                    contact_phone='(495) 748-11-71',
                                                    email='serv@analytica.ru')
                        else:
                            Supplier.objects.create(name=data.get('Поставщик'))
                        logger.info(f'Поставщик {data.get("Поставщик")} добавлен.')
                    except Exception as e:
                        logger.error(e)

    def units(self) -> None:
        """Добавляем единицы измерения"""
        unit_list = [
            Unit(short_name='шт', full_name='штука'),
            Unit(short_name='упак', full_name='упаковка'),

        ]
        Unit.objects.bulk_create(unit_list)




def main():
    insert = InsertData()

    # insert.equipment_status()
    # insert.med_direction()
    # insert.units()
    # insert.cities()
    # insert.countries()

    """Вставка из JSON файлов"""
    # insert.clients()
    # insert.departments()
    # insert.dept_contact_pers()
    insert.manufacturer_supplier()
    insert.equipment()


if __name__ == '__main__':
    main()
    # print(InsertData().get_instance_city(12).name)
    # python manage.py sqlsequencereset myapp | python manage.py dbshell - для сброса счетчика id
