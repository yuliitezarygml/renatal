import telebot
from telebot import types
import json
import os
import requests
import calendar
from datetime import datetime, timedelta, date
import uuid
from config import TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID
from database import get_db_manager

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

PASSPORT_DIR = 'passport'

# Получаем менеджер БД
db = get_db_manager()

# Создаем папку для паспортов если её нет
if not os.path.exists(PASSPORT_DIR):
    os.makedirs(PASSPORT_DIR)

def load_json_file(collection_name):
    """Загрузка данных из MongoDB по названию коллекции"""
    try:
        # Определяем метод доступа в зависимости от названия коллекции
        if 'console' in collection_name.lower():
            return db.get_consoles()
        elif 'user' in collection_name.lower():
            return db.get_users()
        elif 'rental' in collection_name.lower() and 'request' not in collection_name.lower():
            return db.get_rentals()
        elif 'admin' in collection_name.lower():
            return db.get_admins()
        elif 'request' in collection_name.lower():
            return db.get_rental_requests()
        elif 'discount' in collection_name.lower():
            return db.get_discounts()
        elif 'calendar' in collection_name.lower() or 'blocked' in collection_name.lower():
            return db.get_calendar()
        elif 'settings' in collection_name.lower():
            return db.get_admin_settings()
        elif 'rating' in collection_name.lower():
            return db.get_ratings()
        elif 'temp' in collection_name.lower():
            return db.get_temp_reservations()
        else:
            return {}
    except Exception as e:
        print(f"❌ Ошибка загрузки из {collection_name}: {e}")
        return {}

def save_json_file(collection_name, data):
    """Сохранение данных в MongoDB по названию коллекции"""
    try:
        # Определяем метод сохранения в зависимости от названия коллекции
        if 'console' in collection_name.lower():
            for console_id, console in data.items():
                console['_id'] = console_id
                db.save_console(console)
        elif 'user' in collection_name.lower():
            for user_id, user in data.items():
                user['_id'] = user_id
                db.save_user(user)
        elif 'rental' in collection_name.lower() and 'request' not in collection_name.lower():
            for rental_id, rental in data.items():
                rental['_id'] = rental_id
                db.save_rental(rental)
        elif 'admin' in collection_name.lower():
            for admin_id, admin in data.items():
                admin['_id'] = admin_id
                db.save_admin(admin)
        elif 'request' in collection_name.lower():
            for request_id, req in data.items():
                req['_id'] = request_id
                db.save_rental_request(req)
        elif 'discount' in collection_name.lower():
            for discount_id, discount in data.items():
                discount['_id'] = discount_id
                db.save_discount(discount)
        elif 'calendar' in collection_name.lower() or 'blocked' in collection_name.lower():
            db.save_calendar(data)
        elif 'settings' in collection_name.lower():
            db.save_admin_settings(data)
        elif 'rating' in collection_name.lower():
            for rating_id, rating in data.items():
                rating['_id'] = rating_id
                db.save_rating(rating)
        elif 'temp' in collection_name.lower():
            for temp_id, temp_data in data.items():
                temp_data['_id'] = temp_id
                db.save_temp_reservation(temp_data)
    except Exception as e:
        print(f"❌ Ошибка сохранения в {collection_name}: {e}")

def is_user_banned(user_id):
    users = load_json_file('users')
    return users.get(str(user_id), {}).get('is_banned', False)

def mark_user_as_unavailable(user_id):
    """Помечаем пользователя как недоступного для уведомлений"""
    try:
        users = load_json_file('users')
        if user_id in users:
            users[user_id]['bot_blocked'] = True
            users[user_id]['bot_blocked_at'] = datetime.now().isoformat()
            save_json_file('users', users)
            print(f"📝 Пользователь {user_id} помечен как заблокировавший бота")
    except Exception as e:
        print(f"Ошибка при обновлении статуса пользователя {user_id}: {e}")

def safe_send_message(user_id, message, parse_mode='Markdown'):
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        bot.send_message(user_id, message, parse_mode=parse_mode)
        return True
    except Exception as e:
        error_message = str(e)
        
        if "chat not found" in error_message.lower():
            print(f"⚠️ Пользователь {user_id} недоступен (заблокировал бота или удалил чат)")
            mark_user_as_unavailable(user_id)
        elif "bot was blocked by the user" in error_message.lower():
            print(f"⚠️ Пользователь {user_id} заблокировал бота")
            mark_user_as_unavailable(user_id)
        else:
            print(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
        
        return False

def safe_edit_message(call, text, parse_mode='Markdown', reply_markup=None):
    """Безопасное редактирование сообщения с обработкой фото"""
    try:
        if call.message.photo:
            # Если сообщение с фото, удаляем его и отправляем новое текстовое
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        else:
            # Обычное текстовое сообщение - просто редактируем
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        # Fallback - удаляем старое и отправляем новое
        print(f"Error in safe_edit_message: {e}")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, text, parse_mode=parse_mode, reply_markup=reply_markup)

def get_admin_chat_id():
    settings = load_json_file('admin_settings')
    return settings.get('admin_chat_id', ADMIN_TELEGRAM_ID)

def get_discount_for_console(console_id):
    """Получить активную скидку для консоли"""
    discounts = load_json_file('discounts')
    
    for discount_id, discount in discounts.items():
        if (discount['console_id'] == console_id and 
            discount['active'] and 
            datetime.now() >= datetime.fromisoformat(discount['start_date']) and
            datetime.now() <= datetime.fromisoformat(discount['end_date'])):
            return discount
    
    return None

def check_date_has_discount(console_id, target_date):
    """Проверить, есть ли скидка на консоль в конкретную дату"""
    discounts = load_json_file('discounts')
    
    for discount_id, discount in discounts.items():
        if (discount['console_id'] == console_id and 
            discount['active'] and 
            datetime.fromisoformat(discount['start_date']).date() <= target_date and
            datetime.fromisoformat(discount['end_date']).date() >= target_date):
            return True
    
    return False

# ===== ФУНКЦИИ ДЛЯ РАБОТЫ С РЕЙТИНГАМИ =====

def calculate_discipline_score(transactions):
    """Рассчитать дисциплину на основе последних транзакций"""
    if not transactions:
        return 50  # Базовый рейтинг для новых клиентов
    
    try:
        ratings_data = load_json_file('ratings')
        discipline_rules = ratings_data.get('settings', {}).get('discipline_rules', {})
        window = ratings_data.get('settings', {}).get('transactions_window', 5)
        
        # Берем последние N транзакций
        recent_transactions = transactions[-window:]
        scores = []
        
        for transaction in recent_transactions:
            score = 100  # Базовый балл
            
            # Возврат вовремя
            return_timing = transaction.get('return_timing', 'on_time')
            timing_bonus = discipline_rules.get('return_timing', {}).get(return_timing, 0)
            score += timing_bonus
            
            # Состояние имущества
            item_condition = transaction.get('item_condition', 'perfect')
            condition_bonus = discipline_rules.get('item_condition', {}).get(item_condition, 0)
            score += condition_bonus
            
            # Соблюдение правил
            rule_compliance = transaction.get('rule_compliance', 'no_violations')
            compliance_bonus = discipline_rules.get('rule_compliance', {}).get(rule_compliance, 0)
            score += compliance_bonus
            
            # Ограничиваем диапазон 0-100
            score = max(0, min(100, score))
            scores.append(score)
        
        # Возвращаем среднее значение
        return round(sum(scores) / len(scores))
    except Exception as e:
        print(f"Ошибка расчета дисциплины: {e}")
        return 50

def calculate_loyalty_score(user_id, user_data):
    """Рассчитать лояльность клиента"""
    try:
        ratings_data = load_json_file('ratings')
        loyalty_rules = ratings_data.get('settings', {}).get('loyalty_rules', {})
        
        score = 0
        
        # Повторные аренды
        rentals = load_json_file('rentals')
        user_rentals = [r for r in rentals.values() if r.get('user_id') == user_id]
        rental_count = len(user_rentals)
        
        repeat_bonus = min(rental_count * loyalty_rules.get('repeat_rentals', {}).get('bonus_per_rental', 5),
                          loyalty_rules.get('repeat_rentals', {}).get('max_bonus', 30))
        score += repeat_bonus
        
        # Участие в акциях (из профиля пользователя)
        if user_data.get('promotion_participation', False):
            score += loyalty_rules.get('promotion_participation', 10)
        
        # Срок сотрудничества
        if 'joined_at' in user_data:
            join_date = datetime.fromisoformat(user_data['joined_at'])
            tenure_days = (datetime.now() - join_date).days
            
            tenure_bonus = 0
            if tenure_days >= 365:  # 12+ месяцев
                tenure_bonus = loyalty_rules.get('tenure_bonus', {}).get('12_months', 20)
            elif tenure_days >= 180:  # 6+ месяцев
                tenure_bonus = loyalty_rules.get('tenure_bonus', {}).get('6_months', 10)
            
            score += tenure_bonus
        
        # Дополнительные бонусы из профиля
        score += user_data.get('loyalty_bonus', 0)
        
        # Ограничиваем диапазон 0-100
        return max(0, min(100, score))
    except Exception as e:
        print(f"Ошибка расчета лояльности: {e}")
        return 0

def add_rating_transaction(user_id, transaction_type, points, comment):
    """Добавляет транзакцию рейтинга для пользователя"""
    import json
    import datetime
    
    try:
        ratings_data = load_json_file('ratings')
        
        if 'transactions' not in ratings_data:
            ratings_data['transactions'] = {}
        if user_id not in ratings_data['transactions']:
            ratings_data['transactions'][user_id] = []
        
        transaction = {
            'type': transaction_type,
            'points': points,
            'comment': comment,
            'date': datetime.datetime.now().isoformat(),
            'auto_generated': True
        }
        
        ratings_data['transactions'][user_id].append(transaction)
        
        with open('ratings', 'w', encoding='utf-8') as f:
            json.dump(ratings_data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"Ошибка добавления рейтинг транзакции: {e}")
        return False

def update_rating_on_rental_completion(user_id, rental_data, return_condition='perfect', on_time=True):
    """Обновляет рейтинг при завершении аренды"""
    
    # Добавляем баллы дисциплины в зависимости от условий возврата
    if on_time:
        add_rating_transaction(user_id, 'return_timing', 10, 'Возврат вовремя')
    else:
        # Определяем размер штрафа в зависимости от задержки
        # Здесь можно добавить логику определения задержки
        add_rating_transaction(user_id, 'return_timing', -20, 'Опоздание при возврате')
    
    # Баллы за состояние предмета
    if return_condition == 'perfect':
        add_rating_transaction(user_id, 'item_condition', 10, 'Отличное состояние')
    elif return_condition == 'minor_defects':
        add_rating_transaction(user_id, 'item_condition', -15, 'Незначительные повреждения')
    elif return_condition == 'major_defects':
        add_rating_transaction(user_id, 'item_condition', -30, 'Значительные повреждения')
    
    # Бонус лояльности за повторную аренду
    try:
        rentals = load_json_file('rentals')
        user_rentals = [r for r in rentals.values() if r['user_id'] == user_id and r['status'] == 'completed']
        
        if len(user_rentals) >= 2:  # Не первая аренда
            add_rating_transaction(user_id, 'repeat_rental', 5, f'Повторная аренда #{len(user_rentals)}')
    except:
        pass

