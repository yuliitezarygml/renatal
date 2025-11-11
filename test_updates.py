#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы обновлений
"""

import json
from update_manager import UpdateManager

def test_update_system():
    """Тестирует систему обновлений"""
    
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ ОБНОВЛЕНИЙ")
    print("=" * 60)
    
    # Инициализируем менеджер обновлений
    manager = UpdateManager()
    
    # 1. Проверяем текущую версию
    print("\n1️⃣ Текущая версия:")
    current_version = manager.get_current_version()
    print(f"   ✓ Версия: {current_version}")
    
    # 2. Проверяем обновления с GitHub
    print("\n2️⃣ Проверка обновлений на GitHub...")
    result = manager.check_for_updates()
    
    print(f"   ✓ Обновление доступно: {result.get('update_available')}")
    print(f"   ✓ GitHub версия: {result.get('github_version')}")
    
    if result.get('github_version'):
        print(f"   ✓ Changelog: {result.get('changelog', 'N/A')[:100]}...")
    
    # 3. Проверяем версию в файле
    print("\n3️⃣ Проверка версии в version.json:")
    with open('version.json', 'r', encoding='utf-8') as f:
        version_data = json.load(f)
    
    print(f"   ✓ Current: {version_data.get('current_version')}")
    print(f"   ✓ GitHub: {version_data.get('github_version')}")
    print(f"   ✓ Update Available: {version_data.get('update_available')}")
    
    # 4. Проверяем сравнение версий
    print("\n4️⃣ Тест сравнения версий:")
    
    test_cases = [
        ("1.0.0", "1.0.1", -1),  # 1.0.0 < 1.0.1
        ("1.0.0", "1.1.0", -1),  # 1.0.0 < 1.1.0
        ("1.0.0", "2.0.0", -1),  # 1.0.0 < 2.0.0
        ("1.1.0", "1.1.0", 0),   # 1.1.0 == 1.1.0
        ("2.0.0", "1.0.0", 1),   # 2.0.0 > 1.0.0
    ]
    
    for v1, v2, expected in test_cases:
        result = manager._compare_versions(v1, v2)
        status = "✓" if result == expected else "✗"
        print(f"   {status} {v1} vs {v2}: {result} (ожидается {expected})")
    
    # 5. Получаем уведомление
    print("\n5️⃣ Получение уведомления для админ-панели:")
    notification = manager.get_update_notification()
    
    if notification.get('has_update'):
        print(f"   ✓ Есть обновление!")
        print(f"   ✓ От версии: {notification.get('current')}")
        print(f"   ✓ К версии: {notification.get('available')}")
    else:
        print(f"   ℹ Обновление не требуется")
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    
    print("\n📊 РЕЗУЛЬТАТЫ:")
    print(f"   Текущая версия: {current_version}")
    print(f"   Обновление доступно: {result.get('update_available')}")
    
    if result.get('update_available'):
        print(f"\n🎉 ОБНОВЛЕНИЕ НАЙДЕНО!")
        print(f"   v{current_version} → v{result.get('github_version')}")
        print(f"\n   Для установки обновления:")
        print(f"   1. Откройте админ-панель")
        print(f"   2. Нажмите 'Обновить сейчас'")
        print(f"   3. Подтвердите обновление")
    else:
        print(f"\n   Вы используете последнюю версию: v{current_version}")

if __name__ == "__main__":
    test_update_system()
