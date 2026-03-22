# broadcast.py
import asyncio
import logging
import os
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest
from marzban import MarzbanAPI
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)

async def get_telegram_users() -> list[int]:
    """Получение всех telegram_id из Marzban через библиотеку marzban"""
    
    # Инициализация клиента (библиотека сама очистит URL от лишних слэшей)
    api = MarzbanAPI(base_url=config.MARZBAN_URL)
    
    try:
        # Авторизация
        logger.info("Авторизация в Marzban...")
        token_obj = await api.get_token(
            username=config.MARZBAN_USER,
            password=config.MARZBAN_PASS
        )
        token = token_obj.access_token
        logger.info("✓ Токен получен")
        
        # Получение пользователей с пагинацией
        telegram_ids = []
        offset = 0
        limit = 100
        
        logger.info("Загрузка пользователей...")
        
        while True:
            response = await api.get_users(
                token=token,
                offset=offset,
                limit=limit
            )
            
            users = response.get("users", [])
            if not users:
                break
                
            # Фильтруем пользователей с telegram_id
            for user in users:
                tg_id = user.get("telegram_id")
                if tg_id:
                    telegram_ids.append(tg_id)
            
            logger.info(f"Получено {len(users)} пользователей (всего с TG: {len(telegram_ids)})")
            
            if len(users) < limit:
                break
                
            offset += limit
            await asyncio.sleep(0.2)  # Пауза между запросами
        
        return telegram_ids
        
    except Exception as e:
        logger.error(f"Ошибка работы с Marzban: {e}")
        raise
    finally:
        await api.close()

async def send_broadcast(user_ids: list[int]):
    """Отправка фото всем пользователям"""
    
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Файл {config.PHOTO_PATH} не найден!")
        return

    photo = FSInputFile(config.PHOTO_PATH)
    total = len(user_ids)
    success = 0
    failed = 0

    logger.info(f"🚀 Начало рассылки. Всего: {total} пользователей")

    for i, user_id in enumerate(user_ids, 1):
        try:
            await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=config.CAPTION
            )
            success += 1
            logger.info(f"[{i}/{total}] ✓ Отправлено пользователю {user_id}")
            
        except TelegramBadRequest as e:
            failed += 1
            if "Forbidden" in str(e) or "bot was blocked" in str(e).lower():
                logger.warning(f"[{i}/{total}] ⚠ Пользователь {user_id} заблокировал бота")
            else:
                logger.error(f"[{i}/{total}] ✗ Ошибка: {e}")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{total}] ✗ Неизвестная ошибка: {e}")
        
        # Задержка для соблюдения лимитов Telegram (~30 msg/sec)
        await asyncio.sleep(0.05)

    logger.info(f"\n✅ Рассылка завершена!\n   Успешно: {success}\n   Ошибки/блоки: {failed}")

async def main():
    try:
        # 1. Получаем список Telegram ID
        user_ids = await get_telegram_users()
        
        if not user_ids:
            logger.warning("⚠ Список пользователей пуст. Никому нечего отправлять.")
            logger.info("💡 Убедитесь, что пользователи привязали Telegram в панели Marzban")
            return
            
        # 2. Отправляем рассылку
        await send_broadcast(user_ids)
        
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {e}")
    finally:
        await bot.session.close()
        logger.info("🔚 Сессия бота закрыта")

if __name__ == "__main__":
    asyncio.run(main())