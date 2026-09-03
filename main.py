import os
import re
import json
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

# --- 1. Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))  # не используется, но оставлено

# --- 2. Клавиатура с кнопкой "Подписаться" ---
KEYBOARD = {
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
}
KEYBOARD_JSON = json.dumps(KEYBOARD, ensure_ascii=False)

# --- 3. Триггеры (регулярное выражение) ---
TRIGGER_PATTERN = re.compile(
    r'(привет|'
    r'1-?й?\s*студенчески?й?|'
    r'1\s*студент|'
    r'перв[ыо]й?\s*студен[тч]?е?с?к?и?й?|'
    r'студент\s*первого|'
    r'первокурсник)',
    re.IGNORECASE
)

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

            # Проверка триггера
            if TRIGGER_PATTERN.search(message_text):
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
