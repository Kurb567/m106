# send_to_users.py
import asyncio
import logging
import os
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)

def read_chat_ids(filename: str) -> list[int]:
    """Читает chat_id из файла (по одному на строке)"""
    ids = []
    if not os.path.exists(filename):
        logger.error(f"❌ Файл {filename} не найден!")
        return ids
    
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    # Убираем @ если есть, конвертируем в int
                    clean_id = line.lstrip("@")
                    ids.append(int(clean_id))
                except ValueError:
                    logger.warning(f"⚠ Пропущено некорректное значение: {line}")
    
    logger.info(f"📋 Прочитано {len(ids)} chat_id из {filename}")
    return ids

async def send_photo_to_users(chat_ids: list[int]):
    """Отправка фото всем пользователям из списка"""
    
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Фото {config.PHOTO_PATH} не найдено!")
        return
    
    photo = FSInputFile(config.PHOTO_PATH)
    total = len(chat_ids)
    success = failed = blocked = 0
    
    logger.info(f"🚀 Начало рассылки. Всего: {total} получателей")
    
    for i, chat_id in enumerate(chat_ids, 1):
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=config.CAPTION
            )
            success += 1
            logger.info(f"[{i}/{total}] ✓ Отправлено {chat_id}")
            
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "forbidden" in err or "blocked" in err:
                blocked += 1
                logger.warning(f"[{i}/{total}] ⚠ Заблокировал: {chat_id}")
            elif "chat not found" in err or "peer id invalid" in err:
                failed += 1
                logger.warning(f"[{i}/{total}] ❓ Не найден: {chat_id}")
            else:
                failed += 1
                logger.error(f"[{i}/{total}] ✗ Ошибка: {e}")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{total}] ✗ {type(e).__name__}: {e}")
        
        # Задержка чтобы не упереться в лимиты Telegram (~30 msg/sec)
        await asyncio.sleep(0.05)
    
    logger.info(f"\n📊 ИТОГИ:\n✅ Успешно: {success}\n⚠ Заблокировали: {blocked}\n❌ Ошибки: {failed}")

async def main():
    try:
        chat_ids = read_chat_ids(config.IDS_FILE)
        
        if not chat_ids:
            logger.warning("⚠ Список пуст. Нечего отправлять.")
            return
        
        await send_photo_to_users(chat_ids)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("🔚 Сессия бота закрыта")

if __name__ == "__main__":
    asyncio.run(main())