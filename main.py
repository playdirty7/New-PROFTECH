import os
import json
import random
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

VK_TOKEN = os.getenv('VK_TOKEN')
if not VK_TOKEN:
    raise ValueError("VK_TOKEN не задан")

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

def main():
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    print("🤖 Бот запущен (тестовый режим – отвечает на всё)")

    for event in longpoll.listen():
        print(f"🔔 Событие: {event.type}")  # Лог всех событий

        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.peer_id
            message_text = event.text.strip()
            print(f"📩 Сообщение от {user_id}: '{message_text}'")

            # Отвечаем на любое сообщение (для проверки)
            try:
                vk.messages.send(
                    user_id=user_id,
                    message="Бот работает! (это тестовый ответ)",
                    random_id=random.randint(1, 2**31)
                )
                print("✅ Ответ отправлен")
            except Exception as e:
                print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()
