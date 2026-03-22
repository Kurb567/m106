# broadcast.py
import asyncio
import logging
import os
import httpx
from aiogram import Bot
from aiogram.types import FSInputFile
import config
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)

async def get_marzban_token(client: httpx.AsyncClient) -> str:
    """Получаем токен админа"""
    url = f"{config.MARZBAN_URL}/api/admin/token"
    r = await client.post(url, data={
        "username": config.MARZBAN_USER,
        "password": config.MARZBAN_PASS
    })
    r.raise_for_status()
    return r.json()["access_token"]

async def get_telegram_ids(token: str) -> list[int]:
    """Получаем список числовых Telegram ID"""
    url = f"{config.MARZBAN_URL}/api/users"
    headers = {"Authorization": f"Bearer {token}"}
    
    ids = []
    offset = 0
    limit = 100
    
    async with httpx.AsyncClient() as client:
        while True:
            r = await client.get(url, headers=headers, params={"offset": offset, "limit": limit})
            r.raise_for_status()
            data = r.json()
            users = data.get("users", [])
            
            if not users:
                break
                
            for u in users:
                # 🔍 Пытаемся найти ID во всех возможных полях
                tg = (
                    u.get("telegram_id") or 
                    u.get("telegram") or 
                    u.get("tg_id") or
                    (u.get("links") or {}).get("telegram")
                )
                if tg:
                    try:
                        ids.append(int(str(tg).strip().lstrip("@")))
                    except:
                        pass  # пропускаем если не число
            
            logger.info(f"Обработано: {offset + len(users)} / {data.get('total', '?')} (найдено ID: {len(ids)})")
            
            if len(users) < limit:
                break
            offset += limit
            await asyncio.sleep(0.3)
    
    return ids

async def send_photo_to_users(chat_ids: list[int]):
    """Рассылка фото"""
    if not os.path.exists(config.PHOTO_PATH):
        logger.error(f"❌ Файл {config.PHOTO_PATH} не найден!")
        return
    
    photo = FSInputFile(config.PHOTO_PATH)
    total = len(chat_ids)
    ok = fail = no_start = 0
    
    logger.info(f"🚀 Начинаю рассылку: {total} получателей")
    
    for i, cid in enumerate(chat_ids, 1):
        try:
            await bot.send_photo(chat_id=cid, photo=photo, caption=config.CAPTION)
            ok += 1
            logger.info(f"[{i}/{total}] ✓ {cid}")
        except Exception as e:
            err = str(e).lower()
            if "forbidden" in err or "blocked" in err:
                fail += 1
                logger.warning(f"[{i}/{total}] ⚠ Заблокировал: {cid}")
            elif "chat not found" in err or "peer id invalid" in err:
                no_start += 1
                logger.warning(f"[{i}/{total}] ❓ Не запускал бота: {cid}")
            else:
                fail += 1
                logger.error(f"[{i}/{total}] ✗ {cid}: {e}")
        await asyncio.sleep(0.05)  # чтобы не забанили
    
    logger.info(f"\n📊 ГОТОВО:\n✅ {ok}\n⚠ {fail}\n❓ {no_start}")
    if no_start > 0:
        logger.info("💡 Чтобы получать сообщения — пользователи должны нажать /start в боте!")

async def main():
    try:
        async with httpx.AsyncClient() as client:
            token = await get_marzban_token(client)
            logger.info("✅ Токен получен")
            
            chat_ids = await get_telegram_ids(token)
            
            if not chat_ids:
                logger.warning("⚠ Не найдено ни одного Telegram ID!")
                logger.info("💡 Проверь: пользователи должны привязать Telegram в панели Marzban")
                return
                
            await send_photo_to_users(chat_ids)
    except Exception as e:
        logger.error(f"💥 Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    import config  # импорт после настройки логгера
    asyncio.run(main())