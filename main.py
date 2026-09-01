import os
import re
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

# --- 1. Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))

TARGET_POST_ID = 1108
TARGET_OWNER_ID = -235416787

# --- 2. Состояния диалога ---
user_sessions = {}
participant_counter = 0

# --- 3. Хранение уже завершивших участников ---
PARTICIPANTS_FILE = 'participants.txt'
participants = set()

def load_participants():
    global participants
    if os.path.exists(PARTICIPANTS_FILE):
        with open(PARTICIPANTS_FILE, 'r') as f:
            participants = set(line.strip() for line in f if line.strip())
    else:
        participants = set()

def save_participant(user_id):
    with open(PARTICIPANTS_FILE, 'a') as f:
        f.write(str(user_id) + '\n')

# --- 4. Функция для отправки комментария (новый формат) ---
def post_comment(vk, name, college, profession, number):
    comment_text = (
        f"{name} - новый участник лотереи! \n"
        f"Порядковый номер: {number}\n"
        f"Специальность: {profession}\n"
        f"Учебное заведение: {college}"
    )
    try:
        vk.wall.createComment(
            owner_id=TARGET_OWNER_ID,
            post_id=TARGET_POST_ID,
            message=comment_text
        )
        print(f"✅ Комментарий отправлен: {comment_text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке комментария: {e}")

# --- 5. Основная логика ---
def main():
    global participant_counter, participants

    load_participants()

    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен и ждет сообщений...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            # Исправление: используем event.message.from_id вместо event.user_id
            user_id = event.message.from_id
            message_text = event.text.lower().strip()

            # --- Проверка на команду "Первый студенческий" ---
            trigger_pattern = re.compile(r'(первый\s*студенческий|1-?й\s*студенческий|первокурсник|студент\s*первого)')
            is_trigger = bool(trigger_pattern.search(message_text))

            if is_trigger:
                if user_id in participants:
                    vk.messages.send(
                        user_id=user_id,
                        message="Вы уже участвуете в лотерее! Следите за обновлениями 😉",
                        random_id=random.randint(1, 2**31)
                    )
                    continue

                if user_id in user_sessions:
                    vk.messages.send(
                        user_id=user_id,
                        message="Вы уже начали участие, пожалуйста, ответьте на вопросы.",
                        random_id=random.randint(1, 2**31)
                    )
                    continue

                user_sessions[user_id] = {'step': 0, 'name': '', 'college': '', 'profession': ''}
                vk.messages.send(
                    user_id=user_id,
                    message="Привет! На связи Уральский ПрофТех66 😎 Чтобы участвовать в лотерее \"Первый студенческий\", ответь на 3 вопроса.",
                    random_id=random.randint(1, 2**31)
                )
                vk.messages.send(
                    user_id=user_id,
                    message="Как тебя зовут?",
                    random_id=random.randint(1, 2**31)
                )
                user_sessions[user_id]['step'] = 1
                continue

            # --- Обработка шагов диалога ---
            if user_id in user_sessions:
                session = user_sessions[user_id]
                step = session['step']

                if step == 1:
                    session['name'] = event.text
                    vk.messages.send(
                        user_id=user_id,
                        message="Где ты учишься?",
                        random_id=random.randint(1, 2**31)
                    )
                    session['step'] = 2

                elif step == 2:
                    session['college'] = event.text
                    vk.messages.send(
                        user_id=user_id,
                        message="Какую профессию ты осваиваешь?",
                        random_id=random.randint(1, 2**31)
                    )
                    session['step'] = 3

                elif step == 3:
                    session['profession'] = event.text

                    participant_counter += 1
                    user_number = participant_counter

                    final_message = (
                        f"Поздравляю, ты в Уральском Профтехе! 🔥\n\n"
                        f"Твой персональный номер участника лотереи – {user_number}. "
                        f"В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом с акцией. "
                        f"Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе!\n\n"
                        f"Удачи! 🤞"
                    )
                    vk.messages.send(
                        user_id=user_id,
                        message=final_message,
                        random_id=random.randint(1, 2**31)
                    )

                    post_comment(vk, session['name'], session['college'], session['profession'], user_number)

                    participants.add(user_id)
                    save_participant(user_id)

                    del user_sessions[user_id]

if __name__ == '__main__':
    main()
