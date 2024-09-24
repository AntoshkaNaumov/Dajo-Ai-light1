import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


def init_webdriver(driver_path: str, headless: bool = False):
    """Инициализирует веб-драйвер с заданными параметрами."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

    webdriver_service = Service(driver_path)
    driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
    return driver


def scroll_and_wait(driver, num_pages=3, pause_time=30):
    """Прокручивает страницу вниз указанное количество раз с паузой."""
    for page in range(num_pages):
        print(f"Прокручиваем страницу {page + 1}...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)


def parse_job_listings(driver, url: str):
    """Открывает страницу, прокручивает её и парсит вакансии."""
    driver.get(url)

    # Выполняем прокрутку страницы для подгрузки всех элементов
    scroll_and_wait(driver, num_pages=3, pause_time=30)

    # Поиск всех элементов вакансий
    job_elements = driver.find_elements(By.CSS_SELECTOR, 'a.chakra-link.css-1tor594')
    print(f"Парсинг сайта {url}")
    print(f"Найдено вакансий: {len(job_elements)}")

    jobs = []

    # Перебираем карточки вакансий и извлекаем информацию
    for job_element in job_elements:
        try:
            # Извлекаем ссылку на вакансию
            job_link = job_element.get_attribute('href')

            # Извлекаем название компании и должности
            job_info = job_element.find_element(By.CSS_SELECTOR, 'p.chakra-text.css-19t0clg').text.strip()

            # Разделяем текст на компанию и должность (с ограничением по разбиению)
            job_info_split = job_info.split(" - ", 1)
            if len(job_info_split) == 2:
                company_name, job_title = job_info_split
            else:
                company_name = job_info_split[0]
                job_title = ""

            # Извлекаем место работы (например, "Remote")
            work_location = job_element.find_element(By.CSS_SELECTOR, 'p.chakra-text.css-9eiwmc').text.strip()

            # Сохраняем информацию о вакансии в список
            jobs.append({
                "title": job_title,
                "company": company_name,
                "work_mode": work_location,
                "link": job_link
            })

        except Exception as e:
            print(f"Ошибка при извлечении данных: {e}")
            continue

    return jobs


def close_driver(driver):
    """Закрывает веб-драйвер."""
    driver.quit()


# Функция для полного процесса сбора вакансий
def scrape_jobs_4(driver_path: str, url: str, headless: bool = False):
    """Инициализирует драйвер, парсит сайт и возвращает список вакансий."""
    driver = init_webdriver(driver_path, headless)
    try:
        jobs = parse_job_listings(driver, url)
    finally:
        close_driver(driver)

    return jobs
