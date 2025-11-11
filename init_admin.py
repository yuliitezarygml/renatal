#!/usr/bin/env python3
"""
Скрипт инициализации администратора при первом запуске
"""

import os
import json
from datetime import datetime
from database import get_db_manager

def init_admin():
    """Создает администратора по умолчанию если его нет"""
    
    db = get_db_manager()
    
    try:
        # Получаем всех администраторов
        admins = db.get_admins()
        
        if admins:
            print("👤 Администраторы уже существуют")
            return
        
        # Создаем администратора по умолчанию
        default_admin = {
            "username": "admin", 
            "password": "admin123",
            "role": "admin",
            "created_at": datetime.now().isoformat(),
            "created_by": "system"
        }
        
        db.save_admin(default_admin)
        
        print("👤 Создан администратор по умолчанию:")
        print("   Логин: admin")
        print("   Пароль: admin123")
        print("⚠️ ОБЯЗАТЕЛЬНО смените пароль после первого входа!")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации администратора: {e}")

def init_data_files():
    """Инициализирует коллекции в MongoDB"""
    
    db = get_db_manager()
    
    # Создаем пустые коллекции если их нет
    collections = [
        'consoles',
        'users',
        'rentals',
        'rental_requests',
        'admin_settings',
        'discounts',
        'calendar',
        'ratings'
    ]
    
    for collection_name in collections:
        try:
            collection = db.db[collection_name]
            # Проверяем, пуста ли коллекция
            if collection.count_documents({}) == 0:
                print(f"📦 Инициализирована коллекция: {collection_name}")
            else:
                print(f"✓ Коллекция {collection_name} уже содержит данные")
        except Exception as e:
            print(f"⚠️ Ошибка инициализации коллекции {collection_name}: {e}")

def init_passport_dir():
    """Создает папку для документов"""
    passport_dir = 'passport'
    if not os.path.exists(passport_dir):
        os.makedirs(passport_dir)
        print(f"📁 Создана папка {passport_dir}")

if __name__ == "__main__":
    print("🚀 Инициализация проекта...")
    print("🔌 Подключение к MongoDB...")
    
    # Инициализация
    init_data_files()
    init_passport_dir() 
    init_admin()
    
    print("✅ Инициализация завершена!")
    print("🌐 Запустите проект: python run.py")
    print("🌍 Веб-панель: http://0.0.0.0:5000")