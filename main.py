import asyncio
import logging
from aiogram import Bot
from aiogram.types import FSInputFile
from aiomarzban import MarzbanAPI

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8557116313:AAEqp_YBnxLfXZX9VVP5Dtg5XtRZFvIySgw"
MARZBAN_URL = "https://ctjkk.duckdns.org:8000/"
MARZBAN_USER = "admin"
MARZBAN_PASS = "56731096842"
PHOTO_PATH = "1.jpg"  # Путь к файлу фото
CAPTION = "Уважаемые пользователи! обновите подписку как показано на фото для корректной работы"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)

async def start_broadcast():
    # 1. Подключаемся к Marzban
    marzban = MarzbanAPI(
        address=MARZBAN_URL,
        username=MARZBAN_USER,
        password=MARZBAN_PASS
    )
    
    try:
        # 2. Получаем список всех пользователей
        # Можно настроить limit, если пользователей очень много
        users_data = await marzban.get_users(offset=0, limit=500)
        users = users_data.get("users", [])
        
        logging.info(f"Найдено пользователей в Marzban: {len(users)}")
        
        count = 0
        photo = FSInputFile(PHOTO_PATH)

        # 3. Цикл рассылки
        for user in users:
            user_id = user.get("username") # В Marzban ID часто в этом поле
            
            # Проверяем, является ли username числом (ID Telegram)
            if not str(user_id).isdigit():
                continue
                
            try:
                await bot.send_photo(chat_id=user_id, photo=photo, caption=CAPTION)
                count += 1
                logging.info(f"Отправлено пользователю: {user_id}")
                
                # Небольшая пауза, чтобы не поймать лимиты Telegram
                await asyncio.sleep(0.05) 
            except Exception as e:
                logging.error(f"Ошибка при отправке {user_id}: {e}")

        logging.info(f"Рассылка завершена. Успешно отправлено: {count}")

    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(start_broadcast())
