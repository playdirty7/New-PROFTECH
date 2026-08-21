import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
import os

# ========== НАСТРОЙКИ (замените на свои) ==========
POST_OWNER_ID = -235416787          # Владелец поста (всегда с минусом)
POST_ID = 1108                      # ID поста (число после _ в ссылке)
COUNTER_FILE = 'counter.txt'        # Файл для хранения порядкового номера

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
user_states = {}    # Словарь для хранения данных пользователей в процессе опроса
                    # Формат: {user_id: {'step': 1-4, 'name': '', 'college': '', 'profession': ''}}
counter = 0         # Текущий порядковый номер (считается с 1)

# ========== РАБОТА С ПОРЯДКОВЫМ НОМЕРОМ ==========
def read_counter():
    """Читает последний номер из файла при запуске"""
    global counter
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r', encoding='utf-8') as f:
            counter = int(f.read().strip())
    else:
        counter = 0

def save_counter():
    """Сохраняет текущий номер в файл после каждого присвоения"""
    with open(COUNTER_FILE, 'w', encoding='utf-8') as f:
        f.write(str(counter))

read_counter()  # Загружаем сохранённый номер при старте

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def send_message(vk, user_id, text):
    """Отправляет сообщение пользователю"""
    vk.method('messages.send', {
        'user_id': user_id,
        'message': text,
        'random_id': 0
    })

def post_comment(vk, owner_id, post_id, text):
    """Оставляет комментарий от имени группы под указанным постом"""
    try:
        vk.method('wall.createComment', {
            'owner_id': owner_id,
            'post_id': post_id,
            'message': text,
            'from_group': 1   # 1 – комментарий от имени группы
        })
        print(f"[OK] Комментарий оставлен: {text}")
    except Exception as e:
        print(f"[ОШИБКА] Не удалось оставить комментарий: {e}")

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
def handle_message(vk, user_id, message_text):
    global counter
    text = message_text.lower().strip()

    # ---- 1. Проверяем, не является ли сообщение триггером "первый студенческий" ----
    # Если в тексте есть оба ключевых слова (в любом порядке) – начинаем опрос заново
    if 'первый' in text and 'студенческий' in text:
        # Сбрасываем состояние пользователя (или создаём новое)
        user_states[user_id] = {
            'step': 1,
            'name': '',
            'college': '',
            'profession': ''
        }
        # Отправляем приветственное сообщение и первый вопрос
        send_message(vk, user_id,
                     'Привет! На связи Уральский ПрофТех66 😎 Чтобы участвовать в лотерее "Первый студенческий", ответь на 3 вопроса.')
        send_message(vk, user_id, 'Как тебя зовут?')
        return   # больше ничего не делаем, ждём ответа

    # ---- 2. Если это не триггер – проверяем, есть ли активный опрос ----
    if user_id not in user_states or user_states[user_id]['step'] == 0:
        # Нет активного опроса – игнорируем сообщение
        return

    state = user_states[user_id]
    step = state['step']

    # ---- 3. Обрабатываем ответ в зависимости от шага ----
    if step == 1:
        # Сохраняем имя
        state['name'] = message_text
        state['step'] = 2
        send_message(vk, user_id, 'Где ты учишься?')

    elif step == 2:
        # Сохраняем учебное заведение
        state['college'] = message_text
        state['step'] = 3
        send_message(vk, user_id, 'Какую профессию ты осваиваешь?')

    elif step == 3:
        # Сохраняем профессию
        state['profession'] = message_text
        state['step'] = 4   # опрос завершён

        # ---- 4. Присваиваем порядковый номер ----
        counter += 1
        save_counter()
        number = counter

        # ---- 5. Отправляем финальное сообщение ----
        final_msg = f"""Поздравляю, ты в Уральском Профтехе! 🔥

Твой персональный номер участника лотереи – {number}. В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом-воронкой. Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе! 

Удачи! 🤞"""
        send_message(vk, user_id, final_msg)

        # ---- 6. Оставляем комментарий под постом ----
        comment_text = f"{state['profession']} – новый участник лотереи \"Первый студенческий\"! Порядковый номер: {number}"
        post_comment(vk, POST_OWNER_ID, POST_ID, comment_text)

    # Если step == 4 (уже завершил) – другие сообщения игнорируются

# ========== ЗАПУСК БОТА ==========
def main():
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print('✅ Бот запущен и ждёт сообщений...')
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            # Обрабатываем только новые сообщения, адресованные боту
            handle_message(vk, event.user_id, event.text)

if __name__ == '__main__':
    main()