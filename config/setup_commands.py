from aiogram.types import BotCommand

# Функция для установки команд бота
async def set_bot_commands(bot):
    commands = [
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="settings", description="Настройки")
    ]
    await bot.set_my_commands(commands)
