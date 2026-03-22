# broadcast.py
import asyncio
import logging
import os
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from marzban import MarzbanAPI
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)

async def get_telegram_chats() -> list:
    """Получение списка chat_id из Marzban"""
    api = MarzbanAPI(base_url=config.MARZBAN_URL)
    
    try:
        logger.info("🔐 Авторизация в Marzban...")
        token_obj = await api.get_token(
            username=config.MARZBAN_USER,
            password=config.MARZBAN_PASS
        )
        token = token_obj.access_token
        logger.info("✅ Токен получен")
        
        chats = []
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
                
                # Ищем поле с Telegram ID
                tg_value = (
                    user_dict.get("telegram_id") or 
                    user_dict.get("telegram") or 
                    user_dict.get("tg_id")
                )
                
                if tg_value is not None:
                    # Конвертируем в int (убираем @ и пробелы если есть)
                    try:
                        chat_id = int(str(tg_value).strip().lstrip('@'))
                        chats.append(chat_id)
                    except (ValueError, TypeError):
                        # Если не число — пропускаем (это username, а не ID)
                        pass
            
            logger.info(f"📦 Страница: {len(users)} (найдено ID: {len(chats)} из {response.total})")
            if len(users) < limit:
                break
            offset += limit
            await asyncio.sleep(0.2)
        
        return chats
        
    except Exception as e:
        logger.error(f"❌ Ошибка Marzban: {type(e).__name__}: {e}")
        raise
    finally:
        await api.close()

async def send_broadcast(chat_ids: list[int]):
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Файл {config.PHOTO_PATH} не найден!")
        return

    photo = FSInputFile(config.PHOTO_PATH)
    total = len(chat_ids)
    success = failed = not_started = 0

    logger.info(f"🚀 Старт рассылки. Всего: {total} пользователей")

    for i, chat_id in enumerate(chat_ids, 1):
        try:
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=config.CAPTION)
            success += 1
            logger.info(f"[{i}/{total}] ✓ Отправлено {chat_id}")
            
        except TelegramForbiddenError:
            failed += 1
            logger.warning(f"[{i}/{total}] ⚠ Заблокировал: {chat_id}")
            
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "chat not found" in err or "peer id invalid" in err:
                not_started += 1
                logger.warning(f"[{i}/{total}] ❓ Не запускал бота: {chat_id}")
            else:
                failed += 1
                logger.error(f"[{i}/{total}] ✗ Ошибка: {e}")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{total}] ✗ {type(e).__name__}: {e}")
        
        await asyncio.sleep(0.05)  # защита от лимитов Telegram

    logger.info(f"\n📊 ИТОГИ:\n   ✅ Успешно: {success}\n   ⚠ Заблокировали: {failed}\n   ❓ Не запускали бота: {not_started}")
    
    if not_started > 0:
        logger.info("\n💡 ВАЖНО: Пользователи должны нажать /start в боте, чтобы получать сообщения!")
        logger.info("   Это ограничение Telegram, а не ошибка скрипта.\n")

async def main():
    try:
        chat_ids = await get_telegram_chats()
        if not chat_ids:
            logger.warning("⚠ Не найдено ни одного Telegram ID в Marzban!")
            return
        await send_broadcast(chat_ids)
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {type(e).__name__}: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())