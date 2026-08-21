import os
import re
import sqlite3
import logging
from difflib import SequenceMatcher

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id


# ============================================================
# НАСТРОЙКИ
# ============================================================

# ID сообщества БЕЗ минуса.
GROUP_ID = 235416787

# Пост, под которым будет размещаться комментарий.
POST_OWNER_ID = -235416787
POST_ID = 1108

# База данных SQLite.
DATABASE_FILE = "lottery.db"


# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================
# ТЕКСТЫ БОТА
# ============================================================

WELCOME_MESSAGE = (
    'Привет! На связи Уральский ПрофТех66 😎 '
    'Чтобы участвовать в лотерее "Первый студенческий", '
    'ответь на 3 вопроса'
)

QUESTION_NAME = "Как тебя зовут?"

QUESTION_EDUCATION = "Где ты учишься?"

QUESTION_PROFESSION = "Какую профессию ты осваиваешь?"

FINISH_MESSAGE = """Поздравляю, ты в Уральском Профтехе! 🔥

Твой персональный номер участника лотереи – {number}. В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом-воронкой. Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе! 

Удачи! 🤞"""

COMMENT_MESSAGE = (
    '{profession} – новый участник лотереи '
    '"Первый студенческий"! Порядковый номер: {number}'
)


# ============================================================
# БАЗА ДАННЫХ
# ============================================================

def get_db():
    """
    Открывает SQLite-базу и создаёт необходимые таблицы.
    """

    connection = sqlite3.connect(
        DATABASE_FILE,
        timeout=30
    )

    connection.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_user_id INTEGER UNIQUE NOT NULL,
            name TEXT,
            education TEXT,
            profession TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS questionnaire (
            vk_user_id INTEGER PRIMARY KEY,
            step TEXT NOT NULL,
            name TEXT,
            education TEXT,
            profession TEXT
        )
    """)

    connection.commit()

    return connection


# ============================================================
# РАБОТА С СОСТОЯНИЕМ АНКЕТЫ
# ============================================================

def start_questionnaire(user_id):
    """
    Создаёт или сбрасывает анкету пользователя.
    """

    connection = get_db()

    connection.execute("""
        INSERT INTO questionnaire (
            vk_user_id,
            step,
            name,
            education,
            profession
        )
        VALUES (?, ?, NULL, NULL, NULL)

        ON CONFLICT(vk_user_id)
        DO UPDATE SET
            step = excluded.step,
            name = NULL,
            education = NULL,
            profession = NULL
    """, (
        user_id,
        "name"
    ))

    connection.commit()
    connection.close()


def get_questionnaire(user_id):
    """
    Возвращает состояние анкеты пользователя.
    """

    connection = get_db()

    cursor = connection.execute("""
        SELECT
            step,
            name,
            education,
            profession
        FROM questionnaire
        WHERE vk_user_id = ?
    """, (user_id,))

    result = cursor.fetchone()

    connection.close()

    if not result:
        return None

    return {
        "step": result[0],
        "name": result[1],
        "education": result[2],
        "profession": result[3]
    }


def update_questionnaire(
    user_id,
    step,
    name=None,
    education=None,
    profession=None
):
    """
    Сохраняет текущий этап анкеты и ответы.
    """

    connection = get_db()

    connection.execute("""
        UPDATE questionnaire
        SET
            step = ?,
            name = COALESCE(?, name),
            education = COALESCE(?, education),
            profession = COALESCE(?, profession)
        WHERE vk_user_id = ?
    """, (
        step,
        name,
        education,
        profession,
        user_id
    ))

    connection.commit()
    connection.close()


def delete_questionnaire(user_id):
    """
    Удаляет временную анкету после успешной регистрации.
    """

    connection = get_db()

    connection.execute("""
        DELETE FROM questionnaire
        WHERE vk_user_id = ?
    """, (user_id,))

    connection.commit()
    connection.close()


# ============================================================
# УЧАСТНИКИ
# ============================================================

def get_participant(user_id):
    """
    Проверяет, зарегистрирован ли пользователь уже.
    """

    connection = get_db()

    cursor = connection.execute("""
        SELECT
            id,
            name,
            education,
            profession
        FROM participants
        WHERE vk_user_id = ?
    """, (user_id,))

    result = cursor.fetchone()

    connection.close()

    return result


def save_participant(
    user_id,
    name,
    education,
    profession
):
    """
    Регистрирует нового участника.

    ID записи SQLite используется как
    порядковый номер участника.
    """

    connection = get_db()

    cursor = connection.execute("""
        INSERT INTO participants (
            vk_user_id,
            name,
            education,
            profession
        )
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        name,
        education,
        profession
    ))

    participant_number = cursor.lastrowid

    connection.commit()
    connection.close()

    return participant_number


