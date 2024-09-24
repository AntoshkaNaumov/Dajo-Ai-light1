from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Функция для прокрутки страницы вниз и задержки на странице
def scroll_and_wait(driver, num_pages=3, pause_time=5):
    """Прокручивает страницу вниз указанное количество раз с ожиданием загрузки новых элементов."""
    for page in range(num_pages):
        print(f"Прокручиваем страницу {page + 1}...")

        # Прокручиваем страницу вниз
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Ждем появления новых элементов (если они есть)
        try:
            WebDriverWait(driver, pause_time).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'ais-Hits-list'))
            )
        except Exception as e:
            print(f"Не удалось найти новые элементы на странице {page + 1}: {e}")
            break

        # Ждем паузу перед следующей прокруткой
        time.sleep(pause_time)

# Функция для парсинга вакансий
def scrape_jobs_2(url, driver_path, num_pages=3, pause_time=5, headless=True):
    """Парсит вакансии с указанного сайта, возвращает список вакансий."""

    # Настройки для запуска браузера без графического интерфейса (опционально для серверов)
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

    # Инициализация веб-драйвера
    webdriver_service = Service(driver_path)
    driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)

    try:
        # Открываем нужную страницу
        driver.get(url)

        # Выполняем прокрутку страницы для подгрузки вакансий
        scroll_and_wait(driver, num_pages=num_pages, pause_time=pause_time)

        # Поиск всех элементов списка вакансий
        job_elements = driver.find_elements(By.CSS_SELECTOR, 'ol.ais-Hits-list > li')
        print(f"Найдено вакансий: {len(job_elements)}")

        jobs = []
        # Перебираем карточки вакансий и извлекаем информацию
        for job_element in job_elements:
            try:
                # Название должности
                job_title_element = job_element.find_element(By.CSS_SELECTOR, 'h2 a')
                job_title = job_title_element.text.strip()

                # Название компании
                company_name_element = job_element.find_element(By.CSS_SELECTOR, 'h3 a')
                company_name = company_name_element.text.strip()

                # Место работы
                location_element = job_element.find_element(By.CSS_SELECTOR, 'ul li a')
                work_mode = location_element.text.strip() if location_element else "Не указано"

                # Ссылка на вакансию
                job_link = job_title_element.get_attribute('href')

                # Сохраняем информацию о вакансии
                jobs.append({
                    'title': job_title,
                    'company': company_name,
                    'work_mode': work_mode,
                    'link': job_link
                })

            except Exception as e:
                #print(f"Ошибка при обработке вакансии: {e}")
                continue

        return jobs

    finally:
        # Закрываем браузер
        driver.quit()