def calculate_user_final_rating(user_id):
    """Рассчитать итоговый рейтинг пользователя"""
    try:
        ratings_data = load_json_file('ratings')
        settings = ratings_data.get('settings', {})
        
        # Загружаем данные пользователя
        users = load_json_file('users')
        if user_id not in users:
            return None
        
        user_data = users[user_id]
        
        # Получаем транзакции пользователя
        user_transactions = ratings_data.get('transactions', {}).get(user_id, [])
        
        # Рассчитываем компоненты
        discipline = calculate_discipline_score(user_transactions)
        loyalty = calculate_loyalty_score(user_id, user_data)
        
        # Итоговый рейтинг
        discipline_weight = settings.get('discipline_weight', 0.6)
        loyalty_weight = settings.get('loyalty_weight', 0.4)
        
        final_score = round(discipline * discipline_weight + loyalty * loyalty_weight)
        final_score = max(0, min(100, final_score))
        
        # Определяем статус
        thresholds = settings.get('status_thresholds', {})
        if final_score >= thresholds.get('premium', 80):
            status = 'premium'
            status_name = 'Premium ⭐'
        elif final_score >= thresholds.get('regular', 50):
            status = 'regular'
            status_name = 'Обычный 👤'
        else:
            status = 'risk'
            status_name = 'Риск ⚠️'
        
        return {
            'user_id': user_id,
            'final_score': final_score,
            'discipline': discipline,
            'loyalty': loyalty,
            'status': status,
            'status_name': status_name,
            'calculated_at': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Ошибка расчета итогового рейтинга: {e}")
        return None

def get_user_status_benefits(user_id):
    """Получить льготы пользователя по его статусу"""
    try:
        rating = calculate_user_final_rating(user_id)
        if not rating:
            return {
                'discount_percent': 0,
                'deposit_multiplier': 1.0,
                'priority_support': False,
                'advance_booking_days': 30
            }
        
        status = rating['status']
        benefits = {
            'premium': {
                'discount_percent': 10,
                'deposit_multiplier': 0.8,
                'priority_support': True,
                'advance_booking_days': 45
            },
            'regular': {
                'discount_percent': 0,
                'deposit_multiplier': 1.0,
                'priority_support': False,
                'advance_booking_days': 30
            },
            'risk': {
                'discount_percent': 0,
                'deposit_multiplier': 1.5,
                'priority_support': False,
                'advance_booking_days': 7
            }
        }
        
        return benefits.get(status, benefits['regular'])
    except Exception as e:
        print(f"Ошибка получения льгот пользователя: {e}")
        return {
            'discount_percent': 0,
            'deposit_multiplier': 1.0,
            'priority_support': False,
            'advance_booking_days': 30
        }

def create_temp_reservation(user_id, console_id, timeout_minutes=30):
    """Создать временную резервацию консоли"""
    reservations = load_json_file('temp_reservations')
    reservation_id = str(uuid.uuid4())
    
    # Удаляем старые резервации этого пользователя
    for res_id, res in list(reservations.items()):
        if res['user_id'] == user_id:
            del reservations[res_id]
    
    # Создаем новую резервацию
    expiry_time = datetime.now() + timedelta(minutes=timeout_minutes)
    reservations[reservation_id] = {
        'user_id': user_id,
        'console_id': console_id,
        'created_at': datetime.now().isoformat(),
        'expires_at': expiry_time.isoformat(),
        'status': 'active'
    }
    
    save_json_file('temp_reservations', reservations)
    return reservation_id

def remove_temp_reservation(user_id):
    """Удалить временную резервацию пользователя"""
    reservations = load_json_file('temp_reservations')
    for res_id, res in list(reservations.items()):
        if res['user_id'] == user_id:
            del reservations[res_id]
    save_json_file('temp_reservations', reservations)

def cleanup_expired_reservations():
    """Удалить истёкшие резервации"""
    reservations = load_json_file('temp_reservations')
    now = datetime.now()
    
    for res_id, res in list(reservations.items()):
        if datetime.fromisoformat(res['expires_at']) < now:
            del reservations[res_id]
    
    save_json_file('temp_reservations', reservations)

def is_console_temp_reserved(console_id, exclude_user_id=None):
    """Проверить, занята ли консоль временной резервацией"""
    cleanup_expired_reservations()
    reservations = load_json_file('temp_reservations')
    
    for res_id, res in reservations.items():
        if (res['console_id'] == console_id and 
            res['status'] == 'active' and 
            res['user_id'] != exclude_user_id):
            return True, res['user_id']
    
    return False, None

def calculate_discounted_price(console_id, original_price, duration_hours):
    """Вычислить цену с учетом скидки"""
    discount = get_discount_for_console(console_id)
    
    if not discount:
        return original_price, 0, None
    
    # Проверяем минимальную продолжительность для скидки
    if duration_hours < discount.get('min_hours', 0):
        return original_price, 0, None
    
    if discount['type'] == 'percentage':
        discount_amount = original_price * (discount['value'] / 100)
        discounted_price = original_price - discount_amount
    elif discount['type'] == 'fixed':
        discount_amount = min(discount['value'], original_price)  # Скидка не больше самой цены
        discounted_price = original_price - discount_amount
    else:
        return original_price, 0, None
    
    # Округляем до ближайших лей
    discounted_price = max(0, round(discounted_price))
    discount_amount = round(discount_amount)
    
    return discounted_price, discount_amount, discount

def get_console_photo_path_bot(console_id, console_data=None):
    """Получить локальный путь к фото консоли если существует"""
    # Если передана информация о консоли и в ней есть photo_path, используем его
    if console_data and console_data.get('photo_path'):
        photo_path = console_data['photo_path']
        local_path = photo_path.replace('/static/', 'static/')
        if os.path.exists(local_path):
            return local_path
    
    # Иначе ищем по ID консоли
    console_images_dir = os.path.join('static', 'img', 'console')
    allowed_extensions = ['png', 'jpg', 'jpeg', 'gif', 'webp']
    
    for ext in allowed_extensions:
        file_path = os.path.join(console_images_dir, f"{console_id}.{ext}")
        if os.path.exists(file_path):
            return file_path
    return None

def is_approval_required():
    settings = load_json_file('admin_settings')
    return settings.get('require_approval', True)

def get_console_rental_info(console_id):
    """Получить информацию об активной аренде консоли"""
    rentals = load_json_file('rentals')
    users = load_json_file('users')
    
    for rental_id, rental in rentals.items():
        if rental['console_id'] == console_id and rental['status'] == 'active':
            start_time = datetime.fromisoformat(rental['start_time'])
            # Предполагаем аренду на 1 день (можно настроить)
            estimated_end_time = start_time + timedelta(days=1)
            user = users.get(rental['user_id'], {})
            return {
                'start_time': start_time,
                'estimated_end_time': estimated_end_time,
                'user_name': user.get('full_name', user.get('first_name', 'Неизвестный')),
                'rental_id': rental_id
            }
    return None

def notify_admin(message):
    try:
        admin_id = get_admin_chat_id()
        print(f"Отправляем уведомление админу {admin_id}: {message[:100]}...")
        
        # Отправляем без parse_mode сначала, если не получается - с HTML
        try:
            bot.send_message(admin_id, message, parse_mode='Markdown')
            print("✅ Уведомление админу отправлено успешно")
        except Exception as e:
            print(f"Ошибка отправки с Markdown, пробуем без форматирования: {e}")
            # Fallback - отправляем как обычный текст
            bot.send_message(admin_id, message)
            print("✅ Уведомление админу отправлено без форматирования")
    except Exception as e:
        print(f"❌ Полная ошибка отправки уведомления админу: {e}")
        print(f"Admin ID: {get_admin_chat_id()}")
        # Дополнительная диагностика
        try:
            settings = load_json_file('admin_settings')
            print(f"Настройки админа: {settings}")
            if not settings.get('notifications_enabled', True):
                print("⚠️ Уведомления отключены в настройках!")
        except Exception as settings_error:
            print(f"Ошибка загрузки настроек админа: {settings_error}")

def notify_user_about_approval(user_id, console_id, rental_id):
    """Уведомление пользователя об одобрении заявки через админ-панель"""
    try:
        consoles = load_json_file('consoles')
        rentals = load_json_file('rentals')
        console = consoles.get(console_id, {})
        rental = rentals.get(rental_id, {})
        
        user_message = f"✅ **Ваша заявка одобрена администратором!**\n\n"
        user_message += f"🎮 Консоль: {console.get('name', 'Неизвестная консоль')}\n"
        user_message += f"💰 Цена: {console.get('rental_price', 0)} лей/час\n"
        
        selected_hours = rental.get('selected_hours')
        if selected_hours:
            selected_days = selected_hours // 24
            if selected_days == 1:
                user_message += f"⏰ Время аренды: {selected_days} день\n"
            elif selected_days in [2, 3, 4]:
                user_message += f"⏰ Время аренды: {selected_days} дня\n"
            else:
                user_message += f"⏰ Время аренды: {selected_days} дней\n"
            user_message += f"💵 К оплате: {rental.get('expected_cost', 0)} лей\n"
            expected_end = rental.get('expected_end_time')
            if expected_end:
                user_message += f"🕐 Окончание: {datetime.fromisoformat(expected_end).strftime('%Y-%m-%d %H:%M')}\n"
        
        user_message += f"🆔 ID аренды: `{rental_id}`\n\n"
        user_message += f"Аренда началась! Для завершения используйте /end {rental_id}"
        
        bot.send_message(user_id, user_message, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю об одобрении: {e}")

def notify_user_about_rejection(user_id, console_id):
    """Уведомление пользователя об отклонении заявки через админ-панель"""
    try:
        consoles = load_json_file('consoles')
        console = consoles.get(console_id, {})
        
        user_message = f"❌ **Ваша заявка отклонена администратором**\n\n"
        user_message += f"🎮 Консоль: {console.get('name', 'Неизвестная консоль')}\n"
        user_message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        user_message += f"Попробуйте арендовать другую консоль или обратитесь к администратору."
        
        bot.send_message(user_id, user_message, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю об отклонении: {e}")

def notify_user_about_rental_end(user_id, console_id, total_cost, hours):
    """Уведомление пользователя о завершении аренды администратором"""
    try:
        consoles = load_json_file('consoles')
        console = consoles.get(console_id, {})
        
        user_message = f"🏁 **Аренда завершена администратором**\n\n"
        user_message += f"🎮 Консоль: {console.get('name', 'Неизвестная консоль')}\n"
        user_message += f"⏰ Длительность: {hours} часов\n"
        user_message += f"💰 К оплате: {total_cost} лей\n\n"
        user_message += f"Спасибо за использование нашего сервиса! 🎮"
        
        if safe_send_message(user_id, user_message):
            print(f"✅ Уведомление отправлено пользователю {user_id}")
        else:
            print(f"❌ Не удалось отправить уведомление пользователю {user_id}")
        
    except Exception as e:
        print(f"❌ Ошибка подготовки уведомления для пользователя {user_id}: {e}")

def create_rental(user_id, console_id, call=None, location=None):
    """Создание новой аренды с поддержкой геолокации"""
    rentals = load_json_file('rentals')
    consoles = load_json_file('consoles')
    
    rental_id = str(uuid.uuid4())
    rental = {
        'id': rental_id,
        'user_id': str(user_id),
        'console_id': console_id,
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'status': 'active',
        'total_cost': 0
    }
    
    # Добавляем геолокацию только если передана
    if location:
        rental['location'] = location
    
    rentals[rental_id] = rental
    consoles[console_id]['status'] = 'rented'
    
    save_json_file('rentals', rentals)
    save_json_file('consoles', consoles)
    
    return rental_id

def create_user_keyboard():
    """Клавиатура для обычных пользователей"""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton('📊 Мой кабинет'),
        types.KeyboardButton('📝 Арендовать')
    )
    keyboard.add(
        types.KeyboardButton('ℹ️ Помощь')
    )
    return keyboard

def create_admin_keyboard():
    """Клавиатура для администраторов"""
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton('⚙️ Админ панель'),
        types.KeyboardButton('📈 Статистика')
    )
    keyboard.add(
        types.KeyboardButton('👥 Пользователи'),
        types.KeyboardButton('🔔 Уведомления')
    )
    keyboard.add(
        types.KeyboardButton('📝 Арендовать'),
        types.KeyboardButton('ℹ️ Помощь')
    )
    return keyboard

def create_main_keyboard():
    """Универсальная функция создания клавиатуры (для совместимости)"""
    return create_user_keyboard()

def is_user_admin(user_id):
    """Проверить является ли пользователь администратором"""
    admin_id = get_admin_chat_id()
    return str(user_id) == str(admin_id)

def is_user_registered(user_id):
    users = load_json_file('users')
    user = users.get(str(user_id), {})
    return user.get('phone_number') and user.get('full_name')

def get_keyboard_for_user(user_id):
    """Получить подходящую клавиатуру для пользователя"""
    if is_user_admin(user_id):
        return create_admin_keyboard()
    else:
        return create_user_keyboard()

def check_user_documents(user_full_name, user_id):
    """Проверить существующие документы пользователя"""
    safe_name = "".join(c for c in user_full_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    user_folder = os.path.join(PASSPORT_DIR, safe_name)
    
    documents = {
        'passport_front': False,
        'passport_back': False,
        'selfie_with_passport': False
    }
    
    # Проверяем существование папки пользователя
    if not os.path.exists(user_folder):
        return documents
    
    # Проверяем файлы в папке пользователя
    for doc_type in documents.keys():
        # Проверяем разные расширения файлов
        for ext in ['jpg', 'jpeg', 'png', 'webp']:
            filename = f"{doc_type}.{ext}"
            filepath = os.path.join(user_folder, filename)
            if os.path.exists(filepath):
                documents[doc_type] = os.path.join(safe_name, filename)
                break
    
    return documents

def save_photo_document(file_id, user_full_name, document_type):
    """Сохранить фотографию документа пользователя"""
    try:
        # Получаем информацию о файле
        file_info = bot.get_file(file_id)
        
        # Скачиваем файл
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Создаем папку пользователя
        safe_name = "".join(c for c in user_full_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        user_folder = os.path.join(PASSPORT_DIR, safe_name)
        
        # Создаем папку если её нет
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        
        # Создаем имя файла
        file_extension = file_info.file_path.split('.')[-1] if '.' in file_info.file_path else 'jpg'
        filename = f"{document_type}.{file_extension}"
        filepath = os.path.join(user_folder, filename)
        
        # Сохраняем файл
        with open(filepath, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        return {
            'success': True,
            'filepath': filepath,
            'filename': os.path.join(safe_name, filename),
            'user_folder': safe_name
        }
    except Exception as e:
        print(f"Ошибка сохранения фото: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    users = load_json_file('users')
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return
    
    # Если пользователь не существует или не завершил регистрацию
    if user_id not in users or not is_user_registered(user_id):
        if user_id not in users:
            users[user_id] = {
                'id': user_id,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name,
                'is_banned': False,
                'rentals': [],
                'total_spent': 0,
                'joined_at': datetime.now().isoformat(),
                'phone_number': None,
                'full_name': None,
                'registration_step': 'phone'
            }
            save_json_file('users', users)
        
        # Запрос номера телефона
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        phone_button = types.KeyboardButton('📱 Отправить номер телефона', request_contact=True)
        markup.add(phone_button)
        
        bot.reply_to(message, 
                    f"Добро пожаловать в систему аренды PlayStation!\n\n"
                    f"Для продолжения регистрации, пожалуйста, поделитесь своим номером телефона:",
                    reply_markup=markup)
        return
    
    # Пользователь уже зарегистрирован
    welcome_text = f"С возвращением, {users[user_id]['full_name']}!"
    keyboard = get_keyboard_for_user(user_id)
    bot.reply_to(message, welcome_text + "\n\nВыберите действие:", reply_markup=keyboard)

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = str(message.from_user.id)
    users = load_json_file('users')
    
    if user_id in users and message.contact.user_id == message.from_user.id:
        # Сохраняем номер телефона
        users[user_id]['phone_number'] = message.contact.phone_number
        users[user_id]['registration_step'] = 'full_name'
        save_json_file('users', users)
        
        # Запрашиваем ФИО
        markup = types.ReplyKeyboardRemove()
        bot.reply_to(message, 
                    f"✅ Номер телефона сохранен: {message.contact.phone_number}\n\n"
                    f"Теперь введите ваше полное ФИО:",
                    reply_markup=markup)
    else:
        bot.reply_to(message, "❌ Отправьте свой собственный номер телефона")

@bot.message_handler(content_types=['location'])
def handle_location(message):
    user_id = str(message.from_user.id)
    users = load_json_file('users')
    user = users.get(user_id, {})
    
    # Проверяем этап верификации пользователя
    verification_step = user.get('verification_step')
    
    # Ищем одобренную заявку этого пользователя
    rental_requests = load_json_file('rental_requests')
    approved_request = None
    
    for request_id, request in rental_requests.items():
        if request['user_id'] == user_id and request['status'] == 'approved':
            approved_request = request
            break
    
    # Если у пользователя есть одобренная заявка и он прошел верификацию документов
    if approved_request and verification_step == 'location_request':
        # Обрабатываем геолокацию для аренды
        console_id = approved_request['console_id']
        location_data = {
            'latitude': message.location.latitude,
            'longitude': message.location.longitude
        }
        rental_id = create_rental(user_id, console_id, location=location_data)
        
        # Обновляем статус заявки на завершенную
        approved_request['status'] = 'completed'
        approved_request['rental_id'] = rental_id
        save_json_file('rental_requests', rental_requests)
        
        # Очищаем статус верификации пользователя и удаляем резервацию
        users[user_id]['verification_step'] = 'completed'
        remove_temp_reservation(user_id)
        save_json_file('users', users)
        
        consoles = load_json_file('consoles')
        console = consoles[console_id]
        
        # Отправляем подтверждение пользователю
        response = f"✅ **Аренда началась!**\n\n"
        response += f"🎮 Консоль: {console['name']}\n"
        response += f"💰 Цена: {console['rental_price']} лей/час\n"
        response += f"🆔 ID аренды: `{rental_id}`\n"
        response += f"📍 Геолокация получена\n"
        response += f"📄 Документы верифицированы\n"
        response += f"⏰ Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        response += f"Для завершения аренды используйте /end {rental_id}"
        
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=get_keyboard_for_user(user_id))
        
        # Уведомляем администратора о начале аренды
        admin_message = f"🎮 **Аренда началась (с верификацией документов)**\n\n"
        admin_message += f"👤 {user.get('full_name', user.get('first_name', 'Неизвестный'))}\n"
        admin_message += f"📱 {user.get('phone_number', 'Не указан')}\n"
        admin_message += f"🎮 {console['name']}\n"
        admin_message += f"💰 {console['rental_price']} лей/час\n"
        admin_message += f"📍 Геолокация: {message.location.latitude}, {message.location.longitude}\n"
        admin_message += f"🆔 ID аренды: `{rental_id}`\n\n"
        admin_message += f"📄 **Документы сохранены:**\n"
        admin_message += f"• Паспорт (лицо): {user.get('passport_front_file', 'Не найден')}\n"
        admin_message += f"• Паспорт (оборот): {user.get('passport_back_file', 'Не найден')}\n"
        admin_message += f"• Селфи с паспортом: {user.get('selfie_file', 'Не найден')}\n\n"
        admin_message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        notify_admin(admin_message)
    else:
        # Просто отправляем геолокацию администратору
        response = f"📍 **Геолокация отправлена администратору**\n\n"
        response += f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        response += f"📍 Широта: {message.location.latitude}\n"
        response += f"📍 Долгота: {message.location.longitude}"
        
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=get_keyboard_for_user(user_id))
        
        # Уведомляем администратора о получении геолокации
        admin_message = f"📍 **Получена геолокация от пользователя**\n\n"
        admin_message += f"👤 {user.get('full_name', user.get('first_name', 'Неизвестный'))}\n"
        admin_message += f"📱 {user.get('phone_number', 'Не указан')}\n"
        admin_message += f"🆔 ID: `{user_id}`\n"
        admin_message += f"📍 Координаты: {message.location.latitude}, {message.location.longitude}\n"
        admin_message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        admin_message += f"[Открыть на карте](https://www.google.com/maps?q={message.location.latitude},{message.location.longitude})"
        
        notify_admin(admin_message)

@bot.message_handler(content_types=['photo'])
def handle_photo_document(message):
    user_id = str(message.from_user.id)
    users = load_json_file('users')
    
    if user_id not in users:
        bot.reply_to(message, "❌ Пользователь не найден. Выполните /start")
        return
    
    user = users[user_id]
    verification_step = user.get('verification_step')
    
    if not verification_step or verification_step not in ['passport_front', 'passport_back', 'selfie_with_passport']:
        bot.reply_to(message, "🤔 Отправка фото не требуется в данный момент.", reply_markup=get_keyboard_for_user(user_id))
        return
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    user_full_name = user.get('full_name', user.get('first_name', f'user_{user_id}'))
    
    # Получаем наибольшее фото
    photo = message.photo[-1]
    
    # Определяем тип документа
    document_types = {
        'passport_front': 'passport_front',
        'passport_back': 'passport_back', 
        'selfie_with_passport': 'selfie_with_passport'
    }
    
    document_type = document_types.get(verification_step)
    if not document_type:
        bot.reply_to(message, "❌ Неизвестный тип документа")
        return
    
    # Сохраняем фотографию
    result = save_photo_document(photo.file_id, user_full_name, document_type)
    
    if not result['success']:
        bot.reply_to(message, f"❌ Ошибка сохранения фото: {result['error']}")
        return
    
    # Обновляем статус пользователя
    if verification_step == 'passport_front':
        users[user_id]['verification_step'] = 'passport_back'
        users[user_id]['passport_front_file'] = result['filename']
        
        response = f"✅ **Фото передней стороны паспорта сохранено!**\n\n"
        response += f"**Шаг 2 из 3:** Теперь отправьте фото **ЗАДНЕЙ стороны паспорта**\n\n"
        response += f"⚠️ **Требования к фото:**\n"
        response += f"• Четкое изображение без бликов\n"
        response += f"• Все данные должны быть читаемыми\n"
        response += f"• Фото целиком, без обрезанных краев\n\n"
        response += f"📷 Отправьте фото как обычное изображение"
        
    elif verification_step == 'passport_back':
        users[user_id]['verification_step'] = 'selfie_with_passport'
        users[user_id]['passport_back_file'] = result['filename']
        
        response = f"✅ **Фото задней стороны паспорта сохранено!**\n\n"
        response += f"**Шаг 3 из 3:** Теперь отправьте **СЕЛФИ с паспортом**\n\n"
        response += f"⚠️ **Требования к селфи:**\n"
        response += f"• Ваше лицо и паспорт должны быть четко видны\n"
        response += f"• Держите паспорт открытым на странице с фото\n"
        response += f"• Хорошее освещение\n"
        response += f"• Смотрите в камеру\n\n"
        response += f"📷 Отправьте селфи как обычное изображение"
        
    elif verification_step == 'selfie_with_passport':
        users[user_id]['verification_step'] = 'location_request'
        users[user_id]['selfie_file'] = result['filename']
        
        response = f"✅ **Селфи с паспортом сохранено!**\n\n"
        response += f"🎉 **Верификация документов завершена!**\n\n"
        response += f"📍 **Финальный шаг:** Отправьте свою геолокацию для начала аренды\n\n"
        response += f"⚠️ **ВАЖНО:** Отправляйте геолокацию только когда будете готовы получить консоль!\n"
        response += f"Нажмите кнопку ниже для отправки геолокации"
        
        # Создаем кнопку для отправки геолокации
        location_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        location_button = types.KeyboardButton('📍 Отправить геолокацию', request_location=True)
        location_markup.add(location_button)
        
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=location_markup)
        save_json_file('users', users)
        
        # Уведомляем администратора о завершении верификации
        admin_message = f"📄 **Верификация документов завершена**\n\n"
        admin_message += f"👤 {user_full_name}\n"
        admin_message += f"📱 {user.get('phone_number', 'Не указан')}\n"
        admin_message += f"🆔 ID: `{user_id}`\n\n"
        admin_message += f"📁 **Сохраненные документы:**\n"
        admin_message += f"• Паспорт (лицо): {users[user_id].get('passport_front_file', 'Не найден')}\n"
        admin_message += f"• Паспорт (оборот): {users[user_id].get('passport_back_file', 'Не найден')}\n"
        admin_message += f"• Селфи с паспортом: {result['filename']}\n\n"
        admin_message += f"⏳ Ожидает отправки геолокации для начала аренды"
        
        notify_admin(admin_message)
        return
    
    save_json_file('users', users)
    bot.reply_to(message, response, parse_mode='Markdown')
    
    # Уведомляем администратора о получении документа
    step_names = {
        'passport_front': 'фото передней стороны паспорта',
        'passport_back': 'фото задней стороны паспорта',
        'selfie_with_passport': 'селфи с паспортом'
    }
    
    admin_message = f"📄 **Получен документ**\n\n"
    admin_message += f"👤 {user_full_name}\n"
    admin_message += f"📱 {user.get('phone_number', 'Не указан')}\n"
    admin_message += f"🆔 ID: `{user_id}`\n"
    admin_message += f"📁 Тип: {step_names.get(verification_step, 'Неизвестный')}\n"
    admin_message += f"💾 Файл: {result['filename']}\n"
    admin_message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    notify_admin(admin_message)

@bot.message_handler(func=lambda message: message.content_type == 'text' and 
                     message.from_user.id and 
                     str(message.from_user.id) in load_json_file('users') and 
                     load_json_file('users')[str(message.from_user.id)].get('registration_step') == 'full_name')
def handle_full_name(message):
    user_id = str(message.from_user.id)
    users = load_json_file('users')
    
    if user_id in users:
        full_name = message.text.strip()
        
        if len(full_name) < 2:
            bot.reply_to(message, "❌ Пожалуйста, введите корректное ФИО (минимум 2 символа)")
            return
        
        # Завершаем регистрацию
        users[user_id]['full_name'] = full_name
        users[user_id]['registration_step'] = 'completed'
        save_json_file('users', users)
        
        # Показываем главное меню
        keyboard = get_keyboard_for_user(user_id)
        bot.reply_to(message, 
                    f"✅ Регистрация завершена!\n\n"
                    f"👤 ФИО: {full_name}\n"
                    f"📱 Телефон: {users[user_id]['phone_number']}\n\n"
                    f"Добро пожаловать в систему аренды PlayStation консолей!\n"
                    f"Выберите действие:",
                    reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text == 'Консоли')
def list_consoles(message):
    user_id = str(message.from_user.id)
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    if not is_user_registered(user_id):
        bot.reply_to(message, "❌ Пожалуйста, завершите регистрацию с помощью команды /start")
        return
    
    consoles = load_json_file('consoles')
    
    if not consoles:
        bot.reply_to(message, "📭 Консоли пока недоступны", reply_markup=get_keyboard_for_user(user_id))
        return
    
    # Проверяем настройку отображения фото
    settings = load_json_file('admin_settings')
    show_photos = settings.get('show_console_photos', True)  # По умолчанию включено
    
    # Показываем консоли с фото если настройка включена
    for console_id, console in consoles.items():
        status_emoji = "✅" if console['status'] == 'available' else "🔴"
        games_text = ", ".join(console['games'][:3])
        if len(console['games']) > 3:
            games_text += f" и еще {len(console['games']) - 3}"
        
        caption = f"{status_emoji} **{console['name']}** ({console['model']})\n"
        caption += f"💰 Аренда: {console['rental_price']} лей/час\n"
        
        if console.get('sale_price', 0) > 0:
            caption += f"🏷️ Цена покупки: {console['sale_price']} лей\n"
        
        if console['games']:
            caption += f"🎯 Игры: {games_text}\n"
        
        caption += f"🆔 ID: `{console_id}`\n"
        caption += f"📊 Статус: {'Доступна' if console['status'] == 'available' else 'Арендована'}\n"
        
        # Отправляем с фото если включено в глобальных настройках И для этой консоли
        console_photo_enabled = console.get('show_photo_in_bot', True)  # По умолчанию включено
        
        if show_photos and console_photo_enabled:
            try:
                # Проверяем локальный файл фото
                photo_path = get_console_photo_path_bot(console_id, console)
                
                if photo_path:
                    # Отправляем локальное фото
                    with open(photo_path, 'rb') as photo_file:
                        bot.send_photo(
                            message.chat.id, 
                            photo_file, 
                            caption=caption, 
                            parse_mode='Markdown'
                        )
                elif console.get('photo_id'):
                    # Старая система - Telegram file_id (для совместимости)
                    bot.send_photo(
                        message.chat.id, 
                        console['photo_id'], 
                        caption=caption, 
                        parse_mode='Markdown'
                    )
                else:
                    # Фото не найдено, отправляем только текст
                    bot.send_message(message.chat.id, caption, parse_mode='Markdown')
            except Exception as e:
                print(f"Ошибка отправки фото консоли {console_id}: {e}")
                # Если фото недоступно, отправляем только текст
                bot.send_message(message.chat.id, caption, parse_mode='Markdown')
        else:
            # Без фото (отключено глобально или для этой консоли)
            bot.send_message(message.chat.id, caption, parse_mode='Markdown')
    
    # Отправляем клавиатуру в конце
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=get_keyboard_for_user(user_id))

@bot.message_handler(func=lambda message: message.text == '📊 Мой кабинет')
def user_profile(message):
    user_id = str(message.from_user.id)
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    if not is_user_registered(user_id):
        bot.reply_to(message, "❌ Пожалуйста, завершите регистрацию с помощью команды /start")
        return
    
    users = load_json_file('users')
    rentals = load_json_file('rentals')
    
    if user_id not in users:
        bot.reply_to(message, "❌ Пользователь не найден. Выполните /start")
        return
    
    user = users[user_id]
    user_rentals = [r for r in rentals.values() if r['user_id'] == user_id]
    active_rentals = [r for r in user_rentals if r['status'] == 'active']
    
    response = f"👤 **Ваш профиль:**\n\n"
    response += f"🆔 ID: `{user_id}`\n"
    response += f"👤 ФИО: {user.get('full_name', user['first_name'])}\n"
    response += f"📱 Телефон: {user.get('phone_number', 'Не указан')}\n"
    
    if user.get('username'):
        response += f"📞 Username: @{user['username']}\n"
    
    response += f"📅 Регистрация: {user['joined_at'][:10]}\n"
    response += f"📊 Всего аренд: {len(user_rentals)}\n"
    response += f"💰 Потрачено: {user.get('total_spent', 0)} лей\n"
    response += f"🔄 Активных аренд: {len(active_rentals)}\n"
    
    # Рейтинг скрыт от пользователей (доступен только в админ панели)
    
    if active_rentals:
        response += "\n**Активные аренды:**\n"
        consoles = load_json_file('consoles')
        
        # Создаем инлайн-клавиатуру для завершения аренд
        markup = types.InlineKeyboardMarkup()
        
        for rental in active_rentals:
            console = consoles.get(rental['console_id'], {})
            console_name = console.get('name', 'Неизвестная консоль')
            start_time = datetime.fromisoformat(rental['start_time'])
            duration = datetime.now() - start_time
            hours = int(duration.total_seconds() / 3600)
            minutes = int((duration.total_seconds() % 3600) / 60)
            
            response += f"• {console_name}\n"
            response += f"  ⏰ Время: {hours}ч {minutes}м\n"
            response += f"  💰 Текущая стоимость: {hours * console.get('rental_price', 0)} лей\n"
            response += f"  🆔 ID: `{rental['id'][:8]}...`\n"
            
            # Добавляем кнопку завершения для каждой аренды
            markup.add(types.InlineKeyboardButton(
                f"🏁 Завершить {console_name}",
                callback_data=f"end_rental_{rental['id']}"
            ))
        
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=get_keyboard_for_user(user_id))


