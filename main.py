import os
import json
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

VK_TOKEN = os.getenv('VK_TOKEN')
if not VK_TOKEN:
    raise ValueError("VK_TOKEN не задан")

# Клавиатура с кнопкой "Подписаться"
KEYBOARD_JSON = json.dumps({
    "one_time": False,
    "buttons": [[{
        "action": {
            "type": "open_link",
            "link": "https://vk.ru/uralprofteh66",
            "label": "Подписаться"
        },
        "color": "primary"
    }]]
}, ensure_ascii=False)

# Триггерные фразы (все в нижнем регистре)
TRIGGER_PHRASES = [
    "привет",
    "1 студенческий",
    "1-й студенческий",
    "1 студент",
    "первый студент",
    "первый студенческий",
    "первый студенчиский",
    "первый студенеский",
    "студент первого",
    "первокурсник"
]

REPLY_MESSAGE = (
    "Привет! На связи Уральский ПрофТех66 😎 Акция \"Первый студенческий\" завершилась – "
    "итоги опубликованы на стене сообщества. Оставайся с нами, чтобы одним из первых "
    "узнать о новых мероприятиях Уральского ПрофТеха"
)

def main():
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен (режим: акция завершена)")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.peer_id
            message_text = event.text.strip()
            print(f"📩 Сообщение от {user_id}: '{message_text}'")

            lower_msg = message_text.lower()
            # Проверяем, содержит ли сообщение хотя бы одну триггерную фразу
            if any(phrase in lower_msg for phrase in TRIGGER_PHRASES):
                try:
                    vk.messages.send(
                        user_id=user_id,
                        message=REPLY_MESSAGE,
                        keyboard=KEYBOARD_JSON,
                        random_id=random.randint(1, 2**31)
                    )
                    print("✅ Отправлен ответ о завершении акции")
                except Exception as e:
                    print(f"❌ Ошибка при отправке: {e}")
            else:
                print("⏩ Сообщение не содержит триггер, игнорируем")

if __name__ == '__main__':
    main()
