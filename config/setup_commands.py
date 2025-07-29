from aiogram import types
from aiogram.types import BotCommand
from config.config import ADMIN_IDS


# Функция для установки команд бота
async def set_bot_commands(bot, user_id):
    commands = [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="help", description="Помощь")
    ]
    
    # Проверяем, является ли пользователь администратором
    if user_id in ADMIN_IDS:
        # Если это администратор, добавляем дополнительные команды
        commands.append(BotCommand(command="admin", description="Админ-панель"))
    
    await bot.set_my_commands(commands)
