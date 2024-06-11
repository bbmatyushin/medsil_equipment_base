import uuid
import asyncio
import re
from datetime import datetime, date

from sqlalchemy import UUID, Integer, String, TIMESTAMP, ForeignKey, Boolean, SmallInteger, Date
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from database import engine, async_session


class Base(DeclarativeBase):
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    @validates('inn', 'kpp')
    def validate_fields(self, key, value):
        """Проверка правильности заполнения полей"""
        if key == 'inn':
            value = re.sub(r'\s+', '', value)
            if not value.isdigit():
                raise ValueError(f'ИНН должен содержать только цифр: {value}')
            if len(value) not in (10, 12):
                raise ValueError(f'ИНН должен содержать 10 или 12 цифр: {value}')
            return value

        if key == 'kpp': ...


class Cities(Base):
    __tablename__ = "cities"
    __table_args__ = {'comment': 'Информация о городах'}

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название города')
    region: Mapped[str] = mapped_column(String(100), nullable=True, comment='Область / Регион')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')

    # relationships
    department: Mapped[list["Department"]] = relationship(back_populates="city")
    client: Mapped[list["Client"]] = relationship(back_populates="city")
    supplier: Mapped[list["Supplier"]] = relationship(back_populates="city")
    manufacturer: Mapped[list["Manufacturer"]] = relationship(back_populates="city")

    def __repr__(self):
        return f'<City(id={self.id!r}, name={self.name!r}, region={self.region!r})>'


class Client(Base):
    __tablename__ = "client"
    __table_args__ = {'comment': 'Таблица с информацией о клиентах (ЛПУ)'}

    name: Mapped[str] = mapped_column(String(150), nullable=False,  comment='Название клиента')
    inn: Mapped[str] = mapped_column(String(12), nullable=True, comment='ИНН клиента')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               nullable=True, comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), nullable=True, comment='Адрес клиента')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')

    # relationships
    department: Mapped[list["Department"]] = relationship(back_populates="client")
    city: Mapped["Cities"] = relationship(back_populates="client")

    def __repr__(self):
        return f'<Client(id={self.id!r}, name={self.name!r})>'


class Department(Base):
    __tablename__ = "department"
    __table_args__ = {'comment': 'Информациея о подразделениях/филиалах'}

    name: Mapped[str] = mapped_column(String(150), nullable=False,  comment='Название подразделения')
    client_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('client.id', ondelete='CASCADE'),
                                                 nullable=False,
                                                 comment='Значение из таблицы client.id')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               nullable=False,
                                               comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), nullable=True, comment='Адрес подразделения')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')

    # relationships
    city: Mapped["Cities"] = relationship(back_populates="department")
    client: Mapped["Client"] = relationship(back_populates="department")
    dept_contact_pers: Mapped[list["DeptContactPers"]] = relationship(back_populates="department")
    equipment_acc_department: Mapped[list["EquipmentAccDepartment"]] = \
        relationship(back_populates='department')

    def __repr__(self):
        return f'<Department(id={self.id!r}, name={self.name!r})>'


