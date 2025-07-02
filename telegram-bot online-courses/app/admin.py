from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton, InlineKeyboardMarkup
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.requests import get_all_courses, get_course_by_id, create_category, get_all_categories, get_category_by_id, get_courses_by_category
from app.database.models import Course, async_session
from app.keyboards import admin_main_kb, cancel_kb, admin_categories_kb
import os
import app.keyboards as kb
from sqlalchemy import select, update, delete, desc
from loguru import logger
from app.database.models import User
from sqlalchemy import func
from app.database.models import Category

admin = Router()

class EditCategoryStates(StatesGroup):
    NAME = State()
    DESCRIPTION = State()

# Улучшенный обработчик управления категориями
@admin.callback_query(F.data == "manage_categories")
async def manage_categories(callback: CallbackQuery, session: AsyncSession):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Доступ запрещен", show_alert=True)
    
    categories = await get_all_categories(session)
    await callback.message.edit_text(
        "📂 Управление категориями",
        reply_markup=await admin_categories_kb(categories)
    )

# Просмотр конкретной категории
@admin.callback_query(F.data.startswith("view_category_"))
async def view_category(callback: CallbackQuery, session: AsyncSession):
    category_id = int(callback.data.split("_")[-1])
    category = await get_category_by_id(session, category_id)

    if not category:
        return await callback.answer("Категория не найдена", show_alert=True)

    courses = await get_courses_by_category(session, category_id)
    courses_text = "\n".join(f"▪️ {course.title}" for course in courses) if courses else "Нет курсов"

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Редактировать", callback_data=f"edit_category_{category_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete_category_{category_id}")
    builder.button(text="➕ Добавить курс", callback_data=f"add_course_to_cat_{category.id}")
    builder.button(text="⬅️ Назад", callback_data="manage_categories")
    builder.adjust(1)

    await callback.message.edit_text(
        f"📂 <b>{category.name}</b>\n\n"
        f"📝 Описание: {category.description or 'Нет описания'}\n\n"
        f"📚 Курсы в категории:\n{courses_text}",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

# Удаление категории
@admin.callback_query(F.data.startswith("delete_category_"))
async def delete_category(callback: CallbackQuery, session: AsyncSession):
    category_id = int(callback.data.split("_")[-1])
    
    category = await get_category_by_id(session, category_id)
    if not category:
        return await callback.answer("Категория не найдена", show_alert=True)
    
    await session.delete(category)
    await session.commit()
    
    await callback.answer("Категория удалена!", show_alert=True)
    await manage_categories(callback, session)

# Редактирование категории
@admin.callback_query(F.data.startswith("edit_category_"))
async def edit_category_start(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=category_id)
    
    await callback.message.edit_text(
        "Введите новое название категории (или '-' чтобы оставить текущее):",
        reply_markup=cancel_kb()
    )
    await state.set_state(EditCategoryStates.NAME)

@admin.message(EditCategoryStates.NAME)
async def process_edit_category_name(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    category_id = data['category_id']
    
    if message.text != '-':
        if len(message.text) > 50:
            return await message.answer("Слишком длинное название! Макс. 50 символов")
        
        category = await get_category_by_id(session, category_id)
        category.name = message.text
        await session.commit()
    
    await message.answer(
        "Введите новое описание (или '-' чтобы оставить текущее):",
        reply_markup=cancel_kb()
    )
    await state.set_state(EditCategoryStates.DESCRIPTION)

@admin.message(EditCategoryStates.DESCRIPTION)
async def process_edit_category_desc(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    category_id = data['category_id']
    
    if message.text != '-':
        category = await get_category_by_id(session, category_id)
        category.description = message.text if message.text != '-' else None
        await session.commit()
    
    await message.answer(
        "✅ Категория обновлена!",
        reply_markup=admin_main_kb()
    )
    await state.clear()

class AddCategoryStates(StatesGroup):
    NAME = State()
    DESCRIPTION = State()

@admin.callback_query(F.data == "add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Доступ запрещен", show_alert=True)
    
    await callback.message.edit_text(
        "Введите название новой категории:",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddCategoryStates.NAME)
    await callback.answer()

@admin.message(AddCategoryStates.NAME)
async def process_category_name(message: Message, state: FSMContext):
    if len(message.text) > 50:
        return await message.answer("Слишком длинное название! Макс. 50 символов")
    
    await state.update_data(name=message.text)
    await message.answer(
        "Введите описание категории (или '-' чтобы пропустить):",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddCategoryStates.DESCRIPTION)

@admin.message(AddCategoryStates.DESCRIPTION)
async def process_category_description(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    description = message.text if message.text != '-' else None
    
    try:
        await create_category(session, data['name'], description)
        await message.answer(
            f"✅ Категория добавлена!\n\n"
            f"📂 {data['name']}\n"
            f"📝 {description or 'Нет описания'}",
            reply_markup=admin_main_kb()
        )
    except Exception as e:
        await message.answer(
            "❌ Ошибка при создании категории",
            reply_markup=admin_main_kb()
        )
        print(f"Error creating category: {e}")
    finally:
        await state.clear()

# Добавление курса с привязкой к категории
@admin.callback_query(F.data.startswith("add_course_to_cat_"))
async def add_course_to_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        # Правильно извлекаем category_id
        category_id = int(callback.data.split("_")[-1])
        category = await get_category_by_id(session, category_id)

        if not category:
            await callback.answer("Категория не найдена!", show_alert=True)
            return await manage_categories(callback, session)  # Возвращаемся к списку категорий

        await state.update_data(category_id=category_id)

        # Переходим к добавлению курса
        await callback.message.edit_text(
            "Введите название курса:",
            reply_markup=cancel_kb()
        )
        await state.set_state(CourseStates.TITLE)
        await callback.answer()

    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга callback_data: {e}")
        await callback.answer("Ошибка: неверный ID категории", show_alert=True)
        await manage_categories(callback, session)

# Состояния для добавления курса
class CourseStates(StatesGroup):
    TITLE = State()
    DESCRIPTION = State()
    PRICE = State()

ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Команда /admin - вход в админ-панель
@admin.message(Command("admin"))
async def admin_start(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("🚫 Доступ запрещен")
    
    await message.answer(
        "👨‍💻 Админ-панель управления",
        reply_markup=admin_main_kb()
    )


# Обработка названия
@admin.message(CourseStates.TITLE)
async def process_title(message: Message, state: FSMContext):
    if len(message.text) > 100:
        return await message.answer("Слишком длинное название! Макс. 100 символов")
    
    await state.update_data(title=message.text)
    await message.answer(
        "Введите описание курса:",
        reply_markup=cancel_kb()
    )
    await state.set_state(CourseStates.DESCRIPTION)

# Обработка описания
@admin.message(CourseStates.DESCRIPTION)
async def process_description(message: Message, state: FSMContext):
    if len(message.text) > 500:
        return await message.answer("Слишком длинное описание! Макс. 500 символов")
    
    await state.update_data(description=message.text)
    await message.answer(
        "Введите цену курса (только число):",
        reply_markup=cancel_kb()
    )
    await state.set_state(CourseStates.PRICE)

# Обработка цены
@admin.message(CourseStates.PRICE)
async def process_price(message: Message, state: FSMContext):
    try:
        price = Decimal(message.text.replace(',', '.'))
        if price <= 0:
            raise ValueError
        await state.update_data(price=float(price))
        
        data = await state.get_data()
        async with async_session() as session:
            course = Course(
                title=data['title'],
                description=data['description'],
                price=data['price'],
                category_id=data.get('category_id', 1)  # Добавляем category_id
            )
            session.add(course)
            await session.commit()
        
        await message.answer(
            f"✅ Курс добавлен!\n\n"
            f"📚 {data['title']}\n"
            f"💵 {data['price']}₽",
            reply_markup=admin_main_kb()
        )
        await state.clear()
    except:
        await message.answer("❌ Некорректная цена! Введите положительное число:")
# Отмена действий
@admin.callback_query(F.data == "admin_cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Действие отменено",
        reply_markup=admin_main_kb()
    )


@admin.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    """Возврат в главное меню админки"""
    await callback.message.edit_text(
        "👨‍💻 Админ-панель управления курсами",
        reply_markup=admin_main_kb()
    )

#Добавление курса пользователю с админки

class AddCourseToUserStates(StatesGroup):
    USERNAME = State()
    CATEGORY = State()
    COURSE = State()
    CONFIRM = State()

COURSES_PER_PAGE = 10  # Количество курсов на одной странице

# Обработчик начала процесса добавления курса пользователю
@admin.callback_query(F.data == "add_course_to_user")
async def start_add_course_to_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("🚫 Доступ запрещен", show_alert=True)

    await callback.message.edit_text(
        "Введите @username пользователя (без @):",
        reply_markup=cancel_kb()
    )
    await state.set_state(AddCourseToUserStates.USERNAME)
    await callback.answer()


@admin.message(AddCourseToUserStates.USERNAME)
async def process_username(message: Message, state: FSMContext, session: AsyncSession):
    username = message.text.strip().lstrip('@')

    user = await session.execute(
        select(User).where(User.username == username))
    user = user.scalar_one_or_none()

    if not user:
        return await message.answer(
            "❌ Пользователь не найден. Попробуйте еще раз:",
            reply_markup=cancel_kb()
        )

    await state.update_data(user_id=user.telegram_id, username=username)

    # Запрашиваем выбор категории
    categories = await get_all_categories(session)
    if not categories:
        await state.clear()
        return await message.answer(
            "❌ Нет доступных категорий",
            reply_markup=admin_main_kb()
        )

    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.name,
            callback_data=f"addcourse_category_{category.id}"
        )
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите категорию курса:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddCourseToUserStates.CATEGORY)


async def show_courses_page(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    current_page = data['current_page']

    # Получаем курсы для текущей страницы
    courses = await session.execute(
        select(Course)
        .offset(current_page * COURSES_PER_PAGE)
        .limit(COURSES_PER_PAGE)
    )
    courses = courses.scalars().all()

    builder = InlineKeyboardBuilder()

    # Добавляем кнопки курсов
    for course in courses:
        builder.button(
            text=f"{course.title[:20]} (ID: {course.id})",  # Обрезаем длинное название
            callback_data=f"select_course_for_user_{course.id}"
        )

    # Добавляем кнопки навигации
    nav_buttons = []
    if current_page > 0:
        nav_buttons.append(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="prev_course_page"
        ))
    if current_page < data['total_pages'] - 1:
        nav_buttons.append(InlineKeyboardButton(
            text="Далее ➡️",
            callback_data="next_course_page"
        ))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="admin_cancel"
    ))

    try:
        await message.answer(
            f"Выберите курс (Страница {current_page + 1}/{data['total_pages']}):",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка при отображении курсов: {e}")
        await message.answer(
            "Произошла ошибка при отображении списка курсов",
            reply_markup=admin_main_kb()
        )
        await state.clear()

@admin.callback_query(F.data == "prev_course_page")
async def prev_course_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.update_data(current_page=data['current_page'] - 1)
    await callback.message.delete()  # Удаляем старое сообщение
    await show_courses_page(callback.message, session, state)
    await callback.answer()

@admin.callback_query(F.data == "next_course_page")
async def next_course_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.update_data(current_page=data['current_page'] + 1)
    await callback.message.delete()  # Удаляем старое сообщение
    await show_courses_page(callback.message, session, state)
    await callback.answer()

# Обработчик выбора курса
@admin.callback_query(F.data.startswith("addcourse_category_"), AddCourseToUserStates.CATEGORY)
async def select_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    category_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=category_id)

    courses = await session.execute(
        select(Course)
        .where(Course.category_id == category_id)
    )
    courses = courses.scalars().all()

    if not courses:
        await callback.answer("В этой категории нет курсов", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for course in courses:
        builder.button(
            text=f"{course.title} ({course.price}₽)",
            callback_data=f"addcourse_select_{course.id}"
        )
    builder.button(text="⬅️ Назад к категориям", callback_data="addcourse_back_to_categories")
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите курс для добавления:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddCourseToUserStates.COURSE)
    await callback.answer()


@admin.callback_query(F.data == "addcourse_back_to_categories", AddCourseToUserStates.COURSE)
async def back_to_categories(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    categories = await get_all_categories(session)

    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.name,
            callback_data=f"addcourse_category_{category.id}"
        )
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)

    await callback.message.edit_text(
        "Выберите категорию курса:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddCourseToUserStates.CATEGORY)
    await callback.answer()


@admin.callback_query(F.data.startswith("addcourse_select_"), AddCourseToUserStates.COURSE)
async def select_course(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    course_id = int(callback.data.split("_")[-1])
    data = await state.get_data()

    course = await session.get(Course, course_id)

    user = await session.execute(
        select(User).where(User.telegram_id == data['user_id'])
    )
    user = user.scalar_one_or_none()

    if not course or not user:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    # Проверяем, есть ли уже курс у пользователя
    if user.purchased_courses and course_id in user.purchased_courses:
        await callback.answer("⚠️ У пользователя уже есть этот курс", show_alert=True)
        return

    await state.update_data(course_id=course_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="addcourse_confirm")
    builder.button(text="⬅️ Назад", callback_data=f"addcourse_category_{course.category_id}")
    builder.adjust(1)

    await callback.message.edit_text(
        f"Добавить курс пользователю @{data['username']}?\n\n"
        f"📚 Курс: {course.title}\n"
        f"💵 Цена: {course.price}₽\n"
        f"📂 Категория: {(await session.get(Category, course.category_id)).name}",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddCourseToUserStates.CONFIRM)
    await callback.answer()


@admin.callback_query(F.data == "addcourse_confirm", AddCourseToUserStates.CONFIRM)
async def confirm_adding(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()

    user = await session.execute(
        select(User).where(User.telegram_id == data['user_id'])
    )
    user = user.scalar_one_or_none()

    course = await session.get(Course, data['course_id'])

    if not user or not course:
        await callback.answer("❌ Ошибка: пользователь или курс не найдены", show_alert=True)
        await state.clear()
        return

    if user.purchased_courses is None:
        user.purchased_courses = []

    # Проверяем, есть ли уже курс у пользователя
    if data['course_id'] in user.purchased_courses:
        await callback.answer("⚠️ У пользователя уже есть этот курс", show_alert=True)
        return

    # Добавляем курс
    if user.purchased_courses is None:
        user.purchased_courses = [data['course_id']]
    else:
        user.purchased_courses = list(user.purchased_courses) + [data['course_id']]
    await session.commit()

    # Пытаемся уведомить пользователя
    try:
        await callback.bot.send_message(
            user.telegram_id,
            f"🎉 Вам добавлен курс!\n\n"
            f"📚 {course.title}\n"
            f"💵 {course.price}₽\n\n"
            f"Доступен в вашем профиле."
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")

    await callback.message.edit_text(
        f"✅ Курс {course.title} успешно добавлен пользователю @{data['username']}",
        reply_markup=admin_main_kb()
    )
    await state.clear()
    await callback.answer()

@admin.callback_query(F.data == "admin_cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено",
        reply_markup=admin_main_kb()
    )
    await callback.answer()