from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.requests import get_user_telegram_ids, get_admin_ids
from app.keyboards import menu 

support_router = Router()

class SupportStates(StatesGroup):
    WAITING_QUESTION = State()
    WAITING_ANSWER = State()

@support_router.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✉️ Можете задать свой вопрос прямо здесь!\n\n"
        "Просто напишите сообщение в этот чат.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_support')]
        ])  # Здесь была ошибка: скобки не закрыты для InlineKeyboardMarkup
    )
    await state.set_state(SupportStates.WAITING_QUESTION)
    await callback.answer()

@support_router.callback_query(F.data == "cancel_support")
async def cancel_support(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=menu 
    )
    await callback.answer()


@support_router.message(SupportStates.WAITING_QUESTION)
async def process_question(message: Message, state: FSMContext):
    try:
        await state.update_data(
            user_id=message.from_user.id,
            username=message.from_user.username,
            question=message.text
        )
        
        admins = get_admin_ids()

        for admin_id in admins:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"❓ Вопрос от @{message.from_user.username}:\n\n{message.text}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="📨 Ответить",
                            callback_data=f"answer_{message.from_user.id}"
                        )
                    ]])
                )
            except Exception as e:
                print(f"Ошибка отправки админу {admin_id}: {e}")
        
        await message.answer("✅ Ваш вопрос отправлен администраторам")
        
    except Exception as e:
        await message.answer("❌ Произошла ошибка при обработке вопроса")
        print(f"Error in process_question: {e}")
    finally:
        await state.clear()

@support_router.callback_query(F.data.startswith("answer_"))
async def start_answer(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split('_')[1])
    await state.update_data(user_id=user_id)
    
    await callback.message.edit_text(
        f"Отправьте ответ для пользователя (ID: {user_id}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_answer')]
        ])  # Закрыта скобка для InlineKeyboardMarkup
    )
    await state.set_state(SupportStates.WAITING_ANSWER)
    await callback.answer()

@support_router.message(SupportStates.WAITING_ANSWER)
async def send_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await message.bot.send_message(
            data['user_id'],
            f"📩 Ответ от поддержки:\n\n{message.text}"
        )
        await message.answer("✅ Ответ отправлен!")
    except:
        await message.answer("❌ Не удалось отправить ответ. Пользователь заблокировал бота?")
    
    await state.clear()

@support_router.callback_query(F.data == "cancel_answer")
async def cancel_admin_answer(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Ответ отменён")
    await callback.answer()
