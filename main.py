import time
time.sleep(7)

import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, CallbackQuery
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State

from config.bot_instance import bot
from dotenv import load_dotenv
from database import create_tables, get_db, add_user, update_user_acceptance, update_strategy_type, update_user_guide_downloaded, update_last_interaction_date
from config.setup_commands import set_bot_commands
from help_handler import router as help_router


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

# Загружаем переменные из файла .env
load_dotenv()



# === FSM состояния ===
class Test(StatesGroup):
    Q1 = State()
    Q2 = State()
    Q3 = State()
    Q4 = State()
    Q5 = State()
    Q6 = State()
    Q7 = State()

# === Router ===
router = Router()


# Функция для создания клавиатуры с галочками и кнопкой "Принять"
def create_policy_keyboard(accepted_policy=False, accepted_offer=False):
    policy_text = "✅ Политика конфиденциальности" if accepted_policy else "☐ Политика конфиденциальности"
    offer_text = "✅ Публичная оферта" if accepted_offer else "☐ Публичная оферта"

    # Создаем клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton(text=policy_text, callback_data="accept_policy")],
        [InlineKeyboardButton(text=offer_text, callback_data="accept_offer")],
        [InlineKeyboardButton(text="Принять", callback_data="accept")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Словарь для хранения состояния пользователя
user_acceptance = {}


# Обработчик для команды /start
@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    username = message.from_user.username
    language_code = message.from_user.language_code
    
    user_acceptance[user_id] = {"policy": False, "offer": False}
    logger.info(f"Команда /start получена от пользователя с telegram_id: {user_id}. Состояние инициализировано.")

    # Дополнительное логирование для проверки
    logger.info(f"Имя пользователя: {first_name}, Фамилия: {last_name}, Username: {username}, telegram_id: {user_id}, Язык: {language_code}")

    # Подключаем базу данных
    async for db in get_db():
        # Добавляем пользователя в базу данных
        await add_user(db, user_id, first_name, last_name, username, language_code)

    # Обновляем дату последнего взаимодействия
    async for db in get_db():
        await update_last_interaction_date(db, user_id)
    
    policy_url = "http://45.130.214.36:8000/static/policy.html"
    terms_url = "http://45.130.214.36:8000/static/terms.html"
    
    text = (
        "Для использования бота *YourRiskProfile*, пожалуйста, примите публичную оферту и политику конфиденциальности.\n\n"
        "Отметьте галочками оба документа и потом нажмите на кнопку - *Принять*\n\n"
        f"[Политика конфиденциальности]({policy_url})\n"
        f"[Публичная оферта]({terms_url})"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=create_policy_keyboard())


# Обработка нажатий на кнопки политики и оферты
@router.callback_query(lambda callback_query: callback_query.data in ["accept_policy", "accept_offer"])
async def process_policy_offer(callback_query: CallbackQuery, bot: Bot):
    user_id = callback_query.from_user.id
    if user_id not in user_acceptance:
        user_acceptance[user_id] = {"policy": False, "offer": False}

    # Обновляем состояние в зависимости от нажатой кнопки
    if callback_query.data == "accept_policy":
        user_acceptance[user_id]["policy"] = not user_acceptance[user_id]["policy"]
    elif callback_query.data == "accept_offer":
        user_acceptance[user_id]["offer"] = not user_acceptance[user_id]["offer"]

    # Обновляем клавиатуру
    await bot.edit_message_reply_markup(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=create_policy_keyboard(
            accepted_policy=user_acceptance[user_id]["policy"],
            accepted_offer=user_acceptance[user_id]["offer"]
        )
    )
    await callback_query.answer()


# Обработка кнопки "Принять"
@router.callback_query(lambda callback_query: callback_query.data == "accept")
async def process_accept(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    
    # Проверяем, что пользователь уже начал процесс принятия условий
    if user_id in user_acceptance and user_acceptance[user_id]["policy"] and user_acceptance[user_id]["offer"]:
        # Обновляем информацию о принятии условий в базе данных
        async for db in get_db():
            await update_user_acceptance(db, user_id, True, True)  # Обновляем статус принятия политики и оферты

        # Обновляем дату последнего взаимодействия
        async for db in get_db():
            await update_last_interaction_date(db, user_id)
        
        await callback_query.message.answer("Спасибо за доверие. Вы приняли условия.\nПриступим к тесту.")
        await start_next(callback_query.message, state)
    else:
        await callback_query.answer("Пожалуйста, примите оба документа, чтобы продолжить.", show_alert=True)


# === Карта баллов ===
score_map = {"а": 1, "б": 2, "в": 3, "г": 4}

questions = {
    Test.Q2: "2️⃣ Был ли у вас опыт потерь в криптовалютах?",
    Test.Q3: "3️⃣ Насколько вам комфортно наблюдать волатильность 10–30%?",
    Test.Q4: "4️⃣ Случалось ли вам покупать актив из-за эмоций, FOMO?",
    Test.Q5: "5️⃣ Какой у вас опыт в криптовалютах?",
    Test.Q6: "6️⃣ Как вы подходите к выбору монет для инвестиций?",
    Test.Q7: "7️⃣ Насколько вам комфортно использовать заемные средства (плечо)?"
}

answers = [
    [
        "а) Нет, я только начинаю",
        "б) Да, и это было очень неприятно",
        "в) Да, сделал выводы",
        "г) Да, и воспринимаю это как опыт"
    ],
    [
        "а) Это вызывает стресс",
        "б) Немного напрягает",
        "в) Привык, воспринимаю спокойно",
        "г) Чем выше волатильность — тем интереснее"
    ],
    [
        "а) Да, регулярно",
        "б) Иногда, стараюсь сдерживаться",
        "в) Редко, чаще по плану",
        "г) Нет, всегда по анализу"
    ],
    [
        "а) Меньше 6 месяцев",
        "б) До 1 года",
        "в) 1–2 года",
        "г) Более 2 лет"
    ],
    [
        "а) Следую за трендом",
        "б) Смотрю график",
        "в) Анализирую волатильность и ликвидность",
        "г) Глубокий фундаментальный анализ"
    ],
    [
        "а) Не использую и не хочу",
        "б) Только минимальное",
        "в) Использую с пониманием",
        "г) Комфортно использую высокое плечо"
    ]
]

# === Старт теста ===
async def start_next(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Очищаем состояние и устанавливаем начальные данные
    await state.clear()
    await state.update_data(score=0)
    
    # Устанавливаем состояние для первого вопроса
    await state.set_state(Test.Q1)
    
    # Обновляем дату последнего взаимодействия
    async for db in get_db():
        await update_last_interaction_date(db, user_id)
    
    # Отправляем первый вопрос с кнопками
    await message.answer(
        "Привет! Давай определим твой риск-профиль на крипторынке.\n\n"
        "1️⃣ Как вы себя чувствуете, когда цена актива падает на 30% за короткий срок?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="а) Хочу всё продать и выйти из рынка")],
                [KeyboardButton(text="б) Испытываю тревогу, но продолжаю наблюдать")],
                [KeyboardButton(text="в) Понимаю, что такое может быть")],
                [KeyboardButton(text="г) Вижу возможность для нового входа")],
            ],
            resize_keyboard=True
        )
    )


