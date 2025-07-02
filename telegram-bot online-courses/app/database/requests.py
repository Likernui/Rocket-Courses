from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.models import async_session, Category
from app.database.models import User, Course, Purchase
from sqlalchemy import select, update, delete, desc
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import os
import aiohttp
load_dotenv()


async def set_user(tg_id, username=None):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == tg_id))

        if not user:
            user = User(telegram_id=tg_id, username=username)
            session.add(user)
        elif username and user.username != username:
            user.username = username

        await session.commit()

async def get_course(title):
    async with async_session() as session:
        try:
            result = await session.execute(
                select(Course)
                .where(Course.title == title)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"DB error: {e}")
            return None

async def get_course_titles():
    async with async_session() as session:
        result = await session.scalars(select(Course.title))
        return result.all()

async def get_user_telegram_ids():
    """Получить все telegram_id пользователей"""
    async with async_session() as session:
        result = await session.scalars(select(User.telegram_id))
        return result.all()
    
async def get_user_profile(user_id: int, session: AsyncSession) -> dict:
    """Получаем профиль пользователя с учетом сессии"""
    result = await session.execute(
        select(User).where(User.telegram_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    
    return {
        'balance': user.balance,
        'registered_at': user.registered_at
        # Добавьте другие нужные поля
    }
    

async def get_user_courses(user_id: int, session: AsyncSession) -> list[str]:
    """Получаем курсы пользователя из поля purchased_courses"""
    try:
        result = await session.execute(
            select(User.purchased_courses)  # Используем правильное имя поля
            .where(User.telegram_id == user_id)
        )
        courses = result.scalar_one_or_none()
        return courses if courses is not None else []
    except Exception as e:
        print(f"Ошибка при получении курсов: {e}")
        return []
    
async def get_all_courses(session: AsyncSession) -> list[Course]:
    """Получить все курсы (с полной информацией)"""
    result = await session.execute(select(Course))
    return result.scalars().all()

async def delete_course(session: AsyncSession, course_id: int) -> bool:
    """Удалить курс по ID"""
    result = await session.execute(
        delete(Course)
        .where(Course.id == course_id)
    )
    await session.commit()
    return result.rowcount > 0

async def get_course_by_id(session: AsyncSession, course_id: int) -> Course | None:
    """Получить курс по ID"""
    result = await session.execute(
        select(Course)
        .where(Course.id == course_id)
    )
    return result.scalar_one_or_none()

async def get_all_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category))
    return result.scalars().all()

async def get_category_by_id(session: AsyncSession, category_id: int) -> Category | None:
    result = await session.execute(
        select(Category)
        .where(Category.id == category_id)
    )
    return result.scalar_one_or_none()

async def create_category(session: AsyncSession, name: str, description: str = None) -> Category:
    category = Category(name=name, description=description)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category

async def get_courses_by_category(session: AsyncSession, category_id: int) -> list[Course]:
    result = await session.execute(
        select(Course)
        .where(Course.category_id == category_id)
        .order_by(Course.title)
    )
    return result.scalars().all()

def get_admin_ids() -> list[int]:
    admin_ids = os.getenv('ADMIN_IDS', '')
    return [int(id.strip()) for id in admin_ids.split(',') if id.strip()]

async def check_course_ownership(session: AsyncSession, user_id: int, course_id: int) -> bool:

    result = await session.execute(
        select(User.purchased_courses)
        .where(User.telegram_id == user_id)
    )
    purchased_courses = result.scalar_one_or_none()
    return purchased_courses and course_id in purchased_courses

async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Получить пользователя по username"""
    result = await session.execute(
        select(User)
        .where(User.username == username)
    )
    return result.scalar_one_or_none()