@bot.message_handler(func=lambda message: message.text == '💰 Купить')
def buy_console(message):
    user_id = str(message.from_user.id)
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    if not is_user_registered(user_id):
        bot.reply_to(message, "❌ Пожалуйста, завершите регистрацию с помощью команды /start")
        return
    
    consoles = load_json_file('consoles')
    for_sale = {k: v for k, v in consoles.items() if v.get('sale_price', 0) > 0 and v['status'] == 'available'}
    
    if not for_sale:
        bot.reply_to(message, "😔 Сейчас нет консолей для продажи.", reply_markup=get_keyboard_for_user(user_id))
        return
    
    markup = types.InlineKeyboardMarkup()
    for console_id, console in for_sale.items():
        button_text = f"{console['name']} - {console['sale_price']} лей"
        markup.add(types.InlineKeyboardButton(
            button_text, 
            callback_data=f"buy_{console_id}"
        ))
    
    bot.reply_to(message, "💰 Выберите консоль для покупки:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_rent_'))
def handle_confirm_rent_callback(call):
    user_id = str(call.from_user.id)
    data_parts = call.data.split('_')
    console_id = data_parts[2]
    selected_hours = int(data_parts[3]) if len(data_parts) > 3 else None
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль недоступна")
        return
    
    console = consoles[console_id]
    user = users.get(user_id, {})
    
    if is_approval_required():
        # Создаем заявку на аренду
        request_id = str(uuid.uuid4())
        rental_requests = load_json_file('rental_requests')
        
        rental_request = {
            'id': request_id,
            'user_id': user_id,
            'console_id': console_id,
            'selected_hours': selected_hours,
            'expected_cost': selected_hours * console['rental_price'] if selected_hours else 0,
            'request_time': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        rental_requests[request_id] = rental_request
        save_json_file('rental_requests', rental_requests)
        
        # Уведомляем администратора
        def escape_markdown_text(text):
            if text is None:
                return 'Неизвестно'
            # Экранируем специальные символы Markdown
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = str(text).replace(char, f'\\{char}')
            return text
        
        full_name = escape_markdown_text(user.get('full_name', user.get('first_name', 'Неизвестный')))
        phone = escape_markdown_text(user.get('phone_number', 'Не указан'))
        console_name = escape_markdown_text(console['name'])
        console_model = escape_markdown_text(console['model'])
        
        admin_message = f"🔔 **Новая заявка на аренду**\n\n"
        admin_message += f"👤 **Пользователь:**\n"
        admin_message += f"• ФИО: {full_name}\n"
        admin_message += f"• Телефон: {phone}\n"
        admin_message += f"• ID: {user_id}\n\n"
        admin_message += f"🎮 **Консоль:**\n"
        admin_message += f"• {console_name} ({console_model})\n"
        admin_message += f"• Цена: {console['rental_price']} лей/час\n"
        if selected_hours:
            selected_days = selected_hours // 24
            if selected_days == 1:
                admin_message += f"• Время аренды: {selected_days} день\n"
            elif selected_days in [2, 3, 4]:
                admin_message += f"• Время аренды: {selected_days} дня\n"
            else:
                admin_message += f"• Время аренды: {selected_days} дней\n"
            admin_message += f"• К оплате: {selected_hours * console['rental_price']} лей\n"
        admin_message += f"• ID: {console_id}\n\n"
        admin_message += f"⏰ Время заявки: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Создаем клавиатуру для админа
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{request_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{request_id}")
        )
        
        try:
            admin_id = get_admin_chat_id()
            bot.send_message(admin_id, admin_message, parse_mode='Markdown', reply_markup=markup)
        except Exception as e:
            print(f"Ошибка отправки уведомления админу: {e}")
        
        # Отвечаем пользователю
        response = f"📝 **Заявка на аренду отправлена!**\n\n"
        response += f"🎮 Консоль: {console['name']}\n"
        response += f"💰 Цена: {console['rental_price']} лей/час\n"
        if selected_hours:
            selected_days = selected_hours // 24
            if selected_days == 1:
                response += f"⏰ Время: {selected_days} день\n"
            elif selected_days in [2, 3, 4]:
                response += f"⏰ Время: {selected_days} дня\n"
            else:
                response += f"⏰ Время: {selected_days} дней\n"
            response += f"💵 К оплате: {selected_hours * console['rental_price']} лей\n"
        response += f"\n⏳ Ожидайте подтверждения от администратора.\n"
        response += f"🆔 ID заявки: `{request_id}`"
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    else:
        # Мгновенная аренда без подтверждения
        create_rental(user_id, console_id, call, selected_hours=selected_hours)

def create_rental(user_id, console_id, call=None, location=None, selected_hours=None):
    """Создание аренды"""
    rentals = load_json_file('rentals')
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    
    rental_id = str(uuid.uuid4())
    # Рассчитываем время окончания аренды если выбрано время
    end_time = None
    expected_cost = 0
    if selected_hours:
        end_time = (datetime.now() + timedelta(hours=selected_hours)).isoformat()
        expected_cost = selected_hours * consoles[console_id]['rental_price']
    
    rental = {
        'id': rental_id,
        'user_id': user_id,
        'console_id': console_id,
        'start_time': datetime.now().isoformat(),
        'expected_end_time': end_time,
        'selected_hours': selected_hours,
        'expected_cost': expected_cost,
        'end_time': None,
        'status': 'active',
        'total_cost': 0
    }
    
    # Добавляем геолокацию только если передана
    if location:
        rental['location'] = location
    
    rentals[rental_id] = rental
    consoles[console_id]['status'] = 'rented'
    
    save_json_file('rentals', rentals)
    save_json_file('consoles', consoles)
    
    console_name = consoles[console_id]['name']
    price_per_hour = consoles[console_id]['rental_price']
    user = users.get(user_id, {})
    
    # Уведомляем администратора о начале аренды
    admin_message = f"✅ **Аренда началась**\n\n"
    admin_message += f"👤 {user.get('full_name', user.get('first_name', 'Неизвестный'))}\n"
    admin_message += f"📱 {user.get('phone_number', 'Не указан')}\n"
    admin_message += f"🎮 {console_name}\n"
    admin_message += f"💰 {price_per_hour} лей/час\n"
    if selected_hours:
        selected_days = selected_hours // 24
        if selected_days == 1:
            admin_message += f"⏰ Выбранное время: {selected_days} день\n"
        elif selected_days in [2, 3, 4]:
            admin_message += f"⏰ Выбранное время: {selected_days} дня\n"
        else:
            admin_message += f"⏰ Выбранное время: {selected_days} дней\n"
        admin_message += f"💵 Ожидаемая стоимость: {expected_cost} лей\n"
    admin_message += f"🕐 Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    admin_message += f"🆔 ID аренды: `{rental_id}`"
    
    notify_admin(admin_message)
    
    # Ответ пользователю
    response = f"✅ Консоль **{console_name}** арендована!\n\n"
    response += f"🆔 ID аренды: `{rental_id}`\n"
    response += f"💰 Цена: {price_per_hour} лей/час\n"
    if selected_hours:
        selected_days = selected_hours // 24
        if selected_days == 1:
            response += f"⏰ Время аренды: {selected_days} день\n"
        elif selected_days in [2, 3, 4]:
            response += f"⏰ Время аренды: {selected_days} дня\n"
        else:
            response += f"⏰ Время аренды: {selected_days} дней\n"
        response += f"💵 К оплате: {expected_cost} лей\n"
        response += f"🕐 Окончание: {datetime.fromisoformat(end_time).strftime('%Y-%m-%d %H:%M')}\n"
    response += f"🕐 Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    response += "Для завершения аренды используйте команду /end с ID аренды"
    
    if call:
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    return rental_id

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy_callback(call):
    user_id = str(call.from_user.id)
    console_id = call.data.split('_')[1]
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    consoles = load_json_file('consoles')
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль недоступна")
        return
    
    console = consoles[console_id]
    
    response = f"💰 **Покупка консоли**\n\n"
    response += f"🎮 Консоль: {console['name']} ({console['model']})\n"
    response += f"💵 Цена: {console['sale_price']} лей\n\n"
    response += f"Для покупки обратитесь к администратору:\n"
    response += f"Telegram: @{ADMIN_TELEGRAM_ID}\n"
    response += f"ID консоли: `{console_id}`"
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.message_handler(commands=['end'])
def end_rental(message):
    user_id = str(message.from_user.id)
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Укажите ID аренды: /end <ID аренды>")
        return
    
    rental_id = args[1]
    rentals = load_json_file('rentals')
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    
    if rental_id not in rentals:
        bot.reply_to(message, "❌ Аренда не найдена")
        return
    
    rental = rentals[rental_id]
    
    if rental['user_id'] != user_id:
        bot.reply_to(message, "❌ Это не ваша аренда")
        return
    
    if rental['status'] != 'active':
        bot.reply_to(message, "❌ Аренда уже завершена")
        return
    
    start_time = datetime.fromisoformat(rental['start_time'])
    end_time = datetime.now()
    duration = end_time - start_time
    hours = max(1, int(duration.total_seconds() / 3600))
    
    console = consoles[rental['console_id']]
    total_cost = hours * console['rental_price']
    
    rental['end_time'] = end_time.isoformat()
    rental['status'] = 'completed'
    rental['total_cost'] = total_cost
    
    console['status'] = 'available'
    
    if user_id in users:
        users[user_id]['total_spent'] = users[user_id].get('total_spent', 0) + total_cost
    
    save_json_file('rentals', rentals)
    save_json_file('consoles', consoles)
    save_json_file('users', users)
    
    # Обновляем рейтинг пользователя
    update_rating_on_rental_completion(user_id, rental)
    
    response = f"✅ **Аренда завершена!**\n\n"
    response += f"🎮 Консоль: {console['name']}\n"
    response += f"⏰ Длительность: {hours} часов\n"
    response += f"💰 К оплате: {total_cost} лей\n\n"
    response += f"Спасибо за использование нашего сервиса!"
    
    bot.reply_to(message, response, parse_mode='Markdown', reply_markup=get_keyboard_for_user(user_id))

@bot.message_handler(func=lambda message: message.text == '📝 Арендовать')
def rental_menu(message):
    user_id = str(message.from_user.id)
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    if not is_user_registered(user_id):
        bot.reply_to(message, "❌ Пожалуйста, завершите регистрацию с помощью команды /start")
        return
    
    consoles = load_json_file('consoles')
    
    if not consoles:
        bot.reply_to(message, "📭 Консоли пока недоступны", reply_markup=get_keyboard_for_user(user_id))
        return
    
    response = "Выберите консоль для аренды:\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for console_id, console in consoles.items():
        if console['status'] == 'available':
            # Проверяем временную резервацию
            is_reserved, reserved_by = is_console_temp_reserved(console_id, exclude_user_id=user_id)
            
            if is_reserved:
                status_emoji = "⏳"  # Временно недоступна
                button_text = f"{status_emoji} {console['name']} - Временно недоступно"
                callback_data = f"reserved_{console_id}"
            else:
                status_emoji = "🟢"  # Зеленый кружок для свободных
                button_text = f"{status_emoji} {console['name']} - {console['rental_price']} лей/час"
                callback_data = f"console_{console_id}"
                print(f"DEBUG: Creating button with callback_data: {callback_data}")
            
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
        else:
            status_emoji = "🔴"  # Красный кружок для занятых
            rental_info = get_console_rental_info(console_id)
            if rental_info:
                start_date = rental_info['start_time'].strftime('%d.%m')
                end_date = rental_info['estimated_end_time'].strftime('%d.%m')
                button_text = f"{status_emoji} {console['name']} - Занята с {start_date} до {end_date}"
            else:
                button_text = f"{status_emoji} {console['name']} - Занята"
            callback_data = f"console_unavailable_{console_id}"
            print(f"DEBUG: Creating unavailable button with callback_data: {callback_data}")
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    bot.reply_to(message, response, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reserved_'))
def handle_reserved_console(call):
    """Обработчик для временно зарезервированных консолей"""
    bot.answer_callback_query(call.id, "⏳ Эта консоль временно занята другим пользователем. Попробуйте позже.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('console_'))
def handle_console_selection(call):
    try:
        user_id = str(call.from_user.id)
        print(f"DEBUG: Console callback received: {call.data}")
        
        if is_user_banned(user_id):
            bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
            return
        
        callback_parts = call.data.split('_')
        print(f"DEBUG: Callback parts: {callback_parts}")
        
        # Проверяем, если консоль недоступна
        if len(callback_parts) > 2 and callback_parts[1] == 'unavailable':
            console_id = callback_parts[2]
            consoles = load_json_file('consoles')
            
            if console_id in consoles:
                console = consoles[console_id]
                rental_info = get_console_rental_info(console_id)
                
                if rental_info:
                    start_date = rental_info['start_time'].strftime('%d.%m.%Y')
                    end_date = rental_info['estimated_end_time'].strftime('%d.%m.%Y')
                    response = f"**{console['name']}** ({console['model']})\n\n"
                    response += f"🔴 **Статус:** Занята\n"
                    response += f"📅 **Период аренды:** с {start_date} до {end_date}\n"
                    response += f"👤 **Арендатор:** {rental_info['user_name']}\n\n"
                    response += f"💰 Цена аренды: {console['rental_price']} лей/час\n"
                    
                    if console.get('games'):
                        response += f"\n**Доступные игры:**\n"
                        for game in console['games']:
                            response += f"• {game}\n"
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("⬅️ Назад к выбору", callback_data="back_to_selection"))
                    
                    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                                         parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.answer_callback_query(call.id, "❌ Эта консоль сейчас занята")
            else:
                bot.answer_callback_query(call.id, "❌ Консоль не найдена")
            return
        
        console_id = callback_parts[1]
        consoles = load_json_file('consoles')
        print(f"DEBUG: Looking for console_id: {console_id}")
        print(f"DEBUG: Available consoles: {list(consoles.keys())}")
        
        if console_id not in consoles:
            bot.answer_callback_query(call.id, "❌ Консоль не найдена")
            return
        
        console = consoles[console_id]
        print(f"DEBUG: Found console: {console['name']}")
        
        # Показываем подробную информацию о консоли
        caption = f"**{console['name']}** ({console['model']})\n\n"
        caption += f"💰 Цена аренды: {console['rental_price']} лей/час\n"
        
        if console.get('sale_price', 0) > 0:
            caption += f"🏷️ Цена покупки: {console['sale_price']} лей\n"
        
        caption += f"📊 Статус: {'✅ Доступна' if console['status'] == 'available' else '🔴 Занята'}\n\n"
        
        if console.get('games'):
            caption += f"**Доступные игры:**\n"
            for game in console['games']:
                caption += f"• {game}\n"
        
        # Создаем кнопки
        markup = types.InlineKeyboardMarkup()
        
        if console['status'] == 'available':
            current_date = datetime.now()
            short_console_id = console_id[:8]
            calendar_callback = f"cal_{short_console_id}_{current_date.strftime('%Y-%m')}"
            markup.add(types.InlineKeyboardButton("📅 Выбрать дату аренды", callback_data=calendar_callback))
        
        markup.add(types.InlineKeyboardButton("⬅️ Назад к выбору", callback_data="back_to_selection"))
        
        # Проверяем настройки отображения фото
        settings = load_json_file('admin_settings')
        show_photos = settings.get('show_console_photos', True)
        console_photo_enabled = console.get('show_photo_in_bot', True)
        
        # Отправляем с фото если настройки позволяют
        if show_photos and console_photo_enabled:
            try:
                photo_path = get_console_photo_path_bot(console_id, console)
                
                if photo_path:
                    # Удаляем предыдущее сообщение
                    try:
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except:
                        pass
                    
                    # Отправляем новое сообщение с фото
                    with open(photo_path, 'rb') as photo_file:
                        bot.send_photo(
                            call.message.chat.id, 
                            photo_file, 
                            caption=caption, 
                            parse_mode='Markdown',
                            reply_markup=markup
                        )
                elif console.get('photo_id'):
                    # Старая система - Telegram file_id
                    try:
                        bot.delete_message(call.message.chat.id, call.message.message_id)
                    except:
                        pass
                    
                    bot.send_photo(
                        call.message.chat.id, 
                        console['photo_id'], 
                        caption=caption, 
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
                else:
                    # Фото не найдено, редактируем текущее сообщение
                    bot.edit_message_text(caption, call.message.chat.id, call.message.message_id, 
                                         parse_mode='Markdown', reply_markup=markup)
            except Exception as e:
                print(f"Ошибка отправки фото в handle_console_selection: {e}")
                # Fallback на текстовое сообщение
                bot.edit_message_text(caption, call.message.chat.id, call.message.message_id, 
                                     parse_mode='Markdown', reply_markup=markup)
        else:
            # Без фото
            bot.edit_message_text(caption, call.message.chat.id, call.message.message_id, 
                                 parse_mode='Markdown', reply_markup=markup)
        print(f"DEBUG: Successfully updated message")
        
    except Exception as e:
        print(f"ERROR in handle_console_selection: {e}")
        bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")

def get_occupied_dates(console_id):
    """Получить список занятых дат для консоли"""
    rentals = load_json_file('rentals')
    occupied_dates = set()
    
    # Добавляем даты из активных аренд
    for rental in rentals.values():
        if rental['console_id'] == console_id and rental['status'] == 'active':
            start_date = datetime.fromisoformat(rental['start_time'])
            end_date = datetime.fromisoformat(rental['estimated_end_time'])
            
            # Добавляем все даты между началом и концом аренды
            current_date = start_date.date()
            end_date = end_date.date()
            
            while current_date <= end_date:
                occupied_dates.add(current_date)
                current_date += timedelta(days=1)
    
    # Добавляем заблокированные даты из календаря
    try:
        calendar_file = os.path.join('data', 'calendar.json')
        calendar_data = load_json_file(calendar_file)
        
        # Системные заблокированные даты (для всех консолей)
        system_blocked = calendar_data.get('system_blocked_dates', [])
        for date_str in system_blocked:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            occupied_dates.add(date_obj)
        
        # Заблокированные даты для конкретной консоли
        console_blocked = calendar_data.get('console_blocked_dates', {}).get(console_id, [])
        for date_str in console_blocked:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            occupied_dates.add(date_obj)
        
        # Добавляем праздничные дни (нерабочие)
        holidays = calendar_data.get('holidays', [])
        for holiday in holidays:
            if not holiday.get('working', False):  # Если не рабочий праздник
                date_obj = datetime.strptime(holiday['date'], '%Y-%m-%d').date()
                occupied_dates.add(date_obj)
        
        # Примечание: рабочие дни недели проверяются в create_calendar() для конкретного месяца
        # Здесь мы не добавляем нерабочие дни, так как неизвестно для какого периода
            
    except Exception as e:
        print(f"Ошибка загрузки календарных данных: {e}")
        # Fallback на старую систему
        try:
            blocked_dates_file = os.path.join('data', 'blocked_dates.json')
            blocked_data = load_json_file(blocked_dates_file)
            
            system_blocked = blocked_data.get('system_blocked_dates', [])
            for date_str in system_blocked:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                occupied_dates.add(date_obj)
            
            console_blocked = blocked_data.get('console_blocked_dates', {}).get(console_id, [])
            for date_str in console_blocked:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                occupied_dates.add(date_obj)
        except Exception as fallback_error:
            print(f"Ошибка fallback загрузки дат: {fallback_error}")
    
    return occupied_dates

def get_available_time_slots(console_id, date_str):
    """Получить доступные временные слоты для даты"""
    try:
        calendar_file = os.path.join('data', 'calendar.json')
        calendar_data = load_json_file(calendar_file)
        
        # Получаем все временные слоты
        all_slots = calendar_data.get('settings', {}).get('time_slots', [
            "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", 
            "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"
        ])
        
        # Получаем занятые слоты из резерваций
        date_key = f"{date_str}_{console_id}"
        reservations = calendar_data.get('reservations', {}).get(date_key, [])
        occupied_slots = [r['time_slot'] for r in reservations if r['status'] == 'reserved']
        
        # Фильтруем доступные слоты
        available_slots = [slot for slot in all_slots if slot not in occupied_slots]
        
        return available_slots, occupied_slots
        
    except Exception as e:
        print(f"Ошибка получения временных слотов: {e}")
        # Возвращаем базовые слоты при ошибке
        default_slots = ["09:00", "12:00", "15:00", "18:00", "21:00"]
        return default_slots, []

def get_calendar_settings():
    """Получить настройки календаря"""
    try:
        calendar_file = os.path.join('data', 'calendar.json')
        calendar_data = load_json_file(calendar_file)
        return calendar_data.get('settings', {}), calendar_data.get('booking_rules', {})
    except Exception as e:
        print(f"Ошибка получения настроек календаря: {e}")
        return {}, {}

def create_calendar(console_id, year, month):
    """Создать календарь для выбора даты"""
    occupied_dates = get_occupied_dates(console_id)
    today = datetime.now().date()
    
    # Получаем настройки рабочих дней
    try:
        calendar_file = os.path.join('data', 'calendar.json')
        calendar_data = load_json_file(calendar_file)
        working_days = calendar_data.get('working_days', [1, 2, 3, 4, 5, 6, 7])
    except:
        working_days = [1, 2, 3, 4, 5, 6, 7]  # По умолчанию все дни рабочие
    
    # Создаем календарь
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]
    
    keyboard = types.InlineKeyboardMarkup(row_width=7)
    
    # Заголовок с названием месяца и года
    keyboard.add(types.InlineKeyboardButton(
        f"📅 {month_name} {year}", 
        callback_data="ignore"
    ))
    
    # Дни недели
    days_of_week = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    keyboard.add(*[types.InlineKeyboardButton(day, callback_data="ignore") for day in days_of_week])
    
    # Дни месяца
    for week in cal:
        week_buttons = []
        for day in week:
            if day == 0:
                week_buttons.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                current_date = datetime(year, month, day).date()
                weekday = current_date.weekday() + 1  # 1 = понедельник, 7 = воскресенье
                
                if current_date in occupied_dates or weekday not in working_days:
                    # Занятые дни - красные, передаем информацию о дате
                    short_console_id = console_id[:8]
                    callback_data = f"busy_{short_console_id}_{year}-{month:02d}-{day:02d}"
                    week_buttons.append(types.InlineKeyboardButton(f"🔴{day}", callback_data=callback_data))
                else:
                    # Проверяем, есть ли скидка на этот день
                    has_discount = check_date_has_discount(console_id, current_date)
                    short_console_id = console_id[:8]
                    callback_data = f"dt_{short_console_id}_{year}-{month:02d}-{day:02d}"
                    
                    if has_discount:
                        # Доступные дни со скидкой - добавляем огонь
                        week_buttons.append(types.InlineKeyboardButton(f"🔥{day}", callback_data=callback_data))
                    else:
                        # Обычные доступные дни
                        week_buttons.append(types.InlineKeyboardButton(str(day), callback_data=callback_data))
        
        keyboard.add(*week_buttons)
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    short_console_id = console_id[:8]
    keyboard.add(
        types.InlineKeyboardButton("⬅️", callback_data=f"cal_{short_console_id}_{prev_year}-{prev_month:02d}"),
        types.InlineKeyboardButton("➡️", callback_data=f"cal_{short_console_id}_{next_year}-{next_month:02d}")
    )
    
    # Кнопка назад к консоли
    keyboard.add(types.InlineKeyboardButton("⬅️ Назад к консоли", callback_data=f"console_{console_id}"))
    
    return keyboard

@bot.callback_query_handler(func=lambda call: call.data.startswith('cal_'))
def handle_calendar_navigation(call):
    """Обработка навигации по календарю"""
    try:
        parts = call.data.split('_')
        short_console_id = parts[1]
        date_str = parts[2]
        
        # Находим полный console_id по короткому ID
        consoles = load_json_file('consoles')
        console_id = None
        for cid in consoles.keys():
            if cid.startswith(short_console_id):
                console_id = cid
                break
        
        if not console_id:
            bot.answer_callback_query(call.id, "❌ Консоль не найдена")
            return
        year, month = map(int, date_str.split('-'))
        
        response = "📅 **Выберите дату начала аренды**\n\n"
        response += "🔴 - Занято\n"
        response += "❌ - Недоступно\n\n"
        response += "Выберите свободную дату:"
        
        markup = create_calendar(console_id, year, month)
        
        # Проверяем есть ли фото в сообщении
        try:
            if call.message.photo:
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                                    parse_mode='Markdown', reply_markup=markup)
        except Exception as e:
            print(f"Error in calendar navigation: {e}")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
            
    except Exception as e:
        print(f"Error in handle_calendar_navigation: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка навигации по календарю")

@bot.callback_query_handler(func=lambda call: call.data == 'ignore')
def handle_ignore_callback(call):
    """Обработка нажатий на неактивные элементы"""
    # Просто отвечаем пустым callback чтобы убрать "часики"
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('busy_'))
def handle_busy_date_selection(call):
    """Обработка клика по занятой дате"""
    try:
        parts = call.data.split('_')
        short_console_id = parts[1]
        selected_date = parts[2]  # YYYY-MM-DD
        
        # Находим полный console_id по короткому ID
        consoles = load_json_file('consoles')
        console_id = None
        for cid in consoles.keys():
            if cid.startswith(short_console_id):
                console_id = cid
                break
        
        if not console_id:
            bot.answer_callback_query(call.id, "❌ Консоль не найдена")
            return
        
        # Находим информацию об аренде на эту дату
        rentals = load_json_file('rentals')
        users = load_json_file('users')
        
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        rental_info = None
        
        for rental in rentals.values():
            if rental['console_id'] == console_id and rental['status'] == 'active':
                start_date = datetime.fromisoformat(rental['start_time']).date()
                end_date = datetime.fromisoformat(rental['estimated_end_time']).date()
                
                # Проверяем, попадает ли выбранная дата в период аренды
                if start_date <= selected_date_obj <= end_date:
                    rental_info = rental
                    break
        
        if rental_info:
            user = users.get(rental_info['user_id'], {})
            user_name = user.get('full_name', 'Неизвестный пользователь')
            
            start_date_formatted = datetime.fromisoformat(rental_info['start_time']).strftime('%d.%m.%Y')
            end_date_formatted = datetime.fromisoformat(rental_info['estimated_end_time']).strftime('%d.%m.%Y')
            
            message = f"🔴 **Дата занята**\n\n"
            message += f"📅 **Выбранная дата:** {selected_date_obj.strftime('%d.%m.%Y')}\n\n"
            message += f"**Период аренды:** {start_date_formatted} - {end_date_formatted}\n"
            message += f"**Арендатор:** {user_name}\n"
            message += f"**ID аренды:** `{rental_info['id'][:8]}...`\n\n"
            message += "Выберите другую свободную дату для аренды."
        else:
            message = f"🔴 **Дата занята**\n\n"
            message += f"📅 **Выбранная дата:** {selected_date_obj.strftime('%d.%m.%Y')}\n\n"
            message += "Эта дата недоступна для аренды.\nВыберите другую свободную дату."
        
        # Отправляем временное сообщение (всплывающее уведомление)
        bot.answer_callback_query(call.id, "🔴 Эта дата занята! Выберите другую дату.", show_alert=True)
        
    except Exception as e:
        print(f"Error in handle_busy_date_selection: {e}")
        bot.answer_callback_query(call.id, "🔴 Эта дата занята! Выберите другую дату.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dt_'))
def handle_date_selection(call):
    """Обработка выбора даты"""
    try:
        parts = call.data.split('_')
        short_console_id = parts[1]
        selected_date = parts[2]
        
        # Находим полный console_id по короткому ID
        consoles = load_json_file('consoles')
        console_id = None
        for cid in consoles.keys():
            if cid.startswith(short_console_id):
                console_id = cid
                break
        
        if not console_id:
            bot.answer_callback_query(call.id, "❌ Консоль не найдена")
            return
        
        # Сохраняем выбранную дату в user state (можно использовать глобальный словарь)
        if not hasattr(handle_date_selection, 'user_states'):
            handle_date_selection.user_states = {}
        
        user_id = str(call.from_user.id)
        handle_date_selection.user_states[user_id] = {
            'console_id': console_id,
            'selected_date': selected_date
        }
        
        # Теперь показываем варианты продолжительности
        consoles = load_json_file('consoles')
        console = consoles[console_id]
        price_per_hour = console['rental_price']
        
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        formatted_date = selected_date_obj.strftime('%d.%m.%Y')
        
        response = f"⏰ **Выберите продолжительность аренды**\n\n"
        response += f"🎮 Консоль: {console['name']}\n"
        response += f"📅 Дата начала: {formatted_date}\n"
        response += f"💰 Цена: {price_per_hour} лей/час\n\n"
        response += f"📊 **Варианты аренды:**\n"
        
        # Создаем кнопки с вариантами времени и стоимостью
        markup = types.InlineKeyboardMarkup()
        time_options = [24, 48, 72, 168, 336]  # 1, 2, 3, 7, 14 дней в часах
        day_labels = [1, 2, 3, 7, 14]  # соответствующие дни
        
        for i, hours in enumerate(time_options):
            days = day_labels[i]
            original_cost = hours * price_per_hour
            
            # Применяем скидку если есть
            discounted_cost, discount_amount, discount_info = calculate_discounted_price(console_id, original_cost, hours)
            
            # Проверяем, не пересекается ли этот период с занятыми датами
            end_date = selected_date_obj + timedelta(days=days)
            occupied_dates = get_occupied_dates(console_id)
            
            is_available = True
            check_date = selected_date_obj
            while check_date < end_date:
                if check_date in occupied_dates:
                    is_available = False
                    break
                check_date += timedelta(days=1)
            
            # Формируем текст с учетом скидки
            if discount_amount > 0:
                if days == 1:
                    button_text = f"{days} день - {discounted_cost} лей 🔥"
                    response += f"• {days} день = ~~{original_cost}~~ **{discounted_cost} лей** 🔥 (-{discount_amount} лей)"
                elif days in [2, 3, 4]:
                    button_text = f"{days} дня - {discounted_cost} лей 🔥"
                    response += f"• {days} дня = ~~{original_cost}~~ **{discounted_cost} лей** 🔥 (-{discount_amount} лей)"
                else:
                    button_text = f"{days} дней - {discounted_cost} лей 🔥"
                    response += f"• {days} дней = ~~{original_cost}~~ **{discounted_cost} лей** 🔥 (-{discount_amount} лей)"
            else:
                if days == 1:
                    button_text = f"{days} день - {original_cost} лей"
                    response += f"• {days} день = {original_cost} лей"
                elif days in [2, 3, 4]:
                    button_text = f"{days} дня - {original_cost} лей"
                    response += f"• {days} дня = {original_cost} лей"
                else:
                    button_text = f"{days} дней - {original_cost} лей"
                    response += f"• {days} дней = {original_cost} лей"
            
            if not is_available:
                button_text += " ❌"
                response += " ❌ (пересекается с занятыми датами)"
                callback_data = "ignore"
            else:
                # Сокращаем для уменьшения размера callback_data
                short_console_id = console_id[:8]
                callback_data = f"rd_{short_console_id}_{selected_date}_{hours}"
            
            response += "\n"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
        
        short_console_id = console_id[:8]
        markup.add(types.InlineKeyboardButton("⬅️ Выбрать другую дату", 
                                            callback_data=f"cal_{short_console_id}_{selected_date_obj.strftime('%Y-%m')}"))
        
        # Проверяем есть ли фото в сообщении
        try:
            if call.message.photo:
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                                    parse_mode='Markdown', reply_markup=markup)
        except Exception as e:
            print(f"Error in date selection: {e}")
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
            
    except Exception as e:
        print(f"Error in handle_date_selection: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка выбора даты")

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_time_'))
def handle_time_selection(call):
    user_id = str(call.from_user.id)
    console_id = call.data.split('_')[2]
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    consoles = load_json_file('consoles')
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль недоступна")
        return
    
    console = consoles[console_id]
    price_per_hour = console['rental_price']
    
    response = f"⏰ **Выберите время аренды**\n\n"
    response += f"🎮 Консоль: {console['name']}\n"
    response += f"💰 Цена: {price_per_hour} лей/час\n\n"
    response += f"📊 **Варианты аренды:**\n"
    
    # Создаем кнопки с вариантами времени и стоимостью
    markup = types.InlineKeyboardMarkup()
    time_options = [24, 48, 72, 168, 336]  # 1, 2, 3, 7, 14 дней в часах
    day_labels = [1, 2, 3, 7, 14]  # соответствующие дни
    
    for i, hours in enumerate(time_options):
        days = day_labels[i]
        original_cost = hours * price_per_hour
        
        # Применяем скидку если есть
        discounted_cost, discount_amount, discount_info = calculate_discounted_price(console_id, original_cost, hours)
        
        # Формируем текст с учетом скидки
        if discount_amount > 0:
            if days == 1:
                button_text = f"{days} день - {discounted_cost} лей 🔥"
                response += f"• {days} день = ~~{original_cost}~~ **{discounted_cost} лей** 🔥 (-{discount_amount} лей)\n"
            elif days in [2, 3, 4]:
                button_text = f"{days} дня - {discounted_cost} лей 🔥"
                response += f"• {days} дня = ~~{original_cost}~~ **{discounted_cost} лей** 🔥 (-{discount_amount} лей)\n"
            else:
                button_text = f"{days} дней - {discounted_cost} лей 🔥"
                response += f"• {days} дней = ~~{original_cost}~~ **{discounted_cost} лей** 🔥 (-{discount_amount} лей)\n"
        else:
            if days == 1:
                button_text = f"{days} день - {original_cost} лей"
                response += f"• {days} день = {original_cost} лей\n"
            elif days in [2, 3, 4]:
                button_text = f"{days} дня - {original_cost} лей"
                response += f"• {days} дня = {original_cost} лей\n"
            else:
                button_text = f"{days} дней - {original_cost} лей"
                response += f"• {days} дней = {original_cost} лей\n"
        
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"rent_{console_id}_{hours}"))
    
    markup.add(types.InlineKeyboardButton("⬅️ Назад к консоли", callback_data=f"console_{console_id}"))
    
    # Проверяем есть ли фото в сообщении
    try:
        if call.message.photo:
            # Если сообщение с фото, удаляем его и отправляем новое текстовое
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
        else:
            # Обычное текстовое сообщение - просто редактируем
            bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                                parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        # Fallback - удаляем старое и отправляем новое
        print(f"Error in handle_time_selection: {e}")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rd_'))
