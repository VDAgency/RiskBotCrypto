# admin_panel.py
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.future import select

from config.bot_instance import bot
from database import get_db, get_bot_statistics, get_user_info_by_username
from config.config import ADMIN_IDS


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

# Создаем состояние ожидания ввода юзернейма
class AdminStates(StatesGroup):
    waiting_for_username = State()



# === Вызов логики работы команды help ===
@router.message(Command("admin"))
async def admin_handler(message: Message):
    await admin_message(message)


async def admin_message(message: Message):
    user_id = message.from_user.id
    # Проверяем, что отправитель - администратор
    if user_id not in ADMIN_IDS:
        await message.answer("🚫 У вас нет прав для доступа в админ-панель.")
        return

    text = (
        "Добро пожаловать в административную панель бота! 🙌\n\n"
        "Вы можете выбрать одну из следующих опций:\n"
        "1️⃣ Общая статистика по боту (количество пользователей, прошли тест, скачали гайд и т.п.)\n"
        "2️⃣ Индивидуальная информация. Информацию по каждому конкретному пользователю (когда начал пользоваться ботом, какой тип профиля, кол-во балов, скачал ли гайд)\n"
        "3️⃣ Рассылка пользователям (можно отправить рассылку разным категориям пользователей)"
    )

    # Создаем инлайн-кнопки для меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Общая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Индивидуальная информация", callback_data="admin_user_info")],
        [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")]
    ])

    # Отправляем сообщение с кнопками
    await message.answer(text, reply_markup=keyboard)


# Функция получения общей статистики по боту
@router.callback_query(lambda callback_query: callback_query.data == "admin_stats")
async def admin_stats(callback_query: CallbackQuery):
    # Проверка, что администратор нажал кнопку
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("🚫 У вас нет прав для доступа.")
        return

    # Подключаем базу данных
    async for db in get_db():
        # Получаем статистику из базы данных
        stats = await get_bot_statistics(db)

    # Формируем текст для отправки админу
    text = (
        f"📊 Общая статистика бота:\n\n"
        f"1️⃣ Общее количество пользователей: {stats['total_users']}\n"
        f"2️⃣ Приняли Политику и Офферту: {stats['policy_accepted']}\n"
        f"3️⃣ Прошли тест: {stats['test_passed']}\n"
        f"4️⃣ Скачали гайд: {stats['guide_downloaded']}"
    )

    # Создаем клавиатуру с кнопкой "Назад"
    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")]
    ])
    
    # Удаляем старое сообщение и отправляем новое
    await callback_query.message.delete()  # Удаляем старое сообщение
    
    # Отправляем статистику админу
    await callback_query.message.answer(text, reply_markup=back_button)
    await callback_query.answer()


# Функция для обработки нажатия кнопки "Назад"
@router.callback_query(lambda callback_query: callback_query.data == "back_to_admin_menu")
async def back_to_admin_menu(callback_query: CallbackQuery):
    # Проверка, что администратор нажал кнопку
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("🚫 У вас нет прав для доступа.")
        return

    text = (
        "Добро пожаловать в административную панель бота! 🙌\n\n"
        "Вы можете выбрать одну из следующих опций:\n"
        "1️⃣ Общая статистика по боту (количество пользователей, прошли тест, скачали гайд и т.п.)\n"
        "2️⃣ Индивидуальная информация. Информацию по каждому конкретному пользователю (когда начал пользоваться ботом, какой тип профиля, кол-во балов, скачал ли гайд)\n"
        "3️⃣ Рассылка пользователям (можно отправить рассылку разным категориям пользователей)"
    )

    # Создаем инлайн-кнопки для меню
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Общая статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Индивидуальная информация", callback_data="admin_user_info")],
        [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")]
    ])

    # Удаляем старое сообщение и отправляем новое
    await callback_query.message.delete()  # Удаляем старое сообщение
    
    await callback_query.message.answer(text, reply_markup=keyboard)
    await callback_query.answer()



# Обработчик нажатия на кнопку "Индивидуальная информация"
@router.callback_query(lambda callback_query: callback_query.data == "admin_user_info")
async def admin_user_info(callback_query: CallbackQuery, state: FSMContext):
    # Проверка, что администратор нажал кнопку
    if callback_query.from_user.id not in ADMIN_IDS:
        await callback_query.answer("🚫 У вас нет прав для доступа.")
        return

    # Удаляем старое сообщение и отправляем новое
    await callback_query.message.delete()  # Удаляем старое сообщение
    
    # Отправляем админу сообщение с просьбой ввести юзернейм
    prompt_message = await callback_query.message.answer("Введите юзернейм пользователя, чтобы получить информацию.")
    
    # Устанавливаем состояние ожидания ввода
    await state.set_state(AdminStates.waiting_for_username)
    
    # Сохраняем ID сообщения с запросом на ввод
    await state.update_data(prompt_message_id=prompt_message.message_id)
    
    await callback_query.answer()


# Обработчик, который ждет ввода юзернейма и возвращает информацию
@router.message(AdminStates.waiting_for_username)
async def process_username_input(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Проверка, что администратор прислал сообщение
    if user_id not in ADMIN_IDS:
        await message.answer("🚫 У вас нет прав для доступа.")
        return

    username = message.text.strip()
    if username.startswith('@'):
        username = username[1:]

    # Подключаем базу данных и получаем информацию о пользователе
    async for db in get_db():
        user_info = await get_user_info_by_username(db, username)

    if user_info:
        # Формируем текст с информацией о пользователе
        user_info_text = (
            f"🔍 Информация о пользователе {username}:\n\n"
            f"👤 Имя: {user_info['first_name']} {user_info['last_name']}\n"
            f"📅 Дата регистрации: {user_info['registration_date']}\n"
            f"💼 Стратегия: {user_info['strategy_type']}\n"
            f"📊 Количество баллов: {user_info['score']}\n"
            f"📥 Скачал гайд: {'Да' if user_info['guide_downloaded'] else 'Нет'}"
        )
    else:
        user_info_text = f"⚠️ Пользователь с юзернеймом {username} не найден."

    # Получаем ID сообщения с запросом на ввод юзернейма из состояния
    data = await state.get_data()
    prompt_message_id = data.get('prompt_message_id')
    
    # Удаляем старое сообщение (запрос на ввод юзернейма)
    if prompt_message_id:
        await message.bot.delete_message(message.chat.id, prompt_message_id)
    
    # Создаем клавиатуру с кнопкой "Назад"
    back_button = InlineKeyboardMarkup(inline_keyboard=[ 
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin_menu")] 
    ])
    
    # Удаляем старое сообщение и отправляем новое
    await message.delete()  # Удаляем старое сообщение
    
    # Отправляем информацию админу
    await message.answer(user_info_text, reply_markup=back_button)

    # Завершаем состояние
    await state.clear()


