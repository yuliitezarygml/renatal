#!/usr/bin/env python3
"""
Основной файл для запуска системы аренды PlayStation консолей
"""

import threading
import time
from app import app
from bot import bot
from init_admin import init_admin, init_data_files, init_passport_dir

def run_flask():
    """Запуск Flask приложения"""
    print("🌐 Запуск Flask приложения на http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)

def run_bot():
    """Запуск Telegram бота"""
    print("🤖 Запуск Telegram бота...")
    try:
        bot.polling(none_stop=True, interval=0, timeout=20)
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")
        time.sleep(5)
        run_bot()

if __name__ == '__main__':
    print("🎮 Запуск системы аренды PlayStation консолей...")
    print("=" * 50)
    
    # Инициализация при первом запуске
    print("🔧 Инициализация системы...")
    init_data_files()
    init_passport_dir()
    init_admin()
    print("✅ Инициализация завершена")
    print()
    
    try:
        # Запуск Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Небольшая задержка для запуска Flask
        time.sleep(2)
        
        # Запуск Telegram бота в основном потоке
        run_bot()
        
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал завершения...")
        print("👋 Система остановлена")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")