def handle_confirm_rent_with_date(call):
    """Обработка подтверждения аренды с конкретной датой"""
    user_id = str(call.from_user.id)
    data_parts = call.data.split('_')
    short_console_id = data_parts[1]  # Первые 8 символов
    selected_date = data_parts[2]  # YYYY-MM-DD
    selected_hours = int(data_parts[3])
    
    # Находим полный console_id по короткому ID
    consoles = load_json_file('consoles')
    console_id = None
    for cid in consoles.keys():
        if cid.startswith(short_console_id):
            console_id = cid
            break
    
    if not console_id:
        bot.answer_callback_query(call.id, "❌ Консоль не найдена")
        return
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    # Проверяем доступность консоли на выбранные даты
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    end_date_obj = selected_date_obj + timedelta(days=selected_hours//24)
    
    occupied_dates = get_occupied_dates(console_id)
    check_date = selected_date_obj
    while check_date < end_date_obj:
        if check_date in occupied_dates:
            bot.answer_callback_query(call.id, "❌ Выбранные даты больше недоступны")
            return
        check_date += timedelta(days=1)
    
    consoles = load_json_file('consoles')
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль недоступна")
        return
    
    console = consoles[console_id]
    original_cost = selected_hours * console['rental_price']
    
    # Применяем скидку если есть
    total_cost, discount_amount, discount_info = calculate_discounted_price(console_id, original_cost, selected_hours)
    
    # Форматируем даты для отображения
    start_date_formatted = selected_date_obj.strftime('%d.%m.%Y')
    end_date_formatted = end_date_obj.strftime('%d.%m.%Y')
    
    response = f"🎮 **Подтверждение аренды**\n\n"
    response += f"**Консоль:** {console['name']} ({console['model']})\n"
    response += f"**Период:** {start_date_formatted} - {end_date_formatted}\n"
    response += f"**Продолжительность:** {selected_hours//24} дн.\n"
    
    if discount_amount > 0:
        response += f"**Цена без скидки:** ~~{original_cost} лей~~\n"
        response += f"**Скидка:** -{discount_amount} лей 🔥\n"
        response += f"**Итоговая стоимость:** **{total_cost} лей**\n\n"
    else:
        response += f"**Стоимость:** {total_cost} лей\n\n"
    
    if console.get('games'):
        response += f"**Игры:**\n"
        for game in console['games']:
            response += f"• {game}\n"
        response += "\n"
    
    response += "Подтвердить аренду?"
    
    markup = types.InlineKeyboardMarkup()
    # Сокращаем console_id до первых 8 символов для уменьшения размера callback_data
    short_console_id = console_id[:8]
    confirm_callback = f"crd_{short_console_id}_{selected_date}_{selected_hours}"
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_callback))
    short_console_id = console_id[:8]
    markup.add(types.InlineKeyboardButton("⬅️ Выбрать другую дату", 
                                        callback_data=f"cal_{short_console_id}_{selected_date_obj.strftime('%Y-%m')}"))
    
    # Проверяем есть ли фото в сообщении
    try:
        if call.message.photo:
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                                parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        print(f"Error in rent confirmation: {e}")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(call.message.chat.id, response, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('crd_'))
def handle_final_rent_confirmation(call):
    """Финальное подтверждение аренды с датой"""
    user_id = str(call.from_user.id)
    data_parts = call.data.split('_')
    short_console_id = data_parts[1]  # Первые 8 символов
    selected_date = data_parts[2]  # YYYY-MM-DD
    selected_hours = int(data_parts[3])
    
    # Находим полный console_id по короткому ID
    consoles = load_json_file('consoles')
    console_id = None
    for cid in consoles.keys():
        if cid.startswith(short_console_id):
            console_id = cid
            break
    
    if not console_id:
        bot.answer_callback_query(call.id, "❌ Консоль не найдена")
        return
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    # Последняя проверка доступности
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
    end_date_obj = selected_date_obj + timedelta(hours=selected_hours)
    
    consoles = load_json_file('consoles')
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль уже недоступна")
        return
    
    users = load_json_file('users')
    user = users.get(user_id, {})
    
    if not user.get('phone_number') or not user.get('full_name'):
        bot.answer_callback_query(call.id, "❌ Необходимо завершить регистрацию")
        return
    
    console = consoles[console_id]
    original_cost = selected_hours * console['rental_price']
    
    # Применяем скидку если есть
    total_cost, discount_amount, discount_info = calculate_discounted_price(console_id, original_cost, selected_hours)
    
    # Создаем заявку на аренду
    rental_id = str(uuid.uuid4())
    
    rental_data = {
        'id': rental_id,
        'user_id': user_id,
        'console_id': console_id,
        'start_time': selected_date_obj.isoformat(),
        'estimated_end_time': end_date_obj.isoformat(),
        'duration_hours': selected_hours,
        'total_cost': total_cost,
        'status': 'pending_approval' if is_approval_required() else 'active',
        'created_at': datetime.now().isoformat()
    }
    
    # Сохраняем аренду
    if is_approval_required():
        # Сохраняем как заявку на аренду
        requests_data = load_json_file('rental_requests')
        requests_data[rental_id] = rental_data
        save_json_file('rental_requests', requests_data)
        
        response = f"📋 **Заявка на аренду отправлена!**\n\n"
        response += f"🎮 **Консоль:** {console['name']}\n"
        response += f"📅 **Период:** {selected_date_obj.strftime('%d.%m.%Y')} - {end_date_obj.strftime('%d.%m.%Y')}\n"
        response += f"💰 **Стоимость:** {total_cost} лей\n\n"
        response += f"⏳ Ожидайте подтверждения от администратора"
        
        # Уведомляем админа
        admin_id = get_admin_chat_id()
        if admin_id:
            # Экранируем специальные символы для Markdown
            def escape_markdown(text):
                if text is None:
                    return 'Неизвестно'
                # Экранируем специальные символы Markdown
                special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                for char in special_chars:
                    text = str(text).replace(char, f'\\{char}')
                return text
            
            full_name = escape_markdown(user.get('full_name', 'Неизвестно'))
            phone = escape_markdown(user.get('phone_number', 'Неизвестно'))
            console_name = escape_markdown(console['name'])
            
            admin_msg = f"📋 **Новая заявка на аренду!**\n\n"
            admin_msg += f"👤 **Пользователь:** {full_name}\n"
            admin_msg += f"📞 **Телефон:** {phone}\n"
            admin_msg += f"🎮 **Консоль:** {console_name}\n"
            admin_msg += f"📅 **Период:** {selected_date_obj.strftime('%d.%m.%Y')} - {end_date_obj.strftime('%d.%m.%Y')}\n"
            admin_msg += f"💰 **Стоимость:** {total_cost} лей\n"
            admin_msg += f"🆔 **ID заявки:** {rental_id}"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{rental_id}"),
                types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{rental_id}")
            )
            
            try:
                bot.send_message(admin_id, admin_msg, parse_mode='Markdown', reply_markup=markup)
            except Exception as e:
                print(f"Ошибка отправки уведомления админу: {e}")
    else:
        # Прямое подтверждение аренды
        rentals_data = load_json_file('rentals')
        rental_data['status'] = 'active'
        rentals_data[rental_id] = rental_data
        save_json_file('rentals', rentals_data)
        
        # Обновляем статус консоли
        consoles[console_id]['status'] = 'rented'
        save_json_file('consoles', consoles)
        
        response = f"✅ **Аренда подтверждена!**\n\n"
        response += f"🎮 **Консоль:** {console['name']}\n"
        response += f"📅 **Период:** {selected_date_obj.strftime('%d.%m.%Y')} - {end_date_obj.strftime('%d.%m.%Y')}\n"
        response += f"💰 **Стоимость:** {total_cost} лей\n"
        response += f"🆔 **ID аренды:** `{rental_id}`\n\n"
        response += f"📞 Свяжитесь с нами для получения консоли!"
    
    # Удаляем предыдущее сообщение и отправляем новое
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    bot.send_message(call.message.chat.id, response, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('rent_') and len(call.data.split('_')) == 3)
def handle_confirm_rent_with_time(call):
    user_id = str(call.from_user.id)
    data_parts = call.data.split('_')
    console_id = data_parts[1]
    selected_hours = int(data_parts[2])
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль недоступна")
        return
    
    console = consoles[console_id]
    user = users.get(user_id, {})
    original_cost = selected_hours * console['rental_price']
    
    # Применяем скидку если есть
    total_cost, discount_amount, discount_info = calculate_discounted_price(console_id, original_cost, selected_hours)
    
    # Показываем подтверждение аренды с выбранным временем
    selected_days = selected_hours // 24
    response = f"✅ **Подтвердите аренду**\n\n"
    response += f"🎮 Консоль: {console['name']}\n"
    if selected_days == 1:
        response += f"⏰ Время: {selected_days} день\n"
    elif selected_days in [2, 3, 4]:
        response += f"⏰ Время: {selected_days} дня\n"
    else:
        response += f"⏰ Время: {selected_days} дней\n"
    
    if discount_amount > 0:
        response += f"💰 Цена без скидки: ~~{original_cost} лей~~\n"
        response += f"🔥 Скидка: -{discount_amount} лей\n"
        response += f"💰 **К оплате: {total_cost} лей**\n\n"
    else:
        response += f"💰 К оплате: {total_cost} лей\n\n"
    response += f"Подтвердите аренду на выбранное время:"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_rent_{console_id}_{selected_hours}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data=f"select_time_{console_id}")
    )
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_selection')
def handle_back_to_selection(call):
    user_id = str(call.from_user.id)
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    consoles = load_json_file('consoles')
    
    if not consoles:
        safe_edit_message(call, "📭 Консоли пока недоступны")
        return
    
    response = "Выберите консоль для аренды:\n\n"
    markup = types.InlineKeyboardMarkup()
    
    for console_id, console in consoles.items():
        if console['status'] == 'available':
            button_text = f"{console['name']} - {console['rental_price']} лей/час"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"console_{console_id}"))
        else:
            button_text = f"{console['name']} - Занята"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=f"console_unavailable_{console_id}"))
    
    safe_edit_message(call, response, reply_markup=markup)

