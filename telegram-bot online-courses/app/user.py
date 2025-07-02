from aiogram import Router, F
from aiogram import Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
import app.keyboards as kb
from app.database.requests import set_user, get_course, get_user_profile, get_user_courses, get_all_categories, \
    get_category_by_id, get_courses_by_category
from app.database.models import User
from sqlalchemy import select
from loguru import logger 
from app.database.requests import async_session
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton, InlineKeyboardMarkup
from app.database.models import Course, Category,PendingPayment
from aiogram.types import LabeledPrice
from app.database.models import PendingPayment
import uuid
import os
from dotenv import load_dotenv
import os
import aiohttp
from urllib.parse import quote_plus
from app.database.models import async_session
from uuid import uuid4


user = Router()
@user.callback_query(F.data == 'start')
@user.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    user = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id))
    user = user.scalar_one_or_none()

    if not user:
        # Создаем нового пользователя
        new_user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        session.add(new_user)
        await session.commit()
        await message.answer('Привет, я бот по продаже онлайн-курсов!', reply_markup=kb.menu)
    else:
        # Обновляем username, если он изменился
        if user.username != message.from_user.username:
            user.username = message.from_user.username
            await session.commit()
        await message.answer('С возвращением!', reply_markup=kb.menu)


@user.callback_query(F.data == "catalog")
async def show_categories(callback: CallbackQuery, session: AsyncSession):
    categories = await get_all_categories(session)
    if not categories:
        await callback.message.edit_text(
            "Категории курсов пока не добавлены",
            reply_markup=await kb.back_to_menu()
        )
        return
    
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=f"{category.name}", 
            callback_data=f"cat_{category.id}_0"
        )
    
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📚 Выберите категорию курсов:",
        reply_markup=builder.as_markup()
    )

@user.callback_query(F.data.startswith("cat_"))
async def show_courses_in_category(callback: CallbackQuery, session: AsyncSession):
    try:
        _, category_id, page = callback.data.split("_")
        category_id = int(category_id)
        page = int(page)
        
        category = await get_category_by_id(session, category_id)
        if not category:
            return await callback.answer("Категория не найдена")

        all_courses = await get_courses_by_category(session, category_id)
        per_page = 10
        total_pages = (len(all_courses) + per_page - 1) // per_page
        page_courses = all_courses[page*per_page : (page+1)*per_page]

        builder = InlineKeyboardBuilder()
        
        # Кнопки курсов (по одной в строке)
        for course in page_courses:
            builder.row(InlineKeyboardButton(
                text=f"{course.title} - {course.price}₽",
                callback_data=f"course_{course.id}"
            ))
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"cat_{category_id}_{page-1}"
            ))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="Далее ➡️",
                callback_data=f"cat_{category_id}_{page+1}"
            ))
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        builder.row(InlineKeyboardButton(
            text="🔙 В каталог",
            callback_data="catalog"
        ))

        await callback.message.edit_text(
            f"<b>{category.name}</b>\n\n"
            "Выберите курс:",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer("Произошла ошибка")


@user.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Вы вернулись в меню!",
        reply_markup=kb.menu
    )

