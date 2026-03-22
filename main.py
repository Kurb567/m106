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
    api = MarzbanAPI(base_url=config.MARZBAN_URL)
    
    try:
        logger.info("🔐 Авторизация в Marzban...")
        token_obj = await api.get_token(
            username=config.MARZBAN_USER,
            password=config.MARZBAN_PASS
        )
        token = token_obj.access_token
        logger.info("✅ Токен получен")
        
        telegram_ids: list[int] = []
        offset = 0
        limit = 100
        
        logger.info("👥 Загрузка пользователей...")
        
        while True:
            response = await api.get_users(token=token, offset=offset, limit=limit)
            users = response.users
            if not users:
                break
                
            for user in users:
                user_dict = user.model_dump()
                # Пробуем разные варианты названия поля
                tg_id = (
                    user_dict.get("telegram_id") or 
                    user_dict.get("telegram") or 
                    user_dict.get("tg_id")
                )
                if tg_id is not None:
                    telegram_ids.append(int(tg_id))
            
            logger.info(f"📦 Страница: {len(users)} юзеров (всего с TG: {len(telegram_ids)} из {response.total})")
            if len(users) < limit:
                break
            offset += limit
            await asyncio.sleep(0.2)
        
        return telegram_ids
        
    except Exception as e:
        logger.error(f"❌ Ошибка Marzban: {type(e).__name__}: {e}")
        raise
    finally:
        await api.close()

async def send_broadcast(user_ids: list[int]):
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Файл {config.PHOTO_PATH} не найден!")
        return

    photo = FSInputFile(config.PHOTO_PATH)
    total = len(user_ids)
    success = failed = 0

    logger.info(f"🚀 Старт рассылки. Всего: {total} пользователей")

    for i, user_id in enumerate(user_ids, 1):
        try:
            await bot.send_photo(chat_id=user_id, photo=photo, caption=config.CAPTION)
            success += 1
            logger.info(f"[{i}/{total}] ✓ {user_id}")
        except TelegramBadRequest as e:
            failed += 1
            if "forbidden" in str(e).lower() or "blocked" in str(e).lower():
                logger.warning(f"[{i}/{total}] ⚠ Заблокировал: {user_id}")
            else:
                logger.error(f"[{i}/{total}] ✗ {e}")
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{total}] ✗ {type(e).__name__}: {e}")
        await asyncio.sleep(0.05)  # защита от лимитов Telegram

    logger.info(f"\n✅ Готово! Успешно: {success} | Ошибки: {failed}")

async def main():
    try:
        user_ids = await get_telegram_users()
        if not user_ids:
            logger.warning("⚠ Пустой список. Пользователи должны привязать Telegram в Marzban!")
            return
        await send_broadcast(user_ids)
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {type(e).__name__}: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())