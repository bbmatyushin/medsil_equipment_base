import uuid
import asyncio
import re
from datetime import datetime

from sqlalchemy import UUID, Integer, String, TIMESTAMP, ForeignKey, Boolean, SmallInteger
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
    region: Mapped[str] = mapped_column(String(100), comment='Область / Регион')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

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

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название клиента')
    inn: Mapped[str] = mapped_column(String(12), comment='ИНН клиента')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), comment='Адрес клиента')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

    # relationships
    department: Mapped[list["Department"]] = relationship(back_populates="client")
    city: Mapped["Cities"] = relationship(back_populates="client")

    def __repr__(self):
        return f'<Client(id={self.id!r}, name={self.name!r})>'


class Department(Base):
    __tablename__ = "department"
    __table_args__ = {'comment': 'Информациея о подразделениях/филиалах'}

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название подразделения')
    client_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('client.id', ondelete='CASCADE'),
                                                 nullable=False,
                                                 comment='Значение из таблицы client.id')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               nullable=False,
                                               comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), comment='Адрес подразделения')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

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
    surname: Mapped[str] = mapped_column(String(50), comment='Фамилия контактного лица')
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment='Имя контактного лица')
    patron: Mapped[str] = mapped_column(String(50), comment='Отчество контактного лица')
    position: Mapped[str] = mapped_column(String(50),comment='Занимаемая должность')
    mob_phone: Mapped[str] = mapped_column(String(60), comment='Контактный (мобильный) телефон')
    work_phone: Mapped[str] = mapped_column(String(60), comment='Рабочий телефон')
    email: Mapped[str] = mapped_column(String(50), comment='Электронная почта')
    comment: Mapped[str] = mapped_column(String(300), comment='Комментарий')
    is_active: Mapped[bool] = mapped_column(default=True, comment='Для мягкого удаления записи')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='Дата и время добавления записи')

    # relationships
    department: Mapped["Department"] = relationship(back_populates="dept_contact_pers")

    def __repr__(self):
        return f'<DeptContactPers(id={self.id!r}, name={self.name!r}, department_id={self.department_id!r})>'


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = {'comment': 'Таблица с информацией об оборудование'}

    fullname: Mapped[str] = mapped_column(String(50), nullable=False,
                                          comment='Полное название оборудования')
    shortname: Mapped[str] = mapped_column(String(20))
    med_directory: Mapped[str] = mapped_column(String(20),
                                               comment='Вид направления: Гематология, Биохимия и т.д.')
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(UUID,
                                                       ForeignKey('manufacturer.id',
                                                                  ondelete='CASCADE'),
                                                       nullable=False,
                                                       comment='id производителя')
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('supplier.id',
                                                                    ondelete='CASCADE'),
                                                   comment='id поставщика (обязательное поле)')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

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
    dept_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('department.id', ondelete='CASCADE'),
                                                nullable=False, comment='id подразделения')
    serial_num: Mapped[str] = mapped_column(String(50), nullable=False, comment='Серийный номер оборудования')
    service_status_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('service_status.id', ondelete='CASCADE'),
                                                          nullable=False, comment='id статуса обслуживания')
    is_service: Mapped[bool] = mapped_column(Boolean, default=False, comment='True если прибор был обслужан МЕДСИЛ')
    is_our_supply: Mapped[bool] = mapped_column(Boolean, default=False, comment='True если прибор был поставлен МЕДСИЛ')
    usr_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('user.id', ondelete='CASCADE'),
                                               nullable=False, comment='id пользователя, добавившего запись')
    emp_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('employee.id', ondelete='CASCADE'),
                                              comment='id сотрудника, который запускал прибор')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

    # relationships
    equipment: Mapped["Equipment"] = relationship(back_populates="equipment_accounting")
    department: Mapped[list["EquipmentAccDepartment"]] = \
        relationship(back_populates="equipment_accounting")
    user: Mapped["User"] = relationship(back_populates="equipment_accounting")
    employee: Mapped["Employee"] = relationship(back_populates="equipment_accounting")
    service_status: Mapped["ServiceStatus"] = relationship(back_populates="equipment_accounting")
    equipment_acc_department: Mapped[list["EquipmentAccDepartment"]] = \
        relationship(back_populates="equipment_accounting")

    def __repr__(self):
        return f'EquipmentAccounting(id={self.id!r}, equipment_id={self.equipment_id!r}, ' \
               f'dept_id={self.dept_id!r}, serial_num={self.serial_num!r}, is_service={self.is_service!r}, ' \


class EquipmentAccDepartment(Base):
    __tablename__ = "equipment_acc_department"
    __table_args__ = {"comment": "Связь таблиц equipment_accounting и department"}

    equipment_accounting_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment_accounting.id',
                                                                                ondelete='CASCADE'),
                                                               nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('department.id', ondelete='CASCADE'),
                                                     nullable=False)

    # relationship
    equipment_accounting: Mapped[list["EquipmentAccounting"]] = \
        relationship(back_populates='equipment_acc_department')
    department: Mapped[list["Department"]] = relationship(back_populates='equipment_acc_department')

    def __repr__(self):
        return f"EquipmentAccDepartment(id={self.id!r})"


