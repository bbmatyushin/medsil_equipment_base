"""empty message

Revision ID: 83dceaf8c4d2
Revises: 
Create Date: 2024-06-15 15:20:47.655099

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "83dceaf8c4d2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "cities",
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
            comment="Название города",
        ),
        sa.Column(
            "region",
            sa.String(length=100),
            nullable=True,
            comment="Область / Регион",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "region", name="uq_cities_name_region"),
        comment="Таблица с информацией о городах",
    )
    op.create_table(
        "equipment_accounting",
        sa.Column(
            "equipment_id",
            sa.UUID(),
            nullable=False,
            comment="id оборудования",
        ),
        sa.Column(
            "serial_num",
            sa.String(length=50),
            nullable=False,
            comment="Серийный номер оборудования",
        ),
        sa.Column(
            "equipment_status_id",
            sa.UUID(),
            nullable=False,
            comment="id статуса обслуживания",
        ),
        sa.Column(
            "service_id",
            sa.UUID(),
            nullable=True,
            comment="id ремонта. Заполняется если оборудование было сдано в ремонте",
        ),
        sa.Column(
            "is_service",
            sa.Boolean(),
            nullable=True,
            comment="True если прибор был обслужан МЕДСИЛ",
        ),
        sa.Column(
            "is_our_supply",
            sa.Boolean(),
            nullable=True,
            comment="True если прибор был поставлен МЕДСИЛ",
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="id пользователя, добавившего запись",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["equipment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["equipment_status_id"],
            ["equipment_status.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"], ["service.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Учёт оборудования. Основная таблица",
    )
    op.create_table(
        "equipment_status",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="ID статуса",
        ),
        sa.Column(
            "name",
            sa.String(length=50),
            nullable=False,
            comment="Название статуса",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="фиксированный набор статусов для оборудования",
    )
    op.create_table(
        "med_directory",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="ID направления",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Название направления",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="Направление, область применения для оборудования (Гематология, Биохимия и т.п.)",
    )
    op.create_table(
        "position",
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Название должности",
        ),
        sa.Column(
            "type",
            sa.String(length=10),
            nullable=False,
            comment="company - должность для сотрудников компании, client - должность для клиентов",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        comment="Должности сотрудников",
    )
    op.create_table(
        "service",
        sa.Column(
            "service_type_id",
            sa.UUID(),
            nullable=False,
            comment="ID типа ремонта/вида работы",
        ),
        sa.Column(
            "equipment_accounting_id",
            sa.UUID(),
            nullable=False,
            comment="ID учётного оборудования",
        ),
        sa.Column(
            "description",
            sa.String(length=300),
            nullable=True,
            comment="Описание ремонта, неисправности",
        ),
        sa.Column(
            "reason",
            sa.String(length=100),
            nullable=True,
            comment="На основании чего делается ремонт",
        ),
        sa.Column(
            "job_content",
            sa.String(length=300),
            nullable=True,
            comment="Содержание работ",
        ),
        sa.Column(
            "beg_dt", sa.Date(), nullable=True, comment="Дата начала ремонта"
        ),
        sa.Column(
            "end_dt",
            sa.Date(),
            nullable=True,
            comment="Дата окончания ремонта",
        ),
        sa.Column(
            "comment",
            sa.String(length=600),
            nullable=True,
            comment="Примечание, комментарий по ремонту",
        ),
        sa.Column(
            "emp_id",
            sa.UUID(),
            nullable=False,
            comment="ID сотрудника, который добавил запись о ремонте",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["emp_id"], ["employee.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["equipment_accounting_id"],
            ["equipment_accounting.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_type_id"], ["service_type.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Данные по ремонту оборудования",
    )
    op.create_table(
        "service_type",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="ID типа ремонта",
        ),
        sa.Column(
            "name",
            sa.String(length=50),
            nullable=False,
            comment="Название типа ремонта",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Тип ремонта/вида работы",
    )
    op.create_table(
        "spare_part",
        sa.Column(
            "article",
            sa.String(length=50),
            nullable=False,
            comment="Артикул запчасти",
        ),
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
            comment="Название запчасти",
        ),
        sa.Column(
            "unit",
            sa.String(length=10),
            nullable=True,
            comment="Единица измерения",
        ),
        sa.Column("spare_part_count_id", sa.UUID(), nullable=False),
        sa.Column(
            "comment",
            sa.String(length=300),
            nullable=True,
            comment="Комментарий / Примечание",
        ),
        sa.Column(
            "is_expiration",
            sa.Boolean(),
            nullable=True,
            comment="Флаг указывающий, что у запчасти должен быть срок годности",
        ),
        sa.Column(
            "is_overdue",
            sa.Boolean(),
            nullable=False,
            comment="Отмечается когда запчасть просрочилась",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["spare_part_count_id"],
            ["spare_part_count.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name", "article", name="unq_spare_part_name_article"
        ),
        comment="Запчасти для анализаторов",
    )
    op.create_table(
        "spare_part_count",
        sa.Column("spare_part_id", sa.UUID(), nullable=False),
        sa.Column(
            "count",
            sa.Integer(),
            nullable=False,
            comment="Количество запчастей",
        ),
        sa.Column(
            "row_add_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="когда была добавлена запись",
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            comment="Флаг указывающий, что это текущее кол-во запчастей на данные момент",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["spare_part_id"], ["spare_part.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Количество запчастей в офисе",
    )
    op.create_table(
        "user",
        sa.Column(
            "surname",
            sa.String(length=50),
            nullable=True,
            comment="Фамилия пользователя",
        ),
        sa.Column(
            "name",
            sa.String(length=50),
            nullable=False,
            comment="Имя пользователя",
        ),
        sa.Column(
            "patron",
            sa.String(length=50),
            nullable=True,
            comment="Отчество пользователя",
        ),
        sa.Column(
            "sex",
            sa.Integer(),
            nullable=False,
            comment="Пол. 1 - мужчина, 2 - женщина",
        ),
        sa.Column("birth", sa.Date(), nullable=True, comment="Дата рождения"),
        sa.Column(
            "email",
            sa.String(length=100),
            nullable=True,
            comment="Электронная почта",
        ),
        sa.Column(
            "phone", sa.String(length=50), nullable=True, comment="Телефон"
        ),
        sa.Column(
            "is_del",
            sa.Boolean(),
            nullable=True,
            comment="Признак удаления пользователя",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="Дата создания записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "surname", "name", "patron", name="unq_user_surname_name_patron"
        ),
        comment="Таблица зарегистрированных пользователей",
    )
    op.create_table(
        "client",
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
            comment="Название клиента",
        ),
        sa.Column(
            "inn", sa.String(length=12), nullable=True, comment="ИНН клиента"
        ),
        sa.Column(
            "city_id",
            sa.UUID(),
            nullable=True,
            comment="Значение из таблицы cities.id",
        ),
        sa.Column(
            "address",
            sa.String(length=200),
            nullable=True,
            comment="Адрес клиента",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"], ["cities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "inn", name="unq_client_name_inn"),
        comment="Таблица с информацией о клиентах (ЛПУ)",
    )
    op.create_table(
        "employee",
        sa.Column(
            "user_id", sa.UUID(), nullable=False, comment="ID пользователя"
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="True - сотрудник работает, False - сотрудник не работает",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="Дата создания записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="Сотрудники",
    )
    op.create_table(
        "login_pass",
        sa.Column(
            "user_id", sa.UUID(), nullable=False, comment="ID пользователя"
        ),
        sa.Column(
            "login",
            sa.String(length=20),
            nullable=False,
            comment="Логин пользователя",
        ),
        sa.Column(
            "password",
            sa.String(length=32),
            nullable=False,
            comment="Пароль пользователя в шифрованном виде MD5",
        ),
        sa.Column(
            "create_dt",
            sa.Date(),
            nullable=True,
            comment="Дата создания записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("login"),
        sa.UniqueConstraint("user_id"),
        comment="Таблица с логинами и паролями",
    )
    op.create_table(
        "manufacturer",
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
            comment="Название производителя",
        ),
        sa.Column(
            "inn",
            sa.String(length=12),
            nullable=True,
            comment="ИНН производителя",
        ),
        sa.Column(
            "country",
            sa.String(length=20),
            nullable=True,
            comment="Страна производителя",
        ),
        sa.Column(
            "city_id",
            sa.UUID(),
            nullable=True,
            comment="Значение из таблицы cities.id",
        ),
        sa.Column(
            "address",
            sa.String(length=200),
            nullable=True,
            comment="Адрес производителя",
        ),
        sa.Column(
            "contact_person",
            sa.String(length=200),
            nullable=True,
            comment="Контактное лицо. Можно указать несколько",
        ),
        sa.Column(
            "contact_phone",
            sa.String(length=20),
            nullable=True,
            comment="Контактный телефон",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Для мягкого удаления записей",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"], ["cities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inn"),
        sa.UniqueConstraint("name"),
        comment="Таблица с информацией о производителях",
    )
    op.create_table(
        "service_spare_part",
        sa.Column(
            "spare_part_id", sa.UUID(), nullable=False, comment="ID запчасти"
        ),
        sa.Column(
            "service_id", sa.UUID(), nullable=False, comment="ID ремонта"
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"], ["service.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["spare_part_id"], ["spare_part.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("spare_part_id", "service_id", "id"),
        comment="Таблица используется для связи между ремонтом и запчастями для анализаторов",
    )
    op.create_table(
        "supplier",
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
            comment="Название поставщика",
        ),
        sa.Column(
            "inn",
            sa.String(length=12),
            nullable=True,
            comment="ИНН поставщика",
        ),
        sa.Column(
            "country",
            sa.String(length=20),
            nullable=True,
            comment="Страна поставщика",
        ),
        sa.Column(
            "city_id",
            sa.UUID(),
            nullable=True,
            comment="Значение из таблицы cities.id",
        ),
        sa.Column(
            "address",
            sa.String(length=200),
            nullable=True,
            comment="Адрес поставщика",
        ),
        sa.Column(
            "contact_person",
            sa.String(length=200),
            nullable=True,
            comment="Контактное лицо. Можно указать несколько",
        ),
        sa.Column(
            "contact_phone",
            sa.String(length=20),
            nullable=True,
            comment="Контактный телефон",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=True,
            comment="Для мягкого удаления записей",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"], ["cities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inn"),
        sa.UniqueConstraint("name"),
        comment="Таблица с информацией о поставщиках",
    )
    op.create_table(
        "supply_spare_part",
        sa.Column(
            "spare_part_id", sa.UUID(), nullable=False, comment="ID запчасти"
        ),
        sa.Column(
            "count_supply",
            sa.Integer(),
            nullable=False,
            comment="Количество поступивших запчастей",
        ),
        sa.Column(
            "expiration_dt",
            sa.Date(),
            nullable=True,
            comment="Срок годности для некоторых запчастей",
        ),
        sa.Column(
            "supply_dt",
            sa.Date(),
            nullable=True,
            comment="Дата внесения записи о поступлении запчастей",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["spare_part_id"], ["spare_part.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Для фиксации поступления запчастей в офиса.",
    )
    op.create_table(
        "department",
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
            comment="Название подразделения",
        ),
        sa.Column(
            "client_id",
            sa.UUID(),
            nullable=False,
            comment="Значение из таблицы client.id",
        ),
        sa.Column(
            "city_id",
            sa.UUID(),
            nullable=False,
            comment="Значение из таблицы cities.id",
        ),
        sa.Column(
            "address",
            sa.String(length=200),
            nullable=True,
            comment="Адрес подразделения",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"], ["cities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Информациея о подразделениях/филиалах",
    )
    op.create_table(
        "equipment",
        sa.Column(
            "fullname",
            sa.String(length=50),
            nullable=False,
            comment="Полное название оборудования",
        ),
        sa.Column("shortname", sa.String(length=20), nullable=False),
        sa.Column(
            "med_directory_id",
            sa.Integer(),
            nullable=True,
            comment="ID направления",
        ),
        sa.Column(
            "manufacturer_id",
            sa.UUID(),
            nullable=False,
            comment="id производителя",
        ),
        sa.Column(
            "supplier_id",
            sa.UUID(),
            nullable=True,
            comment="id поставщика (обязательное поле)",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["manufacturer_id"], ["manufacturer.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["med_directory_id"], ["med_directory.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["supplier.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Таблица с информацией об оборудование",
    )
    op.create_table(
        "shipment_spare_part",
        sa.Column(
            "spare_part_id", sa.UUID(), nullable=False, comment="ID запчасти"
        ),
        sa.Column(
            "count_shipment",
            sa.Integer(),
            nullable=False,
            comment="Количество отгружаемых запчастей",
        ),
        sa.Column(
            "expiration_dt",
            sa.Date(),
            nullable=True,
            comment="Срок годности для некоторых запчастей",
        ),
        sa.Column(
            "shipment_dt",
            sa.Date(),
            nullable=True,
            comment="Дата внесения записи об отгрузки запчастей",
        ),
        sa.Column(
            "emp_id",
            sa.UUID(),
            nullable=True,
            comment="ID сотрудника, который отгрузил запчасть (передал ее клиенту)",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["emp_id"], ["employee.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["spare_part_id"], ["spare_part.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Для фиксации отгрузки запчастей из офиса. Учитывается только количество запчастей, без указания для какого клиента.",
    )
    op.create_table(
        "user_position",
        sa.Column(
            "emp_id", sa.UUID(), nullable=False, comment="ID сотрудника"
        ),
        sa.Column(
            "position_id", sa.UUID(), nullable=False, comment="ID должности"
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["emp_id"], ["employee.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"], ["position.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("emp_id", "position_id", "id"),
        comment="Должности сотрудников",
    )
    op.create_table(
        "dept_contact_pers",
        sa.Column(
            "department_id",
            sa.UUID(),
            nullable=False,
            comment="Значение из таблицы department.id",
        ),
        sa.Column(
            "surname",
            sa.String(length=50),
            nullable=True,
            comment="Фамилия контактного лица",
        ),
        sa.Column(
            "name",
            sa.String(length=50),
            nullable=False,
            comment="Имя контактного лица",
        ),
        sa.Column(
            "patron",
            sa.String(length=50),
            nullable=True,
            comment="Отчество контактного лица",
        ),
        sa.Column(
            "position_id",
            sa.UUID(),
            nullable=True,
            comment="Значение из таблицы position.id",
        ),
        sa.Column(
            "mob_phone",
            sa.String(length=60),
            nullable=True,
            comment="Контактный (мобильный) телефон",
        ),
        sa.Column(
            "work_phone",
            sa.String(length=60),
            nullable=True,
            comment="Рабочий телефон",
        ),
        sa.Column(
            "email",
            sa.String(length=50),
            nullable=True,
            comment="Электронная почта",
        ),
        sa.Column(
            "comment",
            sa.String(length=300),
            nullable=True,
            comment="Комментарий",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=True,
            comment="Для мягкого удаления записи",
        ),
        sa.Column(
            "create_dt",
            sa.TIMESTAMP(),
            nullable=True,
            comment="Дата и время добавления записи",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"], ["department.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"], ["position.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Контактные лицах для подразделений / филиалов",
    )
    op.create_table(
        "equipment_acc_department",
        sa.Column("equipment_accounting_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Флаг, указывающий на то, что прибор установлен в подразделении клиента",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"], ["department.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["equipment_accounting_id"],
            ["equipment_accounting.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Подразделения в котором установлены приборы, с указанием id сотрудника, который запускал данное оборудование.",
    )
    op.create_table(
        "equipment_spare_part",
        sa.Column(
            "equipment_id",
            sa.UUID(),
            nullable=False,
            comment="id оборудования",
        ),
        sa.Column(
            "spare_part_id", sa.UUID(), nullable=False, comment="id запчасти"
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["equipment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["spare_part_id"], ["spare_part.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("equipment_id", "spare_part_id", "id"),
        comment="Связь между оборудование и запчастями. Связывает таблицы equipment и spare_part",
    )
    op.create_table(
        "equipment_acc_department_emp",
        sa.Column(
            "employee_id", sa.UUID(), nullable=False, comment="id сотрудника"
        ),
        sa.Column(
            "equipment_acc_department_id",
            sa.UUID(),
            nullable=False,
            comment="id записи в таблице equipment_acc_department",
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employee.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["equipment_acc_department_id"],
            ["equipment_acc_department.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "employee_id", "equipment_acc_department_id", "id"
        ),
        comment="Связь между сотрудником(-ми), которые установили оборудование в подразделении",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("equipment_acc_department_emp")
    op.drop_table("equipment_spare_part")
    op.drop_table("equipment_acc_department")
    op.drop_table("dept_contact_pers")
    op.drop_table("user_position")
    op.drop_table("shipment_spare_part")
    op.drop_table("equipment")
    op.drop_table("department")
    op.drop_table("supply_spare_part")
    op.drop_table("supplier")
    op.drop_table("service_spare_part")
    op.drop_table("manufacturer")
    op.drop_table("login_pass")
    op.drop_table("employee")
    op.drop_table("client")
    op.drop_table("user")
    op.drop_table("spare_part_count")
    op.drop_table("spare_part")
    op.drop_table("service_type")
    op.drop_table("service")
    op.drop_table("position")
    op.drop_table("med_directory")
    op.drop_table("equipment_status")
    op.drop_table("equipment_accounting")
    op.drop_table("cities")
    # ### end Alembic commands ###