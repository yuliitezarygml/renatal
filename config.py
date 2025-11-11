import os
import secrets
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7748694745:AAHgBJrLvE5uCqK7GzrAMuTYLMk8HBKolvU')

# Admin Configuration
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID', '762139684')

# Flask Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Генерируем случайный ключ если используется дефолтный
if SECRET_KEY == 'your-secret-key-here':
    SECRET_KEY = secrets.token_hex(32)
    print("⚠️ Используется автоматически сгенерированный SECRET_KEY. Установите свой в переменных окружения.")

# MongoDB Configuration
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('DB_NAME', 'ps4_rental')

print(f"🔗 MongoDB URL: {MONGO_URL}")
print(f"📦 Database: {DB_NAME}")

