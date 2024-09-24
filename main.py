import logging
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import asyncio
import openai
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.utils.exceptions import RetryAfter
from bs4 import BeautifulSoup

from job_scraper import scrape_jobs
from pars_job_cryptocurrency import scrape_jobs_2
from scraper import scrape_jobs_3
from pars_job_degencrypto import scrape_jobs_4


# Установите ваш API-ключи
TOKEN = '7415980925:AAEbwiRWGTOGuMQhazfWS8zGVCcwYEcMLuM'
OPENAI_API_KEY = 'sk-proj-kEUip-CyUJBe7ZoiIm8iACgJic0fwFcojKJdwC7eR8-FWT8vrzlyQQw77lT3BlbkFJDUgLriLYDOVGLxfbjKOC' \
                 'FyHQyGgIS6UKabrF7zm4GtDW1i16zQsliGINIA'


bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Подключение к базе данных SQLite
conn = sqlite3.connect("chat_messages.db")
cursor = conn.cursor()

# Создание таблицы для хранения сообщений
cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    message_text TEXT,
    date TIMESTAMP
)
""")
conn.commit()

# Scheduler для выполнения задач по расписанию
scheduler = AsyncIOScheduler()

# Хранилище для сообщений и сентимента
message_sentiment_data = defaultdict(list)


# Создание базы данных и таблицы
def create_database():
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mess (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            text TEXT,
            sentiment REAL,
            date TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


create_database()


# Командный обработчик для старта
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я ваш бот.")


# Добавляем обработчик для команды админ панели
@dp.message_handler(commands=['admin'])
async def cmd_admin_panel(message: types.Message):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.is_chat_admin():
        await message.answer("Админ-панель активирована:", reply_markup=get_admin_panel())
    else:
        await message.answer("У вас нет прав администратора для вызова этой команды.")


@dp.message_handler(commands=['publish_weekly_post'])
async def cmd_publish_weekly_post(message: types.Message):
    print("Команда /publish_weekly_post вызвана")  # Логирование вызова команды
    await publish_weekly_post()
    await message.answer("Пост на основе обсуждаемых тем опубликован!")


# Функция для парсинга новостей с Medium
def parse_medium_news(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Проверьте, что получили правильный HTML
    print(f"Status Code for {url}: {response.status_code}")

    # Найти все ссылки на статьи
    articles = soup.find_all('a', class_='af ag ah ai aj ak al am an ao ap aq ar as at')
    print(f"Found {len(articles)} articles on {url}")

    news = []
    for article in articles:
        # Попробуйте найти заголовок разными способами
        title_tag = article.find('h2')
        if title_tag:
            title = title_tag.get_text(strip=True)
        else:
            continue  # Пропустите статью, если заголовок не найден

        # Найти ссылку на статью
        link = article.get('href')
        if link:
            # Полный URL статьи
            full_link = f"https://medium.com{link.split('?')[0]}"
            news.append({"title": title, "link": full_link})

    return news


def fetch_and_parse_news():
    urls = [
        "https://medium.com/tag/community-management",
        "https://medium.com/tag/community-building"
    ]

    all_news = []
    for url in urls:
        news = parse_medium_news(url)
        all_news.extend(news)  # Добавляем новости из текущего URL

    return all_news[:10]  # Возвращаем топ-10 новостей из всех URL


# Задача по публикации новостей с помощью бота
async def publish_news():
    news = fetch_and_parse_news()
    if not news:
        print("No news found.")
        return

    message = "🔥 Today's Community Management News:\n\n"
    for article in news:
        message += f"📰 {article['title']}\n🔗 {article['link']}\n\n"

    # Отправляем в топик чата "News"
    await bot.send_message(chat_id='-1002163548507', text=message)


# Командный обработчик для публикации новостей
@dp.message_handler(commands=['publish_news'])
async def cmd_publish_news(message: types.Message):
    await publish_news()
    await message.answer("Новости опубликованы!")


# Сохранение сообщений в базе данных
async def save_messages_to_db(chat_id, messages):
    for message_text in messages:
        cursor.execute(
            "INSERT INTO messages (chat_id, message_text, date) VALUES (?, ?, ?)",
            (chat_id, message_text, datetime.now())
        )
    conn.commit()


# Получение сообщений за вчерашний день
def get_yesterday_messages(chat_id):
    yesterday = datetime.now() - timedelta(days=1)
    cursor.execute(
        "SELECT message_text FROM messages WHERE chat_id = ? AND date >= ?",
        (chat_id, yesterday)
    )
    return [row[0] for row in cursor.fetchall()]


# Получение сообщений за текущий день
def get_today_messages(chat_id):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # Начало текущего дня
    logging.info(f"Получение сообщений для чата {chat_id} начиная с {today}")

    try:
        conn = sqlite3.connect('chat_messages.db')
        cursor = conn.cursor()

        cursor.execute(
            "SELECT message_text FROM messages WHERE chat_id = ? AND date >= ?",
            (chat_id, today)
        )

        messages = [row[0] for row in cursor.fetchall()]
        conn.close()

        if messages:
            logging.info(f"Найдено {len(messages)} сообщений для чата {chat_id}.")
        else:
            logging.info(f"Сообщения для чата {chat_id} не найдены.")

        return messages

    except Exception as e:
        logging.error(f"Ошибка при получении сообщений для чата {chat_id}: {e}")
        return []


# Функция для анализа тем и подсчета сообщений
async def analyze_topics_and_count(messages):
    combined_messages = "\n".join(messages)

    # Используем API OpenAI
    openai.api_key = "sk-proj-kEUip-CyUJBe7ZoiIm8iACgJic0fwFcojKJdwC7eR8-FWT8vrzlyQQw77lT3BlbkFJDUgLriLYDOVGLxfbjKOC" \
                     "FyHQyGgIS6UKabrF7zm4GtDW1i16zQsliGINIA"

    # Формируем запрос к модели
    prompt = (
        f"Проанализируй следующие сообщения и выдели основные темы, укажи для каждой темы количество сообщений. "
        f"Формат: Тема (количество сообщений):\n\n{combined_messages}"
    )

    try:
        # Выполнение запроса
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты аналитик чатов."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5  # Уменьшенная температура для снижения вероятности отклонений
        )

        # Обрабатываем ответ
        topics_summary = response['choices'][0]['message']['content'].strip()
        print(f"Ответ модели: {topics_summary}")

        # Регулярное выражение для извлечения тем
        pattern = re.compile(r'(.+?)\s*\((\d+)\)\s*')

        topics_counter = Counter()
        for line in topics_summary.splitlines():
            match = pattern.match(line)
            if match:
                topic = match.group(1).strip()
                count = int(match.group(2))
                topics_counter[topic] += count
            else:
                print(f"Не удалось распознать строку: {line}")

        return topics_counter

    except Exception as e:
        print(f"Ошибка при анализе тем: {e}")
        return Counter()  # Возвращаем пустой счетчик в случае ошибки


# Функция создания сводки обсуждений
async def generate_summary_new(chat_id, day_date):
    try:
        # Получаем вчерашние сообщения
        messages = get_today_messages(chat_id)

        if not messages:
            print("No messages found.")
            return

        # Анализируем темы и считаем количество сообщений по каждой теме
        topics_counter = await analyze_topics_and_count(messages)

        # Формируем итоговое сообщение
        summary_message = f"📝 Что обсуждалось вчера {day_date}:\n\n"
        for topic, count in topics_counter.items():
            summary_message += f"{topic} ({count} сообщений)\n"

        # Отправляем сообщение в чат
        await bot.send_message(chat_id='-1002163548507', text=summary_message, parse_mode="Markdown")

    except Exception as e:
        print(f"Ошибка при создании сводки: {e}")


# Функция создания сводки обсуждения без аргументов
async def generate_summary():
    try:
        # Используем фиксированный chat_id и дату
        chat_id = '-1002163548507'  # Идентификатор чата
        day_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")  # Вчерашняя дата

        # Получаем вчерашние сообщения
        messages = get_today_messages(chat_id)

        if not messages:
            print("No messages found.")
            return

        # Анализируем темы и считаем количество сообщений по каждой теме
        topics_counter = await analyze_topics_and_count(messages)

        # Формируем итоговое сообщение для отправки
        summary_message = f"📝 Что обсуждалось вчера {day_date}:\n\n"
        for topic, count in topics_counter.items():
            summary_message += f"{topic} ({count} сообщений)\n"

        # Отправляем сообщение в чат
        await bot.send_message(chat_id, text=summary_message, parse_mode="Markdown")

    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")


# Командный обработчик для ручного вызова отчета
@dp.message_handler(commands=['weekly_sentiment'])
async def cmd_weekly_sentiment(message: types.Message):
    avg_sentiment = calculate_weekly_sentiment(message.chat.id)

    if isinstance(avg_sentiment, str):
        sentiment_report = avg_sentiment
    else:
        sentiment_report = f"Средний сентимент сообщений за неделю: {avg_sentiment:.2f} (от -1 до 1)."

    await message.answer(sentiment_report)


# Командный обработчик для публикации новостей
@dp.message_handler(commands=['publish_job'])
async def cmd_publish_job(message: types.Message):
    await publish_jobs()
    await message.answer("Вакансии опубликованы!")


# Задача по созданию сводки обсуждений
#@dp.message_handler(commands=['publish_summary'])
#async def cmd_publish_summary(message: types.Message):
#    day_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
#    await generate_summary_new('-1002163548507', day_date)
#    await message.answer("Сводка обсуждений опубликована!")


# Задача по созданию сводки обсуждений
@dp.message_handler(commands=['publish_summary'])
async def cmd_publish_summary(message: types.Message):
    day_date = datetime.now().strftime("%Y-%m-%d")  # Текущая дата в формате YYYY-MM-DD
    await generate_summary_new('-1002163548507', day_date)
    await message.answer("Сводка обсуждений опубликована!")


# Сохранение новых сообщений из чата
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_new_message(message: types.Message):
    # Проверяем, является ли сообщение командой
    if message.text.startswith('/'):
        # Игнорируем команды
        return

    # Сохраняем сообщение в базу данных и анализируем сентимент
    await save_messages_to_db(message.chat.id, [message.text])
    sentiment_value = await analyze_sentiment(message.text)

    # Сохранение в базу данных
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO mess (chat_id, text, sentiment, date)
        VALUES (?, ?, ?, ?)
    ''', (message.chat.id, message.text, sentiment_value, datetime.now()))

    conn.commit()
    conn.close()

    await message.answer(f"Сообщение сохранено с сентиментом: {sentiment_value}")


# Функция для анализа сентимента сообщения с помощью OpenAI
async def analyze_sentiment(message_text):
    prompt = \
        f"Определи тональность следующего сообщения как -1 (негативное), 0 (нейтральное) или 1 (позитивное):\n\n{message_text}"

    openai.api_key = "sk-proj-kEUip-CyUJBe7ZoiIm8iACgJic0fwFcojKJdwC7eR8-FWT8vrzlyQQw77lT3BlbkFJDUgLriLYDOVGLxfbjKOCF" \
                     "yHQyGgIS6UKabrF7zm4GtDW1i16zQsliGINIA"

    # Используем новую модель OpenAI для определения тем обсуждения
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=1,
        temperature=0.0
    )

    response_message = response['choices'][0]['message']['content'].strip()

    try:
        sentiment_value = float(response_message)
    except ValueError:
        sentiment_value = 0  # Если не удалось распознать сентимент, считаем нейтральным

    return sentiment_value


# Функция для фильтрации спама
@dp.message_handler(lambda message: is_spam(message))
async def handle_spam(message: types.Message):
    await message.delete()
    await message.reply("⚠️ Спам был удален.")


# Логика определения спама
def is_spam(message: types.Message) -> bool:
    if message.text.startswith('/'):
        return False  # Команды бота не считаются спамом

    spam_patterns = [
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',  # Ссылки
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # Email
        r'(?i)(free|click here|buy now|limited time offer|sale)',  # Спам-слова
        r'([0-9]{10})',  # Телефонные номера
    ]

    if any(re.search(pattern, message.text) for pattern in spam_patterns):
        return True

    if message.forward_from or len(message.text.split()) < 3:
        return True

    return False


def get_admin_panel():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        KeyboardButton("/publish_news"),
        KeyboardButton("/publish_summary"),
        KeyboardButton("/weekly_sentiment"),
        KeyboardButton("/publish_weekly_post"),  # Новая кнопка для публикации контента
    ]
    keyboard.add(*buttons)
    return keyboard


async def generate_content_from_topics(chat_id):
    # Получаем сообщения за предыдущий день
    messages = get_today_messages(chat_id)

    if not messages:
        print("No messages found.")
        return

    # Анализируем темы и считаем количество сообщений по каждой теме
    topics_counter = await analyze_topics_and_count(messages)

    # Формируем список тем для запроса к OpenAI
    topics_list = "\n".join([f"{topic}" for topic, _ in topics_counter.items()])

    # Используем API OpenAI для генерации контента по темам
    openai.api_key = 'sk-proj-kEUip-CyUJBe7ZoiIm8iACgJic0fwFcojKJdwC7eR8-FWT8vrzlyQQw77lT3BlbkFJDUgLriLYDOVGLxfbjK' \
                     'OCFyHQyGgIS6UKabrF7zm4GtDW1i16zQsliGINIA'

    prompt = (
        f"Создай информативный и интересный пост по следующим темам, которые обсуждали вчера в чате. "
        f"Необходимо раскрыть эти темы и дать рекомендации или информацию, полезную для участников чата:\n\n{topics_list}"
    )

    try:
        # Выполнение запроса к модели OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты пишешь информативные посты для обсуждений в Telegram чате."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,  # Ограничение на количество символов
            temperature=0.7  # Баланс креативности и точности
        )

        # Получаем сгенерированный контент
        content = response['choices'][0]['message']['content'].strip()
        print(f"Сгенерированный контент: {content}")

        return content

    except Exception as e:
        print(f"Ошибка при генерации контента: {e}")
        return None


async def publish_weekly_post():
    chat_id = '-1002163548507'  # Идентификатор чата

    print("Начало публикации поста...")  # Логирование
    content = await generate_content_from_topics(chat_id)

    if content:
        print(f"Сгенерированный контент: {content}")  # Логируем контент

        # Разбиваем сообщение, если оно слишком длинное
        messages = split_message(content)

        # Отправляем каждую часть сообщения
        for part in messages:
            print(f"Отправляем часть сообщения: {part}")  # Логируем отправку каждой части
            await send_message_with_retry(bot, chat_id, part)
            await asyncio.sleep(5)
    else:
        print("Не удалось сгенерировать контент для поста.")  # Логирование в случае ошибки


# Добавляем обработчик для команды админ панели
@dp.message_handler(commands=['admin'])
async def cmd_admin_panel(message: types.Message):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.is_chat_admin():
        await message.answer("Админ-панель активирована:", reply_markup=get_admin_panel())
    else:
        await message.answer("У вас нет прав администратора для вызова этой команды.")


# Функция для разбиения текста на части по ограничению Telegram
def split_message(text, max_length=4096):
    # Разделяем сообщение на части по длине
    messages = []
    while len(text) > max_length:
        # Найдем ближайший символ новой строки, чтобы разбить текст корректно
        split_pos = text[:max_length].rfind('\n')
        if split_pos == -1:
            split_pos = max_length
        messages.append(text[:split_pos])
        text = text[split_pos:].strip()
    messages.append(text)
    return messages


# Функция для отправки сообщения с обработкой исключений
async def send_message_with_retry(bot, chat_id, text):
    while True:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            break  # Выход из цикла, если сообщение успешно отправлено
        except RetryAfter as e:
            wait_time = e.timeout
            print(f"Flood control exceeded. Retrying in {wait_time} seconds.")
            await asyncio.sleep(wait_time)


# Функция для публикации вакансий ботом
async def publish_jobs():
    # Парсинг данных с нескольких сайтов
    driver_path = "chromedriver.exe"
    jobs_site_1 = scrape_jobs(url="https://jobstash.xyz/jobs", chrome_driver_path=driver_path,
                              headless=True, max_pages=5)

    url_2 = "https://cryptocurrencyjobs.co"
    jobs_site_2 = scrape_jobs_2(url_2, driver_path, num_pages=3, pause_time=5, headless=True)

    url_3 = "https://cryptojobslist.com"
    jobs_site_3 = scrape_jobs_3(url_3, driver_path)

    url_4 = 'https://degencryptojobs.com/'
    jobs_site_4 = scrape_jobs_4(driver_path, url_4, headless=True)

    # Собираем все вакансии в один список
    all_jobs = jobs_site_1 + jobs_site_2 + jobs_site_3 + jobs_site_4

    if not all_jobs:
        print("No jobs found.")
        return

    # Формируем сообщение для отправки
    message = "💼 Вакансии на сегодня:\n\n"
    for job in all_jobs:
        message += f"📌 Название должности: {job['title']}\n"
        message += f"🏢 Компания: {job['company']}\n"
        message += f"🌍 Место работы: {job['work_mode']}\n"
        message += f"🔗 Ссылка на вакансию: {job['link']}\n"
        message += "-" * 40 + "\n\n"

    # Разбиваем сообщение, если оно слишком длинное
    messages = split_message(message)

    # Отправляем каждую часть сообщения
    for part in messages:
        await send_message_with_retry(bot, chat_id='-1002163548507', text=part)
        await asyncio.sleep(10)


@dp.message_handler(content_types=["new_chat_members"])
async def new_member(message: types.Message):
    welcome_message = (
        "🌟 Welcome to the Community Managers' HUB!\n"
        "This is your go-to place for exchanging experiences, finding collaborations, and growing together.\n"
        "Share insights, seek advice, or partner on projects, our community of CMs is here to support you."
    )

    # Отправляем приветственное сообщение и сохраняем его
    sent_message = await bot.send_message(message.chat.id, welcome_message, parse_mode="html")

    # Ждём 30 секунд
    await asyncio.sleep(30)

    # Удаляем сообщение
    await bot.delete_message(chat_id=message.chat.id, message_id=sent_message.message_id)


# Функция для расчета среднего сентимента за неделю
def calculate_weekly_sentiment(chat_id):
    one_week_ago = datetime.now() - timedelta(days=7)

    # Подключаемся к базе данных
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT sentiment FROM mess 
        WHERE chat_id = ? AND date >= ?
    ''', (chat_id, one_week_ago))

    messages_in_week = cursor.fetchall()
    conn.close()

    if not messages_in_week:
        return "Недостаточно данных для анализа сентимента."

    # Подсчет среднего сентимента
    total_sentiment = sum(msg[0] for msg in messages_in_week)
    average_sentiment = total_sentiment / len(messages_in_week)

    return average_sentiment


# Задача для публикации еженедельного отчета
async def publish_weekly_sentiment_report():
    conn = sqlite3.connect('mess.db')
    cursor = conn.cursor()

    # Получаем уникальные чаты
    cursor.execute('SELECT DISTINCT chat_id FROM mess')
    chat_ids = cursor.fetchall()

    for chat_id_tuple in chat_ids:
        chat_id = chat_id_tuple[0]
        avg_sentiment = calculate_weekly_sentiment(chat_id)

        if isinstance(avg_sentiment, str):
            sentiment_report = avg_sentiment  # Если недостаточно данных
        else:
            sentiment_report = f"Средний сентимент сообщений за неделю: {avg_sentiment:.2f} (от -1 до 1)."

        # Отправляем отчет в чат
        await bot.send_message('-1002163548507', sentiment_report)

    conn.close()


# Настройка задач по расписанию
scheduler.add_job(publish_news, "cron", hour=9, minute=0)
scheduler.add_job(generate_summary, "cron", hour=10, minute=0)
scheduler.add_job(publish_jobs, "cron", hour=11, minute=0)
scheduler.add_job(publish_weekly_sentiment_report, 'cron', day_of_week='mon', hour=9, minute=0)
scheduler.add_job(publish_weekly_post, 'cron', day_of_week='mon', hour=12, minute=0)


# Запуск бота и планировщика
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)
