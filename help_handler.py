# help_handler.py
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select

from config.bot_instance import bot
from database import get_db, save_question_to_db, get_question_by_id, get_questions_by_user, Question



# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)
logger = logging.getLogger(__name__)


# Создаём роутер
router = Router()

# Определяем состояния для FSM
class AdminResponse(StatesGroup):
    waiting_for_response = State()

# ID администратора
ADMIN_ID = 5389520473


# === Вызов логики работы команды help ===
@router.message(Command("help"))
async def help_command(message: Message):
    await help_message(message)


async def help_message(message: Message):
    text = (
        "👋 Привет! Я — бот, который помогает определить твой риск-профиль для торговли с помощью сеточных ботов.\n\n"
        "💡 Сейчас ведется разработка функционала для регистрации в закрытой группе по торговле сеточными ботами и ручной торговле торговле на бирже.\n\n"
        "❓ Если у тебя есть вопросы, ты можешь задать их мне! Я передам их создателю курса по торговле.\n\n"
        "🔗 Для регистрации в закрытой группе, переходи по [ссылке](https://example.com/register). Это пока заглушка.\n\n"
        "👇 Нажми кнопку, чтобы задать вопрос создателю курса."
    )

    # Создаем клавиатуру с кнопкой "Задать вопрос"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Задать вопрос", callback_data="ask_question")]
    ])

    # Отправляем сообщение с кнопкой
    await message.answer(text, reply_markup=keyboard)


# === Обработка нажатия на кнопку "Задать вопрос" ===
@router.callback_query(F.data == "ask_question")
async def ask_question(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    # Сохраняем состояние, что пользователь хочет задать вопрос
    await state.set_state(AdminResponse.waiting_for_response)  # Устанавливаем состояние для ожидания вопроса
    await callback_query.message.answer(
        "Введите ваш вопрос и нажмите отправить.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Отмена")]
            ],
            resize_keyboard=True
        )
    )
    await callback_query.answer()


# === Обработка вопроса пользователя ===
@router.message(AdminResponse.waiting_for_response, F.text != "Отмена")
async def handle_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    question_text = message.text

    # Сохраняем вопрос в базе данных
    async for db in get_db():
        question = await save_question_to_db(db, user_id, question_text)

    # Создаём inline-кнопку для ответа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ответить", callback_data=f"answer_{question.id}")]
    ])

    # Отправляем сообщение администратору
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💬 Новый вопрос от пользователя {message.from_user.full_name} (ID: {user_id}, Question ID: {question.id}):\n\n{question_text}",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке вопроса администратору: {str(e)}")
        await message.answer("Ошибка при отправке вопроса. Попробуйте позже.")
        await state.clear()
        return

    # Подтверждение пользователю
    await message.answer(
        "Ваш вопрос отправлен создателю курса. Ожидайте ответа.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True
        )
    )
    await state.clear()



# === Обработка команды /questions для администратора ===
@router.message(Command("questions"), F.from_user.id == ADMIN_ID)
async def list_questions(message: Message):
    async for db in get_db():
        # Получаем все открытые вопросы (answered = False)
        result = await db.execute(select(Question).filter(Question.answered == False))
        questions = result.scalars().all()

        if not questions:
            await message.answer("Нет активных вопросов.")
            return

        # Формируем сообщение со списком вопросов
        response = "📋 Активные вопросы:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for question in questions:
            user_name = f"User_{question.user_id}"  # Можно улучшить, достав имя из таблицы User
            response += f"👤 {user_name} (ID: {question.user_id}, Question ID: {question.id}): {question.question[:50]}...\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=f"Ответить {user_name}", callback_data=f"answer_{question.id}")
            ])

        await message.answer(response, reply_markup=keyboard)


# === Обработка нажатия кнопки "Ответить" ===
@router.callback_query(F.data.startswith("answer_"))
async def handle_answer_button(callback: CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id

    # Проверяем, что это администратор
    if admin_id != ADMIN_ID:
        await callback.answer("Только администратор может отвечать на вопросы!", show_alert=True)
        return

    # Извлекаем question_id из callback_data
    question_id = int(callback.data.split("_")[1])

    # Проверяем, существует ли вопрос
    async for db in get_db():
        result = await db.execute(select(Question).filter(Question.id == question_id))
        question = result.scalars().first()
        if not question:
            await callback.message.answer("Ошибка: вопрос не найден.")
            await callback.answer()
            return

        # Сохраняем question_id в состоянии
        await state.update_data(question_id=question_id, user_id=question.user_id)
        await state.set_state(AdminResponse.waiting_for_response)

        # Просим администратора ввести ответ
        await callback.message.answer(f"Введите ответ для вопроса (ID: {question_id}):")
        await callback.answer()


# === Обработка ответа администратора ===
@router.message(AdminResponse.waiting_for_response, F.from_user.id == ADMIN_ID)
async def process_admin_response(message: Message, state: FSMContext):
    admin_id = message.from_user.id

    # Проверяем, что это администратор
    if admin_id != ADMIN_ID:
        await message.answer("Только администратор может отвечать на вопросы!")
        return

    # Получаем question_id и user_id из состояния
    state_data = await state.get_data()
    question_id = state_data.get("question_id")
    user_id = state_data.get("user_id")

    if not question_id or not user_id:
        await message.answer("Ошибка: не выбран вопрос для ответа.")
        await state.clear()
        return

    # Сохраняем ответ в базе данных
    async for db in get_db():
        result = await db.execute(select(Question).filter(Question.id == question_id))
        question = result.scalars().first()
        if question:
            question.answer = message.text
            question.answered = True
            await db.commit()
            await db.refresh(question)
        else:
            await message.answer("Ошибка: вопрос не найден.")
            await state.clear()
            return

    # Отправляем ответ пользователю
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"Ответ от администратора:\n\n{message.text}"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке ответа пользователю: {str(e)}")
        await message.answer("Ошибка при отправке ответа пользователю.")
        await state.clear()
        return

    # Подтверждаем администратору
    await message.answer(f"Ответ отправлен пользователю (ID: {user_id}).")
    await state.clear()

# === Обработка команды "Отмена" ===
@router.message(F.text == "Отмена")
async def cancel_question(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Отправка вопроса отменена.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True
        )
    )