# ============================================================
# НОРМАЛИЗАЦИЯ ТЕКСТА
# ============================================================

def normalize_text(text):
    """
    Приводит текст к виду, удобному для проверки триггера.
    """

    text = text.lower().strip()

    # Оставляем только русские буквы.
    text = re.sub(r"[^а-яё]", "", text)

    return text


# ============================================================
# ПРОВЕРКА ТРИГГЕРА
# ============================================================

def is_lottery_trigger(text):
    """
    Определяет, написал ли пользователь
    "Первый студенческий", даже если допустил
    небольшую ошибку.
    """

    if not text:
        return False

    original = text.lower().strip()

    normalized = normalize_text(original)

    # Самые очевидные варианты.
    exact_variants = {
        "первыйстуденческий",
        "первыйстуденчиский",
        "первыйстуденческий",
        "первыйстуденческий",
        "первыйстуденческий",
        "первыйстуденческий",
    }

    if normalized in exact_variants:
        return True

    # Убираем повторяющиеся пробелы.
    words = re.findall(r"[а-яё]+", original)

    if len(words) >= 2:

        first_word = words[0]
        second_word = words[1]

        first_similarity = SequenceMatcher(
            None,
            first_word,
            "первый"
        ).ratio()

        second_similarity = SequenceMatcher(
            None,
            second_word,
            "студенческий"
        ).ratio()

        if (
            first_similarity >= 0.80
            and second_similarity >= 0.75
        ):
            return True

    # Проверяем всю фразу целиком.
    target = "первыйстуденческий"

    similarity = SequenceMatcher(
        None,
        normalized,
        target
    ).ratio()

    return similarity >= 0.82


# ============================================================
# ОТПРАВКА СООБЩЕНИЯ
# ============================================================

def send_message(vk, user_id, message):
    """
    Отправляет сообщение пользователю.
    """

    vk.messages.send(
        user_id=user_id,
        random_id=get_random_id(),
        message=message
    )


# ============================================================
# КОММЕНТАРИЙ ПОД ПОСТОМ
# ============================================================

def create_comment(
    vk,
    profession,
    participant_number
):
    """
    Создаёт комментарий под постом акции.
    """

    comment = COMMENT_MESSAGE.format(
        profession=profession,
        number=participant_number
    )

    try:

        vk.wall.createComment(
            owner_id=POST_OWNER_ID,
            post_id=POST_ID,
            message=comment,
            from_group=GROUP_ID
        )

        logger.info(
            "Комментарий для участника №%s создан.",
            participant_number
        )

        return True

    except Exception as error:

        logger.exception(
            "Ошибка создания комментария: %s",
            error
        )

        return False


# ============================================================
# ОБРАБОТКА АНКЕТЫ
# ============================================================

