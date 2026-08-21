import os
import re
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# --- 1. Конфигурация ---
# Токен и ID группы берутся из переменных окружения, которые мы зададим на Bothost
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))  # ID вашей группы VK

# ID поста, под которым нужно оставить комментарий
TARGET_POST_ID = 1108  # из ссылки vk.ru/wall-235416787_1108
TARGET_OWNER_ID = -235416787  # Отрицательный ID для группы

# --- 2. Состояния диалога ---
# Словарь для хранения временных данных пользователей
# Ключ: user_id, Значение: {'step': 0, 'name': '', 'college': '', 'profession': ''}
user_sessions = {}
# Счетчик для порядковых номеров
participant_counter = 0

# --- 3. Функция для отправки комментария под постом ---
def post_comment(vk, profession, number):
    """Отправляет комментарий под указанным постом."""
    comment_text = f"{profession} – новый участник лотереи \"Первый студенческий\"! Порядковый номер: {number}"
    try:
        vk.wall.createComment(
            owner_id=TARGET_OWNER_ID,
            post_id=TARGET_POST_ID,
            message=comment_text
        )
        print(f"✅ Комментарий отправлен: {comment_text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке комментария: {e}")

# --- 4. Обработка сообщений ---
def main():
    global participant_counter

    # Инициализация VK API
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен и ждет сообщений...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            message_text = event.text.lower().strip()

            # --- 5. Проверка на команду "Первый студенческий" (с вариациями) ---
            # Регулярное выражение ищет варианты: первый студенческий, 1-й студенческий, первокурсник и т.д.
            trigger_pattern = re.compile(r'(первый\s*студенческий|1-?й\s*студенческий|первокурсник|студент\s*первого)')
            is_trigger = bool(trigger_pattern.search(message_text))

            # --- 6. Логика диалога ---
            if is_trigger:
                # Начинаем новый диалог
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
                user_sessions[user_id]['step'] = 1  # Ожидаем имя

            elif user_id in user_sessions:
                session = user_sessions[user_id]
                step = session['step']

                if step == 1:
                    # Сохраняем имя
                    session['name'] = event.text
                    vk.messages.send(
                        user_id=user_id,
                        message="Где ты учишься?",
                        random_id=random.randint(1, 2**31)
                    )
                    session['step'] = 2

                elif step == 2:
                    # Сохраняем учебное заведение
                    session['college'] = event.text
                    vk.messages.send(
                        user_id=user_id,
                        message="Какую профессию ты осваиваешь?",
                        random_id=random.randint(1, 2**31)
                    )
                    session['step'] = 3

                elif step == 3:
                    # Сохраняем профессию
                    session['profession'] = event.text

                    # Присваиваем порядковый номер
                    participant_counter += 1
                    user_number = participant_counter

                    # Отправляем финальное сообщение
                    final_message = (
                        f"Поздравляю, ты в Уральском Профтехе! 🔥\n\n"
                        f"Твой персональный номер участника лотереи – {user_number}. "
                        f"В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом-воронкой. "
                        f"Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе!\n\n"
                        f"Удачи! 🤞"
                    )
                    vk.messages.send(
                        user_id=user_id,
                        message=final_message,
                        random_id=random.randint(1, 2**31)
                    )

                    # --- 7. Отправка комментария под постом ---
                    post_comment(vk, session['profession'], user_number)

                    # Удаляем сессию пользователя, так как диалог завершен
                    del user_sessions[user_id]

            # Игнорируем все остальные сообщения

if __name__ == '__main__':
    main()
