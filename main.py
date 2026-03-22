# broadcast.py — исправленная версия для username
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

async def get_telegram_usernames() -> list[str]:
    """Получение всех telegram_username из Marzban"""
    api = MarzbanAPI(base_url=config.MARZBAN_URL)
    
    try:
        logger.info("🔐 Авторизация в Marzban...")
        token_obj = await api.get_token(
            username=config.MARZBAN_USER,
            password=config.MARZBAN_PASS
        )
        token = token_obj.access_token
        logger.info("✅ Токен получен")
        
        usernames: list[str] = []
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
                # Ищем поле с юзернеймом (может называться по-разному)
                tg_user = (
                    user_dict.get("telegram_username") or 
                    user_dict.get("telegram") or 
                    user_dict.get("tg_username") or
                    user_dict.get("username")  # осторожно: это может быть логин Marzban
                )
                if tg_user and isinstance(tg_user, str) and tg_user.strip():
                    # Убираем @ если есть, добавим потом
                    clean = tg_user.strip().lstrip('@')
                    if clean:  # не пустой
                        usernames.append(clean)
            
            logger.info(f"📦 Страница: {len(users)} юзеров (найдено юзернеймов: {len(usernames)} из {response.total})")
            if len(users) < limit:
                break
            offset += limit
            await asyncio.sleep(0.2)
        
        return usernames
        
    except Exception as e:
        logger.error(f"❌ Ошибка Marzban: {type(e).__name__}: {e}")
        raise
    finally:
        await api.close()

async def send_broadcast(usernames: list[str]):
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Файл {config.PHOTO_PATH} не найден!")
        return

    photo = FSInputFile(config.PHOTO_PATH)
    total = len(usernames)
    success = failed = skipped = 0

    logger.info(f"🚀 Старт рассылки. Всего: {total} юзернеймов")

    for i, username in enumerate(usernames, 1):
        chat_id = f"@{username}"  # формат для отправки
        
        try:
            await bot.send_photo(chat_id=chat_id, photo=photo, caption=config.CAPTION)
            success += 1
            logger.info(f"[{i}/{total}] ✓ Отправлено @{username}")
            
        except TelegramForbiddenError:
            failed += 1
            logger.warning(f"[{i}/{total}] ⚠ @{username} заблокировал бота или бот не знает этого пользователя")
            
        except TelegramBadRequest as e:
            failed += 1
            err = str(e).lower()
            if "chat not found" in err or "user not found" in err:
                skipped += 1
                logger.warning(f"[{i}/{total}] ❓ @{username} — бот не может найти этот чат (пользователь не запускал бота)")
            else:
                logger.error(f"[{i}/{total}] ✗ @{username}: {e}")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{total}] ✗ @{username}: {type(e).__name__}: {e}")
        
        await asyncio.sleep(0.05)

    logger.info(f"\n📊 Итоги:\n   ✓ Успешно: {success}\n   ⚠ Не доставлено: {failed}\n   ❓ Не найдено в боте: {skipped}")
    if skipped > 0:
        logger.info("💡 Чтобы рассылка работала — пользователи должны нажать /start в боте!")

async def main():
    try:
        usernames = await get_telegram_usernames()
        if not usernames:
            logger.warning("⚠ Не найдено ни одного Telegram-юзернейма в Marzban!")
            return
        await send_broadcast(usernames)
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {type(e).__name__}: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())