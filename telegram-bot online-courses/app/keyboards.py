from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database.requests import get_course_titles, get_all_courses, get_all_categories
from app.database.models import async_session

menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='📚 Каталог курсов', callback_data='catalog')],
    [InlineKeyboardButton(text='👤 Профиль', callback_data='profile')],
    [InlineKeyboardButton(text='💬 Связь с поддержкой', callback_data='support')]
])


async def back_to_menu() -> InlineKeyboardMarkup:
    """Клавиатура для возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    return builder.as_markup()


async def courses_keyboard():
    titles = await get_course_titles()

    builder = InlineKeyboardBuilder()
    for title in titles:
        builder.button(
            text=title,
            callback_data=f"course_{title}"
        )

    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1, 1)
    return builder.as_markup()


async def profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Пополнить баланс", callback_data="deposit")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


async def back_to_catalog_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="catalog")
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    """Клавиатура отмены действия"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    return builder.as_markup()


async def admin_courses_kb() -> InlineKeyboardMarkup:
    """Клавиатура со списком курсов для админа"""
    async with async_session() as session:
        courses = await get_all_courses(session)
        builder = InlineKeyboardBuilder()

        for course in courses:
            builder.button(text=course.title, callback_data=f"admin_view_{course.id}")  # Используем ID

        builder.button(text="⬅️ Назад", callback_data="admin_panel")
        builder.adjust(1)
        return builder.as_markup()


def admin_course_actions_kb(course_id: int) -> InlineKeyboardMarkup:
    """Действия с конкретным курсом"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"admin_edit_{course_id}")
    builder.button(text="🗑 Удалить", callback_data=f"admin_delete_{course_id}")
    builder.button(text="⬅️ Назад", callback_data="list_courses")  # Возврат к списку
    builder.adjust(2)
    return builder.as_markup()


async def admin_categories_kb(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.button(
            text=f"{category.name} (ID: {category.id})",
            callback_data=f"view_category_{category.id}"
        )

    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="➕ Добавить категорию", callback_data="add_category"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")
    )
    return builder.as_markup()


def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📂 Управление категориями", callback_data="manage_categories")
    builder.button(text="🎁 Добавить курс пользователю", callback_data="add_course_to_user")
    builder.button(text="🔙 В меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


async def back_to_category_kb(category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в категорию", callback_data=f"cat_{category_id}_0")
    return builder.as_markup()


async def payment_options_kb(course_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с вариантами оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Оплатить через менеджера", callback_data=f"pay_manager_{course_id}")
    builder.button(text="💰 Оплатить CryptoCloud", callback_data=f"pay_cryptocloud_{course_id}")
    builder.button(text="⬅️ Назад", callback_data=f"back_to_course_{course_id}")
    builder.adjust(1)
    return builder.as_markup()


async def back_to_course_kb(course_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для возврата к курсу"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к курсу", callback_data=f"course_{course_id}")
    return builder.as_markup()