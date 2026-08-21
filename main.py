import os
import re
import random
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType  # ← изменён импорт
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# --- 1. Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))

TARGET_POST_ID = 1108
TARGET_OWNER_ID = -235416787
GROUP_SCREEN_NAME = 'uralprofteh66'  # или числовой ID, но лучше screen_name

# --- 2. Состояния диалога ---
user_sessions = {}
participant_counter = 0
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
    keyboard = VkKeyboard(one_time=False, inline=True)
    keyboard.add_openlink_button(
        label='Подписаться',
        link=f'https://vk.com/{GROUP_SCREEN_NAME}'
    )
    keyboard.add_callback_button(
        label='Я подписан(а)!',
        color=VkKeyboardColor.POSITIVE,
        payload={'type': 'check_subscription'}
    )
    return keyboard

def remove_keyboard():
    return VkKeyboard(one_time=False, inline=True).get_empty_keyboard()

# --- 4. Проверка подписки ---
def is_user_subscribed(vk, user_id):
    try:
        response = vk.groups.isMember(
            group_id=GROUP_SCREEN_NAME,
            user_id=user_id
        )
        return response
    except Exception as e:
        print(f'❌ Ошибка проверки подписки: {e}')
        return False

# --- 5. Отправка комментария ---
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
        print(f'❌ Ошибка комментария: {e}')

# --- 6. Основная логика ---
def main():
    global participant_counter
    load_counter()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID)  # ← изменено

    print('🤖 Бот запущен (BotLongPoll)...')

    for event in longpoll.listen():
        # --- Обработка обычных сообщений ---
        if event.type == VkBotEventType.MESSAGE_NEW:
            user_id = event.object.message.from_id
            message_text = event.object.message.text.lower().strip()

            trigger_pattern = re.compile(r'(первый\s*студенческий|1-?й\s*студенческий|первокурсник|студент\s*первого)')
            is_trigger = bool(trigger_pattern.search(message_text))

            if is_trigger:
                user_sessions[user_id] = {'step': 0, 'name': '', 'college': '', 'profession': ''}
                vk.messages.send(
                    user_id=user_id,
                    message='Привет! На связи Уральский ПрофТех66 😎 Чтобы участвовать в лотерее "Первый студенческий", подпишись на наше сообщество.',
                    random_id=random.randint(1, 2**31),
                    keyboard=get_subscription_keyboard().get_keyboard()
                )
                continue

            if user_id in user_sessions:
                session = user_sessions[user_id]
                step = session['step']

                if step == 1:
                    session['name'] = event.object.message.text
                    vk.messages.send(
                        user_id=user_id,
                        message='Где ты учишься?',
                        random_id=random.randint(1, 2**31),
                        keyboard=remove_keyboard()
                    )
                    session['step'] = 2

                elif step == 2:
                    session['college'] = event.object.message.text
                    vk.messages.send(
                        user_id=user_id,
                        message='Какую профессию ты осваиваешь?',
                        random_id=random.randint(1, 2**31)
                    )
                    session['step'] = 3

                elif step == 3:
                    session['profession'] = event.object.message.text
                    participant_counter += 1
                    save_counter()
                    user_number = participant_counter

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

                    post_comment(vk, session['profession'], user_number)
                    del user_sessions[user_id]

        # --- Обработка нажатий на callback-кнопки ---
        elif event.type == VkBotEventType.MESSAGE_EVENT:
            user_id = event.object.user_id
            payload = event.object.payload

            if payload.get('type') == 'check_subscription':
                if is_user_subscribed(vk, user_id):
                    if user_id in user_sessions and user_sessions[user_id]['step'] == 0:
                        user_sessions[user_id]['step'] = 1
                        vk.messages.send(
                            user_id=user_id,
                            message='Отлично! А теперь скажи, как тебя зовут?',
                            random_id=random.randint(1, 2**31),
                            keyboard=remove_keyboard()
                        )
                    else:
                        vk.messages.send(
                            user_id=user_id,
                            message='Ты уже прошёл этот этап!',
                            random_id=random.randint(1, 2**31)
                        )
                else:
                    vk.messages.send(
                        user_id=user_id,
                        message='Тебя всё ещё нет в числе наших подписчиков 😔',
                        random_id=random.randint(1, 2**31),
                        keyboard=get_subscription_keyboard().get_keyboard()
                    )

                # Обязательный ответ на событие, чтобы убрать "часики" на кнопке
                vk.messages.sendMessageEventAnswer(
                    event_id=event.object.event_id,
                    user_id=user_id,
                    peer_id=event.object.peer_id
                )

if __name__ == '__main__':
    main()