class DeptContactPers(Base):
    __tablename__ = "dept_contact_pers"
    __table_args__ = {'comment': 'Контактные лицах для подразделений / филиалов'}

    department_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('department.id', ondelete='CASCADE'),
                                                     nullable=False,
                                                     comment='Значение из таблицы department.id')
    surname: Mapped[str] = mapped_column(String(50), nullable=True, comment='Фамилия контактного лица')
    name: Mapped[str] = mapped_column(String(50), nullable=False,  comment='Имя контактного лица')
    patron: Mapped[str] = mapped_column(String(50), nullable=True, comment='Отчество контактного лица')
    position_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('position.id', ondelete='CASCADE'),
                                                   nullable=True, comment='Значение из таблицы position.id')
    mob_phone: Mapped[str] = mapped_column(String(60), nullable=True, comment='Контактный (мобильный) телефон')
    work_phone: Mapped[str] = mapped_column(String(60), nullable=True, comment='Рабочий телефон')
    email: Mapped[str] = mapped_column(String(50), nullable=True, comment='Электронная почта')
    comment: Mapped[str] = mapped_column(String(300), nullable=True, comment='Комментарий')
    is_active: Mapped[bool] = mapped_column(default=True, nullable=True, comment='Для мягкого удаления записи')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='Дата и время добавления записи')

    # relationships
    department: Mapped["Department"] = relationship(back_populates="dept_contact_pers")
    position: Mapped["Position"] = relationship(back_populates="dept_contact_pers")

    def __repr__(self):
        return f'<DeptContactPers(id={self.id!r}, name={self.name!r}, department_id={self.department_id!r})>'


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = {'comment': 'Таблица с информацией об оборудование'}

    fullname: Mapped[str] = mapped_column(String(50), nullable=False, comment='Полное название оборудования')
    shortname: Mapped[str] = mapped_column(String(20))
    med_directory: Mapped[str] = mapped_column(String(20), nullable=True, comment='Вид направления: Гематология, Биохимия и т.д.')
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(UUID,
                                                       ForeignKey('manufacturer.id',
                                                                  ondelete='CASCADE'),
                                                       nullable=False,
                                                       comment='id производителя')
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('supplier.id',
                                                                    ondelete='CASCADE'),
                                                   nullable=True, comment='id поставщика (обязательное поле)')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')

    # relationships
    equipment_accounting: Mapped[list["EquipmentAccounting"]] = relationship(back_populates='equipment')
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="equipment")
    supplier: Mapped["Supplier"] = relationship(back_populates="equipment")
    equipment_spare_part: Mapped[list["EquipmentSparePart"]] = relationship(back_populates='equipment')

    def my_test(self):
        print(self.__dict__)

    def __repr__(self):
        return f'Equipment(id={self.id!r}, fullname={self.fullname!r}, shortname={self.shortname!r}, ' \
               f'med_directory={self.med_directory!r}, manufacturer_id={self.manufacturer_id!r}, ' \
               f'supplier_id={self.supplier_id!r}, create_dt={self.create_dt!r})'


class EquipmentAccounting(Base):
    __tablename__ = "equipment_accounting"
    __table_args__ = {'comment': 'Учёт оборудования. Основная таблица'}

    equipment_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment.id', ondelete='CASCADE'),
                                                    nullable=False, comment='id оборудования')
    serial_num: Mapped[str] = mapped_column(String(50), nullable=False, comment='Серийный номер оборудования')
    equipment_status_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment_status.id', ondelete='CASCADE'),
                                                          nullable=False, comment='id статуса обслуживания')
    service_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('service.id', ondelete='CASCADE'),
                                                  nullable=True, comment='id ремонта. Заполняется если оборудование было сдано в ремонте')
    is_service: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True, comment='True если прибор был обслужан МЕДСИЛ')
    is_our_supply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True, comment='True если прибор был поставлен МЕДСИЛ')
    usr_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'),
                                               nullable=False, comment='id пользователя, добавившего запись')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')

    # relationships
    equipment: Mapped["Equipment"] = relationship(back_populates="equipment_accounting")
    user: Mapped["User"] = relationship(back_populates="equipment_accounting")
    equipment_status: Mapped["EquipmentStatus"] = relationship(back_populates="equipment_accounting")
    equipment_acc_department: Mapped[list["EquipmentAccDepartment"]] = \
        relationship(back_populates="equipment_accounting")
    service: Mapped[list["Service"]] = \
        relationship(back_populates="equipment_accounting",
                     primaryjoin='EquipmentAccounting.id == Service.equipment_accounting_id')

    def __repr__(self):
        return f'EquipmentAccounting(id={self.id!r}, equipment_id={self.equipment_id!r}, ' \
               f'serial_num={self.serial_num!r}, is_service={self.is_service!r}, ' \


class EquipmentAccDepartment(Base):
    __tablename__ = "equipment_acc_department"
    __table_args__ = {"comment": "Подразделения в котором установлены приборы, с указанием id сотрудника, "
                                 "который запускал данное оборудование."}

    equipment_accounting_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment_accounting.id',
                                                                                ondelete='CASCADE'),
                                                               nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('department.id', ondelete='CASCADE'),
                                                     nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            comment='Флаг, указывающий на то, что прибор установлен в '
                                                    'подразделении клиента')

    # relationship
    equipment_accounting: Mapped["EquipmentAccounting"] = \
        relationship(back_populates='equipment_acc_department')
    department: Mapped["Department"] = relationship(back_populates='equipment_acc_department')
    equipment_acc_department_emp: Mapped[list["EquipmentAccDepartmentEmp"]] = \
        relationship(back_populates='equipment_acc_department')

    def __repr__(self):
        return f"EquipmentAccDepartment(id={self.id!r})"


