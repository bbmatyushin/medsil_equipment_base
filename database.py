from dotenv import dotenv_values

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


env = dotenv_values('.env')

async_engine = create_async_engine(env['DB_URL_ASYNC'], echo=True)
async_session = async_sessionmaker(async_engine, expire_on_commit=True)