# Обработчики админских кнопок
@bot.message_handler(func=lambda message: message.text == '⚙️ Админ панель')
def admin_panel(message):
    user_id = str(message.from_user.id)
    
    if not is_user_admin(user_id):
        bot.reply_to(message, "❌ У вас нет доступа к админ панели.")
        return
    
    response = "⚙️ **Админ панель**\n\n"
    response += "Выберите действие:"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("📊 Заявки на аренду", callback_data="admin_requests")
    )
    markup.add(
        types.InlineKeyboardButton("⭐ Рейтинги", callback_data="admin_ratings"),
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")
    )
    markup.add(
        types.InlineKeyboardButton("🎮 Веб-панель", callback_data="admin_web_info")
    )
    
    bot.reply_to(message, response, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '📈 Статистика')
def admin_statistics(message):
    user_id = str(message.from_user.id)
    
    if not is_user_admin(user_id):
        bot.reply_to(message, "❌ У вас нет доступа к статистике.")
        return
    
    users = load_json_file('users')
    consoles = load_json_file('consoles')
    rentals = load_json_file('rentals')
    
    active_rentals = [r for r in rentals.values() if r['status'] == 'active']
    completed_rentals = [r for r in rentals.values() if r['status'] == 'completed']
    available_consoles = [c for c in consoles.values() if c['status'] == 'available']
    
    total_revenue = sum(r.get('total_cost', 0) for r in completed_rentals)
    
    response = "📈 **Статистика системы**\n\n"
    response += f"👥 Всего пользователей: {len(users)}\n"
    response += f"🎮 Всего консолей: {len(consoles)}\n"
    response += f"✅ Доступных консолей: {len(available_consoles)}\n"
    response += f"🔄 Активных аренд: {len(active_rentals)}\n"
    response += f"✅ Завершенных аренд: {len(completed_rentals)}\n"
    response += f"💰 Общая выручка: {total_revenue} лей\n\n"
    
    if active_rentals:
        response += "**Активные аренды:**\n"
        for rental in active_rentals[:5]:
            console = consoles.get(rental['console_id'], {})
            user = users.get(rental['user_id'], {})
            response += f"• {console.get('name', 'Неизвестная')} - {user.get('full_name', 'Неизвестный')}\n"
    
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '👥 Пользователи')
def admin_users(message):
    user_id = str(message.from_user.id)
    
    if not is_user_admin(user_id):
        bot.reply_to(message, "❌ У вас нет доступа к управлению пользователями.")
        return
    
    users = load_json_file('users')
    
    response = "👥 **Управление пользователями**\n\n"
    response += f"Всего пользователей: {len(users)}\n\n"
    response += "Выберите пользователя для управления:"
    
    # Показываем последних 10 пользователей
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('joined_at', ''), reverse=True)
    
    markup = types.InlineKeyboardMarkup()
    for uid, user in sorted_users[:10]:
        status = "🚫" if user.get('is_banned', False) else "✅"
        name = user.get('full_name', user.get('first_name', 'Неизвестный'))
        button_text = f"{status} {name[:20]}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"user_manage_{uid}"))
    
    bot.reply_to(message, response, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '🔔 Уведомления')