def process_questionnaire(
    vk,
    user_id,
    text
):
    """
    Обрабатывает ответ пользователя
    в зависимости от текущего вопроса.
    """

    questionnaire = get_questionnaire(user_id)

    if not questionnaire:
        return False

    text = text.strip()

    if not text:
        return True

    step = questionnaire["step"]

    # --------------------------------------------------------
    # ИМЯ
    # --------------------------------------------------------

    if step == "name":

        update_questionnaire(
            user_id=user_id,
            step="education",
            name=text
        )

        send_message(
            vk,
            user_id,
            QUESTION_EDUCATION
        )

        return True

    # --------------------------------------------------------
    # УЧЕБНОЕ ЗАВЕДЕНИЕ
    # --------------------------------------------------------

    if step == "education":

        update_questionnaire(
            user_id=user_id,
            step="profession",
            education=text
        )

        send_message(
            vk,
            user_id,
            QUESTION_PROFESSION
        )

        return True

    # --------------------------------------------------------
    # ПРОФЕССИЯ
    # --------------------------------------------------------

    if step == "profession":

        update_questionnaire(
            user_id=user_id,
            step="finished",
            profession=text
        )

        # Получаем обновлённые данные.
        questionnaire = get_questionnaire(user_id)

        name = questionnaire["name"]
        education = questionnaire["education"]
        profession = questionnaire["profession"]

        # ----------------------------------------------------
        # РЕГИСТРАЦИЯ УЧАСТНИКА
        # ----------------------------------------------------

        try:

            participant_number = save_participant(
                user_id=user_id,
                name=name,
                education=education,
                profession=profession
            )

        except sqlite3.IntegrityError:

            # Пользователь уже зарегистрирован.
            existing = get_participant(user_id)

            if existing:

                existing_number = existing[0]

                send_message(
                    vk,
                    user_id,
                    (
                        "Ты уже участвуешь в лотерее! 😎\n\n"
                        f"Твой номер участника: "
                        f"{existing_number}"
                    )
                )

                delete_questionnaire(user_id)

                return True

            raise

        # ----------------------------------------------------
        # ОТПРАВЛЯЕМ НОМЕР УЧАСТНИКУ
        # ----------------------------------------------------

        send_message(
            vk,
            user_id,
            FINISH_MESSAGE.format(
                number=participant_number
            )
        )

        # ----------------------------------------------------
        # СОЗДАЁМ КОММЕНТАРИЙ
        # ----------------------------------------------------

        create_comment(
            vk=vk,
            profession=profession,
            participant_number=participant_number
        )

        logger.info(
            "Зарегистрирован участник №%s | VK ID: %s | %s",
            participant_number,
            user_id,
            name
        )

        # ----------------------------------------------------
        # УДАЛЯЕМ ВРЕМЕННУЮ АНКЕТУ
        # ----------------------------------------------------

        delete_questionnaire(user_id)

        return True

    return True


# ============================================================
# ОБРАБОТКА НОВОГО СООБЩЕНИЯ
# ============================================================

def handle_message(vk, event):
    """
    Обрабатывает входящее сообщение VK.
    """

    if event.type != VkBotEventType.MESSAGE_NEW:
        return

    message = event.object

    user_id = message.get("from_id")
    text = message.get("text", "").strip()

    if not user_id or not text:
        return

    # Сообщения от пользователей имеют положительный ID.
    # Сообщения от сообществ могут иметь отрицательный ID.
    if user_id < 0:
        return

    logger.info(
        "Сообщение от пользователя %s: %s",
        user_id,
        text
    )

    # ========================================================
    # 1. ПОЛЬЗОВАТЕЛЬ УЖЕ ПРОХОДИТ АНКЕТУ
    # ========================================================

    questionnaire = get_questionnaire(user_id)

    if questionnaire:

        process_questionnaire(
            vk,
            user_id,
            text
        )

        return

    # ========================================================
    # 2. ПРОВЕРЯЕМ, УЧАСТВОВАЛ ЛИ ПОЛЬЗОВАТЕЛЬ РАНЬШЕ
    # ========================================================

    participant = get_participant(user_id)

    if participant:

        participant_number = participant[0]

        if is_lottery_trigger(text):

            send_message(
                vk,
                user_id,
                (
                    "Ты уже участвуешь в лотерее! 😎\n\n"
                    f"Твой номер участника: "
                    f"{participant_number}"
                )
            )

        return

    # ========================================================
    # 3. ПРОВЕРЯЕМ ТРИГГЕР
    # ========================================================

    if is_lottery_trigger(text):

        # Первое сообщение.
        send_message(
            vk,
            user_id,
            WELCOME_MESSAGE
        )

        # Запускаем анкету.
        start_questionnaire(user_id)

        # Сразу задаём первый вопрос.
        send_message(
            vk,
            user_id,
            QUESTION_NAME
        )

        logger.info(
            "Пользователь %s начал анкету.",
            user_id
        )


# ============================================================
# ЗАПУСК
# ============================================================

def main():

    logger.info("Запуск бота...")

    # Авторизация сообщества.
    vk_session = vk_api.VkApi(
        token=VK_TOKEN
    )

    vk = vk_session.get_api()

    # Подключаем Long Poll.
    longpoll = VkBotLongPoll(
        vk_session,
        GROUP_ID
    )

    logger.info(
        "Бот запущен. Ожидаю сообщения..."
    )

    for event in longpoll.listen():

        try:

            handle_message(
                vk,
                event
            )

        except Exception as error:

            logger.exception(
                "Ошибка при обработке события: %s",
                error
            )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
