import os
import json
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

# --- 1. Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
if not VK_TOKEN:
    raise ValueError("Не задан VK_TOKEN в переменных окружения")

# --- 2. Клавиатура с кнопкой "Подписаться" ---
KEYBOARD_JSON = json.dumps({
    "one_time": False,
    "buttons": [
        [
            {
                "action": {
                    "type": "open_link",
                    "link": "https://vk.ru/uralprofteh66",
                    "label": "Подписаться"
                },
                "color": "primary"
            }
        ]
    ]
}, ensure_ascii=False)

# --- 3. Триггерные фразы (все в нижнем регистре) ---
TRIGGER_PHRASES = [
    "привет",
    "1 студенческий",
    "1-й студенческий",
    "1 студент",
    "первый студент",
    "первый студенческий",
    "первый студенчиский",   # с опечаткой
    "первый студенеский",    # с опечаткой
    "студент первого",
    "первокурсник"
]

# --- 4. Ответное сообщение ---
REPLY_MESSAGE = (
    "Привет! На связи Уральский ПрофТех66 😎 Акция \"Первый студенческий\" завершилась – "
    "итоги опубликованы на стене сообщества. Оставайся с нами, чтобы одним из первых "
    "узнать о новых мероприятиях Уральского ПрофТеха"
)

# --- 5. Основная логика ---
def main():
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен (режим: акция завершена) и ждет сообщений...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.peer_id
            message_text = event.text.strip()
            print(f"📩 Получено сообщение от {user_id}: {message_text}")

            # Проверяем, содержит ли сообщение хотя бы одну из триггерных фраз (игнорируя регистр)
            lower_msg = message_text.lower()
            if any(phrase in lower_msg for phrase in TRIGGER_PHRASES):
                try:
                    vk.messages.send(
                        user_id=user_id,
                        message=REPLY_MESSAGE,
                        keyboard=KEYBOARD_JSON,
                        random_id=random.randint(1, 2 ** 31)
                    )
                    print(f"✅ Ответ отправлен пользователю {user_id}")
                except Exception as e:
                    print(f"❌ Ошибка при отправке: {e}")

if __name__ == '__main__':
    main()
