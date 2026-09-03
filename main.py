import os
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

VK_TOKEN = os.getenv('VK_TOKEN')
if not VK_TOKEN:
    raise ValueError("VK_TOKEN не задан")

# Все варианты триггеров (в нижнем регистре)
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
    "узнать о новых мероприятиях Уральского ПрофТеха!"
)

def main():
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен (без кнопки) и ждет сообщений...")

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.peer_id
            message_text = event.text.strip()
            print(f"📩 Получено: {message_text}")

            lower_msg = message_text.lower()
            if any(phrase in lower_msg for phrase in TRIGGER_PHRASES):
                try:
                    vk.messages.send(
                        user_id=user_id,
                        message=REPLY_MESSAGE,
                        random_id=random.randint(1, 2**31)
                    )
                    print("✅ Ответ отправлен")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
            else:
                print("⏩ Триггер не найден")

if __name__ == '__main__':
    main()
