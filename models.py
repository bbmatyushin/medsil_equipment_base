import uuid
import asyncio
import re
from datetime import datetime

from sqlalchemy import UUID, Integer, String, TIMESTAMP, ForeignKey
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
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="equipment")
    supplier: Mapped["Supplier"] = relationship(back_populates="equipment")

    def my_test(self):
        print(self.__dict__)

    def __repr__(self):
        return f'Equipment(id={self.id!r}, fullname={self.fullname!r}, shortname={self.shortname!r}, ' \
               f'med_directory={self.med_directory!r}, manufacturer_id={self.manufacturer_id!r}, ' \
               f'supplier_id={self.supplier_id!r}, create_dt={self.create_dt!r})'


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
