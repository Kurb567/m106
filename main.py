import asyncio
import httpx
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile

# ================= КОНФИГУРАЦИЯ =================
CONFIG = {
    # Данные от вашей панели Marzban
    "marzban_url": "https://ctjkk.duckdns.org:8000",  # Ссылка на панель (без слэша в конце)
    "marzban_username": "admin",               # Логин админа Marzban
    "marzban_password": "56731096842",       # Пароль админа Marzban

    # Данные от Telegram бота
    "bot_token": "8557116313:AAEqp_YBnxLfXZX9VVP5Dtg5XtRZFvIySgw",
    
    # Путь к фото (локальный файл) или URL картинки
    # Если локальный: "photo.jpg"
    # Если ссылка: "https://example.com/image.jpg"
    "photo_path": "1.jpg", 
    
    # Текст сообщения под фото
    "caption": "Уважаемый пользователь! Перезагрузите вашу подписку как показано на фото для корректной работы серверов"
}
# ==================================================

async def get_marzban_token(client: httpx.AsyncClient):
    """Получает токен доступа к API Marzban"""
    url = f"{CONFIG['marzban_url']}/api/admin/token"
    data = {
        "username": CONFIG['marzban_username'],
        "password": CONFIG['marzban_password']
    }
    
    try:
        response = await client.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"❌ Ошибка авторизации в Marzban: {e}")
        return None

async def get_users_list(client: httpx.AsyncClient, token: str):
    """Получает список всех пользователей из Marzban"""
    url = f"{CONFIG['marzban_url']}/api/users"
    headers = {"Authorization": f"Bearer {token}"}
    
    all_users = []
    offset = 0
    limit = 100 # Marzban обычно отдает по 100 за раз

    while True:
        params = {"offset": offset, "limit": limit}
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            users = data.get("users", [])
            if not users:
                break
            
            all_users.extend(users)
            
            # Если пользователей меньше лимита, значит это последняя страница
            if len(users) < limit:
                break
            
            offset += limit
        except Exception as e:
            print(f"❌ Ошибка получения пользователей: {e}")
            break
            
    return all_users

async def main():
    # Инициализация бота и HTTP клиента
    bot = Bot(token=CONFIG['bot_token'])
    async with httpx.AsyncClient() as client:
        
        print("🔄 Авторизация в Marzban...")
        token = await get_marzban_token(client)
        if not token:
            return

        print("🔄 Получение списка пользователей...")
        users = await get_users_list(client, token)
        print(f"✅ Найдено пользователей: {len(users)}")

        success_count = 0
        fail_count = 0

        print("🚀 Начало рассылки...")

        for user in users:
            # В Marzban поле с Telegram ID называется 'telegram_id'
            # Если вы храните ID в поле 'username' (что нестандартно), замените user['telegram_id'] на user['username']
            chat_id = user.get('username')
            username = user.get('') # Имя пользователя в панели (для логов)

            if not chat_id:
                # Если у пользователя не привязан телеграм аккаунт
                continue
            try:
                # Создаём объект файла для отправки
                photo_file = FSInputFile(CONFIG['photo_path'])
                
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_file,  # <--- Передаём объект FSInputFile
                    caption=CONFIG['caption']
                )
                print(f"✅ Отправлено: {chat_id}")
                success_count += 1
                await asyncio.sleep(0.05)        
            except TelegramBadRequest as e:
                # Частые ошибки: бот заблокирован или пользователь не запускал бота
                if "bot was blocked" in str(e) or "chat not found" in str(e):
                    print(f"⚠️ Не удалось отправить {username}: Бот заблокирован или не запущен пользователем.")
                else:
                    print(f"⚠️ Ошибка отправки {username}: {e}")
                fail_count += 1
            except Exception as e:
                print(f"❌ Критическая ошибка для {username}: {e}")
                fail_count += 1

    print(f"\n🏁 Рассылка завершена.\nУспешно: {success_count}\nНеудачно: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())