class EquipmentAccDepartmentEmp(Base):
    __tablename__ = "equipment_acc_department_emp"
    __table_args__ = {"comment": "Связь между сотрудником(-ми), которые установили оборудование в подразделении"}

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('employee.id', ondelete='CASCADE'),
                                                   nullable=False, comment='id сотрудника')
    equipment_acc_department_id: Mapped[uuid.UUID] = mapped_column(UUID,
                                                                   ForeignKey('equipment_acc_department.id',
                                                                              ondelete='CASCADE'),
                                                                   nullable=False,
                                                                   comment='id записи в таблице equipment_acc_department')

    # relationship
    employee: Mapped["Employee"] = relationship(back_populates='equipment_acc_department_emp')
    equipment_acc_department: Mapped["EquipmentAccDepartment"] = \
        relationship(back_populates='equipment_acc_department_emp')

    def __repr__(self):
        return f"EquipmentAccDepartmentEmp(id={self.id!r})"


class EquipmentSparePart(Base):
    __tablename__ = "equipment_spare_part"
    __table_args__ = {"comment": "Связь между оборудование и запчастями. Связывает таблицы equipment и spare_part"}

    equipment_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment.id', ondelete='CASCADE'),
                                                    nullable=False)
    spare_part_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part.id', ondelete='CASCADE'),
                                                     nullable=False)

    # relationship
    equipment: Mapped[list["Equipment"]] = relationship(back_populates='equipment_spare_part')
    spare_part: Mapped[list["SparePart"]] = relationship(back_populates='equipment_spare_part')

    def __repr__(self):
        return f"EquipmentSparePart(id={self.id!r})"


class EquipmentStatus(Base):
    __tablename__ = 'equipment_status'
    __table_args__ = {'comment': 'фиксированный набор статусов для оборудования'}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True, comment='ID статуса')
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='Название статуса')

    # relationships
    equipment_accounting: Mapped[list["EquipmentAccounting"]] = relationship(back_populates="equipment_status")

    def __repr__(self):
        return f'<EquipmentStatus(id={self.id!r}, name={self.name!r})>'


class Employee(Base):
    __tablename__ = 'employee'
    __table_args__ = {'comment': 'Сотрудники'}

    usr_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'),
                                              nullable=False, comment='ID пользователя')
    position_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('position.id', ondelete='CASCADE'),
                                                   nullable=False, comment='ID должности')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                            comment='True - сотрудник работает, False - сотрудник не работает')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(), nullable=True, comment='Дата создания записи')

    # relationships
    user: Mapped["User"] = relationship(back_populates="employee")
    position: Mapped["Position"] = relationship(back_populates="employee")
    equipment_acc_department_emp: Mapped[list["EquipmentAccDepartmentEmp"]] = \
        relationship(back_populates="employee")
    service: Mapped[list["Service"]] = relationship(back_populates="employee")

    def __repr__(self):
        return f'<Employee(usr_id={self.usr_id!r}, position_id={self.position_id!r}, ' \
               f'is_active={self.is_active!r}, create_dt={self.create_dt!r})>'


class LoginPass(Base):
    __tablename__ = 'login_pass'
    __table_args__ = {"comment": "Таблица с логинами и паролями"}

    usr_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'),
                                              unique=True, nullable=False, comment='ID пользователя')
    login: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment='Логин пользователя')
    password: Mapped[str] = mapped_column(String(32), nullable=False, comment='Пароль пользователя в шифрованном виде MD5')
    create_dt: Mapped[date] = mapped_column(Date, default=date.today(), nullable=True, comment='Дата создания записи')

    # relationships
    user: Mapped["User"] = relationship(back_populates="login_pass")

    # def __init__(self, login, password):
    #     self.login = login
    #     self.password = password

    def __repr__(self):
        return f'<LoginPass(usr_id={self.usr_id!r}, login={self.login!r}, password={self.password!r})>'


class Manufacturer(Base):
    __tablename__ = "manufacturer"
    __table_args__ = {'comment': 'Таблица с информацией о производителях'}

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название производителя')  # обязательное поле)
    inn: Mapped[str] = mapped_column(String(12), nullable=True, comment='ИНН производителя')
    country: Mapped[str] = mapped_column(String(20), nullable=True, comment='Страна производителя')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               comment='Значение из таблицы cities.id',
                                               nullable=True)
    address: Mapped[str] = mapped_column(String(200), nullable=True, comment='Адрес производителя')
    contact_person: Mapped[str] = mapped_column(String(200), nullable=True,
                                                comment='Контактное лицо. Можно указать несколько')
    contact_phone: Mapped[str] = mapped_column(String(20),  nullable=True, comment='Контактный телефон')
    is_active: Mapped[bool] = mapped_column(default=True, comment='Для мягкого удаления записей')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(), nullable=True,
                                                 comment='дата и время добавления записи')

    # relationships
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="manufacturer")
    city: Mapped["Cities"] = relationship(back_populates="manufacturer")

    def __repr__(self):
        return f'<Manufacturer(id={self.id!r}, name={self.name!r})>'


