import os
import re
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# --- 1. Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))

# ID поста, под которым нужно оставить комментарий
TARGET_POST_ID = 1108
TARGET_OWNER_ID = -235416787

# ID группы для проверки подписки (можно использовать screen_name 'uralprofteh66' или числовой ID)
# Для проверки подписки проще использовать screen_name
GROUP_SCREEN_NAME = 'uralprofteh66'

# --- 2. Состояния диалога ---
# user_sessions[user_id] = {
#   'step': 0,           # 0 - ожидание подписки, 1 - ожидание имени, 2 - ожидание вуза, 3 - ожидание профессии
#   'name': '',
#   'college': '',
#   'profession': ''
# }
user_sessions = {}
participant_counter = 0

# Файл для сохранения счетчика (чтобы номера не сбрасывались при перезапуске)
COUNTER_FILE = 'counter.txt'

def load_counter():
    global participant_counter
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r') as f:
            participant_counter = int(f.read().strip())
    else:
        participant_counter = 0

def save_counter():
    with open(COUNTER_FILE, 'w') as f:
        f.write(str(participant_counter))

# --- 3. Клавиатуры ---
def get_subscription_keyboard():
    """Клавиатура с кнопками 'Подписаться' (ссылка) и 'Я подписан(а)!' (callback)"""
    keyboard = VkKeyboard(one_time=False, inline=True)
    # Кнопка-ссылка
    keyboard.add_openlink_button(
        label='Подписаться',
        link=f'https://vk.com/{GROUP_SCREEN_NAME}'
    )
    # Кнопка для проверки подписки (callback)
    keyboard.add_callback_button(
        label='Я подписан(а)!',
        color=VkKeyboardColor.POSITIVE,
        payload={'type': 'check_subscription'}
    )
    return keyboard

def remove_keyboard():
    """Пустая клавиатура (убирает кнопки)"""
    return VkKeyboard(one_time=False, inline=True).get_empty_keyboard()

# --- 4. Функция проверки подписки ---
def is_user_subscribed(vk, user_id):
    """Проверяет, подписан ли пользователь на группу"""
    try:
        response = vk.groups.isMember(
            group_id=GROUP_SCREEN_NAME,
            user_id=user_id
        )
        return response  # True или False
    except Exception as e:
        print(f"❌ Ошибка при проверке подписки: {e}")
        return False

# --- 5. Функция для отправки комментария под постом ---
def post_comment(vk, profession, number):
    comment_text = f'{profession} – новый участник лотереи "Первый студенческий"! Порядковый номер: {number}'
    try:
        vk.wall.createComment(
            owner_id=TARGET_OWNER_ID,
            post_id=TARGET_POST_ID,
            message=comment_text
        )
        print(f'✅ Комментарий отправлен: {comment_text}')
    except Exception as e:
        print(f'❌ Ошибка при отправке комментария: {e}')

# --- 6. Основная логика ---
def main():
    global participant_counter

    load_counter()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print('🤖 Бот запущен и ждет сообщений...')

    for event in longpoll.listen():
        # Обработка обычных сообщений
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            message_text = event.text.lower().strip()

            # --- Проверка на команду "Первый студенческий" ---
            trigger_pattern = re.compile(r'(первый\s*студенческий|1-?й\s*студенческий|первокурсник|студент\s*первого)')
            is_trigger = bool(trigger_pattern.search(message_text))

            if is_trigger:
                # Начинаем новый диалог
                user_sessions[user_id] = {'step': 0, 'name': '', 'college': '', 'profession': ''}

                # Отправляем приветственное сообщение с клавиатурой
                vk.messages.send(
                    user_id=user_id,
                    message='Привет! На связи Уральский ПрофТех66 😎 Чтобы участвовать в лотерее "Первый студенческий", подпишись на наше сообщество.',
                    random_id=random.randint(1, 2**31),
                    keyboard=get_subscription_keyboard().get_keyboard()
                )
                continue

            # --- Обработка сообщений в рамках диалога (после подписки) ---
            if user_id in user_sessions:
                session = user_sessions[user_id]
                step = session['step']

                if step == 1:
                    # Сохраняем имя
                    session['name'] = event.text
                    vk.messages.send(
                        user_id=user_id,
                        message='Где ты учишься?',
                        random_id=random.randint(1, 2**31),
                        keyboard=remove_keyboard()
                    )
                    session['step'] = 2

                elif step == 2:
                    # Сохраняем учебное заведение
                    session['college'] = event.text
                    vk.messages.send(
                        user_id=user_id,
                        message='Какую профессию ты осваиваешь?',
                        random_id=random.randint(1, 2**31)
                    )
                    session['step'] = 3

                elif step == 3:
                    # Сохраняем профессию
                    session['profession'] = event.text

                    # Присваиваем порядковый номер
                    participant_counter += 1
                    save_counter()
                    user_number = participant_counter

                    # Отправляем финальное сообщение
                    final_message = (
                        f'Поздравляю, ты в Уральском Профтехе! 🔥\n\n'
                        f'Твой персональный номер участника лотереи – {user_number}. '
                        f'В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом-воронкой. '
                        f'Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе!\n\n'
                        f'Удачи! 🤞'
                    )
                    vk.messages.send(
                        user_id=user_id,
                        message=final_message,
                        random_id=random.randint(1, 2**31)
                    )

                    # Отправляем комментарий под постом
                    post_comment(vk, session['profession'], user_number)

                    # Удаляем сессию
                    del user_sessions[user_id]

        # --- Обработка нажатий на callback-кнопки ---
        elif event.type == VkEventType.MESSAGE_EVENT:
            user_id = event.user_id
            payload = event.object.payload

            # Проверяем, что это наша кнопка
            if payload.get('type') == 'check_subscription':
                if is_user_subscribed(vk, user_id):
                    # Пользователь подписан — переходим к вопросу
                    if user_id in user_sessions:
                        session = user_sessions[user_id]
                        # Проверяем, что мы ещё на шаге 0 (ожидание подписки)
                        if session['step'] == 0:
                            session['step'] = 1
                            vk.messages.send(
                                user_id=user_id,
                                message='Отлично! А теперь скажи, как тебя зовут?',
                                random_id=random.randint(1, 2**31),
                                keyboard=remove_keyboard()
                            )
                        else:
                            # Если шаг не 0 — игнорируем или отправляем сообщение
                            vk.messages.send(
                                user_id=user_id,
                                message='Ты уже прошёл этот этап!',
                                random_id=random.randint(1, 2**31)
                            )
                    else:
                        # Если сессии нет — возможно, бот перезапустился
                        vk.messages.send(
                            user_id=user_id,
                            message='Напиши "Первый студенческий", чтобы начать заново.',
                            random_id=random.randint(1, 2**31)
                        )
                else:
                    # Пользователь не подписан
                    vk.messages.send(
                        user_id=user_id,
                        message='Тебя всё ещё нет в числе наших подписчиков 😔',
                        random_id=random.randint(1, 2**31),
                        keyboard=get_subscription_keyboard().get_keyboard()
                    )

                # Отвечаем на callback (чтобы убрать индикатор загрузки)
                vk.messages.sendMessageEventAnswer(
                    event_id=event.object.event_id,
                    user_id=user_id,
                    peer_id=event.object.peer_id
                )

if __name__ == '__main__':
    main()
