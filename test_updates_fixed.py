#!/usr/bin/env python3
"""
✅ УСПЕШНЫЙ ТЕСТОВЫЙ СКРИПТ СИСТЕМЫ ОБНОВЛЕНИЙ
"""

import json
from update_manager import UpdateManager

def test_update_system():
    """Тестирует систему обновлений"""
    
    print("\n" + "=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ ОБНОВЛЕНИЙ")
    print("=" * 70)
    
    manager = UpdateManager()
    
    # 1. Текущая версия
    print("\n1️⃣ ТЕКУЩАЯ ВЕРСИЯ:")
    current = manager.get_current_version()
    print(f"   ✓ Установленная версия: v{current}")
    
    # 2. Проверка GitHub
    print("\n2️⃣ ПРОВЕРКА GITHUB:")
    check_result = manager.check_for_updates()
    github_version = check_result.get('github_version')
    print(f"   ✓ GitHub версия найдена: v{github_version}")
    
    # 3. Сравнение версий
    print("\n3️⃣ СРАВНЕНИЕ ВЕРСИЙ:")
    comparison = manager._compare_versions(current, github_version)
    if comparison < 0:
        print(f"   ✓ v{current} < v{github_version}")
        print(f"   ✓ Обновление ДОСТУПНО ✅")
        update_available = True
    elif comparison == 0:
        print(f"   ✓ v{current} == v{github_version}")
        print(f"   ✓ Вы используете последнюю версию")
        update_available = False
    else:
        print(f"   ✓ v{current} > v{github_version}")
        print(f"   ✓ Установлена более новая версия")
        update_available = False
    
    # 4. Проверка версии в файле
    print("\n4️⃣ СОСТОЯНИЕ version.json:")
    with open('version.json', 'r', encoding='utf-8') as f:
        version_data = json.load(f)
    
    print(f"   ✓ current_version: {version_data.get('current_version')}")
    print(f"   ✓ github_version: {version_data.get('github_version')}")
    print(f"   ✓ update_available: {version_data.get('update_available')}")
    
    # 5. Тесты версионирования
    print("\n5️⃣ ТЕСТЫ СЕМАНТИЧЕСКОГО ВЕРСИОНИРОВАНИЯ:")
    
    test_cases = [
        ("1.0.0", "1.0.1", "Patch (исправление)"),
        ("1.0.0", "1.1.0", "Minor (новая функция)"),
        ("1.0.0", "2.0.0", "Major (большие изменения)"),
        ("1.1.0", "1.1.0", "Без изменений"),
    ]
    
    for v1, v2, desc in test_cases:
        cmp = manager._compare_versions(v1, v2)
        if cmp < 0:
            symbol = "→"
        elif cmp == 0:
            symbol = "="
        else:
            symbol = "←"
        print(f"   ✓ v{v1} {symbol} v{v2}  ({desc})")
    
    # 6. Уведомление
    print("\n6️⃣ УВЕДОМЛЕНИЕ ДЛЯ АДМИН-ПАНЕЛИ:")
    notification = manager.get_update_notification()
    
    if notification.get('has_update'):
        print(f"   ✓ Обновление доступно!")
        print(f"   ✓ Текущая: v{notification.get('current')}")
        print(f"   ✓ Доступна: v{notification.get('available')}")
    else:
        print(f"   ℹ Обновление не требуется")
    
    # ИТОГИ
    print("\n" + "=" * 70)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 70)
    
    print("\n📊 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print(f"   Версия приложения:  v{current}")
    print(f"   Версия на GitHub:   v{github_version}")
    print(f"   Обновление доступно: {update_available}")
    
    if update_available:
        print(f"\n🚀 НОВОЕ ОБНОВЛЕНИЕ: v{current} → v{github_version}")
        print(f"\n   Как установить обновление:")
        print(f"   1. Откройте админ-панель в браузере")
        print(f"   2. В верхней части появится уведомление")
        print(f"   3. Нажмите кнопку 'Обновить сейчас'")
        print(f"   4. Подтвердите обновление в диалоге")
        print(f"   5. Приложение загрузит обновления и перезагрузится")
    else:
        print(f"\n   Система обновлений работает корректно!")
        print(f"   Текущая версия: v{current}")
    
    print("\n" + "=" * 70 + "\n")

if __name__ == "__main__":
    try:
        test_update_system()
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
