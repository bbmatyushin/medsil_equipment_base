import async

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.future import select

# Асинхронный движок для подключения к базе данных
async_engine = create_async_engine('postgresql+asyncpg://user:password@localhost/dbname')

# Отражение базы данных
Base = automap_base()

# Подготовка классов отражения
async with async_engine.begin() as conn:
    Base.prepare(conn, reflect=True, schema="external")

# Получение класса автоматически сгенерированной модели
People = Base.classes.people

# Создание сессии
async_session = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Использование асинхронной сессии для выполнения запроса
async with async_session() as session:
    # Асинхронный запрос для получения всех записей из таблицы people
    result = await session.execute(select(People))
    people = result.scalars().all()

    # Вывод данных
    for person in people:
        print(person.name)  # Или любое другое поле из вашей таблицы