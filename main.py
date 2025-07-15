import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State

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

# === Старт ===
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(score=0)
    await state.set_state(Test.Q1)
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
    score = score_map.get(message.text[:1].lower(), 0)
    await state.update_data(score=score)
    await state.set_state(Test.Q2)
    q_text = questions[Test.Q2]
    a_buttons = answers[0]
    await message.answer(q_text, reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=opt)] for opt in a_buttons],
        resize_keyboard=True
    ))

# === Q2–Q7 ===
@router.message(F.text.startswith(("а", "б", "в", "г")))
async def handle_question(message: Message, state: FSMContext):
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
        await show_result(message, score)
        await state.clear()
    else:
        next_state = states[current_index + 1]
        await state.set_state(next_state)
        await message.answer(questions[next_state], reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=opt)] for opt in answers[current_index + 1]],
            resize_keyboard=True
        ))

# === Финальный результат и гайд ===
async def show_result(message: Message, score: int):
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

    await message.answer(f"✅ *Тест завершён!* Вот твой результат:\n\n{result}", parse_mode="Markdown")

    # Кнопки: скачать гайд + пройти заново
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Скачать гайд", callback_data="download_guide")],
        [InlineKeyboardButton(text="🔁 Пройти тест заново", callback_data="restart_test")]
    ])
    await message.answer("Что хочешь сделать дальше?", reply_markup=keyboard)

# === Обработка кнопок ===
@router.callback_query(F.data == "download_guide")
async def send_guide(callback):
    await callback.message.answer_document(InputFile("гайд.pdf"), caption="📘 *Скачай гайд по настройке грид-ботов!*", parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "restart_test")
async def restart(callback: Message, state: FSMContext):
    await state.clear()
    await start(callback.message, state)
    await callback.answer()

# === Запуск бота ===
async def main():
    bot = Bot(
        token="8181084618:AAE-MU87yQh8yzNL4iXhbQ3CITV9J9ggI5s",  # Замените на свой
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())