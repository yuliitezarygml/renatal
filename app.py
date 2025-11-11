from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from werkzeug.utils import secure_filename
import json
import os
import sys
import shutil
from datetime import datetime, timedelta, date
import uuid
from config import TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID, SECRET_KEY
from database import get_db_manager, init_db
from rating_system import calculate_user_rating_manual

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

PASSPORT_DIR = 'passport'

# Получаем менеджер БД
db = get_db_manager()

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
    except Exception as e:
        print(f"❌ Ошибка сохранения в {collection_name}: {e}")

def get_console_photo_path(console_id):
    """Получить путь к фото консоли если существует"""
    console_images_dir = os.path.join('static', 'img', 'console')
    allowed_extensions = ['png', 'jpg', 'jpeg', 'gif', 'webp']
    
    for ext in allowed_extensions:
        file_path = os.path.join(console_images_dir, f"{console_id}.{ext}")
        if os.path.exists(file_path):
            return f"/static/img/console/{console_id}.{ext}"
    return None

def allowed_file(filename):
    """Проверить допускается ли расширение файла"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    admins = load_json_file('admins')
    if user_id in admins:
        return User(user_id)
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        admins = load_json_file('admins')
        if username in admins and admins[username]['password'] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('admin'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    rentals = load_json_file('rentals')
    rental_requests = load_json_file('rental_requests')
    admin_settings = load_json_file('admin_settings')
    
    # Добавляем пути к фото для каждой консоли
    for console_id, console in consoles.items():
        photo_path = get_console_photo_path(console_id)
        if photo_path:
            console['photo_path'] = photo_path
    
    discounts = load_json_file('discounts')
    
    return render_template('admin.html', 
                         consoles=consoles, 
                         users=users, 
                         rentals=rentals,
                         rental_requests=rental_requests,
                         admin_settings=admin_settings,
                         discounts=discounts)

@app.route('/admin/ratings')
@login_required
def admin_ratings():
    """Страница управления рейтингами пользователей"""
    return render_template('ratings.html')

@app.route('/api/consoles', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def manage_consoles():
    consoles = load_json_file('consoles')
    
    if request.method == 'POST':
        data = request.json
        console_id = str(uuid.uuid4())
        consoles[console_id] = {
            'id': console_id,
            'name': data['name'],
            'model': data['model'],
            'games': data.get('games', []),
            'rental_price': data['rental_price'],
            'sale_price': data.get('sale_price', 0),
            'show_photo_in_bot': data.get('show_photo_in_bot', True),
            'status': 'available',
            'created_at': datetime.now().isoformat()
        }
        save_json_file('consoles', consoles)
        return jsonify({'status': 'success', 'console': consoles[console_id]})
    
    elif request.method == 'PUT':
        data = request.json
        console_id = data.get('console_id')
        
        if not console_id:
            return jsonify({'status': 'error', 'message': 'ID консоли не указан'})
        
        if console_id not in consoles:
            return jsonify({'status': 'error', 'message': 'Консоль не найдена'})
        
        # Обновляем данные консоли
        console = consoles[console_id]
        console['name'] = data.get('name', console['name'])
        console['model'] = data.get('model', console['model'])
        console['games'] = data.get('games', console.get('games', []))
        console['rental_price'] = data.get('rental_price', console['rental_price'])
        console['sale_price'] = data.get('sale_price', console.get('sale_price', 0))
        console['show_photo_in_bot'] = data.get('show_photo_in_bot', console.get('show_photo_in_bot', True))
        console['updated_at'] = datetime.now().isoformat()
        
        # Обновляем путь к фото если передан
        if 'photo_path' in data:
            console['photo_path'] = data['photo_path']
        
        save_json_file('consoles', consoles)
        return jsonify({'status': 'success', 'console': console})
    
    elif request.method == 'DELETE':
        console_id = request.json.get('console_id')
        if console_id in consoles:
            del consoles[console_id]
            save_json_file('consoles', consoles)
            return jsonify({'status': 'success'})
    
    return jsonify(consoles)

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_users():
    users = load_json_file('users')
    
    if request.method == 'POST':
        action = request.json.get('action')
        user_id = request.json.get('user_id')
        
        if user_id in users:
            if action == 'ban':
                users[user_id]['is_banned'] = True
            elif action == 'unban':
                users[user_id]['is_banned'] = False
            save_json_file('users', users)
        
        return jsonify({'status': 'success'})
    
    elif request.method == 'DELETE':
        user_id = request.json.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ID пользователя не указан'})
        
        if user_id not in users:
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        try:
            # Сохраняем данные пользователя до удаления для удаления документов
            deleted_user = users[user_id]
            user_full_name = deleted_user.get('full_name', deleted_user.get('first_name', f'user_{user_id}'))
            
            # Удаляем пользователя из базы
            del users[user_id]
            save_json_file('users', users)
            
            # Удаляем связанные данные пользователя
            rentals = load_json_file('rentals')
            rental_requests = load_json_file('rental_requests')
            
            # Удаляем аренды пользователя
            rentals_to_delete = [rental_id for rental_id, rental in rentals.items() if rental.get('user_id') == user_id]
            for rental_id in rentals_to_delete:
                del rentals[rental_id]
            
            # Удаляем заявки пользователя
            requests_to_delete = [req_id for req_id, req in rental_requests.items() if req.get('user_id') == user_id]
            for req_id in requests_to_delete:
                del rental_requests[req_id]
            
            # Сохраняем обновленные данные
            save_json_file('rentals', rentals)
            save_json_file('rental_requests', rental_requests)
            
            # Пытаемся удалить папку с документами пользователя
            import shutil
            safe_name = "".join(c for c in user_full_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            user_docs_folder = os.path.join(PASSPORT_DIR, safe_name)
            if os.path.exists(user_docs_folder):
                shutil.rmtree(user_docs_folder)
            
            return jsonify({
                'status': 'success', 
                'message': 'Пользователь и все связанные данные удалены',
                'deleted_rentals': len(rentals_to_delete),
                'deleted_requests': len(requests_to_delete)
            })
            
        except Exception as e:
            print(f"Ошибка удаления пользователя: {e}")
            return jsonify({
                'status': 'error', 
                'message': f'Ошибка при удалении: {str(e)}'
            })
    
    return jsonify({'success': True, 'users': users})

@app.route('/api/rentals', methods=['GET', 'POST'])
@login_required
def manage_rentals():
    rentals = load_json_file('rentals')
    
    if request.method == 'GET':
        return jsonify(rentals)
    
    action = request.json.get('action')
    rental_id = request.json.get('rental_id')
    
    consoles = load_json_file('consoles')
    users = load_json_file('users')
    
    if action == 'end' and rental_id in rentals:
        rental = rentals[rental_id]
        
        if rental['status'] == 'active':
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
            user_id = rental['user_id']
            if user_id in users:
                users[user_id]['total_spent'] = users[user_id].get('total_spent', 0) + total_cost
            
            # Сохраняем изменения
            save_json_file('rentals', rentals)
            save_json_file('consoles', consoles)
            save_json_file('users', users)
            
            # Отправляем уведомление пользователю о завершении аренды
            try:
                from bot import bot, notify_user_about_rental_end
                notify_user_about_rental_end(user_id, rental['console_id'], total_cost, hours)
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю о завершении аренды: {e}")
            
            return jsonify({
                'status': 'success',
                'total_cost': total_cost,
                'hours': hours
            })
    
    return jsonify({'status': 'error', 'message': 'Аренда не найдена или уже завершена'})

@app.route('/api/admin/settings', methods=['GET', 'POST'])
@login_required
def manage_admin_settings():
    settings = load_json_file('admin_settings')
    
    if request.method == 'POST':
        data = request.json
        
        if 'admin_chat_id' in data:
            settings['admin_chat_id'] = str(data['admin_chat_id'])
        
        if 'require_approval' in data:
            settings['require_approval'] = bool(data['require_approval'])
        
        if 'notifications_enabled' in data:
            settings['notifications_enabled'] = bool(data['notifications_enabled'])
        
        if 'max_rental_hours' in data:
            settings['max_rental_hours'] = int(data['max_rental_hours'])
        
        if 'reminder_hours' in data:
            settings['reminder_hours'] = int(data['reminder_hours'])
        
        save_json_file('admin_settings', settings)
        return jsonify({'status': 'success', 'settings': settings})
    
    return jsonify(settings)

@app.route('/api/rental-requests', methods=['GET', 'POST'])
@login_required
def manage_rental_requests():
    rental_requests = load_json_file('rental_requests')
    
    if request.method == 'POST':
        action = request.json.get('action')
        request_id = request.json.get('request_id')
        
        if action == 'approve' and request_id in rental_requests:
            request_data = rental_requests[request_id]
            
            if request_data['status'] == 'pending':
                # Проверяем доступность консоли
                consoles = load_json_file('consoles')
                console_id = request_data['console_id']
                
                if console_id in consoles and consoles[console_id]['status'] == 'available':
                    # Одобряем заявку и создаем аренду
                    request_data['status'] = 'approved'
                    save_json_file('rental_requests', rental_requests)
                    
                    # Создаем аренду (логика из бота)
                    rentals = load_json_file('rentals')
                    users = load_json_file('users')
                    
                    rental_id = str(uuid.uuid4())
                    # Получаем данные о выбранном времени из заявки
                    selected_hours = request_data.get('selected_hours')
                    expected_cost = request_data.get('expected_cost', 0)
                    end_time = None
                    
                    if selected_hours:
                        end_time = (datetime.now() + timedelta(hours=selected_hours)).isoformat()
                    
                    rental = {
                        'id': rental_id,
                        'user_id': request_data['user_id'],
                        'console_id': console_id,
                        'start_time': datetime.now().isoformat(),
                        'expected_end_time': end_time,
                        'selected_hours': selected_hours,
                        'expected_cost': expected_cost,
                        'end_time': None,
                        'status': 'active',
                        'total_cost': 0
                    }
                    
                    rentals[rental_id] = rental
                    consoles[console_id]['status'] = 'rented'
                    
                    save_json_file('rentals', rentals)
                    save_json_file('consoles', consoles)
                    
                    # Отправляем уведомление пользователю в Telegram
                    try:
                        from bot import bot, notify_user_about_approval
                        notify_user_about_approval(request_data['user_id'], console_id, rental_id)
                    except Exception as e:
                        print(f"Ошибка отправки уведомления пользователю: {e}")
                    
                    return jsonify({'status': 'success', 'rental_id': rental_id})
                else:
                    return jsonify({'status': 'error', 'message': 'Консоль недоступна'})
        
        elif action == 'reject' and request_id in rental_requests:
            request_data = rental_requests[request_id]
            rental_requests[request_id]['status'] = 'rejected'
            save_json_file('rental_requests', rental_requests)
            
            # Отправляем уведомление пользователю о отклонении
            try:
                from bot import bot, notify_user_about_rejection
                notify_user_about_rejection(request_data['user_id'], request_data['console_id'])
            except Exception as e:
                print(f"Ошибка отправки уведомления пользователю: {e}")
            
            return jsonify({'status': 'success'})
    
    return jsonify(rental_requests)

@app.route('/api/location-request', methods=['POST'])
@login_required
def request_user_location():
    """Запросить геолокацию у пользователя через Telegram бота"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Не указан ID пользователя'})
        
        users = load_json_file('users')
        if user_id not in users:
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        # Импортируем бот и отправляем запрос геолокации
        from bot import bot
        from telebot import types
        
        user = users[user_id]
        
        # Создаем кнопку для отправки геолокации
        location_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        location_button = types.KeyboardButton('📍 Отправить мою геолокацию', request_location=True)
        location_markup.add(location_button)
        
        user_message = f"📍 **Запрос геолокации от администратора (веб-панель)**\n\n"
        user_message += f"Администратор запросил вашу текущую геолокацию через веб-панель.\n"
        user_message += f"Нажмите кнопку ниже, чтобы отправить ее."
        
        bot.send_message(user_id, user_message, parse_mode='Markdown', reply_markup=location_markup)
        
        return jsonify({
            'status': 'success',
            'message': f'Запрос геолокации отправлен пользователю {user.get("full_name", "Неизвестный")}'
        })
        
    except Exception as e:
        print(f"Ошибка запроса геолокации: {e}")
        return jsonify({'status': 'error', 'message': f'Ошибка отправки запроса: {str(e)}'})