# === Q1 ===
@router.message(Test.Q1, F.text.startswith(("а", "б", "в", "г")))
async def handle_q1(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    score = score_map.get(message.text[:1].lower(), 0)
    await state.update_data(score=score)
    await state.set_state(Test.Q2)
    q_text = questions[Test.Q2]
    a_buttons = answers[0]
    
    # Обновляем дату последнего взаимодействия
    async for db in get_db():
        await update_last_interaction_date(db, user_id)
    
    await message.answer(q_text, reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in a_buttons],
        resize_keyboard=True
    ))

# === Q2–Q7 ===
@router.message(F.text.startswith(("а", "б", "в", "г")))
async def handle_question(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    state_data = await state.get_data()
    score = state_data.get("score", 0)
    score += score_map.get(message.text[:1].lower(), 0)
    await state.update_data(score=score)

    current_state = await state.get_state()
    states = list(questions.keys())

    try:
        current_index = states.index(getattr(Test, current_state.split(":")[-1]))
    except ValueError:
        return

    if current_state == Test.Q7.state:
        # Вместо вызова show_result, вызываем функцию удаления клавиатуры
        await delete_keyboard(message, state, score)
        
        # Обновляем дату последнего взаимодействия
        async for db in get_db():
            await update_last_interaction_date(db, user_id)
        
        await state.clear()
    else:
        next_state = states[current_index + 1]
        await state.set_state(next_state)
        await message.answer(questions[next_state], reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=opt)] for opt in answers[current_index + 1]],
            resize_keyboard=True
        ))


async def delete_keyboard(message: Message, state: FSMContext, score: int):
    try:
        # Проверка на существование клавиатуры, удаляем её, если она есть
        if message.reply_markup:
            await message.edit_reply_markup()
        else:
            logger.info("Клавиатура не найдена, пропускаем редактирование.")
    except Exception as e:
        logger.warning(f"Не удалось удалить клавиатуру: {e}")

    # Теперь вызываем функцию для отображения результата
    await show_result(message, score)


