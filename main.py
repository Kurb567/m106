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

def parse_telegram_field(value) -> int | str | None:
    """
    Преобразует значение из Marzban в правильный формат для отправки:
    - Если число (строка или int) → возвращает int (chat_id)
    - Если юзернейм (строка с буквами) → возвращает строку с @
    - Если пусто → None
    """
    if value is None:
        return None
    
    value_str = str(value).strip().lstrip('@')
    if not value_str:
        return None
    
    # Если всё символы цифровые — это chat_id
    if value_str.isdigit():
        return int(value_str)
    
    # Иначе считаем это юзернеймом
    return f"@{value_str}"

async def get_telegram_targets() -> list[int | str]:
    """Получение списка chat_id / username из Marzban"""
    api = MarzbanAPI(base_url=config.MARZBAN_URL)
    
    try:
        logger.info("🔐 Авторизация в Marzban...")
        token_obj = await api.get_token(
            username=config.MARZBAN_USER,
            password=config.MARZBAN_PASS
        )
        token = token_obj.access_token
        logger.info("✅ Токен получен")
        
        targets: list[int | str] = []
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
                
                # Пробуем разные названия полей
                tg_value = (
                    user_dict.get("telegram_id") or 
                    user_dict.get("telegram") or 
                    user_dict.get("telegram_username") or
                    user_dict.get("tg_id")
                )
                
                parsed = parse_telegram_field(tg_value)
                if parsed is not None:
                    targets.append(parsed)
            
            logger.info(f"📦 Страница: {len(users)} юзеров (найдено: {len(targets)} из {response.total})")
            if len(users) < limit:
                break
            offset += limit
            await asyncio.sleep(0.2)
        
        return targets
        
    except Exception as e:
        logger.error(f"❌ Ошибка Marzban: {type(e).__name__}: {e}")
        raise
    finally:
        await api.close()

async def send_broadcast(targets: list[int | str]):
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Файл {config.PHOTO_PATH} не найден!")
        return

    photo = FSInputFile(config.PHOTO_PATH)
    total = len(targets)
    success = failed = not_found = 0

    logger.info(f"🚀 Старт рассылки. Всего: {total} получателей")

    for i, target in enumerate(targets, 1):
        # Для лога: красиво отображаем куда отправляем
        target_display = f"@{target}" if isinstance(target, str) else target
        print(target)
        try:
            await bot.send_photo(chat_id=target, photo=photo, caption=config.CAPTION)
            success += 1
            logger.info(f"[{i}/{total}] ✓ Отправлено {target_display}")
            
        except TelegramForbiddenError:
            failed += 1
            logger.warning(f"[{i}/{total}] ⚠ {target_display} заблокировал бота")
            
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "chat not found" in err or "user not found" in err or "peer id invalid" in err:
                not_found += 1
                logger.warning(f"[{i}/{total}] ❓ {target_display} — пользователь не запускал бота")
            else:
                failed += 1
                logger.error(f"[{i}/{total}] ✗ {target_display}: {e}")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{i}/{total}] ✗ {target_display}: {type(e).__name__}: {e}")
        
        await asyncio.sleep(0.05)  # защита от лимитов

    logger.info(f"\n📊 Итоги:\n   ✓ Успешно: {success}\n   ⚠ Заблокировали: {failed}\n   ❓ Не запускали бота: {not_found}")
    if not_found > 0:
        logger.info("💡 Чтобы получать рассылку — пользователи должны нажать /start в боте!")

async def main():
    try:
        targets = await get_telegram_targets()
        if not targets:
            logger.warning("⚠ Не найдено ни одного Telegram-контакта в Marzban!")
            return
        await send_broadcast(targets)
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка: {type(e).__name__}: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())