@user.callback_query(F.data.startswith("course_"))
async def show_course(callback: CallbackQuery):
    try:
        async with async_session() as session:
            async with session.begin():
                course_id = int(callback.data.split("_")[1])
                course = await session.get(Course, course_id)
                
                if not course:
                    await callback.answer("Курс не найден", show_alert=True)
                    return
                
                await session.refresh(course, ['category'])
                
                user = await session.execute(
                    select(User)
                    .where(User.telegram_id == callback.from_user.id)
                )
                user = user.scalar_one_or_none()
                
                has_course = user and course.id in (user.purchased_courses or [])
                
                builder = InlineKeyboardBuilder()
                
                if not has_course:
                    builder.button(text="💳 Оплатить", callback_data=f"pay_{course.id}")
                
                builder.button(text="⬅️ Назад", callback_data=f"cat_{course.category_id}_0")
                builder.adjust(1)
                
                message_text = (
                    f"📂 Категория: {course.category.name}\n\n"
                    f"📚 <b>{course.title}</b>\n"
                    f"💵 Цена: {course.price} руб.\n"
                    f"{course.description}"
                )
                
                if has_course:
                    message_text += "\n\n✅ Вы уже приобрели этот курс"
                
                await callback.message.edit_text(
                    message_text,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
                
    except Exception as e:
        logger.error(f"Error in show_course: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)

@user.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        async with session.begin():
            try:
                # Получаем пользователя
                user = await session.execute(
                    select(User)
                    .where(User.telegram_id == callback.from_user.id)
                )
                user = user.scalar_one_or_none()
                
                if not user:
                    await callback.answer("Пользователь не найден", show_alert=True)
                    return
                
                # Формируем базовую информацию профиля
                profile_text = [
                    "💼 <b>Профиль</b>\n\n"
                ]
                
                # Добавляем баланс, если есть
                if hasattr(user, 'balance'):
                    profile_text.append(f"💰 Баланс: {user.balance} руб.\n")
                
                # Добавляем дату регистрации, если есть
                if hasattr(user, 'registered_at'):
                    profile_text.append(f"📅 Регистрация: {user.registered_at.strftime('%d.%m.%Y')}\n\n")
                else:
                    profile_text.append("\n")
                
                # Обрабатываем курсы
                if hasattr(user, 'purchased_courses') and user.purchased_courses:
                    courses = []
                    for item in user.purchased_courses:
                        if isinstance(item, str):
                            courses.append(f"▪️ {item}")
                        elif isinstance(item, int):
                            course = await session.get(Course, item)
                            if course:
                                courses.append(f"▪️ {course.title}")
                    
                    if courses:
                        profile_text.append("📚 <b>Ваши курсы:</b>\n")
                        profile_text.append("\n".join(courses))
                        profile_text.append("\n\nНажмите на курс в меню ниже")
                    else:
                        profile_text.append("📚 У вас пока нет купленных курсов")
                else:
                    profile_text.append("📚 У вас пока нет купленных курсов")
                
                # Создаем кнопки для курсов
                builder = InlineKeyboardBuilder()
                
                if hasattr(user, 'purchased_courses') and user.purchased_courses:
                    for item in user.purchased_courses:
                        if isinstance(item, int):
                            course = await session.get(Course, item)
                            if course:
                                builder.button(
                                    text=f"📚 {course.title}",
                                    callback_data=f"courseinfo_{course.id}"
                                )
                        elif isinstance(item, str):
                            # Ищем курс по названию
                            course = await session.execute(
                                select(Course)
                                .where(Course.title == item)
                                .limit(1)
                            )
                            course = course.scalar_one_or_none()
                            if course:
                                builder.button(
                                    text=f"📚 {course.title}",
                                    callback_data=f"courseinfo_{course.id}"
                                )
                
                builder.row(InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_to_menu"
                ))
                
                await callback.message.edit_text(
                    "".join(profile_text),
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
                
            except Exception as e:
                logger.error(f"Error in show_profile: {e}")
                await callback.answer("Произошла ошибка при загрузке профиля", show_alert=True)

@user.callback_query(F.data.startswith("courseinfo_"))
async def show_course_info(callback: CallbackQuery):
    try:
        async with async_session() as session:
            async with session.begin():
                course_id = int(callback.data.split("_")[1])
                course = await session.get(Course, course_id)
                
                if not course:
                    await callback.answer("Курс не найден", show_alert=True)
                    return
                
                # Формируем сообщение с информацией о курсе
                message_text = (
                    f"<b>📚 Название:</b> {course.title}\n\n"
                    f"<b>📝 Описание:</b>\n{course.description}\n\n"
                    f"<b>🔗 Ссылка:</b> {course.link}"
                )
                
                builder = InlineKeyboardBuilder()
                builder.button(text="⬅️ Назад", callback_data="profile")
                
                await callback.message.edit_text(
                    message_text,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup(),
                    disable_web_page_preview=True  # Отключаем превью ссылки
                )
                
    except Exception as e:
        logger.error(f"Error in show_course_info: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)



@user.callback_query(F.data.regexp(r"^pay_\d+$"))
async def choose_payment_method(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(
        "💳 Выберите способ оплаты:",
        reply_markup=await kb.payment_options_kb(course_id)
    )

@user.callback_query(F.data.startswith("pay_manager_"))
async def pay_via_manager(callback: CallbackQuery):
    manager_tag = "@rassokhin1"
    await callback.message.edit_text(
        f"💬 Напишите менеджеру для оплаты: {manager_tag}",
        reply_markup=await kb.back_to_course_kb(int(callback.data.split("_")[2]))
    )


import uuid

# В user.py добавляем этот код (заменяем текущую реализацию pay_via_cryptocloud)
import os
import uuid
import requests  # Добавляем этот импорт
from dotenv import load_dotenv
from requests.exceptions import RequestException
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

load_dotenv()




API_KEY = os.getenv("CRYPTOCLOUD_API_TOKEN")
SHOP_ID = os.getenv("CRYPTOCLOUD_PUBLIC_KEY")

@user.callback_query(F.data.startswith("pay_cryptocloud_"))
async def pay_via_cryptocloud(callback: CallbackQuery):
    course_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    async with async_session() as session:
        # Получаем курс из БД
        course = await session.get(Course, course_id)
        if not course:
            await callback.answer("Курс не найден", show_alert=True)
            return

        # Создаем уникальный идентификатор платежа
        payment_uuid = str(uuid.uuid4())

        # Сохраняем информацию о платеже в базу
        payment = PendingPayment(
            user_id=user_id,
            course_id=course_id,
            payment_id=payment_uuid,
            status="pending"
        )
        session.add(payment)
        await session.commit()

    # Формируем данные для API CryptoCloud
    payload = {
        "amount": float(course.price),
        "shop_id": SHOP_ID,
        "currency": "RUB",
        "order_id": payment_uuid  # Передаем наш UUID в заказ
    }

    headers = {
        "Authorization": f"Token {API_KEY}",
        "Content-Type": "application/json"
    }

    # Создаем счет в CryptoCloud
    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(
            "https://api.cryptocloud.plus/v2/invoice/create",
            json=payload,
            headers=headers
        ) as resp:
            if resp.status != 200:
                await callback.answer("Ошибка создания счета. Попробуйте позже.", show_alert=True)
                return
            data = await resp.json()

    pay_link = data.get("result", {}).get("link")
    if not pay_link:
        await callback.answer("Ошибка получения ссылки на оплату.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_link)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment_uuid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"course_{course_id}")]
    ])

    await callback.message.edit_text(
        f"<b>💳 Оплата курса '{course.title}'</b>\n\n"
        f"Сумма: <b>{course.price} RUB</b>\n\n"
        f"После оплаты нажмите кнопку 'Проверить оплату'.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@user.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery):
    payment_uuid = callback.data.split("_")[-1]
    success = await verify_payment(payment_uuid, callback.bot)

    if success:
        async with async_session() as session:
            payment = await session.execute(
                select(PendingPayment)
                .where(PendingPayment.payment_id == payment_uuid)
            )
            payment = payment.scalar_one_or_none()
            course = await session.get(Course, payment.course_id)

            await callback.message.edit_text(
                f"✅ Оплата подтверждена! Курс '{course.title}' добавлен в ваш профиль.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📚 Перейти к курсу", callback_data=f"courseinfo_{course.id}")]
                ])
            )
    else:
        await callback.answer("Оплата еще не поступила. Попробуйте позже.", show_alert=True)

