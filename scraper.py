# scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def initialize_driver(chromedriver_path):
    """Инициализация веб-драйвера Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")

    webdriver_service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
    return driver

def scroll_and_load_more(driver, max_attempts=5, wait_time=30, pause_time=2):
    """Прокручивает страницу вниз и ожидает загрузки новых данных."""
    attempt = 0
    while attempt < max_attempts:
        print(f"Попытка {attempt + 1}")

        # Прокручиваем страницу вниз
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Ждем паузу для подгрузки данных
        time.sleep(pause_time)

        # Ждем указанное время на странице для полной загрузки
        print(f"Ожидание {wait_time} секунд для загрузки...")
        time.sleep(wait_time)

        # Проверяем наличие кнопки "Load more" и кликаем на нее, если она есть
        try:
            load_more_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Load more')]")
            if load_more_button.is_displayed():
                load_more_button.click()
                print("Нажата кнопка 'Load more'.")
                attempt = 0  # Сбросить счётчик попыток, так как данные загружаются
            else:
                break
        except:
            print("Кнопка 'Load more' не найдена или не доступна.")
            break

        attempt += 1

def scrape_jobs_3(url, chromedriver_path):
    """Открывает URL, прокручивает страницу и извлекает информацию о вакансиях."""
    driver = initialize_driver(chromedriver_path)
    driver.get(url)

    # Прокручиваем страницы и ждем
    scroll_and_load_more(driver)

    # Поиск всех элементов вакансий
    job_elements = driver.find_elements(By.TAG_NAME, 'tr')

    print(f"Парсинг сайта {url}")
    print(f"Найдено вакансий: {len(job_elements)}")

    job_list = []

    # Перебираем карточки вакансий и извлекаем информацию
    for job_element in job_elements:
        try:
            # Название должности
            job_title_element = job_element.find_element(By.CSS_SELECTOR, 'a.job-title-text')
            job_title = job_title_element.text.strip()

            # Название компании
            company_name_element = job_element.find_element(By.CSS_SELECTOR, 'a.job-company-name-text')
            company_name = company_name_element.text.strip()

            # Место работы (используем find_elements для избежания ошибки, если элемента нет)
            location_elements = job_element.find_elements(By.CSS_SELECTOR, 'span.job-location-text')
            work_mode = location_elements[0].text.strip() if location_elements else "Не указано"

            # Ссылка на вакансию (находится в атрибуте href того же элемента, что и название должности)
            job_link = job_title_element.get_attribute('href')

            # Проверка на пустые значения, чтобы пропускать некорректные записи
            if job_title and company_name and job_link:
                # Сохраняем информацию в список
                job_list.append({
                    'title': job_title,
                    'company': company_name,
                    'work_mode': work_mode,
                    'link': job_link
                })

        except Exception:
            # Пропускаем вакансии, если не удается найти необходимые элементы
            pass

    # Закрываем браузер
    driver.quit()

    return job_list
