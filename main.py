# broadcast.py
import asyncio
import logging
import os
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest
import httpx
import config

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)

async def get_marzban_token(client: httpx.AsyncClient) -> str:
    """Получение токена администратора Marzban"""
    url = f"{config.MARZBAN_URL}/api/admins/token"
    data = {
        "username": config.MARZBAN_USER,
        "password": config.MARZBAN_PASS
    }
    try:
        response = await client.post(url, data=data)
        response.raise_for_status()
        token = response.json().get("access_token")
        logger.info("Токен Marzban получен успешно.")
        return token
    except Exception as e:
        logger.error(f"Ошибка получения токена Marzban: {e}")
        raise

async def get_marzban_users(client: httpx.AsyncClient, token: str) -> list:
    """Получение списка пользователей с telegram_id из Marzban"""
    url = f"{config.MARZBAN_URL}/api/users"
    headers = {"Authorization": f"Bearer {token}"}
    
    all_users = []
    offset = 0
    limit = 100  # Лимит за один запрос
    
    logger.info("Загрузка пользователей из Marzban...")
    
    while True:
        try:
            params = {"offset": offset, "limit": limit}
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            users_list = data.get("users", [])
            if not users_list:
                break
                
            # Фильтруем только тех, у кого есть telegram_id
            for user in users_list:
                tg_id = user.get("telegram_id")
                if tg_id:
                    all_users.append(tg_id)
            
            logger.info(f"Получено {len(users_list)} пользователей со страницы (всего найдено с TG: {len(all_users)})")
            
            if len(users_list) < limit:
                break
            
            offset += limit
            await asyncio.sleep(0.5) # Небольшая пауза между запросами к API
            
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей: {e}")
            break
            
    return all_users

async def send_broadcast(user_ids: list):
    """Отправка фото всем пользователям"""
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"Файл {config.PHOTO_PATH} не найден!")
        return

    photo = FSInputFile(config.PHOTO_PATH)
    total = len(user_ids)
    success_count = 0
    fail_count = 0

    logger.info(f"Начало рассылки. Всего пользователей: {total}")

    for i, user_id in enumerate(user_ids):
        try:
            await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=config.CAPTION
            )
            success_count += 1
            logger.info(f"[{i+1}/{total}] Отправлено пользователю {user_id}")
        except TelegramBadRequest as e:
            fail_count += 1
            # 403 Forbidden means user blocked the bot
            if "Forbidden" in str(e):
                logger.warning(f"Пользователь {user_id} заблокировал бота.")
            else:
                logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
        except Exception as e:
            fail_count += 1
            logger.error(f"Неизвестная ошибка для {user_id}: {e}")
        
        # Задержка чтобы не упереться в лимиты Telegram (30 сообщений в сек)
        # 0.05 сек задержки достаточно для безопасности
        await asyncio.sleep(0.05)

    logger.info(f"Рассылка завершена. Успешно: {success_count}, Ошибки/Блоки: {fail_count}")

async def main():
    async with httpx.AsyncClient() as client:
        try:
            # 1. Авторизация в Marzban
            token = await get_marzban_token(client)
            
            # 2. Получение пользователей
            user_ids = await get_marzban_users(client, token)
            
            if not user_ids:
                logger.warning("Список пользователей пуст. Никому нечего отправлять.")
                return

            # 3. Рассылка
            await send_broadcast(user_ids)
            
        except Exception as e:
            logger.critical(f"Критическая ошибка в главном цикле: {e}")
        finally:
            await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())