async def verify_payment(payment_uuid: str, bot: Bot = None):
    """Проверяет статус платежа и выдает курс"""
    async with async_session() as session:
        payment = await session.execute(
            select(PendingPayment).where(PendingPayment.payment_id == payment_uuid)
        )
        payment = payment.scalar_one_or_none()

        if not payment or payment.status == "paid":
            return False

        # Запрос к CryptoCloud
        headers = {"Authorization": f"Token {API_KEY}", "Content-Type": "application/json"}
        payload = {"uuids": [payment_uuid]}

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                "https://api.cryptocloud.plus/v2/invoice/merchant/info",
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()

        invoice = data.get("result", [{}])
        if len(invoice)==0:
            print(data)
            return False
        else:
            invoice = data.get("result", [{}])[0]
        if invoice.get("status") not in ["paid", "overpaid"]:
            return False

        # Обновляем статус
        payment.status = "paid"
        user = await session.get(User, payment.user_id)
        if user.purchased_courses is None:
            user.purchased_courses = []
        if payment.course_id not in user.purchased_courses:
            user.purchased_courses.append(payment.course_id)
        await session.commit()

        # Уведомляем пользователя (если передан бот)
        if bot:
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"✅ Платеж подтвержден! Курс добавлен в ваш профиль."
                )
            except:
                pass  # Пользователь заблокировал бота
        return True









