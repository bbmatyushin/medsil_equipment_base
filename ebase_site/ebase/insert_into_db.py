"""Наполнение таблиц Postgres данными полученными из MS Access."""

import os
import logging
import json
import uuid
from datetime import datetime

import django

from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ebase_site.settings")
django.setup()

from ebase.models import *
from users.models import CompanyUser

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

    def get_instance_equipment(self, equipment_code_ms: int) -> django.db.models:
        """Получаем экземпляр оборудования из нашей БД.
        :params equipment_code_ms: Код оборудования из MS Access."""
        with open(Path(json_dir, 'список_оборудования.json'), 'r', encoding='utf-8') as f:
            for line in f:
                equipment = json.loads(line)
                if equipment.get('Код') == equipment_code_ms:
                    equipment = Equipment.objects.get(full_name=equipment.get('Название полное'),
                                                      short_name=equipment.get('Краткое название'))
                    return equipment

    def get_instance_equipment_by_sn(self, serial_number: str) -> django.db.models:
        """Получаем экземпляр оборудования из нашей БД.
        :params serial_number: Серийный номер оборудования."""
        try:
            equipment = EquipmentAccounting.objects.get(serial_number=serial_number).equipment
        except Exception as err:
            logger.error(err)
            equipment = None
        return equipment

    def get_instance_equipment_accounting(self, serial_namber: str) -> django.db.models:
        """Получаем экземпляр учтенного оборудования из нашей БД"""
        equipment_acc = EquipmentAccounting.objects.get(serial_number=serial_namber)
        return equipment_acc

    def get_instance_equipment_status(self, status: str) -> django.db.models:
        """Получаем экземпляр статуса оборудования из нашей БД."""
        equipment_status = EquipmentStatus.objects.get(name=status)
        return equipment_status

    def get_instance_engineer(self, engineer_name: str) -> django.db.models:
        """Получаем экземпляр инженера из нашей БД"""
        engineer = Engineer.objects.get(name=engineer_name)
        return engineer
                
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

    def get_instance_service_type(self, type_name: str) -> django.db.models:
        """Получаем экземпляр вида работ из нашей БД.
        :params type_name: Название типа сервиса."""
        return ServiceType.objects.get(name=type_name)

    def get_instance_spare_part(self, spare_part_name: str, serial_number: str) -> django.db.models:
        """Получаем экземпляр запчасти из нашей БД.
        :params spare_part_name: Название запчасти."""
        equipment = EquipmentAccounting.objects.get(serial_number=serial_number)
        return SparePart.objects.get(name=spare_part_name, equipment=equipment.equipment_id)
    
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
                    if department.get('Код') == 125:
                        print(department)
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

    def equipment_accounting(self) -> None:
        """Добовляем обородования для ведения учета"""
        user = CompanyUser.objects.get(username='admin')
        with open(Path(json_dir, 'общая_база.json'), 'r', encoding='utf-8') as f:
            for line in f:
                equipment, status = None, None
                data = json.loads(line)
                if data.get('Наименование прибора'):
                    equipment = self.get_instance_equipment(data.get('Наименование прибора'))
                if data.get('Статус прибора'):
                    status = self.get_instance_equipment_status(data.get('Статус прибора'))
                try:
                    EquipmentAccounting.objects.create(equipment=equipment, serial_number=data.get('Серийный номер'),
                                                       equipment_status=status, user=user)
                    logger.info(f'Оборудование {equipment} добавлено.')
                except Exception as e:
                    logger.error(e)

    def equipment_acc_department(self) -> None:
        """Добавляем подразделения в которых установлено оборудование"""
        with open(Path(json_dir, 'общая_база.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                equipment_acc = self.get_instance_equipment_accounting(data.get('Серийный номер'))
                department = self.get_instance_department(data.get('Подразделение'))
                engineer = self.get_instance_engineer(data.get('Инженер')) if data.get('Инженер') else None
                install_dt = datetime.strptime(data['Дата монтажа'], '%Y-%m-%d %H:%M:%S') \
                    if data.get('Дата монтажа') else None
                try:
                    EquipmentAccDepartment.objects.create(equipment_accounting=equipment_acc,
                                                          department=department,
                                                          engineer=engineer,
                                                          install_dt=install_dt)
                    logger.info(f'Оборудование {equipment_acc} + {department} добавлено.')
                    # TODO: Выпадает с ошибкой - несущесвующее подразделение
                except Exception as e:
                    logger.error(f"{department=}\n{e}")

    def equipment_status(self) -> None:
        """Добавляем фиксированные надоры статусов"""
        status_list: set = set()
        with open(Path(json_dir, 'общая_база.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                if data.get('Статус прибора'):
                    status_list.add(data.get('Статус прибора'))
        status_list = [EquipmentStatus(name=s) for s in status_list]
        EquipmentStatus.objects.bulk_create(status_list)

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

    def positions(self) -> None:
        """Добавляем должность инженер компании"""
        Position.objects.create(name='инженер', type=PositionType.employee.name)

    def service(self) -> None:
        """Добавляем записи о ремонте"""
        with open(Path(json_dir, 'ремонт.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                user = CompanyUser.objects.get(username='admin')
                service_type = self.get_instance_service_type(data.get('Вид работ')) if data.get('Вид работ') else None
                description = data['Описание неисправности'] if data.get('Описание неисправности') else None
                reason = data['На основании'] if data.get('На основании') else None
                job_content = data['Содержание работ']if data.get('Содержание работ') else None
                beg_dt = datetime.strptime(data['Дата ремонта'], '%Y-%m-%d %H:%M:%S') \
                    if data.get('Дата ремонта') else None
                comment = data['Примечание'] if data.get('Примечание') else None
                equipment_accounting = self.get_instance_equipment_accounting(data.get('Серийный номер'))
                spare_part_instances = []
                if data.get('Запчасти'):
                    parts = data['Запчасти'].split('\r\n')
                    for part in parts:
                        spare_part_instances.append(self.get_instance_spare_part(part, data['Серийный номер']))
                try:
                    service = Service(
                        service_type=service_type,
                        description=description,
                        reason=reason,
                        job_content=job_content,
                        beg_dt=beg_dt,
                        comment=comment,
                        user=user
                    )
                    pk = service.pk
                    service.save()
                    service_instance = Service.objects.get(pk=pk)
                    if equipment_accounting:
                        service_instance.equipment_accounting.set([equipment_accounting])
                    if spare_part_instances:
                        for spare_part in spare_part_instances:
                            service_instance.spare_part.set([spare_part])
                    logger.info(f'Ремонт {data.get("Серийный номер")} добавлен.')
                except Exception as e:
                    logger.error(e)

    def service_type(self) -> None:
        """Добавляем виды работ"""
        with open(Path(json_dir, 'ремонт.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                if data.get('Вид работ'):
                    try:
                        ServiceType.objects.create(name=data.get('Вид работ'))
                    except Exception as e:
                        logger.error(e)

    def spare_parts(self) -> None:
        """Добавляем запчасти"""
        with open(Path(json_dir, 'ремонт.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                equipment = self.get_instance_equipment_by_sn(data.get('Серийный номер'))
                if equipment:
                    if data.get('Запчасти'):
                        parts = data.get('Запчасти').split('\r\n')  # TODO: Нужно ещё разделять по запятым
                        for part in parts:
                            try:
                                spare_part = SparePart(name=part, article=equipment.full_name[:50],)
                                pr_key = spare_part.pk
                                spare_part.save()
                                part_instance = SparePart.objects.get(pk=pr_key)
                                part_instance.equipment.set([equipment])
                                logger.info(f'Запчасть {part} добавлена.')
                            except Exception as e:
                                logger.error(e)

    def units(self) -> None:
        """Добавляем единицы измерения"""
        unit_list: set = set()
        with open(Path(json_dir, 'запчасти.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                if data.get('Едизм'):
                    unit_list.add(data.get('Едизм'))
        unit_list = [Unit(short_name=u) for u in unit_list]
        Unit.objects.bulk_create(unit_list)

    def engineers(self) -> None:
        """Добавляем инженеров"""
        with open(Path(json_dir, 'общая_база.json'), 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                if data.get('Инженер'):
                    try:
                        Engineer.objects.create(name=data.get('Инженер'))
                    except Exception as e:
                        logger.error(e)


def get_json_keys() -> str:
    """Возвращает список ключей JSON файлов."""
    file_name = 'ремонт.json'
    keys: set = set()
    users: set = set()
    with open(Path(json_dir, file_name), 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            for k in data.keys():
                keys.add(k)
                if k == 'Инженер':
                    users.add(data.get(k))

    return f"{sorted(keys)=}\n{sorted(users)=}"


def main():
    insert = InsertData()

    # insert.med_direction()
    # insert.units()
    # insert.cities()
    # insert.countries()
    # insert.positions()

    """Вставка из JSON файлов"""
    # insert.equipment_status()
    # insert.clients()
    # TODO: Заменить у подразделения.json "Код":125,"Наименование":"Сланцевская межрайонная больница","Клиент":90 на 16 ! ! !
    # insert.departments()
    # insert.dept_contact_pers()
    # insert.manufacturer_supplier()
    # insert.equipment()
    # insert.engineers()
    # insert.equipment_accounting()
    # insert.equipment_acc_department()
    # insert.spare_parts()  # TODO: Нужно исправить # TODO: Нужно ещё разделять по запятым
    # insert.service_type()
    # TODO: В таблице service_equipment_accounting слишком много записей по ремонты одного оборудования. Нужно проверить связи.
    insert.service()


if __name__ == '__main__':
    main()
    # print(InsertData().get_instance_city(12).name)
    # python manage.py sqlsequencereset myapp | python manage.py dbshell - для сброса счетчика id
    print(get_json_keys())
