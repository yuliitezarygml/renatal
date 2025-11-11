"""
MongoDB Database Manager
Замена JSON файлов на MongoDB
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Конфигурация MongoDB
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('DB_NAME', 'ps4_rental')

class MongoDBManager:
    """Менеджер для работы с MongoDB"""
    
    def __init__(self, mongo_url=MONGO_URL, db_name=DB_NAME):
        self.mongo_url = mongo_url
        self.db_name = db_name
        self.client = None
        self.db = None
        self.connect()
    
    def connect(self):
        """Подключение к MongoDB"""
        try:
            self.client = MongoClient(self.mongo_url, serverSelectionTimeoutMS=5000)
            # Проверяем подключение
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            print(f"✅ Подключение к MongoDB успешно: {self.mongo_url}")
            print(f"📦 База данных: {self.db_name}")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"❌ Ошибка подключения к MongoDB: {e}")
            return False
    
    def disconnect(self):
        """Отключение от MongoDB"""
        if self.client:
            self.client.close()
            print("👋 Отключение от MongoDB")
    
    # ===== КОНСОЛИ =====
    def get_consoles(self):
        """Получить все консоли"""
        try:
            collection = self.db['consoles']
            consoles = {}
            for doc in collection.find():
                console_id = str(doc['_id'])
                consoles[console_id] = doc
            return consoles
        except Exception as e:
            print(f"❌ Ошибка получения консолей: {e}")
            return {}
    
    def get_console(self, console_id):
        """Получить консоль по ID"""
        try:
            collection = self.db['consoles']
            doc = collection.find_one({'_id': str(console_id)})
            return doc
        except Exception as e:
            print(f"❌ Ошибка получения консоли {console_id}: {e}")
            return None
    
    def save_console(self, console_data):
        """Сохранить консоль"""
        try:
            collection = self.db['consoles']
            console_id = str(console_data.get('_id', console_data.get('id')))
            console_data['_id'] = console_id
            collection.replace_one({'_id': console_id}, console_data, upsert=True)
            return console_id
        except Exception as e:
            print(f"❌ Ошибка сохранения консоли: {e}")
            return None
    
    def delete_console(self, console_id):
        """Удалить консоль"""
        try:
            collection = self.db['consoles']
            result = collection.delete_one({'_id': str(console_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления консоли {console_id}: {e}")
            return False
    
    # ===== ПОЛЬЗОВАТЕЛИ =====
    def get_users(self):
        """Получить всех пользователей"""
        try:
            collection = self.db['users']
            users = {}
            for doc in collection.find():
                user_id = str(doc['_id'])
                users[user_id] = doc
            return users
        except Exception as e:
            print(f"❌ Ошибка получения пользователей: {e}")
            return {}
    
    def get_user(self, user_id):
        """Получить пользователя по ID"""
        try:
            collection = self.db['users']
            doc = collection.find_one({'_id': str(user_id)})
            return doc
        except Exception as e:
            print(f"❌ Ошибка получения пользователя {user_id}: {e}")
            return None
    
    def save_user(self, user_data):
        """Сохранить пользователя"""
        try:
            collection = self.db['users']
            user_id = str(user_data.get('_id', user_data.get('id')))
            user_data['_id'] = user_id
            collection.replace_one({'_id': user_id}, user_data, upsert=True)
            return user_id
        except Exception as e:
            print(f"❌ Ошибка сохранения пользователя: {e}")
            return None
    
    def delete_user(self, user_id):
        """Удалить пользователя"""
        try:
            collection = self.db['users']
            result = collection.delete_one({'_id': str(user_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления пользователя {user_id}: {e}")
            return False
    
    # ===== АРЕНДЫ =====
    def get_rentals(self):
        """Получить все аренды"""
        try:
            collection = self.db['rentals']
            rentals = {}
            for doc in collection.find():
                rental_id = str(doc['_id'])
                rentals[rental_id] = doc
            return rentals
        except Exception as e:
            print(f"❌ Ошибка получения аренд: {e}")
            return {}
    
    def save_rental(self, rental_data):
        """Сохранить аренду"""
        try:
            collection = self.db['rentals']
            rental_id = str(rental_data.get('_id', rental_data.get('id')))
            rental_data['_id'] = rental_id
            collection.replace_one({'_id': rental_id}, rental_data, upsert=True)
            return rental_id
        except Exception as e:
            print(f"❌ Ошибка сохранения аренды: {e}")
            return None
    
    def delete_rental(self, rental_id):
        """Удалить аренду"""
        try:
            collection = self.db['rentals']
            result = collection.delete_one({'_id': str(rental_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления аренды {rental_id}: {e}")
            return False
    
    def save_return_info(self, rental_id, return_data):
        """Сохранить информацию о возврате аренды"""
        try:
            collection = self.db['rentals']
            # Добавляем информацию о возврате к существующей аренде
            result = collection.update_one(
                {'_id': str(rental_id)},
                {
                    '$set': {
                        'return_info': {
                            'condition': return_data.get('condition'),  # Состояние товара
                            'admin_comment': return_data.get('admin_comment', ''),  # Комментарий админа
                            'return_photos': return_data.get('return_photos', []),  # Фото возврата
                            'return_date': return_data.get('return_date'),  # Дата возврата
                            'client_confirmed': return_data.get('client_confirmed', False),  # Подтверждение клиента
                            'client_signature': return_data.get('client_signature', ''),  # Подпись клиента
                            'recorded_by': return_data.get('recorded_by'),  # Кто записал информацию
                            'recorded_at': datetime.now().isoformat()  # Когда записано
                        },
                        'status': 'returned'
                    }
                }
            )
            return result.matched_count > 0
        except Exception as e:
            print(f"❌ Ошибка сохранения информации о возврате {rental_id}: {e}")
            return False
    
    def get_return_info(self, rental_id):
        """Получить информацию о возврате аренды"""
        try:
            collection = self.db['rentals']
            doc = collection.find_one({'_id': str(rental_id)})
            if doc and 'return_info' in doc:
                return doc['return_info']
            return None
        except Exception as e:
            print(f"❌ Ошибка получения информации о возврате {rental_id}: {e}")
            return None
    
    # ===== АДМИНИСТРАТОРЫ =====
    def get_admins(self):
        """Получить всех администраторов"""
        try:
            collection = self.db['admins']
            admins = {}
            for doc in collection.find():
                admin_id = str(doc['_id'])
                admins[admin_id] = doc
            return admins
        except Exception as e:
            print(f"❌ Ошибка получения администраторов: {e}")
            return {}
    
    def save_admin(self, admin_data):
        """Сохранить администратора"""
        try:
            collection = self.db['admins']
            admin_id = str(admin_data.get('_id', admin_data.get('username', 'admin')))
            admin_data['_id'] = admin_id
            collection.replace_one({'_id': admin_id}, admin_data, upsert=True)
            return admin_id
        except Exception as e:
            print(f"❌ Ошибка сохранения администратора: {e}")
            return None
    
    def delete_admin(self, admin_id):
        """Удалить администратора"""
        try:
            collection = self.db['admins']
            result = collection.delete_one({'_id': str(admin_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления администратора {admin_id}: {e}")
            return False
    
    # ===== ЗАЯВКИ =====
    def get_rental_requests(self):
        """Получить все заявки на аренду"""
        try:
            collection = self.db['rental_requests']
            requests = {}
            for doc in collection.find():
                request_id = str(doc['_id'])
                requests[request_id] = doc
            return requests
        except Exception as e:
            print(f"❌ Ошибка получения заявок: {e}")
            return {}
    
    def save_rental_request(self, request_data):
        """Сохранить заявку на аренду"""
        try:
            collection = self.db['rental_requests']
            request_id = str(request_data.get('_id', request_data.get('id')))
            request_data['_id'] = request_id
            collection.replace_one({'_id': request_id}, request_data, upsert=True)
            return request_id
        except Exception as e:
            print(f"❌ Ошибка сохранения заявки: {e}")
            return None
    
    def delete_rental_request(self, request_id):
        """Удалить заявку на аренду"""
        try:
            collection = self.db['rental_requests']
            result = collection.delete_one({'_id': str(request_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления заявки {request_id}: {e}")
            return False
    
    # ===== СКИДКИ =====
    def get_discounts(self):
        """Получить все скидки"""
        try:
            collection = self.db['discounts']
            discounts = {}
            for doc in collection.find():
                discount_id = str(doc['_id'])
                discounts[discount_id] = doc
            return discounts
        except Exception as e:
            print(f"❌ Ошибка получения скидок: {e}")
            return {}
    
    def save_discount(self, discount_data):
        """Сохранить скидку"""
        try:
            collection = self.db['discounts']
            discount_id = str(discount_data.get('_id', discount_data.get('id')))
            discount_data['_id'] = discount_id
            collection.replace_one({'_id': discount_id}, discount_data, upsert=True)
            return discount_id
        except Exception as e:
            print(f"❌ Ошибка сохранения скидки: {e}")
            return None
    
    def delete_discount(self, discount_id):
        """Удалить скидку"""
        try:
            collection = self.db['discounts']
            result = collection.delete_one({'_id': str(discount_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления скидки {discount_id}: {e}")
            return False
    
    # ===== КАЛЕНДАРЬ =====
    def get_calendar(self):
        """Получить данные календаря"""
        try:
            collection = self.db['calendar']
            doc = collection.find_one({'_id': 'calendar_data'})
            if doc:
                doc.pop('_id', None)
            return doc or {}
        except Exception as e:
            print(f"❌ Ошибка получения календаря: {e}")
            return {}
    
    def save_calendar(self, calendar_data):
        """Сохранить данные календаря"""
        try:
            collection = self.db['calendar']
            calendar_data['_id'] = 'calendar_data'
            result = collection.replace_one({'_id': 'calendar_data'}, calendar_data, upsert=True)
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения календаря: {e}")
            return False
    
    # ===== РЕЙТИНГИ =====
    def get_ratings(self):
        """Получить все рейтинги"""
        try:
            collection = self.db['ratings']
            ratings = {}
            for doc in collection.find():
                rating_id = str(doc['_id'])
                ratings[rating_id] = doc
            return ratings
        except Exception as e:
            print(f"❌ Ошибка получения рейтингов: {e}")
            return {}
    
    def save_rating(self, rating_data):
        """Сохранить рейтинг"""
        try:
            collection = self.db['ratings']
            rating_id = str(rating_data.get('_id', rating_data.get('id', 'ratings')))
            rating_data['_id'] = rating_id
            collection.replace_one({'_id': rating_id}, rating_data, upsert=True)
            return rating_id
        except Exception as e:
            print(f"❌ Ошибка сохранения рейтинга: {e}")
            return None
    
    def delete_rating(self, rating_id):
        """Удалить рейтинг"""
        try:
            collection = self.db['ratings']
            result = collection.delete_one({'_id': str(rating_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления рейтинга {rating_id}: {e}")
            return False
    
    # ===== АДМИН НАСТРОЙКИ =====
    def get_admin_settings(self):
        """Получить настройки администратора"""
        try:
            collection = self.db['admin_settings']
            doc = collection.find_one({'_id': 'admin_settings'})
            if doc:
                doc.pop('_id', None)
            return doc or {}
        except Exception as e:
            print(f"❌ Ошибка получения настроек: {e}")
            return {}
    
    def save_admin_settings(self, settings_data):
        """Сохранить настройки администратора"""
        try:
            collection = self.db['admin_settings']
            settings_data['_id'] = 'admin_settings'
            result = collection.replace_one({'_id': 'admin_settings'}, settings_data, upsert=True)
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения настроек: {e}")
            return False
    
    # ===== НОВАЯ СИСТЕМА РЕЙТИНГА (РУЧНОЕ УПРАВЛЕНИЕ) =====
    
    def get_completed_rentals_without_rating(self):
        """Получить завершенные аренды без рейтинга"""
        try:
            collection = self.db['rentals']
            rentals = []
            
            # Ищем аренды со статусом 'completed' и без поля 'rating_id'
            for doc in collection.find({'status': 'completed', 'rating_id': {'$exists': False}}):
                rentals.append({
                    'rental_id': str(doc['_id']),
                    'user_id': doc.get('user_id'),
                    'console_id': doc.get('console_id'),
                    'start_date': doc.get('start_date'),
                    'end_date': doc.get('end_date'),
                    'duration': doc.get('duration'),
                    'price': doc.get('price')
                })
            
            return rentals
        except Exception as e:
            print(f"❌ Ошибка получения завершенных аренд: {e}")
            return []
    
    def add_manual_rating(self, rental_id, user_id, console_condition, rule_compliance, 
                         return_timing, admin_id, admin_notes=''):
        """Добавить рейтинг с ручным выбором администратора"""
        try:
            # Сохраняем рейтинг в collection ratings
            collection = self.db['ratings']
            rating_doc = {
                '_id': rental_id,  # Используем rental_id как идентификатор рейтинга
                'user_id': user_id,
                'rental_id': rental_id,
                'console_condition': console_condition,
                'rule_compliance': rule_compliance,
                'return_timing': return_timing,
                'admin_id': admin_id,
                'admin_notes': admin_notes,
                'timestamp': datetime.now().isoformat(),
                'created_at': datetime.now()
            }
            collection.insert_one(rating_doc)
            
            # Отмечаем аренду как имеющую рейтинг
            rentals_collection = self.db['rentals']
            rentals_collection.update_one(
                {'_id': rental_id},
                {'$set': {'rating_id': rental_id, 'rated_at': datetime.now().isoformat()}}
            )
            
            return True
        except Exception as e:
            print(f"❌ Ошибка при добавлении рейтинга: {e}")
            return False
    
    def get_user_rating(self, user_id):
        """Получить рейтинг пользователя с историей транзакций"""
        try:
            collection = self.db['ratings']
            transactions = []
            
            for doc in collection.find({'user_id': user_id}):
                transaction = {
                    'rating_id': str(doc['_id']),
                    'rental_id': doc.get('rental_id'),
                    'console_condition': doc.get('console_condition'),
                    'rule_compliance': doc.get('rule_compliance'),
                    'return_timing': doc.get('return_timing'),
                    'admin_id': doc.get('admin_id'),
                    'admin_notes': doc.get('admin_notes', ''),
                    'timestamp': doc.get('timestamp')
                }
                transactions.append(transaction)
            
            # Пересчитываем общий рейтинг на основе всех транзакций
            rating = self._calculate_rating_from_transactions(transactions)
            
            return {
                'user_id': user_id,
                'rating': rating,
                'transactions': transactions
            }
        except Exception as e:
            print(f"❌ Ошибка получения рейтинга пользователя {user_id}: {e}")
            return None
    
    def _calculate_rating_from_transactions(self, transactions):
        """Вычислить рейтинг на основе всех транзакций"""
        if not transactions:
            return 5.0  # Начальный рейтинг для новых пользователей
        
        score = 5.0
        weight_condition = 0.4
        weight_compliance = 0.3
        weight_timing = 0.3
        
        for transaction in transactions:
            trans_score = 0
            
            # Оценка состояния консоли
            condition = transaction.get('console_condition', '')
            if condition == 'perfect':
                trans_score += 1.0 * weight_condition
            elif condition == 'minor_damage':
                trans_score += 0.5 * weight_condition
            elif condition == 'major_damage':
                trans_score += -0.5 * weight_condition
            elif condition == 'lost':
                trans_score += -1.5 * weight_condition
            
            # Оценка соответствия правилам
            compliance = transaction.get('rule_compliance', '')
            if compliance == 'no_violations':
                trans_score += 1.0 * weight_compliance
            elif compliance == 'minor_violations':
                trans_score += 0.3 * weight_compliance
            elif compliance == 'major_violations':
                trans_score += -0.7 * weight_compliance
            
            # Оценка времени возврата
            timing = transaction.get('return_timing', '')
            if timing == 'on_time':
                trans_score += 1.0 * weight_timing
            elif timing == 'late_hours':
                trans_score += 0.3 * weight_timing
            elif timing == 'late_days':
                trans_score += -0.5 * weight_timing
            
            score += trans_score
        
        # Ограничиваем рейтинг от 1.0 до 5.0
        score = max(1.0, min(5.0, score))
        return round(score, 2)
    
    # ===== ВРЕМЕННЫЕ РЕЗЕРВАЦИИ =====
    def get_temp_reservations(self):
        """Получить все временные резервации"""
        try:
            collection = self.db['temp_reservations']
            reservations = {}
            for doc in collection.find():
                res_id = str(doc['_id'])
                reservations[res_id] = doc
            return reservations
        except Exception as e:
            print(f"❌ Ошибка получения временных резервации: {e}")
            return {}
    
    def save_temp_reservation(self, reservation_data):
        """Сохранить временную резервацию"""
        try:
            collection = self.db['temp_reservations']
            res_id = str(reservation_data.get('_id', reservation_data.get('id')))
            reservation_data['_id'] = res_id
            collection.replace_one({'_id': res_id}, reservation_data, upsert=True)
            return res_id
        except Exception as e:
            print(f"❌ Ошибка сохранения временной резервации: {e}")
            return None
    
    def delete_temp_reservation(self, reservation_id):
        """Удалить временную резервацию"""
        try:
            collection = self.db['temp_reservations']
            result = collection.delete_one({'_id': str(reservation_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"❌ Ошибка удаления временной резервации {reservation_id}: {e}")
            return False


# Глобальный экземпляр менеджера БД
db_manager = None

def get_db_manager():
    """Получить экземпляр менеджера БД"""
    global db_manager
    if db_manager is None:
        db_manager = MongoDBManager()
    return db_manager

def init_db():
    """Инициализация БД при запуске"""
    manager = get_db_manager()
    if manager.db:
        print("✅ База данных инициализирована")
        return True
    else:
        print("❌ Не удалось инициализировать БД")
        return False
