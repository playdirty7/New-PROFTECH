import os
import asyncio
import logging
from datetime import datetime

from vkbottle import Bot, BotLabeler, CtxStorage
from vkbottle.types import Message
import aiosqlite

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
VK_TOKEN = os.getenv('VK_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID', 0))
TARGET_POST_ID = 1108
TARGET_OWNER_ID = -235416787

# --- Инициализация бота ---
bot = Bot(token=VK_TOKEN)
labeler = BotLabeler()
bot.labeler = labeler
ctx_storage = CtxStorage()

# --- Работа с базой данных ---
DB_PATH = 'participants.db'

async def init_db():
    """Создание таблиц, если их нет"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                number INTEGER UNIQUE,
                name TEXT,
                college TEXT,
                profession TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS counter (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_number INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            INSERT OR IGNORE INTO counter (id, last_number) VALUES (1, 0)
        ''')
        await db.commit()

async def is_participant(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM participants WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def add_participant(user_id: int, name: str, college: str, profession: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('BEGIN IMMEDIATE'):
            cur = await db.execute('SELECT last_number FROM counter WHERE id = 1')
            row = await cur.fetchone()
            new_number = row[0] + 1 if row else 1
            await db.execute('UPDATE counter SET last_number = ? WHERE id = 1', (new_number,))
            await db.execute(
                'INSERT INTO participants (user_id, number, name, college, profession) VALUES (?, ?, ?, ?, ?)',
                (user_id, new_number, name, college, profession)
            )
            await db.commit()
            return new_number

# --- Кеш участников ---
participants_cache = set()
cache_updated = None

async def refresh_cache():
    global participants_cache, cache_updated
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id FROM participants') as cursor:
            rows = await cursor.fetchall()
            participants_cache = {row[0] for row in rows}
            cache_updated = datetime.now()

async def is_participant_cached(user_id: int) -> bool:
    global cache_updated
    if cache_updated is None or (datetime.now() - cache_updated).seconds > 5:
        await refresh_cache()
    return user_id in participants_cache

# --- FSM состояния ---
class States:
    WAITING_NAME = 1
    WAITING_COLLEGE = 2
    WAITING_PROFESSION = 3

# --- Хранилище сессий ---
user_sessions = {}

# --- Функция отправки комментария с повторными попытками ---
async def post_comment_with_retry(name: str, college: str, profession: str, number: int, max_retries=3):
    comment_text = (
        f"{name} - новый участник лотереи! \n"
        f"Порядковый номер: {number}\n"
        f"Специальность: {profession}\n"
        f"Учебное заведение: {college}"
    )
    for attempt in range(1, max_retries + 1):
        try:
            await bot.api.wall.create_comment(
                owner_id=TARGET_OWNER_ID,
                post_id=TARGET_POST_ID,
                message=comment_text
            )
            logger.info(f"✅ Комментарий отправлен (попытка {attempt}): {comment_text}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке комментария (попытка {attempt}): {e}")
            if attempt == max_retries:
                logger.error("❌ Все попытки отправки комментария исчерпаны.")
                return False
            await asyncio.sleep(2 ** attempt)
    return False

# --- Обработчики сообщений ---

@labeler.private_message(regex=r'первый\s*студенческий|1-?й\s*студенческий|первокурсник|студент\s*первого')
async def start_dialog(message: Message):
    user_id = message.from_id

    if await is_participant_cached(user_id):
        await message.answer("Вы уже участвуете в лотерее! Следите за обновлениями 😉")
        return

    if user_id in user_sessions:
        await message.answer("Вы уже начали участие, пожалуйста, ответьте на вопросы.")
        return

    user_sessions[user_id] = {'step': States.WAITING_NAME, 'name': '', 'college': '', 'profession': ''}
    await message.answer(
        "Привет! На связи Уральский ПрофТех66 😎 Чтобы участвовать в лотерее \"Первый студенческий\", ответь на 3 вопроса.\n\nКак тебя зовут?"
    )

@labeler.private_message(func=lambda message: message.from_id in user_sessions)
async def dialog_step(message: Message):
    user_id = message.from_id
    session = user_sessions[user_id]
    step = session['step']
    text = message.text.strip()

    if step == States.WAITING_NAME:
        session['name'] = text
        session['step'] = States.WAITING_COLLEGE
        await message.answer("Где ты учишься?")
    elif step == States.WAITING_COLLEGE:
        session['college'] = text
        session['step'] = States.WAITING_PROFESSION
        await message.answer("Какую профессию ты осваиваешь?")
    elif step == States.WAITING_PROFESSION:
        session['profession'] = text

        try:
            number = await add_participant(user_id, session['name'], session['college'], session['profession'])
        except Exception as e:
            logger.error(f"Ошибка при добавлении участника: {e}")
            await message.answer("Произошла ошибка, попробуйте позже.")
            del user_sessions[user_id]
            return

        final_message = (
            f"Поздравляю, ты в Уральском Профтехе! 🔥\n\n"
            f"Твой персональный номер участника лотереи – {number}. "
            f"В качестве подтверждения участия комментарий с порядковым номером автоматически появится под постом с акцией. "
            f"Остался один шаг: поделись акцией с другом, чтобы и он успел заявить о себе!\n\n"
            f"Удачи! 🤞"
        )
        await message.answer(final_message)

        asyncio.create_task(
            post_comment_with_retry(
                session['name'],
                session['college'],
                session['profession'],
                number
            )
        )

        asyncio.create_task(refresh_cache())
        del user_sessions[user_id]

# Запуск бота
async def main():
    await init_db()
    await refresh_cache()
    await bot.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