# === Финальный результат и гайд ===
async def show_result(message: Message, score: int):
    user_id = message.from_user.id
    strategy_type = None
    
    if score <= 13:
        result = """🟢 *Консервативная стратегия*
                    Вы предпочитаете стабильность и контроль, не готовы рисковать значительной частью депозита.

                    🔧 *Рекомендованная стратегия:*
                    • Сетка: широкая (консервативная)
                    • Тип торговли: только спот или фьючерсы с ISO-маржой
                    • Плечо: от 1 до 3
                    • Активы: монеты из *топ-50 CoinMarketCap* с высокой ликвидностью и историей
                    • Цель: сохранить депозит, ориентированная доходность *5–10%/м*

                    🛡 *Риск-менеджмент обязателен*: лимит убытка на цикл, ограниченное число ботов.
                """
        strategy_type = "Консервативная"
    
    elif score <= 21:
        result = """🟡 *Умеренная стратегия*
                    Вы открыты к риску, но хотите держать ситуацию под контролем.

                    🔧 *Рекомендованная стратегия:*
                    • Сетка: умеренная, консервативная
                    • Маржа: *ISO или Cross*, в зависимости от фазы рынка и волатильности
                    • Плечо: от 1 до 5
                    • Активы: криптовалюты из *топ-100 до топ-200 CMC*
                    • Цель: баланс доходности и рисков, работа в *обе стороны (лонг/шорт)* с фильтрацией тренда

                    ⚖️ Подходит для трейдеров, осознанно управляющих рисками и понимающих фазу рынка.
                """
        strategy_type = "Умеренная"
    
    else:
        result = """🔴 *Агрессивная стратегия*
                    Вы — трейдер с высокой терпимостью к риску. Вас не пугает волатильность, вы охотно заходите в быстро меняющиеся рыночные ситуации.

                    🔥 *Рекомендованная стратегия:*
                    • Сетка: *агрессивная и умеренная ширина*
                    • Маржа: *Cross*
                    • Плечо: от 5 до 10
                    • Активы: любые монеты CMC, соответствующие критериям *волатильности, ликвидности, объёма*
                    • Примеры: свежие листинги, памповые/дамповые активы
                    • Цель: высокая доходность *20–40% в месяц*

                    ⚠️ Требуется *ручное управление и частое взаимодействие с ботами*.
                """
        strategy_type = "Агрессивная"

    # Отправляем результат пользователю
    await message.answer(f"✅ *Тест завершён!* Вот твой результат:\n\n{result}", parse_mode="Markdown")

    # Подключаем базу данных и обновляем тип стратегии
    async for db in get_db():
        await update_strategy_type(db, user_id, score, strategy_type)
    
    # Обновляем дату последнего взаимодействия
    async for db in get_db():
        await update_last_interaction_date(db, user_id)
    
    # Кнопки: скачать гайд + пройти заново
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Скачать гайд", callback_data="download_guide")],
        [InlineKeyboardButton(text="🔁 Пройти тест заново", callback_data="restart_test")]
    ])
    await message.answer("Что хочешь сделать дальше?", reply_markup=keyboard)

# === Обработка кнопок ===

# === Обработка кнопки "Скачать гайд" ===
@router.callback_query(F.data == "download_guide")
async def send_guide(callback: CallbackQuery):
    file_path = "Guide_RM_MM.pdf"
    input_file = FSInputFile(path=file_path, filename="Guide_RM_MM.pdf")
    await callback.message.answer_document(input_file, caption="📘 *Скачай гайд по настройке грид-ботов!*", parse_mode="Markdown")
    
    # Подтверждаем обработку запроса
    await callback.answer()
    
    # Обновляем базу данных, что пользователь скачал гайд
    user_id = callback.from_user.id
    async for db in get_db():
        await update_user_guide_downloaded(db, user_id)  # Обновляем статус скачивания гайда
    
    # Обновляем дату последнего взаимодействия
    async for db in get_db():
        await update_last_interaction_date(db, user_id)


@router.callback_query(F.data == "restart_test")
async def restart(callback: Message, state: FSMContext):
    await state.clear()
    await start_next(callback.message, state)
    await callback.answer()

# === Запуск бота ===
async def main():
    # Инициализация базы данных (создание таблиц)
    await create_tables()  # Убедитесь, что таблицы созданы перед запуском бота
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.include_router(help_router)
    
    # Устанавливаем команды бота асинхронно
    await set_bot_commands(bot)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())