class Position(Base):
    __tablename__ = 'position'
    __table_args__ = {'comment': 'Должности сотрудников'}

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment='Название должности')
    type: Mapped[str] = mapped_column(String(10), nullable=False,
                                      comment='company - должность для сотрудников компании, '
                                              'client - должность для клиентов')

    # relationships
    employee: Mapped["Employee"] = relationship(back_populates="position")
    dept_contact_pers: Mapped["DeptContactPers"] = relationship(back_populates="position")

    def __repr__(self):
        return f'<Position(id={self.id!r}, name={self.name!r})>'


class Service(Base):
    __tablename__ = 'service'
    __table_args__ = {'comment': 'Данные по ремонту оборудования'}

    service_type_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('service_type.id', ondelete='CASCADE'),
                                                       nullable=False, comment='ID типа ремонта/вида работы')
    equipment_accounting_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment_accounting.id',
                                                                                ondelete='CASCADE'),
                                                               nullable=False, comment='ID учётного оборудования')
    description: Mapped[str] = mapped_column(String(300), nullable=True, comment='Описание ремонта, неисправности')
    reason: Mapped[str] = mapped_column(String(100), nullable=True, comment='На основании чего делается ремонт')
    job_content: Mapped[str] = mapped_column(String(300), nullable=True, comment='Содержание работ')
    beg_dt: Mapped[date] = mapped_column(Date, default=date.today(), nullable=True, comment='Дата начала ремонта')
    end_dt: Mapped[date] = mapped_column(Date, default=None, nullable=True, comment='Дата окончания ремонта')
    comment: Mapped[str] = mapped_column(String(600), nullable=True, comment='Примечание, комментарий по ремонту')
    emp_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('employee.id', ondelete='CASCADE'),
                                              comment='ID сотрудника, который добавил запись о ремонте',
                                              nullable=False)

    # relationships
    service_type: Mapped["ServiceType"] = relationship(back_populates="service")
    service_spare_part: Mapped[list["ServiceSparePart"]] = \
        relationship(back_populates="service",
                     primaryjoin='Service.id == ServiceSparePart.service_id')
    employee: Mapped["Employee"] = relationship(back_populates="service")
    equipment_accounting: Mapped["EquipmentAccounting"] = \
        relationship(back_populates="service",
                     primaryjoin='Service.equipment_accounting_id == EquipmentAccounting.id')

    def __repr__(self):
        return (f'<Service(id={self.id!r}, service_type_id={self.service_type_id!r}, '
                f'equipment_accounting_id={self.equipment_accounting_id!r})>')


class ServiceSparePart(Base):
    __tablename__ = 'service_spare_part'
    __table_args__ = {'comment': 'Таблица используется для связи между ремонтом и запчастями для анализаторов'}

    spare_part_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part.id', ondelete='CASCADE'),
                                                      nullable=False, comment='ID запчасти')
    service_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('service.id', ondelete='CASCADE'),
                                                  nullable=False, comment='ID ремонта')

    # relationships
    spare_part: Mapped["SparePart"] = relationship(back_populates="service_spare_part")
    service: Mapped["Service"] = relationship(back_populates="service_spare_part")

    def __repr__(self):
        return f'<ServiceSparePart(id={self.id!r}, service_id={self.service_id!r})>'


class ServiceType(Base):
    __tablename__ = 'service_type'
    __table_args__ = {'comment': 'Тип ремонта/вида работы'}

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True, comment='ID типа ремонта')
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='Название типа ремонта')

    # relationships
    service: Mapped[list["Service"]] = relationship(back_populates="service_type")

    def __repr__(self):
        return f'<ServiceType(id={self.id!r}, name={self.name!r})>'


