from aiogram import Bot, Dispatcher
from os import getenv
from dotenv import load_dotenv
from loguru import logger
import asyncio
from app.user import user
from app.database.models import async_main
from app.admin import admin
from app.support import support_router
from app.middlewares import DbSessionMiddleware
import aiohttp

load_dotenv()

TG_TOKEN = getenv('TG_TOKEN')

dp = Dispatcher()
bot = Bot(token=TG_TOKEN)

async def on_startup():
    """Запуск фоновых задач"""
    logger.info("Бот запущен")

async def main():
    dp.update.middleware(DbSessionMiddleware())
    await async_main()
    dp.include_routers(user, admin, support_router)
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка бота")
    except Exception as e:
        logger.error(f"Ошибка: {e}")