@app.route('/api/documents/<user_id>')
@login_required
def get_user_documents(user_id):
    """Получить документы пользователя"""
    try:
        users = load_json_file('users')
        if user_id not in users:
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        user = users[user_id]
        user_full_name = user.get('full_name', user.get('first_name', f'user_{user_id}'))
        
        # Импортируем функцию из бота
        import sys
        sys.path.append('.')
        from bot import check_user_documents
        
        documents = check_user_documents(user_full_name, user_id)
        
        return jsonify({
            'status': 'success',
            'user_name': user_full_name,
            'documents': documents
        })
        
    except Exception as e:
        print(f"Ошибка получения документов: {e}")
        return jsonify({'status': 'error', 'message': f'Ошибка: {str(e)}'})

@app.route('/api/documents/<user_id>/<document_type>')
@login_required
def view_document(user_id, document_type):
    """Просмотр конкретного документа пользователя"""
    try:
        users = load_json_file('users')
        if user_id not in users:
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        user = users[user_id]
        user_full_name = user.get('full_name', user.get('first_name', f'user_{user_id}'))
        safe_name = "".join(c for c in user_full_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        
        # Проверяем допустимые типы документов
        if document_type not in ['passport_front', 'passport_back', 'selfie_with_passport']:
            return jsonify({'status': 'error', 'message': 'Неверный тип документа'})
        
        # Ищем файл документа
        passport_dir = 'passport'
        user_folder = os.path.join(passport_dir, safe_name)
        
        if not os.path.exists(user_folder):
            return jsonify({'status': 'error', 'message': 'Папка пользователя не найдена'})
        
        # Ищем файл с разными расширениями
        document_path = None
        for ext in ['jpg', 'jpeg', 'png', 'webp']:
            filename = f"{document_type}.{ext}"
            filepath = os.path.join(user_folder, filename)
            if os.path.exists(filepath):
                document_path = filepath
                break
        
        if not document_path:
            return jsonify({'status': 'error', 'message': 'Документ не найден'})
        
        # Отправляем файл
        from flask import send_file
        return send_file(document_path)
        
    except Exception as e:
        print(f"Ошибка просмотра документа: {e}")
        return jsonify({'status': 'error', 'message': f'Ошибка: {str(e)}'})

@app.route('/api/request-documents', methods=['POST'])
@login_required
def request_user_documents():
    """Запросить повторную загрузку документов у пользователя"""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Не указан ID пользователя'})
        
        users = load_json_file('users')
        if user_id not in users:
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        # Импортируем бот и отправляем запрос документов
        from bot import bot
        from telebot import types
        
        user = users[user_id]
        user_full_name = user.get('full_name', user.get('first_name', f'user_{user_id}'))
        
        # Обновляем статус пользователя для процесса верификации
        users[user_id]['verification_step'] = 'passport_front'
        save_json_file('users', users)
        
        user_message = f"📄 **Запрос повторной загрузки документов**\n\n"
        user_message += f"Администратор запросил повторную загрузку ваших документов.\n\n"
        user_message += f"**Шаг 1 из 3:** Отправьте фото **ПЕРЕДНЕЙ стороны паспорта**\n\n"
        user_message += f"⚠️ **Требования к фото:**\n"
        user_message += f"• Четкое изображение без бликов\n"
        user_message += f"• Все данные должны быть читаемыми\n"
        user_message += f"• Фото целиком, без обрезанных краев\n\n"
        user_message += f"📷 Отправьте фото как обычное изображение"
        
        # Убираем все кнопки меню для процесса верификации
        markup = types.ReplyKeyboardRemove()
        
        bot.send_message(user_id, user_message, parse_mode='Markdown', reply_markup=markup)
        
        return jsonify({
            'status': 'success',
            'message': f'Запрос документов отправлен пользователю {user_full_name}'
        })
        
    except Exception as e:
        print(f"Ошибка запроса документов: {e}")
        return jsonify({'status': 'error', 'message': f'Ошибка отправки запроса: {str(e)}'})

@app.route('/api/admins', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_admins():
    admins = load_json_file('admins')
    
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        chat_id = data.get('chat_id', '')
        
        if not username or not password:
            return jsonify({'status': 'error', 'message': 'Логин и пароль обязательны'})
        
        if len(password) < 6:
            return jsonify({'status': 'error', 'message': 'Пароль должен быть минимум 6 символов'})
        
        if username in admins:
            return jsonify({'status': 'error', 'message': 'Администратор с таким логином уже существует'})
        
        # Добавляем нового админа
        admins[username] = {
            'username': username,
            'password': password,
            'role': 'admin',
            'chat_id': chat_id,
            'created_at': datetime.now().isoformat(),
            'created_by': current_user.id
        }
        
        save_json_file('admins', admins)
        return jsonify({'status': 'success', 'message': 'Администратор добавлен'})
    
    elif request.method == 'DELETE':
        username = request.json.get('username')
        
        if not username:
            return jsonify({'status': 'error', 'message': 'Укажите логин администратора'})
        
        if username == current_user.id:
            return jsonify({'status': 'error', 'message': 'Нельзя удалить себя'})
        
        if username not in admins:
            return jsonify({'status': 'error', 'message': 'Администратор не найден'})
        
        del admins[username]
        save_json_file('admins', admins)
        return jsonify({'status': 'success', 'message': 'Администратор удален'})
    
    # GET - возвращаем список админов (без паролей)
    admins_safe = {}
    for username, admin_data in admins.items():
        admins_safe[username] = {
            'username': username,
            'role': admin_data.get('role', 'admin'),
            'chat_id': admin_data.get('chat_id', ''),
            'created_at': admin_data.get('created_at', ''),
            'created_by': admin_data.get('created_by', '')
        }
    
    return jsonify(admins_safe)

@app.route('/api/reset-data', methods=['POST'])
@login_required
def reset_all_data():
    """Сброс всех данных системы (консоли, аренды, заявки)"""
    try:
        # Очищаем файлы данных, оставляя только пустые объекты
        save_json_file('consoles', {})
        save_json_file('rentals', {})
        save_json_file('rental_requests', {})
        
        return jsonify({
            'status': 'success', 
            'message': 'Все данные успешно сброшены'
        })
        
    except Exception as e:
        print(f"Ошибка сброса данных: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'Ошибка при сбросе данных: {str(e)}'
        })

@app.route('/api/console-photo', methods=['POST'])
@login_required
def upload_console_photo():
    """Загрузка фото консоли в локальную папку"""
    try:
        if 'photo' not in request.files:
            return jsonify({'status': 'error', 'message': 'Файл не выбран'})
        
        file = request.files['photo']
        console_id = request.form.get('console_id')
        
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Файл не выбран'})
        
        if not console_id:
            return jsonify({'status': 'error', 'message': 'ID консоли не указан'})
        
        # Проверяем тип файла
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({
                'status': 'error',
                'message': 'Неподдерживаемый формат файла. Разрешены: PNG, JPG, JPEG, GIF, WEBP'
            })
        
        # Создаем директорию если не существует
        console_images_dir = os.path.join('static', 'img', 'console')
        os.makedirs(console_images_dir, exist_ok=True)
        
        # Удаляем старое фото если существует
        for ext in allowed_extensions:
            old_file = os.path.join(console_images_dir, f"{console_id}.{ext}")
            if os.path.exists(old_file):
                os.remove(old_file)
        
        # Сохраняем новое фото с именем ID консоли
        filename = f"{console_id}.{file_extension}"
        file_path = os.path.join(console_images_dir, filename)
        file.save(file_path)
        
        return jsonify({
            'status': 'success',
            'photo_path': f"/static/img/console/{filename}",
            'message': 'Фото успешно загружено'
        })
            
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при загрузке фото: {str(e)}'
        })