class SparePart(Base):
    __tablename__ = "spare_part"
    __table_args__ = {'comment': 'Запчасти для анализаторов'}

    article: Mapped[str] = mapped_column(String(50), nullable=True, comment='Артикул запчасти')
    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название запчасти')
    unit: Mapped[str] = mapped_column(String(10), nullable=True, comment='Единица измерения')
    spare_part_count_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part_count.id',
                                                                            ondelete='CASCADE'),
                                                           nullable=False)
    comment: Mapped[str] = mapped_column(String(300), nullable=True, comment='Комментарий / Примечание')
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
                                             comment='Отмечается когда запчасть просрочилась')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')

    # relationships
    equipment_spare_part: Mapped[list["EquipmentSparePart"]] = \
        relationship(back_populates='spare_part',
                     primaryjoin='SparePart.id == EquipmentSparePart.spare_part_id')
    spare_part_count: Mapped[list["SparePartCount"]] = \
        relationship(back_populates='spare_part',
                     primaryjoin='SparePart.id == SparePartCount.spare_part_id')
    service_spare_part: Mapped[list["ServiceSparePart"]] = \
        relationship(back_populates="spare_part",
                     primaryjoin='SparePart.id == ServiceSparePart.spare_part_id')

    def __repr__(self):
        return f'<SparePart(id={self.id!r}, article={self.article!r}, name={self.name!r})>'


class SparePartCount(Base):
    __tablename__ = "spare_part_count"
    __table_args__ = {'comment': 'Количество запчастей в офисе'}

    spare_part_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part.id', ondelete='CASCADE'),
                                                     nullable=False)
    count: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment='Количество запчастей')
    row_add_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='когда была добавлена запись')
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False,
                                             comment='Флаг указывающий, что это текущее кол-во запчастей на данные момент')

    # relationships
    spare_part: Mapped["SparePart"] = \
        relationship(back_populates='spare_part_count',
                     primaryjoin='SparePartCount.spare_part_id == SparePart.id')

    def __repr__(self):
        return f'<SparePartCount(id={self.id!r}, count={self.count!r}, is_current={self.is_current!r})>'

class Supplier(Base):
    __tablename__ = "supplier"
    __table_args__ = {'comment': 'Таблица с информацией о поставщиках'}

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название поставщика')  # обязательное поле)
    inn: Mapped[str] = mapped_column(String(12), nullable=True, comment='ИНН поставщика')
    country: Mapped[str] = mapped_column(String(20), nullable=True, comment='Страна поставщика')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               nullable=True, comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), nullable=True, comment='Адрес поставщика')
    contact_person: Mapped[str] = mapped_column(String(200),
                                                nullable=True, comment='Контактное лицо. Можно указать несколько')
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=True, comment='Контактный телефон')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='дата и время добавления записи')
    is_active: Mapped[bool] = mapped_column(default=True, nullable=True, comment='Для мягкого удаления записей')

    # relationships
    equipment: Mapped[list[Equipment]] = relationship(back_populates="supplier")
    city: Mapped["Cities"] = relationship(back_populates="supplier")

    def __repr__(self):
        return f'<Supplier(id={self.id!r}, name={self.name!r})>'


class User(Base):
    __tablename__ = "user"
    __table_args__ = {'comment': 'Таблица зарегистрированных пользователей'}

    surname: Mapped[str] = mapped_column(String(50), nullable=True, comment='Фамилия пользователя')
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='Имя пользователя')
    patron: Mapped[str] = mapped_column(String(50), nullable=True, comment='Отчество пользователя')
    sex: Mapped[int] = mapped_column(SmallInteger,  nullable=False, comment='Пол. 1 - мужчина, 2 - женщина')
    birth: Mapped[date] = mapped_column(Date, nullable=True, comment='Дата рождения')
    email: Mapped[str] = mapped_column(String(100), nullable=True, comment='Электронная почта')
    phone: Mapped[str] = mapped_column(String(50), nullable=True, comment='Телефон')
    is_del: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True, comment='Признак удаления пользователя')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=func.now(),
                                                 nullable=True, comment='Дата создания записи')

    # relationships
    login_pass: Mapped["LoginPass"] = relationship(back_populates="user")
    employee: Mapped[list["Employee"]] = relationship(back_populates="user")
    equipment_accounting: Mapped[list["EquipmentAccounting"]] = relationship(back_populates="user")

    def __repr__(self):
        return f'<User(id={self.id!r}, name={self.name!r}, create_dt={self.create_dt!r})>'


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def add_manufacturer():
    async with async_session() as session:
        async with session.begin():
            new_man = Manufacturer(
                name='Рога и Корпус',
                inn='123 456   789 0 12 ',
                country=None,
                city_id=None,
            )
            session.add(new_man)
            await session.commit()


if __name__ == '__main__':
    asyncio.run(main())
    asyncio.run(add_manufacturer())
    # Equipment().test()