def admin_notifications(message):
    user_id = str(message.from_user.id)
    
    if not is_user_admin(user_id):
        bot.reply_to(message, "❌ У вас нет доступа к уведомлениям.")
        return
    
    rental_requests = load_json_file('rental_requests')
    pending_requests = [r for r in rental_requests.values() if r['status'] == 'pending']
    
    response = "🔔 **Уведомления**\n\n"
    
    if pending_requests:
        response += f"⏳ Ожидающих заявок: {len(pending_requests)}\n\n"
        for request in pending_requests[:5]:
            users = load_json_file('users')
            consoles = load_json_file('consoles')
            user = users.get(request['user_id'], {})
            console = consoles.get(request['console_id'], {})
            
            response += f"• {user.get('full_name', 'Неизвестный')} - {console.get('name', 'Неизвестная консоль')}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📋 Перейти к заявкам", callback_data="admin_requests"))
        bot.reply_to(message, response, parse_mode='Markdown', reply_markup=markup)
    else:
        response += "✅ Нет ожидающих заявок"
        bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Помощь')
def help_command(message):
    user_id = str(message.from_user.id)
    
    if is_user_admin(user_id):
        help_text = """
🎮 **Команды бота (Администратор):**



📱 **Основные функции:**
📝 Арендовать - Арендовать консоль

👨‍💼 **Админ функции:**
⚙️ Админ панель - Управление системой
📈 Статистика - Статистика системы
👥 Пользователи - Управление пользователями
🔔 Уведомления - Проверка заявок

🌐 **Веб-панель:** Доступна локально на порту 5000
"""
    else:
        help_text = """
🎮 **Команды бота:**



📱 **Основные функции:**
📊 Мой кабинет - Ваша статистика
📝 Арендовать - Арендовать консоль

🎯 **Игры и модели:**
• PlayStation 4 / PS4 Pro
• PlayStation 5
• Большой выбор игр

💳 **Оплата:**
После завершения аренды обратитесь к администратору
"""
    
    bot.reply_to(message, help_text, parse_mode='Markdown', reply_markup=get_keyboard_for_user(user_id))

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = str(message.from_user.id)
    
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Ваш аккаунт заблокирован.")
        return
    
    bot.reply_to(message, "🤔 Не понимаю эту команду. Используйте меню или /help", reply_markup=get_keyboard_for_user(user_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def handle_approve_request(call):
    admin_id = str(call.from_user.id)
    request_id = call.data.split('_')[1]
    
    # Проверяем, что это администратор
    if admin_id != get_admin_chat_id():
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    rental_requests = load_json_file('rental_requests')
    
    if request_id not in rental_requests:
        bot.answer_callback_query(call.id, "❌ Заявка не найдена")
        return
    
    request = rental_requests[request_id]
    
    if request['status'] not in ['pending', 'pending_approval']:
        bot.answer_callback_query(call.id, "❌ Заявка уже обработана")
        return
    
    # Проверяем доступность консоли
    consoles = load_json_file('consoles')
    console_id = request['console_id']
    
    if console_id not in consoles or consoles[console_id]['status'] != 'available':
        bot.answer_callback_query(call.id, "❌ Консоль больше недоступна")
        request['status'] = 'rejected'
        save_json_file('rental_requests', rental_requests)
        return
    
    # Одобряем заявку
    request['status'] = 'approved'
    save_json_file('rental_requests', rental_requests)
    
    # Создаем временную резервацию консоли (на 30 минут)
    create_temp_reservation(request['user_id'], console_id, timeout_minutes=30)
    
    # Получаем данные пользователя
    users = load_json_file('users')
    user = users.get(request['user_id'], {})
    console = consoles[console_id]
    user_full_name = user.get('full_name', user.get('first_name', f'user_{request["user_id"]}'))
    
    # Проверяем существующие документы
    existing_documents = check_user_documents(user_full_name, request['user_id'])
    all_documents_exist = all(existing_documents.values())
    
    if all_documents_exist:
        # Все документы уже загружены - сразу запрашиваем геолокацию
        users[request['user_id']]['verification_step'] = 'location_request'
        users[request['user_id']]['pending_rental_id'] = console_id
        save_json_file('users', users)
        
        user_message = f"✅ **Ваша заявка одобрена!**\n\n"
        user_message += f"🎮 Консоль: {console['name']}\n"
        user_message += f"💰 Цена: {console['rental_price']} лей/час\n\n"
        user_message += f"📄 **Паспорт верифицирован** ✅\n"
        user_message += f"(Документы уже загружены ранее)\n\n"
        user_message += f"📍 **Финальный шаг:** Отправьте свою геолокацию для начала аренды\n\n" 
        user_message += f"⚠️ **ВАЖНО:** Отправляйте геолокацию только когда будете готовы получить консоль!\n"
        user_message += f"Нажмите кнопку ниже для отправки геолокации"
        
        # Создаем кнопку для отправки геолокации
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        location_button = types.KeyboardButton('📍 Отправить геолокацию', request_location=True)
        markup.add(location_button)
    else:
        # Нужна верификация документов
        users[request['user_id']]['verification_step'] = 'passport_front'
        users[request['user_id']]['pending_rental_id'] = console_id
        save_json_file('users', users)
        
        user_message = f"✅ **Ваша заявка одобрена!**\n\n"
        user_message += f"🎮 Консоль: {console['name']}\n"
        user_message += f"💰 Цена: {console['rental_price']} лей/час\n\n"
        user_message += f"📄 **Для начала аренды необходима верификация документов**\n\n"
        user_message += f"**Шаг 1 из 3:** Отправьте фото **ПЕРЕДНЕЙ стороны паспорта**\n\n"
        user_message += f"⚠️ **Требования к фото:**\n"
        user_message += f"• Четкое изображение без бликов\n"
        user_message += f"• Все данные должны быть читаемыми\n"
        user_message += f"• Фото целиком, без обрезанных краев\n\n"
        user_message += f"📷 Отправьте фото как обычное изображение"
        
        # Убираем все кнопки меню
        markup = types.ReplyKeyboardRemove()
    
    try:
        bot.send_message(request['user_id'], user_message, parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю: {e}")
    
    # Обновляем сообщение администратора
    admin_update_message = f"✅ **Заявка одобрена**\n\n"
    admin_update_message += f"👤 {user.get('full_name', 'Неизвестный')}\n"
    admin_update_message += f"🎮 {console['name']}\n"
    
    if all_documents_exist:
        admin_update_message += f"📄 Паспорт верифицирован ✅\n"
        admin_update_message += f"📍 Ожидает геолокацию для начала аренды\n"
    else:
        admin_update_message += f"📄 Ожидает загрузку документов\n"
    
    admin_update_message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    bot.edit_message_text(
        admin_update_message,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def handle_reject_request(call):
    admin_id = str(call.from_user.id)
    request_id = call.data.split('_')[1]
    
    # Проверяем, что это администратор
    if admin_id != get_admin_chat_id():
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    rental_requests = load_json_file('rental_requests')
    
    if request_id not in rental_requests:
        bot.answer_callback_query(call.id, "❌ Заявка не найдена")
        return
    
    request = rental_requests[request_id]
    
    if request['status'] not in ['pending', 'pending_approval']:
        bot.answer_callback_query(call.id, "❌ Заявка уже обработана")
        return
    
    # Отклоняем заявку и удаляем резервацию
    request['status'] = 'rejected'
    remove_temp_reservation(request['user_id'])
    save_json_file('rental_requests', rental_requests)
    
    # Уведомляем пользователя
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    user = users.get(request['user_id'], {})
    console = consoles.get(request['console_id'], {})
    
    user_message = f"❌ **Ваша заявка отклонена**\n\n"
    user_message += f"🎮 Консоль: {console.get('name', 'Неизвестная консоль')}\n"
    user_message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    user_message += f"Попробуйте арендовать другую консоль или обратитесь к администратору."
    
    # Очищаем статусы пользователя
    if request['user_id'] in users:
        users[request['user_id']]['verification_step'] = None
        users[request['user_id']]['pending_rental_id'] = None
        save_json_file('users', users)
    
    try:
        bot.send_message(request['user_id'], user_message, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю: {e}")
    
    # Обновляем сообщение администратора
    bot.edit_message_text(
        f"❌ **Заявка отклонена**\n\n"
        f"👤 {user.get('full_name', 'Неизвестный')}\n"
        f"🎮 {console.get('name', 'Неизвестная консоль')}\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('end_rental_'))
def handle_end_rental_callback(call):
    user_id = str(call.from_user.id)
    rental_id = call.data.split('_')[2]
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "❌ Ваш аккаунт заблокирован.")
        return
    
    # Завершаем аренду
    result = end_rental_by_id(user_id, rental_id)
    
    if result['success']:
        response = f"✅ **Аренда завершена!**\n\n"
        response += f"🎮 Консоль: {result['console_name']}\n"
        response += f"⏰ Длительность: {result['hours']} часов\n"
        response += f"💰 К оплате: {result['total_cost']} лей\n\n"
        response += f"Спасибо за использование нашего сервиса!"
        
        # Уведомляем администратора
        admin_message = f"🏁 **Аренда завершена пользователем**\n\n"
        admin_message += f"👤 {result.get('user_name', 'Неизвестный')}\n"
        admin_message += f"📱 {result.get('user_phone', 'Не указан')}\n"
        admin_message += f"🎮 {result['console_name']}\n"
        admin_message += f"⏰ {result['hours']} часов\n"
        admin_message += f"💰 {result['total_cost']} лей"
        
        notify_admin(admin_message)
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    else:
        bot.answer_callback_query(call.id, f"❌ {result['error']}")

def end_rental_by_id(user_id, rental_id):
    """Завершение аренды по ID"""
    rentals = load_json_file('rentals')
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    
    if rental_id not in rentals:
        return {'success': False, 'error': 'Аренда не найдена'}
    
    rental = rentals[rental_id]
    
    if rental['user_id'] != user_id:
        return {'success': False, 'error': 'Это не ваша аренда'}
    
    if rental['status'] != 'active':
        return {'success': False, 'error': 'Аренда уже завершена'}
    
    # Рассчитываем стоимость
    start_time = datetime.fromisoformat(rental['start_time'])
    end_time = datetime.now()
    duration = end_time - start_time
    hours = max(1, int(duration.total_seconds() / 3600))
    
    console = consoles[rental['console_id']]
    total_cost = hours * console['rental_price']
    
    # Завершаем аренду
    rental['end_time'] = end_time.isoformat()
    rental['status'] = 'completed'
    rental['total_cost'] = total_cost
    
    # Освобождаем консоль
    console['status'] = 'available'
    
    # Обновляем статистику пользователя
    if user_id in users:
        users[user_id]['total_spent'] = users[user_id].get('total_spent', 0) + total_cost
    
    # Сохраняем изменения
    save_json_file('rentals', rentals)
    save_json_file('consoles', consoles)
    save_json_file('users', users)
    
    # Обновляем рейтинг пользователя
    update_rating_on_rental_completion(user_id, rental)
    
    user = users.get(user_id, {})
    
    return {
        'success': True,
        'console_name': console['name'],
        'hours': hours,
        'total_cost': total_cost,
        'user_name': user.get('full_name', user.get('first_name', 'Неизвестный')),
        'user_phone': user.get('phone_number', 'Не указан')
    }

# Callback обработчики для админ панели
@bot.callback_query_handler(func=lambda call: call.data == 'admin_web_info')
def handle_admin_web_info(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    response = "🌐 **Веб-панель администратора**\n\n"
    response += "Для доступа к полной веб-панели управления:\n\n"
    response += "1️⃣ Откройте браузер\n"
    response += "2️⃣ Перейдите по адресу: `http://localhost:5000`\n"
    response += "3️⃣ Войдите как администратор\n\n"
    response += "В веб-панели доступно:\n"
    response += "• Управление консолями\n"
    response += "• Просмотр заявок на аренду\n"
    response += "• Настройки системы\n"
    response += "• Детальная статистика"
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'admin_requests')
def handle_admin_requests(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    rental_requests = load_json_file('rental_requests')
    pending_requests = [r for r in rental_requests.values() if r['status'] == 'pending']
    
    response = "📊 **Заявки на аренду**\n\n"
    
    if pending_requests:
        response += f"⏳ Ожидающих заявок: {len(pending_requests)}\n\n"
        
        users = load_json_file('users')
        consoles = load_json_file('consoles')
        
        markup = types.InlineKeyboardMarkup()
        
        for request in pending_requests[:5]:
            user = users.get(request['user_id'], {})
            console = consoles.get(request['console_id'], {})
            
            response += f"👤 **{user.get('full_name', 'Неизвестный')}**\n"
            response += f"🎮 {console.get('name', 'Неизвестная консоль')}\n"
            response += f"💰 {console.get('rental_price', 0)} лей/час\n"
            response += f"⏰ {request.get('request_time', '')[:16]}\n\n"
            
            # Кнопки для каждой заявки
            markup.add(
                types.InlineKeyboardButton(f"✅ Одобрить {user.get('full_name', '')[:10]}", 
                                         callback_data=f"approve_{request['id']}"),
                types.InlineKeyboardButton(f"❌ Отклонить {user.get('full_name', '')[:10]}", 
                                         callback_data=f"reject_{request['id']}")
            )
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                             parse_mode='Markdown', reply_markup=markup)
    else:
        response += "✅ Нет ожидающих заявок"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'admin_settings')
def handle_admin_settings(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    settings = load_json_file('admin_settings')
    
    response = "⚙️ **Настройки системы**\n\n"
    response += f"🕒 Макс. время аренды: {settings.get('max_rental_hours', 24)} часов\n"
    response += f"⏰ Напоминание за: {settings.get('reminder_hours', 23)} часов\n"
    response += f"✅ Требовать подтверждение: {'Да' if settings.get('require_approval', True) else 'Нет'}\n"
    response += f"🔔 Уведомления: {'Включены' if settings.get('notifications_enabled', True) else 'Отключены'}\n\n"
    response += "Для изменения настроек используйте веб-панель"
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == 'admin_ratings')
def handle_admin_ratings(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    users = load_json_file('users')
    ratings_data = load_json_file('ratings')
    
    response = "⭐ **Управление рейтингами**\n\n"
    response += f"Всего пользователей: {len(users)}\n"
    response += f"Пользователей с рейтингом: {len(ratings_data.get('user_ratings', {}))}\n\n"
    response += "Выберите пользователя для управления рейтингом:"
    
    # Показываем пользователей с рейтингами
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('joined_at', ''), reverse=True)
    
    markup = types.InlineKeyboardMarkup()
    for uid, user in sorted_users[:10]:
        name = user.get('full_name', user.get('first_name', 'Неизвестный'))
        try:
            rating = calculate_user_final_rating(uid)
            if rating:
                button_text = f"⭐ {name[:15]} ({rating['final_score']})"
            else:
                button_text = f"➖ {name[:15]} (без рейтинга)"
        except:
            button_text = f"➖ {name[:15]} (без рейтинга)"
        
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"rating_manage_{uid}"))
    
    markup.add(types.InlineKeyboardButton("📊 Статистика рейтингов", callback_data="rating_stats"))
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_users')
def handle_admin_users_callback(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    users = load_json_file('users')
    
    response = "👥 **Управление пользователями**\n\n"
    response += f"Всего пользователей: {len(users)}\n\n"
    
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('joined_at', ''), reverse=True)
    
    markup = types.InlineKeyboardMarkup()
    for uid, user in sorted_users[:10]:
        status = "🚫" if user.get('is_banned', False) else "✅"
        name = user.get('full_name', user.get('first_name', 'Неизвестный'))
        button_text = f"{status} {name[:20]}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"user_manage_{uid}"))
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('user_manage_'))
def handle_user_manage(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    users = load_json_file('users')
    
    if user_id not in users:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")
        return
    
    user = users[user_id]
    is_banned = user.get('is_banned', False)
    
    response = f"👤 **Пользователь:** {user.get('full_name', 'Неизвестный')}\n\n"
    response += f"📱 Телефон: {user.get('phone_number', 'Не указан')}\n"
    response += f"🆔 ID: `{user_id}`\n"
    response += f"📅 Регистрация: {user.get('joined_at', '')[:10]}\n"
    response += f"💰 Потрачено: {user.get('total_spent', 0)} лей\n"
    response += f"🚫 Статус: {'Заблокирован' if is_banned else 'Активен'}\n"
    
    markup = types.InlineKeyboardMarkup()
    if is_banned:
        markup.add(types.InlineKeyboardButton("✅ Разблокировать", callback_data=f"unban_user_{user_id}"))
    else:
        markup.add(types.InlineKeyboardButton("🚫 Заблокировать", callback_data=f"ban_user_{user_id}"))
    
    markup.add(types.InlineKeyboardButton("📍 Запросить геолокацию", callback_data=f"request_location_{user_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_users"))
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ban_user_'))
def handle_ban_user(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    users = load_json_file('users')
    
    if user_id in users:
        users[user_id]['is_banned'] = True
        save_json_file('users', users)
        
        bot.answer_callback_query(call.id, "✅ Пользователь заблокирован")
        
        # Уведомляем пользователя
        try:
            bot.send_message(user_id, "🚫 Ваш аккаунт был заблокирован администратором.")
        except:
            pass
        
        # Обновляем сообщение с новой информацией
        user = users[user_id]
        is_banned = user.get('is_banned', False)
        
        response = f"👤 **Пользователь:** {user.get('full_name', 'Неизвестный')}\n\n"
        response += f"📱 Телефон: {user.get('phone_number', 'Не указан')}\n"
        response += f"🆔 ID: `{user_id}`\n"
        response += f"📅 Регистрация: {user.get('joined_at', '')[:10]}\n"
        response += f"💰 Потрачено: {user.get('total_spent', 0)} лей\n"
        response += f"🚫 Статус: {'Заблокирован' if is_banned else 'Активен'}\n"
        response += f"⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        
        markup = types.InlineKeyboardMarkup()
        if is_banned:
            markup.add(types.InlineKeyboardButton("✅ Разблокировать", callback_data=f"unban_user_{user_id}"))
        else:
            markup.add(types.InlineKeyboardButton("🚫 Заблокировать", callback_data=f"ban_user_{user_id}"))
        
        markup.add(types.InlineKeyboardButton("📍 Запросить геолокацию", callback_data=f"request_location_{user_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_users"))
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                             parse_mode='Markdown', reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")

@bot.callback_query_handler(func=lambda call: call.data.startswith('unban_user_'))
def handle_unban_user(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    users = load_json_file('users')
    
    if user_id in users:
        users[user_id]['is_banned'] = False
        save_json_file('users', users)
        
        bot.answer_callback_query(call.id, "✅ Пользователь разблокирован")
        
        # Уведомляем пользователя
        try:
            bot.send_message(user_id, "✅ Ваш аккаунт был разблокирован администратором.")
        except:
            pass
        
        # Обновляем сообщение с новой информацией
        user = users[user_id]
        is_banned = user.get('is_banned', False)
        
        response = f"👤 **Пользователь:** {user.get('full_name', 'Неизвестный')}\n\n"
        response += f"📱 Телефон: {user.get('phone_number', 'Не указан')}\n"
        response += f"🆔 ID: `{user_id}`\n"
        response += f"📅 Регистрация: {user.get('joined_at', '')[:10]}\n"
        response += f"💰 Потрачено: {user.get('total_spent', 0)} лей\n"
        response += f"🚫 Статус: {'Заблокирован' if is_banned else 'Активен'}\n"
        response += f"⏰ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        
        markup = types.InlineKeyboardMarkup()
        if is_banned:
            markup.add(types.InlineKeyboardButton("✅ Разблокировать", callback_data=f"unban_user_{user_id}"))
        else:
            markup.add(types.InlineKeyboardButton("🚫 Заблокировать", callback_data=f"ban_user_{user_id}"))
        
        markup.add(types.InlineKeyboardButton("📍 Запросить геолокацию", callback_data=f"request_location_{user_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_users"))
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                             parse_mode='Markdown', reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")

@bot.callback_query_handler(func=lambda call: call.data.startswith('request_location_'))
def handle_request_location(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    users = load_json_file('users')
    
    if user_id not in users:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")
        return
    
    user = users[user_id]
    
    # Отправляем запрос геолокации пользователю
    try:
        location_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        location_button = types.KeyboardButton('📍 Отправить мою геолокацию', request_location=True)
        location_markup.add(location_button)
        
        user_message = f"📍 **Запрос геолокации от администратора**\n\n"
        user_message += f"Администратор запросил вашу текущую геолокацию.\n"
        user_message += f"Нажмите кнопку ниже, чтобы отправить ее."
        
        bot.send_message(user_id, user_message, parse_mode='Markdown', reply_markup=location_markup)
        
        bot.answer_callback_query(call.id, "✅ Запрос отправлен пользователю")
        
        # Уведомляем админа об отправке запроса
        admin_response = f"✅ **Запрос геолокации отправлен**\n\n"
        admin_response += f"👤 Пользователь: {user.get('full_name', 'Неизвестный')}\n"
        admin_response += f"📱 Телефон: {user.get('phone_number', 'Не указан')}\n"
        admin_response += f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        admin_response += f"Пользователь получил запрос на отправку геолокации."
        
        bot.edit_message_text(admin_response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Ошибка отправки запроса геолокации: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка отправки запроса")

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_users')
def handle_back_to_users(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    users = load_json_file('users')
    
    response = "👥 **Управление пользователями**\n\n"
    response += f"Всего пользователей: {len(users)}\n\n"
    response += "Выберите пользователя для управления:"
    
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('joined_at', ''), reverse=True)
    
    markup = types.InlineKeyboardMarkup()
    for uid, user in sorted_users[:10]:
        status = "🚫" if user.get('is_banned', False) else "✅"
        name = user.get('full_name', user.get('first_name', 'Неизвестный'))
        button_text = f"{status} {name[:20]}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=f"user_manage_{uid}"))
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rating_manage_'))
def handle_rating_manage(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    users = load_json_file('users')
    
    if user_id not in users:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")
        return
    
    user = users[user_id]
    
    try:
        rating = calculate_user_final_rating(user_id)
        if rating:
            response = f"⭐ **Рейтинг пользователя:** {user.get('full_name', 'Неизвестный')}\n\n"
            response += f"🏆 Общий балл: {rating['final_score']}/100\n"
            response += f"📏 Дисциплина: {rating['discipline']}/100\n"
            response += f"❤️ Лояльность: {rating['loyalty']}/100\n"
            response += f"🎖️ Статус: {rating['status_name']}\n\n"
            
            # Показываем последние транзакции
            ratings_data = load_json_file('ratings')
            user_transactions = ratings_data.get('transactions', {}).get(user_id, [])
            if user_transactions:
                response += "📋 **Последние изменения:**\n"
                for transaction in user_transactions[-3:]:
                    response += f"• {transaction.get('type', 'unknown')}: {transaction.get('points', 0)} баллов\n"
                    response += f"  {transaction.get('comment', '')} ({transaction.get('date', '')[:10]})\n"
        else:
            response = f"⭐ **Рейтинг пользователя:** {user.get('full_name', 'Неизвестный')}\n\n"
            response += "📊 У пользователя пока нет рейтинга\n\n"
    except Exception as e:
        response = f"❌ Ошибка загрузки рейтинга: {str(e)}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ Добавить дисциплину", callback_data=f"add_discipline_{user_id}"),
        types.InlineKeyboardButton("➖ Снять дисциплину", callback_data=f"sub_discipline_{user_id}")
    )
    markup.add(
        types.InlineKeyboardButton("❤️ Добавить лояльность", callback_data=f"add_loyalty_{user_id}"),
        types.InlineKeyboardButton("🎁 Бонус лояльности", callback_data=f"loyalty_bonus_{user_id}")
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_ratings"))
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'rating_stats')
def handle_rating_stats(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    users = load_json_file('users')
    ratings_data = load_json_file('ratings')
    
    # Подсчитываем статистику
    total_users = len(users)
    users_with_rating = len(ratings_data.get('user_ratings', {}))
    
    premium_count = 0
    regular_count = 0
    risk_count = 0
    total_score = 0
    
    for user_id in users.keys():
        try:
            rating = calculate_user_final_rating(user_id)
            if rating:
                total_score += rating['final_score']
                status = rating['status_name']
                if status == 'Premium':
                    premium_count += 1
                elif status == 'Regular':
                    regular_count += 1
                else:
                    risk_count += 1
        except:
            continue
    
    avg_score = total_score / users_with_rating if users_with_rating > 0 else 0
    
    response = "📊 **Статистика рейтингов**\n\n"
    response += f"👥 Всего пользователей: {total_users}\n"
    response += f"⭐ С рейтингом: {users_with_rating}\n"
    response += f"📈 Средний балл: {avg_score:.1f}/100\n\n"
    response += "**Распределение по статусам:**\n"
    response += f"🏆 Premium: {premium_count}\n"
    response += f"⭐ Regular: {regular_count}\n"
    response += f"⚠️ Risk: {risk_count}\n\n"
    
    # Показываем топ пользователей
    top_users = []
    for user_id in users.keys():
        try:
            rating = calculate_user_final_rating(user_id)
            if rating:
                user = users[user_id]
                top_users.append({
                    'name': user.get('full_name', 'Неизвестный'),
                    'score': rating['final_score']
                })
        except:
            continue
    
    top_users.sort(key=lambda x: x['score'], reverse=True)
    
    if top_users:
        response += "🏆 **Топ-5 пользователей:**\n"
        for i, user in enumerate(top_users[:5], 1):
            response += f"{i}. {user['name'][:20]} - {user['score']}/100\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_ratings"))
    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, 
                         parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_discipline_'))
def handle_add_discipline(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    
    # Добавляем положительные баллы дисциплины
    import json
    import datetime
    
    ratings_data = load_json_file('ratings')
    
    if 'transactions' not in ratings_data:
        ratings_data['transactions'] = {}
    if user_id not in ratings_data['transactions']:
        ratings_data['transactions'][user_id] = []
    
    transaction = {
        'type': 'discipline_bonus',
        'points': 10,
        'comment': 'Ручное добавление администратором',
        'date': datetime.datetime.now().isoformat(),
        'admin_id': admin_id
    }
    
    ratings_data['transactions'][user_id].append(transaction)
    
    with open('ratings', 'w', encoding='utf-8') as f:
        json.dump(ratings_data, f, ensure_ascii=False, indent=2)
    
    bot.answer_callback_query(call.id, "✅ Добавлено +10 баллов дисциплины")
    
    # Перенаправляем обратно к управлению рейтингом
    call.data = f"rating_manage_{user_id}"
    handle_rating_manage(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_discipline_'))
def handle_sub_discipline(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    
    # Снимаем баллы дисциплины
    import json
    import datetime
    
    ratings_data = load_json_file('ratings')
    
    if 'transactions' not in ratings_data:
        ratings_data['transactions'] = {}
    if user_id not in ratings_data['transactions']:
        ratings_data['transactions'][user_id] = []
    
    transaction = {
        'type': 'discipline_penalty',
        'points': -15,
        'comment': 'Нарушение правил (ручное снятие)',
        'date': datetime.datetime.now().isoformat(),
        'admin_id': admin_id
    }
    
    ratings_data['transactions'][user_id].append(transaction)
    
    with open('ratings', 'w', encoding='utf-8') as f:
        json.dump(ratings_data, f, ensure_ascii=False, indent=2)
    
    bot.answer_callback_query(call.id, "❌ Снято -15 баллов дисциплины")
    
    # Перенаправляем обратно к управлению рейтингом
    call.data = f"rating_manage_{user_id}"
    handle_rating_manage(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_loyalty_'))
def handle_add_loyalty(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    
    # Добавляем баллы лояльности
    import json
    import datetime
    
    ratings_data = load_json_file('ratings')
    
    if 'transactions' not in ratings_data:
        ratings_data['transactions'] = {}
    if user_id not in ratings_data['transactions']:
        ratings_data['transactions'][user_id] = []
    
    transaction = {
        'type': 'loyalty_bonus',
        'points': 5,
        'comment': 'Повторная аренда (ручное добавление)',
        'date': datetime.datetime.now().isoformat(),
        'admin_id': admin_id
    }
    
    ratings_data['transactions'][user_id].append(transaction)
    
    with open('ratings', 'w', encoding='utf-8') as f:
        json.dump(ratings_data, f, ensure_ascii=False, indent=2)
    
    bot.answer_callback_query(call.id, "✅ Добавлено +5 баллов лояльности")
    
    # Перенаправляем обратно к управлению рейтингом
    call.data = f"rating_manage_{user_id}"
    handle_rating_manage(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('loyalty_bonus_'))
def handle_loyalty_bonus(call):
    admin_id = str(call.from_user.id)
    
    if not is_user_admin(admin_id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав администратора")
        return
    
    user_id = call.data.split('_')[2]
    
    # Добавляем специальный бонус лояльности
    import json
    import datetime
    
    ratings_data = load_json_file('ratings')
    
    if 'transactions' not in ratings_data:
        ratings_data['transactions'] = {}
    if user_id not in ratings_data['transactions']:
        ratings_data['transactions'][user_id] = []
    
    transaction = {
        'type': 'special_loyalty_bonus',
        'points': 15,
        'comment': 'Специальный бонус от администрации',
        'date': datetime.datetime.now().isoformat(),
        'admin_id': admin_id
    }
    
    ratings_data['transactions'][user_id].append(transaction)
    
    with open('ratings', 'w', encoding='utf-8') as f:
        json.dump(ratings_data, f, ensure_ascii=False, indent=2)
    
    bot.answer_callback_query(call.id, "🎁 Добавлен специальный бонус +15 баллов")
    
    # Перенаправляем обратно к управлению рейтингом
    call.data = f"rating_manage_{user_id}"
    handle_rating_manage(call)

# Общий обработчик всех callback для отладки (должен быть последним)
@bot.callback_query_handler(func=lambda call: True)
def debug_all_callbacks(call):
    print(f"DEBUG: UNHANDLED CALLBACK RECEIVED: {call.data}")
    bot.answer_callback_query(call.id, "❌ Неизвестная команда callback")

if __name__ == '__main__':
    print("🤖 Telegram бот запущен...")
    bot.polling(none_stop=True)