class EquipmentSparePart(Base):
    __tablename__ = "equipment_spare_part"
    __table_args__ = {"comment": "Связь таблиц equipment и spare_part"}

    equipment_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('equipment.id', ondelete='CASCADE'),
                                                    nullable=False)
    spare_part_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part.id', ondelete='CASCADE'),
                                                     nullable=False)

    # relationship
    equipment: Mapped[list["Equipment"]] = relationship(back_populates='equipment_spare_part')
    spare_part: Mapped[list["SparePart"]] = relationship(back_populates='equipment_spare_part')

    def __repr__(self):
        return f"EquipmentSparePart(id={self.id!r})"


class Manufacturer(Base):
    __tablename__ = "manufacturer"
    __table_args__ = {'comment': 'Таблица с информацией о производителях'}

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название производителя')  # обязательное поле)
    inn: Mapped[str] = mapped_column(String(12), comment='ИНН производителя')
    country: Mapped[str] = mapped_column(String(20), comment='Страна производителя')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), comment='Адрес производителя')
    contact_person: Mapped[str] = mapped_column(String(200),
                                                comment='Контактное лицо. Можно указать несколько')
    contact_phone: Mapped[str] = mapped_column(String(20), comment='Контактный телефон')
    is_active: Mapped[bool] = mapped_column(default=True, comment='Для мягкого удаления записей')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

    # relationships
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="manufacturer")
    city: Mapped["Cities"] = relationship(back_populates="manufacturer")

    def __repr__(self):
        return f'<Manufacturer(id={self.id!r}, name={self.name!r})>'


class SparePart(Base):
    __tablename__ = "spare_part"
    __table_args__ = {'comment': 'Запчасти для анализаторов'}

    article: Mapped[str] = mapped_column(String(50), comment='Артикул запчасти')
    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название запчасти')
    unit: Mapped[str] = mapped_column(String(10), comment='Единица измерения')
    spare_part_count_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part_count.id',
                                                                            ondelete='CASCADE'),
                                                           nullable=False)
    comment: Mapped[str] = mapped_column(String(300), comment='Комментарий / Примечание')
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False,
                                             comment='Отмечается когда запчасть просрочилась')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')

    # relationships
    equipment_spare_part: Mapped[list["EquipmentSparePart"]] = relationship(back_populates='spare_part')
    spare_part_count: Mapped[list["SparePartCount"]] = relationship(back_populates='spare_part')

    def __repr__(self):
        return f'<SparePart(id={self.id!r}, article={self.article!r}, name={self.name!r})>'


class SparePartCount(Base):
    __tablename__ = "spare_part_count"
    __table_args__ = {'comment': 'Количество запчастей в офисе'}

    spare_part_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('spare_part.id', ondelete='CASCADE'),
                                                      nullable=False)
    count: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment='Количество запчастей')
    row_add_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='когда была добавлена запись')
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False,
                                             comment='Флаг указывающий, что это текущее кол-во запчастей на данные момент')

    # relationships
    spare_part: Mapped["SparePart"] = relationship(back_populates='spare_part_count')

    def __repr__(self):
        return f'<SparePartCount(id={self.id!r}, count={self.count!r}, is_current={self.is_current!r})>'

class Supplier(Base):
    __tablename__ = "supplier"
    __table_args__ = {'comment': 'Таблица с информацией о поставщиках'}

    name: Mapped[str] = mapped_column(String(150), nullable=False, comment='Название поставщика')  # обязательное поле)
    inn: Mapped[str] = mapped_column(String(12), comment='ИНН поставщика')
    country: Mapped[str] = mapped_column(String(20), comment='Страна поставщика')
    city_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey('cities.id', ondelete='CASCADE'),
                                               comment='Значение из таблицы cities.id')
    address: Mapped[str] = mapped_column(String(200), comment='Адрес поставщика')
    contact_person: Mapped[str] = mapped_column(String(200),
                                                comment='Контактное лицо. Можно указать несколько')
    contact_phone: Mapped[str] = mapped_column(String(20), comment='Контактный телефон')
    create_dt: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, default=datetime.now(),
                                                 comment='дата и время добавления записи')
    is_active: Mapped[bool] = mapped_column(default=True, comment='Для мягкого удаления записей')

    # relationships
    equipment: Mapped[list[Equipment]] = relationship(back_populates="supplier")
    city: Mapped["Cities"] = relationship(back_populates="supplier")

    def __repr__(self):
        return f'<Supplier(id={self.id!r}, name={self.name!r})>'


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
            )
            session.add(new_man)
            await session.commit()


if __name__ == '__main__':
    asyncio.run(main())
    asyncio.run(add_manufacturer())
    # Equipment().test()
