import os
import re
import random
import threading
import sqlite3
import time
from datetime import datetime

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

# --- Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))

TARGET_POST_ID = 1108
TARGET_OWNER_ID = -235416787

# --- Глобальные блокировки ---
counter_lock = threading.Lock()
db_lock = threading.Lock()

# --- Кеш участников (периодически обновляется) ---
participants_cache = set()
cache_updated = None
cache_lock = threading.Lock()

# --- Хранилище сессий (словарь, защищённый блокировкой) ---
user_sessions = {}
sessions_lock = threading.Lock()

# --- Подключение к БД (создание таблиц) ---
DB_PATH = 'participants.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                number INTEGER UNIQUE,
                name TEXT,
                college TEXT,
                profession TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS counter (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_number INTEGER DEFAULT 0
            )
        ''')
        c.execute('INSERT OR IGNORE INTO counter (id, last_number) VALUES (1, 0)')
        conn.commit()

def refresh_cache():
    """Обновление кеша из БД"""
    global participants_cache, cache_updated
    with db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT user_id FROM participants')
            rows = c.fetchall()
            with cache_lock:
                participants_cache = {row[0] for row in rows}
                cache_updated = datetime.now()

def is_participant_cached(user_id):
    """Проверка с кешем (обновляется раз в 5 секунд)"""
    global cache_updated
    with cache_lock:
        if cache_updated is None or (datetime.now() - cache_updated).seconds > 5:
            refresh_cache()
        return user_id in participants_cache

def add_participant(user_id, name, college, profession):
    """Добавление участника, возвращает номер"""
    with counter_lock:
        with sqlite3.connect(DB_PATH) as conn:
            with conn:  # автоматическая транзакция
                c = conn.cursor()
                # Получаем текущий номер
                c.execute('SELECT last_number FROM counter WHERE id = 1')
                row = c.fetchone()
                new_number = row[0] + 1 if row else 1
                c.execute('UPDATE counter SET last_number = ? WHERE id = 1', (new_number,))
                c.execute(
                    'INSERT INTO participants (user_id, number, name, college, profession) VALUES (?, ?, ?, ?, ?)',
                    (user_id, new_number, name, college, profession)
                )
                conn.commit()
                # Обновляем кеш
                with cache_lock:
                    participants_cache.add(user_id)
                return new_number

# --- Функция отправки комментария с повторными попытками ---
def post_comment_with_retry(vk, name, college, profession, number, max_retries=3):
    comment_text = (
        f"{name} - новый участник лотереи! \n"
        f"Порядковый номер: {number}\n"
        f"Специальность: {profession}\n"
        f"Учебное заведение: {college}"
    )
    for attempt in range(1, max_retries + 1):
        try:
            vk.wall.createComment(
                owner_id=TARGET_OWNER_ID,
                post_id=TARGET_POST_ID,
                message=comment_text
            )
            print(f"✅ Комментарий отправлен (попытка {attempt}): {comment_text}")
            return True
        except Exception as e:
            print(f"❌ Ошибка при отправке комментария (попытка {attempt}): {e}")
            if attempt == max_retries:
                print("❌ Все попытки исчерпаны.")
                return False
            time.sleep(2 ** attempt)  # экспоненциальная задержка
    return False

# --- Обработка одного сообщения ---
def handle_message(vk, user_id, message_text):
    # Проверка на команду запуска
    trigger_pattern = re.compile(r'(первый\s*студенческий|1-?й\s*студенческий|первокурсник|студент\s*первого)', re.IGNORECASE)
    is_trigger = bool(trigger_pattern.search(message_text))

    if is_trigger:
        # Проверка участия
        if is_participant_cached(user_id):
            vk.messages.send(
                user_id=user_id,
                message="Вы уже участвуете в лотерее! Следите за обновлениями 😉",
                random_id=random.randint(1, 2**31)
            )
            return

        with sessions_lock:
            if user_id in user_sessions:
                vk.messages.send(
                    user_id=user_id,
                    message="Вы уже начали участие, пожалуйста, ответьте на вопросы.",
                    random_id=random.randint(1, 2**31)
                )
                return

            user_sessions[user_id] = {'step': 1, 'name': '', 'college': '', 'profession': ''}

        vk.messages.send(
            user_id=user_id,
            message="Привет! На связи Уральский ПрофТех66 😎 Чтобы участвовать в лотерее \"Первый студенческий\", ответь на 3 вопроса.\n\nКак тебя зовут?",
            random_id=random.randint(1, 2**31)
        )
        return

    # Обработка шагов диалога
    with sessions_lock:
        if user_id not in user_sessions:
            return
        session = user_sessions[user_id]
        step = session['step']

    if step == 1:
        session['name'] = message_text
        session['step'] = 2
        vk.messages.send(
            user_id=user_id,
            message="Где ты учишься?",
            random_id=random.randint(1, 2**31)
        )
    elif step == 2:
        session['college'] = message_text
        session['step'] = 3
        vk.messages.send(
            user_id=user_id,
            message="Какую профессию ты осваиваешь?",
            random_id=random.randint(1, 2**31)
        )
    elif step == 3:
        session['profession'] = message_text
        name = session['name']
        college = session['college']
        profession = session['profession']

        # Добавляем участника (атомарно)
        number = add_participant(user_id, name, college, profession)

        # Финальное сообщение
        final_message = (
            f"Поздравляю, ты в Уральском Профтехе! 🔥\n\n"
            f"Твой персональный номер участника лотереи – {number}. "
            f"В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом с акцией. "
            f"Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе!\n\n"
            f"Удачи! 🤞"
        )
        vk.messages.send(
            user_id=user_id,
            message=final_message,
            random_id=random.randint(1, 2**31)
        )

        # Отправляем комментарий (в отдельном потоке, чтобы не задерживать ответ)
        threading.Thread(
            target=post_comment_with_retry,
            args=(vk, name, college, profession, number),
            daemon=True
        ).start()

        # Удаляем сессию
        with sessions_lock:
            del user_sessions[user_id]

# --- Основной цикл с многопоточностью ---
def main():
    init_db()
    refresh_cache()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен и ждет сообщений...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            message_text = event.text.strip()
            # Запускаем обработку в отдельном потоке
            threading.Thread(
                target=handle_message,
                args=(vk, user_id, message_text),
                daemon=True
            ).start()

if __name__ == '__main__':
    main()