@app.route('/api/console-photo/<console_id>/delete', methods=['DELETE'])
@login_required
def delete_console_photo(console_id):
    """Удаление фото консоли из локальной папки"""
    try:
        consoles = load_json_file('consoles')
        
        if console_id not in consoles:
            return jsonify({'status': 'error', 'message': 'Консоль не найдена'})
        
        # Удаляем файл фото если существует
        console_images_dir = os.path.join('static', 'img', 'console')
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        
        deleted = False
        for ext in allowed_extensions:
            file_path = os.path.join(console_images_dir, f"{console_id}.{ext}")
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted = True
                print(f"Удален файл фото: {file_path}")
        
        # Удаляем photo_path из данных консоли
        if 'photo_path' in consoles[console_id]:
            del consoles[console_id]['photo_path']
        if 'photo_id' in consoles[console_id]:  # Для совместимости со старой системой
            del consoles[console_id]['photo_id']
        
        save_json_file('consoles', consoles)
        
        message = 'Фото успешно удалено' if deleted else 'Фото не найдено, но запись очищена'
        return jsonify({
            'status': 'success',
            'message': message
        })
        
    except Exception as e:
        print(f"Ошибка удаления фото: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при удалении фото: {str(e)}'
        })

@app.route('/api/discounts', methods=['GET', 'POST'])
@login_required
def manage_discounts():
    """Управление скидками"""
    if request.method == 'GET':
        discounts = load_json_file('discounts')
        consoles = load_json_file('consoles')
        
        # Добавляем названия консолей к скидкам
        for discount in discounts.values():
            if discount['console_id'] in consoles:
                discount['console_name'] = consoles[discount['console_id']]['name']
            else:
                discount['console_name'] = 'Консоль не найдена'
        
        return jsonify({
            'status': 'success',
            'discounts': discounts,
            'consoles': consoles
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        
        # Валидация данных
        required_fields = ['console_id', 'type', 'value', 'start_date', 'end_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'message': f'Поле {field} обязательно'})
        
        # Проверка типа скидки
        if data['type'] not in ['percentage', 'fixed']:
            return jsonify({'status': 'error', 'message': 'Тип скидки должен быть percentage или fixed'})
        
        # Проверка значения скидки
        if data['type'] == 'percentage' and (data['value'] <= 0 or data['value'] >= 100):
            return jsonify({'status': 'error', 'message': 'Процентная скидка должна быть от 1 до 99'})
        
        if data['type'] == 'fixed' and data['value'] <= 0:
            return jsonify({'status': 'error', 'message': 'Фиксированная скидка должна быть больше 0'})
        
        # Проверка существования консоли
        consoles = load_json_file('consoles')
        if data['console_id'] not in consoles:
            return jsonify({'status': 'error', 'message': 'Консоль не найдена'})
        
        # Создание скидки
        discount_id = str(uuid.uuid4())
        discount = {
            'id': discount_id,
            'console_id': data['console_id'],
            'type': data['type'],
            'value': float(data['value']),
            'start_date': data['start_date'],
            'end_date': data['end_date'],
            'min_hours': data.get('min_hours', 0),
            'description': data.get('description', ''),
            'active': True,
            'created_at': datetime.now().isoformat()
        }
        
        discounts = load_json_file('discounts')
        discounts[discount_id] = discount
        save_json_file('discounts', discounts)
        
        return jsonify({
            'status': 'success',
            'message': 'Скидка создана успешно',
            'discount': discount
        })

@app.route('/api/discounts/<discount_id>', methods=['PUT', 'DELETE'])
@login_required
def manage_discount(discount_id):
    """Управление конкретной скидкой"""
    discounts = load_json_file('discounts')
    
    if discount_id not in discounts:
        return jsonify({'status': 'error', 'message': 'Скидка не найдена'})
    
    if request.method == 'PUT':
        data = request.get_json()
        discount = discounts[discount_id]
        
        # Обновляем поля если они переданы
        updatable_fields = ['type', 'value', 'start_date', 'end_date', 'min_hours', 'description', 'active']
        for field in updatable_fields:
            if field in data:
                discount[field] = data[field]
        
        discount['updated_at'] = datetime.now().isoformat()
        save_json_file('discounts', discounts)
        
        return jsonify({
            'status': 'success',
            'message': 'Скидка обновлена успешно',
            'discount': discount
        })
    
    elif request.method == 'DELETE':
        del discounts[discount_id]
        save_json_file('discounts', discounts)
        
        return jsonify({
            'status': 'success',
            'message': 'Скидка удалена успешно'
        })

# API для управления заблокированными датами
@app.route('/api/blocked-dates', methods=['GET'])
@login_required
def get_blocked_dates():
    """Получить все заблокированные даты"""
    try:
        blocked_dates = load_json_file('blocked_dates')
        return jsonify({
            'success': True,
            'data': blocked_dates
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/blocked-dates/system', methods=['POST'])
@login_required
def add_system_blocked_date():
    """Добавить системную заблокированную дату"""
    try:
        data = request.get_json()
        date_str = data.get('date')
        
        if not date_str:
            return jsonify({'success': False, 'error': 'Дата не указана'})
        
        blocked_dates = load_json_file('blocked_dates')
        
        if date_str not in blocked_dates['system_blocked_dates']:
            blocked_dates['system_blocked_dates'].append(date_str)
            blocked_dates['system_blocked_dates'].sort()
            
            if save_json_file('blocked_dates', blocked_dates):
                return jsonify({'success': True, 'message': f'Дата {date_str} заблокирована для всех консолей'})
            else:
                return jsonify({'success': False, 'error': 'Ошибка сохранения'})
        else:
            return jsonify({'success': False, 'error': 'Дата уже заблокирована'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/blocked-dates/system/<date_str>', methods=['DELETE'])
@login_required
def remove_system_blocked_date(date_str):
    """Удалить системную заблокированную дату"""
    try:
        blocked_dates = load_json_file('blocked_dates')
        
        if date_str in blocked_dates['system_blocked_dates']:
            blocked_dates['system_blocked_dates'].remove(date_str)
            
            if save_json_file('blocked_dates', blocked_dates):
                return jsonify({'success': True, 'message': f'Дата {date_str} разблокирована'})
            else:
                return jsonify({'success': False, 'error': 'Ошибка сохранения'})
        else:
            return jsonify({'success': False, 'error': 'Дата не найдена'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/blocked-dates/console', methods=['POST'])
@login_required
def add_console_blocked_date():
    """Добавить заблокированную дату для консоли"""
    try:
        data = request.get_json()
        console_id = data.get('console_id')
        date_str = data.get('date')
        
        if not console_id or not date_str:
            return jsonify({'success': False, 'error': 'Консоль или дата не указаны'})
        
        blocked_dates = load_json_file('blocked_dates')
        
        if console_id not in blocked_dates['console_blocked_dates']:
            blocked_dates['console_blocked_dates'][console_id] = []
        
        if date_str not in blocked_dates['console_blocked_dates'][console_id]:
            blocked_dates['console_blocked_dates'][console_id].append(date_str)
            blocked_dates['console_blocked_dates'][console_id].sort()
            
            # Получаем название консоли для сообщения
            consoles = load_json_file('consoles')
            console_name = consoles.get(console_id, {}).get('name', 'Неизвестная консоль')
            
            if save_json_file('blocked_dates', blocked_dates):
                return jsonify({'success': True, 'message': f'Дата {date_str} заблокирована для {console_name}'})
            else:
                return jsonify({'success': False, 'error': 'Ошибка сохранения'})
        else:
            return jsonify({'success': False, 'error': 'Дата уже заблокирована для этой консоли'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/blocked-dates/console/<console_id>/<date_str>', methods=['DELETE'])
@login_required
def remove_console_blocked_date(console_id, date_str):
    """Удалить заблокированную дату для консоли"""
    try:
        blocked_dates = load_json_file('blocked_dates')
        
        if console_id in blocked_dates['console_blocked_dates'] and date_str in blocked_dates['console_blocked_dates'][console_id]:
            blocked_dates['console_blocked_dates'][console_id].remove(date_str)
            
            # Удаляем пустой массив если дат больше нет
            if not blocked_dates['console_blocked_dates'][console_id]:
                del blocked_dates['console_blocked_dates'][console_id]
            
            # Получаем название консоли для сообщения
            consoles = load_json_file('consoles')
            console_name = consoles.get(console_id, {}).get('name', 'Неизвестная консоль')
            
            if save_json_file('blocked_dates', blocked_dates):
                return jsonify({'success': True, 'message': f'Дата {date_str} разблокирована для {console_name}'})
            else:
                return jsonify({'success': False, 'error': 'Ошибка сохранения'})
        else:
            return jsonify({'success': False, 'error': 'Дата не найдена'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calendar-preview/<console_id>/<year>/<month>')
@login_required  
def get_calendar_preview(console_id, year, month):
    """Получить предпросмотр календаря для консоли с учетом всех настроек"""
    try:
        import calendar
        
        year = int(year)
        month = int(month)
        
        # Получаем данные календаря
        calendar_data_file = load_json_file('calendar')
        
        # Получаем настройки календаря
        working_days = calendar_data_file.get('working_days', [1, 2, 3, 4, 5, 6, 7])
        holidays = calendar_data_file.get('holidays', [])
        system_blocked = calendar_data_file.get('system_blocked_dates', [])
        console_blocked = calendar_data_file.get('console_blocked_dates', {}).get(console_id, [])
        reservations = calendar_data_file.get('reservations', {})
        
        # Получаем занятые даты (из активных аренд)
        rentals = load_json_file('rentals')
        occupied_rental_dates = set()
        
        for rental in rentals.values():
            if rental['console_id'] == console_id and rental['status'] == 'active':
                start_date = datetime.fromisoformat(rental['start_time']).date()
                # Проверяем наличие estimated_end_time или end_time
                end_time_str = rental.get('estimated_end_time') or rental.get('end_time')
                if end_time_str:
                    end_date = datetime.fromisoformat(end_time_str).date()
                else:
                    # Если нет времени окончания, считаем только день начала
                    end_date = start_date
                
                current_date = start_date
                while current_date <= end_date:
                    occupied_rental_dates.add(current_date.isoformat())
                    current_date += timedelta(days=1)
        
        # Получаем занятые слоты из резерваций
        occupied_reservation_dates = set()
        for date_key, res_list in reservations.items():
            if date_key.endswith(f"_{console_id}"):
                date_part = date_key.split('_')[0]
                if res_list:  # Если есть резервации на эту дату
                    occupied_reservation_dates.add(date_part)
        
        # Создаем календарь
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        today = date.today()
        
        calendar_preview = {
            'year': year,
            'month': month,
            'month_name': month_name,
            'weeks': [],
            'legend': {
                'available': 'Доступно',
                'occupied': 'Занято (активная аренда)',
                'reserved': 'Забронировано',
                'system_blocked': 'Заблокировано (система)',
                'console_blocked': 'Заблокировано (консоль)',
                'non_working_day': 'Нерабочий день',
                'holiday': 'Праздничный день',
                'past_date': 'Прошедшая дата'
            }
        }
        
        # Создаем словарь праздников для быстрого поиска
        holiday_dates = {}
        for holiday in holidays:
            holiday_dates[holiday['date']] = holiday
        
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append({'day': '', 'status': 'empty'})
                else:
                    current_date = date(year, month, day)
                    date_str = current_date.isoformat()
                    weekday = current_date.weekday() + 1  # 1 = понедельник, 7 = воскресенье
                    
                    # Определяем статус даты по приоритету
                    if current_date < today:
                        status = 'past_date'
                    elif date_str in system_blocked:
                        status = 'system_blocked'
                    elif date_str in console_blocked:
                        status = 'console_blocked'
                    elif date_str in occupied_rental_dates:
                        status = 'occupied'
                    elif date_str in occupied_reservation_dates:
                        status = 'reserved'
                    elif date_str in holiday_dates:
                        # Проверяем, рабочий ли это праздник
                        if holiday_dates[date_str].get('working', False):
                            status = 'available'
                        else:
                            status = 'holiday'
                    elif weekday not in working_days:
                        status = 'non_working_day'
                    else:
                        status = 'available'
                    
                    day_info = {
                        'day': day,
                        'date': date_str,
                        'status': status,
                        'weekday': weekday
                    }
                    
                    # Добавляем дополнительную информацию
                    if date_str in holiday_dates:
                        day_info['holiday_name'] = holiday_dates[date_str]['name']
                    
                    if date_str in occupied_reservation_dates:
                        date_key = f"{date_str}_{console_id}"
                        day_info['reservations_count'] = len(reservations.get(date_key, []))
                    
                    week_data.append(day_info)
            
            calendar_preview['weeks'].append(week_data)
        
        return jsonify({
            'success': True,
            'calendar': calendar_preview
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== НОВЫЕ API ДЛЯ УПРАВЛЕНИЯ КАЛЕНДАРЕМ =====

@app.route('/api/calendar', methods=['GET'])
@login_required
def get_calendar_data():
    """Получить все данные календаря"""
    try:
        calendar_data = load_json_file('calendar')
        return jsonify({
            'success': True,
            'data': calendar_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calendar/settings', methods=['GET', 'POST'])
@login_required
def manage_calendar_settings():
    """Управление настройками календаря"""
    try:
        calendar_data = load_json_file('calendar')
        
        if request.method == 'POST':
            data = request.get_json()
            
            # Обновляем настройки
            if 'settings' in data:
                calendar_data['settings'].update(data['settings'])
            
            if 'booking_rules' in data:
                calendar_data['booking_rules'].update(data['booking_rules'])
            
            if 'working_days' in data:
                calendar_data['working_days'] = data['working_days']
            
            save_json_file('calendar', calendar_data)
            
            return jsonify({
                'success': True,
                'message': 'Настройки календаря обновлены',
                'data': calendar_data
            })
        
        return jsonify({
            'success': True,
            'data': calendar_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calendar/blocked-dates', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_calendar_blocked_dates():
    """Управление заблокированными датами"""
    try:
        calendar_data = load_json_file('calendar')
        
        if request.method == 'POST':
            data = request.get_json()
            date_str = data.get('date')
            console_id = data.get('console_id')  # Если None - системная блокировка
            
            if not date_str:
                return jsonify({'success': False, 'error': 'Дата не указана'})
            
            if console_id:
                # Блокировка для конкретной консоли
                if console_id not in calendar_data['console_blocked_dates']:
                    calendar_data['console_blocked_dates'][console_id] = []
                
                if date_str not in calendar_data['console_blocked_dates'][console_id]:
                    calendar_data['console_blocked_dates'][console_id].append(date_str)
                    calendar_data['console_blocked_dates'][console_id].sort()
                    message = f'Дата {date_str} заблокирована для консоли'
                else:
                    return jsonify({'success': False, 'error': 'Дата уже заблокирована'})
            else:
                # Системная блокировка
                if date_str not in calendar_data['system_blocked_dates']:
                    calendar_data['system_blocked_dates'].append(date_str)
                    calendar_data['system_blocked_dates'].sort()
                    message = f'Дата {date_str} заблокирована системно'
                else:
                    return jsonify({'success': False, 'error': 'Дата уже заблокирована'})
            
            save_json_file('calendar', calendar_data)
            
            return jsonify({
                'success': True,
                'message': message,
                'data': calendar_data
            })
        
        elif request.method == 'DELETE':
            data = request.get_json()
            date_str = data.get('date')
            console_id = data.get('console_id')
            
            if not date_str:
                return jsonify({'success': False, 'error': 'Дата не указана'})
            
            if console_id:
                # Разблокировка для консоли
                if (console_id in calendar_data['console_blocked_dates'] and 
                    date_str in calendar_data['console_blocked_dates'][console_id]):
                    calendar_data['console_blocked_dates'][console_id].remove(date_str)
                    if not calendar_data['console_blocked_dates'][console_id]:
                        del calendar_data['console_blocked_dates'][console_id]
                    message = f'Дата {date_str} разблокирована для консоли'
                else:
                    return jsonify({'success': False, 'error': 'Дата не найдена'})
            else:
                # Системная разблокировка
                if date_str in calendar_data['system_blocked_dates']:
                    calendar_data['system_blocked_dates'].remove(date_str)
                    message = f'Дата {date_str} разблокирована системно'
                else:
                    return jsonify({'success': False, 'error': 'Дата не найдена'})
            
            save_json_file('calendar', calendar_data)
            
            return jsonify({
                'success': True,
                'message': message,
                'data': calendar_data
            })
        
        # GET
        return jsonify({
            'success': True,
            'data': {
                'system_blocked_dates': calendar_data.get('system_blocked_dates', []),
                'console_blocked_dates': calendar_data.get('console_blocked_dates', {})
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calendar/reservations', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_calendar_reservations():
    """Управление резервациями календаря"""
    try:
        calendar_data = load_json_file('calendar')
        
        if request.method == 'POST':
            data = request.get_json()
            
            reservation = {
                'id': str(uuid.uuid4()),
                'console_id': data.get('console_id'),
                'user_id': data.get('user_id'),
                'date': data.get('date'),
                'time_slot': data.get('time_slot'),
                'duration_hours': data.get('duration_hours', 1),
                'status': 'reserved',
                'created_at': datetime.now().isoformat(),
                'notes': data.get('notes', '')
            }
            
            # Проверка доступности
            date_key = f"{reservation['date']}_{reservation['console_id']}"
            if date_key not in calendar_data['reservations']:
                calendar_data['reservations'][date_key] = []
            
            # Проверка конфликтов времени
            for existing in calendar_data['reservations'][date_key]:
                if existing['time_slot'] == reservation['time_slot']:
                    return jsonify({
                        'success': False, 
                        'error': 'Время уже занято'
                    })
            
            calendar_data['reservations'][date_key].append(reservation)
            save_json_file('calendar', calendar_data)
            
            return jsonify({
                'success': True,
                'message': 'Резервация создана',
                'reservation': reservation
            })
        
        elif request.method == 'DELETE':
            data = request.get_json()
            reservation_id = data.get('reservation_id')
            
            # Поиск и удаление резервации
            for date_key, reservations in calendar_data['reservations'].items():
                for i, reservation in enumerate(reservations):
                    if reservation['id'] == reservation_id:
                        del calendar_data['reservations'][date_key][i]
                        if not calendar_data['reservations'][date_key]:
                            del calendar_data['reservations'][date_key]
                        
                        save_json_file('calendar', calendar_data)
                        
                        return jsonify({
                            'success': True,
                            'message': 'Резервация удалена'
                        })
            
            return jsonify({'success': False, 'error': 'Резервация не найдена'})
        
        # GET - получить все резервации
        return jsonify({
            'success': True,
            'data': calendar_data.get('reservations', {})
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calendar/availability/<console_id>/<date>')
@login_required
def check_calendar_availability(console_id, date_str):
    """Проверить доступность консоли на дату"""
    try:
        calendar_data = load_json_file('calendar')
        
        # Проверка системных блокировок
        if date_str in calendar_data.get('system_blocked_dates', []):
            return jsonify({
                'success': True,
                'available': False,
                'reason': 'system_blocked',
                'message': 'Дата заблокирована системно'
            })
        
        # Проверка блокировок консоли
        console_blocked = calendar_data.get('console_blocked_dates', {}).get(console_id, [])
        if date_str in console_blocked:
            return jsonify({
                'success': True,
                'available': False,
                'reason': 'console_blocked',
                'message': 'Дата заблокирована для этой консоли'
            })
        
        # Проверка резерваций
        date_key = f"{date_str}_{console_id}"
        reservations = calendar_data.get('reservations', {}).get(date_key, [])
        
        # Получаем доступные временные слоты
        all_slots = calendar_data.get('settings', {}).get('time_slots', [])
        occupied_slots = [r['time_slot'] for r in reservations if r['status'] == 'reserved']
        available_slots = [slot for slot in all_slots if slot not in occupied_slots]
        
        return jsonify({
            'success': True,
            'available': len(available_slots) > 0,
            'available_slots': available_slots,
            'occupied_slots': occupied_slots,
            'reservations': reservations
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/calendar/holidays', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_calendar_holidays():
    """Управление праздничными днями"""
    try:
        calendar_data = load_json_file('calendar')
        
        if request.method == 'POST':
            data = request.get_json()
            holiday = {
                'date': data.get('date'),
                'name': data.get('name'),
                'working': data.get('working', False)  # Рабочий ли праздник
            }
            
            if 'holidays' not in calendar_data:
                calendar_data['holidays'] = []
            
            # Проверка на дубликаты
            for existing in calendar_data['holidays']:
                if existing['date'] == holiday['date']:
                    return jsonify({'success': False, 'error': 'Праздник уже существует'})
            
            calendar_data['holidays'].append(holiday)
            save_json_file('calendar', calendar_data)
            
            return jsonify({
                'success': True,
                'message': 'Праздник добавлен',
                'holiday': holiday
            })
        
        elif request.method == 'DELETE':
            data = request.get_json()
            date_str = data.get('date')
            
            calendar_data['holidays'] = [
                h for h in calendar_data.get('holidays', []) 
                if h['date'] != date_str
            ]
            
            save_json_file('calendar', calendar_data)
            
            return jsonify({
                'success': True,
                'message': 'Праздник удален'
            })
        
        # GET
        return jsonify({
            'success': True,
            'data': calendar_data.get('holidays', [])
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== СИСТЕМА РЕЙТИНГА КЛИЕНТОВ =====

def calculate_discipline_score(transactions):
    """Рассчитать дисциплину на основе последних транзакций"""
    if not transactions:
        return 50  # Базовый рейтинг для новых клиентов
    
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

def calculate_loyalty_score(user_id, user_data):
    """Рассчитать лояльность клиента"""
    ratings_data = load_json_file('ratings')
    loyalty_rules = ratings_data.get('settings', {}).get('loyalty_rules', {})
    
    score = 0
    
    # Повторные аренды
    rental_count = len(user_data.get('rentals', []))
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

def calculate_final_rating(user_id):
    """Рассчитать итоговый рейтинг клиента"""
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
        status_name = 'Premium'
    elif final_score >= thresholds.get('regular', 50):
        status = 'regular'
        status_name = 'Обычный'
    else:
        status = 'risk'
        status_name = 'Риск'
    
    return {
        'user_id': user_id,
        'final_score': final_score,
        'discipline': discipline,
        'loyalty': loyalty,
        'status': status,
        'status_name': status_name,
        'calculated_at': datetime.now().isoformat()
    }

def get_status_benefits(status):
    """Получить льготы по статусу"""
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

@app.route('/api/ratings', methods=['GET'])
@login_required
def get_all_ratings():
    """Получить рейтинги всех пользователей"""
    try:
        users = load_json_file('users')
        ratings = []
        
        for user_id in users.keys():
            rating = calculate_final_rating(user_id)
            if rating:
                rating['user_name'] = users[user_id].get('first_name', 'Неизвестный')
                rating['username'] = users[user_id].get('username', '')
                ratings.append(rating)
        
        # Сортируем по рейтингу (по убыванию)
        ratings.sort(key=lambda x: x['final_score'], reverse=True)
        
        return jsonify({
            'success': True,
            'ratings': ratings
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ratings/<user_id>', methods=['GET'])
@login_required
def get_user_rating(user_id):
    """Получить рейтинг конкретного пользователя"""
    try:
        rating = calculate_final_rating(user_id)
        if not rating:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
        
        # Получаем дополнительную информацию
        users = load_json_file('users')
        user_data = users.get(user_id, {})
        ratings_data = load_json_file('ratings')
        transactions = ratings_data.get('transactions', {}).get(user_id, [])
        
        rating['user_name'] = user_data.get('first_name', 'Неизвестный')
        rating['username'] = user_data.get('username', '')
        rating['benefits'] = get_status_benefits(rating['status'])
        rating['transactions_count'] = len(transactions)
        rating['recent_transactions'] = transactions[-5:]  # Последние 5 транзакций
        
        return jsonify({
            'success': True,
            'rating': rating
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ratings/transaction', methods=['POST'])
@login_required
def add_rating_transaction():
    """Добавить транзакцию для расчета рейтинга"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'ID пользователя не указан'})
        
        # Создаем транзакцию
        transaction = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'rental_id': data.get('rental_id'),
            'return_timing': data.get('return_timing', 'on_time'),  # on_time, late_1_24h, late_over_24h
            'item_condition': data.get('item_condition', 'perfect'),  # perfect, minor_defects, major_defects
            'rule_compliance': data.get('rule_compliance', 'no_violations'),  # no_violations, minor_violation, major_violation
            'notes': data.get('notes', ''),
            'created_at': datetime.now().isoformat(),
            'created_by': current_user.id
        }
        
        # Сохраняем транзакцию
        ratings_data = load_json_file('ratings')
        if user_id not in ratings_data['transactions']:
            ratings_data['transactions'][user_id] = []
        
        ratings_data['transactions'][user_id].append(transaction)
        save_json_file('ratings', ratings_data)
        
        # Пересчитываем рейтинг
        new_rating = calculate_final_rating(user_id)
        
        # Сохраняем в историю рейтингов
        ratings_data = load_json_file('ratings')
        if 'rating_history' not in ratings_data:
            ratings_data['rating_history'] = {}
        if 'user_ratings' not in ratings_data:
            ratings_data['user_ratings'] = {}
            
        if user_id not in ratings_data['rating_history']:
            ratings_data['rating_history'][user_id] = []
        
        ratings_data['rating_history'][user_id].append(new_rating)
        ratings_data['user_ratings'][user_id] = new_rating
        save_json_file('ratings', ratings_data)
        
        return jsonify({
            'success': True,
            'message': 'Транзакция добавлена, рейтинг пересчитан',
            'transaction': transaction,
            'new_rating': new_rating
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ratings/settings', methods=['GET', 'POST'])
@login_required
def manage_rating_settings():
    """Управление настройками рейтинговой системы"""
    try:
        ratings_data = load_json_file('ratings')
        
        if request.method == 'POST':
            data = request.get_json()
            
            # Обновляем настройки
            if 'settings' in data:
                ratings_data['settings'].update(data['settings'])
                save_json_file('ratings', ratings_data)
                
                return jsonify({
                    'success': True,
                    'message': 'Настройки рейтинговой системы обновлены'
                })
        
        return jsonify({
            'success': True,
            'settings': ratings_data.get('settings', {})
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ratings/loyalty-bonus', methods=['POST'])
@login_required
def add_loyalty_bonus():
    """Добавить бонус лояльности пользователю"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        bonus = data.get('bonus', 0)
        reason = data.get('reason', '')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'ID пользователя не указан'})
        
        # Обновляем бонус лояльности в профиле пользователя
        users = load_json_file('users')
        if user_id not in users:
            return jsonify({'success': False, 'error': 'Пользователь не найден'})
        
        current_bonus = users[user_id].get('loyalty_bonus', 0)
        users[user_id]['loyalty_bonus'] = max(0, min(100, current_bonus + bonus))
        save_json_file('users', users)
        
        # Пересчитываем рейтинг
        new_rating = calculate_final_rating(user_id)
        
        # Сохраняем в историю
        ratings_data = load_json_file('ratings')
        if 'rating_history' not in ratings_data:
            ratings_data['rating_history'] = {}
        if 'user_ratings' not in ratings_data:
            ratings_data['user_ratings'] = {}
            
        if user_id not in ratings_data['rating_history']:
            ratings_data['rating_history'][user_id] = []
        
        ratings_data['rating_history'][user_id].append({
            **new_rating,
            'bonus_reason': reason,
            'bonus_amount': bonus
        })
        ratings_data['user_ratings'][user_id] = new_rating
        save_json_file('ratings', ratings_data)
        
        return jsonify({
            'success': True,
            'message': f'Бонус лояльности ({bonus:+d}) добавлен',
            'new_rating': new_rating
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/user-rentals/<user_id>', methods=['GET'])
@login_required
def get_user_rentals(user_id):
    """Получить аренды конкретного пользователя"""
    try:
        rentals = load_json_file('rentals')
        consoles = load_json_file('consoles')
        
        # Фильтруем аренды пользователя
        user_rentals = []
        for rental_id, rental in rentals.items():
            if rental.get('user_id') == user_id:
                # Добавляем информацию о консоли
                console_info = consoles.get(rental.get('console_id'), {})
                rental_info = {
                    'id': rental_id,
                    'console_id': rental.get('console_id'),
                    'console_name': console_info.get('name', 'Неизвестная консоль'),
                    'status': rental.get('status'),
                    'start_time': rental.get('start_time'),
                    'end_time': rental.get('end_time'),
                    'total_cost': rental.get('total_cost', 0)
                }
                user_rentals.append(rental_info)
        
        # Сортируем по дате начала (новые первыми)
        user_rentals.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'rentals': user_rentals
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ratings/history', methods=['GET'])
@login_required
def get_rating_history():
    """Получить историю всех транзакций рейтингов"""
    try:
        users = load_json_file('users')
        ratings_data = load_json_file('ratings')
        
        history_data = []
        
        for user_id in users.keys():
            user = users[user_id]
            user_transactions = ratings_data.get('transactions', {}).get(user_id, [])
            
            for transaction in user_transactions:
                if 'return_timing' in transaction:  # Это полная транзакция
                    # Получаем описание рейтинга
                    rating_desc = get_rating_description(
                        transaction.get('return_timing'),
                        transaction.get('item_condition'),
                        transaction.get('rule_compliance')
                    )
                    
                    history_data.append({
                        'user_id': user_id,
                        'user_name': user.get('first_name', 'Неизвестный'),
                        'username': user.get('username', ''),
                        'full_name': user.get('full_name', ''),
                        'date': transaction.get('created_at', '')[:10],
                        'return_timing': transaction.get('return_timing'),
                        'item_condition': transaction.get('item_condition'),
                        'rule_compliance': transaction.get('rule_compliance'),
                        'notes': transaction.get('notes', ''),
                        'description': rating_desc,
                        'rental_id': transaction.get('rental_id', ''),
                        'transaction_id': transaction.get('id', '')
                    })
        
        # Сортируем по дате (новые первыми)
        history_data.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({
            'success': True,
            'history': history_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== НОВАЯ СИСТЕМА РЕЙТИНГА (РУЧНОЕ УПРАВЛЕНИЕ) ====================

@app.route('/api/completed-rentals-for-rating', methods=['GET'])
@login_required
def api_get_completed_rentals_for_rating():
    """Получить список завершенных аренд без рейтинга"""
    db = get_db_manager()
    rentals = db.get_completed_rentals_without_rating()
    return jsonify({'success': True, 'rentals': rentals}), 200

@app.route('/api/add-manual-rating', methods=['POST'])
@login_required
def api_add_manual_rating():
    """Добавить рейтинг с ручным выбором администратора"""
    data = request.get_json()
    admin_id = session.get('user_id')
    
    if not admin_id:
        return jsonify({'success': False, 'message': 'Администратор не определен'}), 401
    
    rental_id = data.get('rental_id')
    user_id = data.get('user_id')
    console_condition = data.get('console_condition')  # perfect, minor_damage, major_damage, lost
    rule_compliance = data.get('rule_compliance')      # no_violations, minor_violations, major_violations
    return_timing = data.get('return_timing')          # on_time, late_hours, late_days
    admin_notes = data.get('admin_notes', '')
    
    if not all([rental_id, user_id, console_condition, rule_compliance, return_timing]):
        return jsonify({'success': False, 'message': 'Не все параметры указаны'}), 400
    
    # Возможные значения параметров
    valid_conditions = ['perfect', 'minor_damage', 'major_damage', 'lost']
    valid_compliance = ['no_violations', 'minor_violations', 'major_violations']
    valid_timings = ['on_time', 'late_hours', 'late_days']
    
    if console_condition not in valid_conditions:
        return jsonify({'success': False, 'message': f'Неверное состояние консоли'}), 400
    if rule_compliance not in valid_compliance:
        return jsonify({'success': False, 'message': f'Неверное соответствие правилам'}), 400
    if return_timing not in valid_timings:
        return jsonify({'success': False, 'message': f'Неверно указано время возврата'}), 400
    
    try:
        db = get_db_manager()
        result = db.add_manual_rating(
            rental_id=rental_id,
            user_id=user_id,
            console_condition=console_condition,
            rule_compliance=rule_compliance,
            return_timing=return_timing,
            admin_id=admin_id,
            admin_notes=admin_notes
        )
        
        if result:
            # Пересчитываем рейтинг пользователя
            new_rating = calculate_user_rating_manual(user_id)
            return jsonify({
                'success': True, 
                'message': 'Рейтинг добавлен',
                'new_user_rating': new_rating
            }), 201
        else:
            return jsonify({'success': False, 'message': 'Ошибка при добавлении рейтинга'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/user-ratings', methods=['GET'])
@login_required
def api_get_all_user_ratings():
    """Получить рейтинги всех пользователей"""
    db = get_db_manager()
    users = db.get_all_users()
    ratings = []
    
    for user in users:
        user_id = user.get('user_id')
        rating_data = db.get_user_rating(user_id)
        if rating_data:
            ratings.append({
                'user_id': user_id,
                'username': user.get('first_name', ''),
                'rating': rating_data.get('rating', 0),
                'transaction_count': len(rating_data.get('transactions', []))
            })
    
    return jsonify({'success': True, 'ratings': ratings}), 200

@app.route('/api/user-rating-history/<user_id>', methods=['GET'])
@login_required
def api_get_user_rating_history(user_id):
    """Получить историю рейтинга пользователя со всеми транзакциями"""
    db = get_db_manager()
    rating_data = db.get_user_rating(user_id)
    
    if not rating_data:
        return jsonify({'success': False, 'message': 'Рейтинг пользователя не найден'}), 404
    
    transactions = rating_data.get('transactions', [])
    # Сортируем по дате (новые сверху)
    transactions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'current_rating': rating_data.get('rating', 0),
        'total_transactions': len(transactions),
        'transactions': transactions
    }), 200

# ==================== СТАРАЯ СИСТЕМА РЕЙТИНГА (оставляем для обратной совместимости) ====================

def get_rating_description(return_timing, item_condition, rule_compliance):
    """Получить описание рейтинга на основе параметров"""
    if return_timing == 'on_time' and item_condition == 'perfect' and rule_compliance == 'no_violations':
        return '⭐ Отличная аренда'
    elif return_timing != 'on_time' and item_condition == 'perfect' and rule_compliance == 'no_violations':
        return '⏰ Опоздание, но вещь в порядке'
    elif return_timing == 'on_time' and item_condition != 'perfect' and rule_compliance == 'no_violations':
        return '🔧 Вовремя, но есть повреждения'
    elif return_timing == 'on_time' and item_condition == 'perfect' and rule_compliance != 'no_violations':
        return '⚠️ Вовремя, но нарушения правил'
    elif return_timing == 'late_1_24h':
        if item_condition == 'major_defects' or rule_compliance == 'major_violation':
            return '🚨 Серьезные нарушения'
        else:
            return '⏰ Небольшое опоздание'
    elif return_timing == 'late_over_24h':
        if item_condition == 'major_defects' or rule_compliance == 'major_violation':
            return '🚨 Серьезные нарушения'
        else:
            return '⏰ Опоздание более суток'
    elif item_condition == 'major_defects' or rule_compliance == 'major_violation':
        return '🚨 Серьезные нарушения'
    else:
        return '⚠️ Смешанные результаты'

# ==================== ФОРМА ВОЗВРАТА АРЕНДЫ ====================

@app.route('/return-form')
@login_required
def return_form_page():
    """Отобразить форму возврата аренды"""
    rental_id = request.args.get('rental_id')
    return render_template('return_form.html', rental_id=rental_id)

@app.route('/api/rental-info/<rental_id>', methods=['GET'])
@login_required
def get_rental_info(rental_id):
    """Получить информацию об аренде для формы возврата"""
    try:
        rentals = load_json_file('rentals')
        if rental_id not in rentals:
            return jsonify({'success': False, 'message': 'Аренда не найдена'}), 404
        
        rental = rentals[rental_id]
        return jsonify({
            'success': True,
            'rental': {
                'rental_id': rental_id,
                'console_id': rental.get('console_id'),
                'user_id': rental.get('user_id'),
                'start_date': rental.get('start_time', rental.get('start_date')),
                'end_date': rental.get('end_time', rental.get('end_date')),
                'status': rental.get('status')
            }
        })
    except Exception as e:
        print(f"❌ Ошибка получения информации об аренде: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/return-rental', methods=['POST'])
@login_required
def process_return_rental():
    """Обработать возврат аренды с заполнением всех полей"""
    try:
        rental_id = request.form.get('rental_id')
        condition = request.form.get('condition')
        admin_comment = request.form.get('admin_comment', '')
        return_date = request.form.get('return_date')
        client_confirmed = request.form.get('client_confirmed') == 'true'
        client_signature = request.form.get('client_signature', '')
        
        # Валидация
        if not all([rental_id, condition, return_date]):
            return jsonify({
                'success': False,
                'message': 'Заполните все обязательные поля'
            }), 400
        
        # Сохраняем фотографии
        photos = []
        if 'return_photos' in request.files:
            files = request.files.getlist('return_photos')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"return_{rental_id}_{datetime.now().timestamp()}_{file.filename}")
                    filepath = os.path.join('static/returns', filename)
                    os.makedirs('static/returns', exist_ok=True)
                    file.save(filepath)
                    photos.append(filepath)
        
        # Подготовляем данные для сохранения
        return_data = {
            'condition': condition,  # excellent, minor_defects, damaged, lost
            'admin_comment': admin_comment,
            'return_photos': photos,
            'return_date': return_date,
            'client_confirmed': client_confirmed,
            'client_signature': client_signature,
            'recorded_by': current_user.username if current_user else 'admin',
            'recorded_by_id': current_user.id if current_user else 'admin'
        }
        
        # Сохраняем через MongoDB
        result = db.save_return_info(rental_id, return_data)
        
        if result:
            # Обновляем аренду в JSON для совместимости
            rentals = load_json_file('rentals')
            if rental_id in rentals:
                rentals[rental_id]['return_info'] = return_data
                rentals[rental_id]['status'] = 'returned'
                save_json_file('rentals', rentals)
            
            return jsonify({
                'success': True,
                'message': 'Информация о возврате успешно зарегистрирована',
                'rental_id': rental_id,
                'condition': condition,
                'photos_count': len(photos)
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': 'Ошибка при сохранении информации о возврате'
            }), 500
            
    except Exception as e:
        print(f"❌ Ошибка при обработке возврата аренды: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/return-info/<rental_id>', methods=['GET'])
@login_required
def get_return_info(rental_id):
    """Получить информацию о возврате аренды"""
    try:
        return_info = db.get_return_info(rental_id)
        if return_info:
            return jsonify({
                'success': True,
                'return_info': return_info
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Информация о возврате не найдена'
            }), 404
    except Exception as e:
        print(f"❌ Ошибка при получении информации о возврате: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== СТАРЫЕ МАРШРУТЫ (СОВМЕСТИМОСТЬ) ====================


    print("🚀 Запуск сервера...")
    print("📦 Инициализация MongoDB...")
    
    # Инициализируем БД
    if init_db():
        print("✅ MongoDB готова!")
    else:
        print("⚠️ Не удалось подключиться к MongoDB!")
    
    # Импортируем новую систему рейтинга
    from rating_system import (
        get_completed_rentals_for_rating,
        add_manual_rating,
        get_all_user_ratings,
        get_user_rating_history,
        calculate_user_rating_manual
    )
    
    app.run(
        debug=False,
        port=5000,
        host='0.0.0.0'
    )