from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


engine = create_async_engine('sqlite+aiosqlite:///equipment.db', echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=True)
