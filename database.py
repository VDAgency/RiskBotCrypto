import os
import asyncio
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import func
from dotenv import load_dotenv


# Загружает переменные из .env файла
load_dotenv()

# Определяем базовый класс для наших моделей
Base = declarative_base()

# Определяем модель для пользователей
class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True, autoincrement=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    username = Column(String(100))
    language_code = Column(String(10))
    registration_date = Column(DateTime, default=datetime.utcnow)
    policy_accepted = Column(Boolean, default=False)
    offer_accepted = Column(Boolean, default=False)
    score = Column(Integer, default=0)
    strategy_type = Column(String(50))
    guide_downloaded = Column(Boolean, default=False)
    last_interaction_date = Column(DateTime, default=datetime.utcnow)
    has_asked_question = Column(Boolean, default=False)
    admin_notified = Column(Boolean, default=False)


# Модель Question для фиксации вопросов и ответов
class Question(Base):
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True, index=True)  # Порядковый номер
    user_id = Column(Integer)  # ID пользователя, задавшего вопрос
    question = Column(String)  # Текст вопроса
    answer = Column(String, nullable=True)  # Ответ администратора
    answered = Column(Boolean, default=False)  # Статус ответа (по умолчанию False)
    parent_question_id = Column(Integer, ForeignKey('questions.id'), nullable=True)  # Связь с вопросом, на который отвечает

    # Отношение: Если это ответ, то parent_question_id указывает на вопрос
    parent_question = relationship("Question", remote_side=[id])



# Устанавливаем асинхронное соединение с MySQL
DATABASE_URL = os.getenv("DATABASE_URL")

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(DATABASE_URL, echo=True)

# Создание асинхронной сессии
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Создание таблиц в базе данных (асинхронно)
async def create_tables():
    async with engine.begin() as conn:
        # Создаем таблицы в базе данных
        await conn.run_sync(Base.metadata.create_all)

# Функция для получения сессии
async def get_db():
    async with async_session() as session:
        yield session

# Функция добавления пользователя в базу данных (асинхронно)
async def add_user(db: AsyncSession, user_id: int, first_name: str, last_name: str, username: str, language_code: str):
    # Проверяем, существует ли пользователь в базе данных
    result = await db.execute(select(User).filter(User.user_id == user_id))
    existing_user = result.scalars().first()

    if existing_user:
        # Если пользователь уже существует, можно обновить его данные (если нужно)
        return existing_user

    # Если пользователь новый, добавляем его в базу данных
    db_user = User(
        user_id=user_id, 
        first_name=first_name, 
        last_name=last_name, 
        username=username, 
        language_code=language_code
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


# Функция для обновления записи пользователя, создание записи о принятии Политики и Оферты
async def update_user_acceptance(db: AsyncSession, user_id: int, policy_accepted: bool, offer_accepted: bool):
    # Ищем пользователя по user_id
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalars().first()

    if user:
        # Обновляем поля policy_accepted и offer_accepted
        user.policy_accepted = policy_accepted
        user.offer_accepted = offer_accepted
        await db.commit()
        await db.refresh(user)
        return user
    return None  # Если пользователь не найден


# Функция записи количества баллов и типа стратегии
async def update_strategy_type(db: AsyncSession, user_id: int, score: int, strategy_type: str):
    # Ищем пользователя по user_id
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalars().first()

    if user:
        # Обновляем поле strategy_type
        user.strategy_type = strategy_type
        user.score = score
        await db.commit()
        await db.refresh(user)
        return user
    return None  # Если пользователь не найден


# Функция записи, что пользователь скачал гайд
async def update_user_guide_downloaded(db: AsyncSession, user_id: int):
    # Проверяем, существует ли пользователь в базе данных
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalars().first()

    if user:
        # Обновляем поле guide_downloaded
        user.guide_downloaded = True
        await db.commit()
        await db.refresh(user)
        return user
    return None  # Если пользователь не найден


# Функция обновления последнего взаимодействия пользователя с ботом
async def update_last_interaction_date(db: AsyncSession, user_id: int):
    # Получаем пользователя по user_id
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalars().first()

    if user:
        # Обновляем поле last_interaction_date
        user.last_interaction_date = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        return user
    return None  # Если пользователь не найден


# Пример получения пользователя из базы данных (асинхронно)
async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalars().first()
    return user

# Пример работы с асинхронной сессией (для добавления пользователя и получения его данных)
async def example_usage():
    async for db in get_db():
        # Добавление пользователя
        user = await add_user(db, 1, 'John', 'Doe', 'john_doe', 'en')
        print(f"User added: {user.first_name} {user.last_name}")
        
        # Получение пользователя
        retrieved_user = await get_user(db, 1)
        print(f"User retrieved: {retrieved_user.first_name} {retrieved_user.last_name}")



# === Логика работы с вопросами и ответами ===


async def save_question_to_db(db, user_id, question_text):
    new_question = Question(user_id=user_id, question=question_text)
    db.add(new_question)
    await db.commit()
    await db.refresh(new_question)
    return new_question

async def get_question_by_id(db, question_id):
    return await db.execute(select(Question).filter(Question.id == question_id))

async def save_answer_to_db(db, parent_question_id, answer_text):
    new_answer = Question(parent_question_id=parent_question_id, answer=answer_text, answered=True)
    db.add(new_answer)
    await db.commit()
    await db.refresh(new_answer)
    return new_answer


async def get_questions_by_user(db, user_id):
    return await db.execute(select(Question).filter(Question.user_id == user_id))


async def get_answers_for_question(db, question_id):
    return await db.execute(select(Question).filter(Question.parent_question_id == question_id))


# === Логика работы со статистикой бота ===

# Функция получения общей статистики по боту
async def get_bot_statistics(db):
    result = await db.execute(
        select(
            func.count().label("total_users"),  # Общее количество пользователей
            func.count().filter(
                (User.policy_accepted == 1) & (User.offer_accepted == 1)
            ).label("policy_accepted"),  # Сколько приняли политику и офферту
            func.count().filter(
                (User.score > 0) & (User.strategy_type.isnot(None))
            ).label("test_passed"),  # Сколько прошли тест
            func.count().filter(User.guide_downloaded == 1).label("guide_downloaded")  # Сколько скачали гайд
        ).select_from(User)  # Запрос на таблицу пользователей
    )

    stats = result.fetchone()  # Получаем результат запроса
    return {
        "total_users": stats[0],  # Общее количество пользователей
        "policy_accepted": stats[1],  # Сколько приняли политику и офферту
        "test_passed": stats[2],  # Сколько прошли тест
        "guide_downloaded": stats[3],  # Сколько скачали гайд
    }


# Функция получения данных о пользователе
async def get_user_info_by_username(db, username: str):
    # Запрос к базе данных для получения информации о пользователе
    result = await db.execute(
        select(
            User.first_name,
            User.last_name,
            User.registration_date,
            User.strategy_type,
            User.score,
            User.guide_downloaded
        ).where(func.lower(User.username) == func.lower(username))
    )

    user_info = result.fetchone()  # Получаем первый результат

    if user_info:
        return {
            "first_name": user_info[0],
            "last_name": user_info[1],
            "registration_date": user_info[2],
            "strategy_type": user_info[3],
            "score": user_info[4],
            "guide_downloaded": user_info[5]
        }
    return None  # Если пользователь не найден





# Для проверки работы базы данных на старте
if __name__ == "__main__":
    asyncio.run(create_tables())  # Создаем таблицы
    asyncio.run(example_usage())  # Пример работы с базой данных
