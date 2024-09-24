from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def init_driver(chrome_driver_path="chromedriver.exe", headless=True):
    """Инициализирует веб-драйвер с опциональными настройками для headless режима."""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

    # Укажите путь к вашему chromedriver
    webdriver_service = Service(chrome_driver_path)
    driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)
    return driver

def close_popup_if_present(driver):
    """Закрывает всплывающее окно, если оно есть."""
    try:
        time.sleep(2)  # Ждем появления всплывающего окна
        ok_button = driver.find_element(By.XPATH, "//footer//button[text()='OK']")
        if ok_button.is_displayed():
            ok_button.click()
            print("Всплывающее окно закрыто.")
        else:
            print("Кнопка 'OK' не найдена.")
    except Exception as e:
        print(f"Ошибка при закрытии всплывающего окна: {e}")

def scroll_and_wait(driver, max_pages=2, wait_time=30, pause_time=2):
    """Прокручивает страницу вниз, ожидая загрузки новых данных."""
    last_height = driver.execute_script("return document.body.scrollHeight")

    for page in range(max_pages):
        print(f"Обрабатываем страницу {page + 1}")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)
        print(f"Ожидание {wait_time} секунд для загрузки...")
        time.sleep(wait_time)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("Больше страниц не найдено. Останавливаем прокрутку.")
            break
        last_height = new_height

def parse_jobs(driver):
    """Парсит вакансии с сайта и возвращает список найденных вакансий."""
    job_elements = driver.find_elements(By.TAG_NAME, 'a')
    print(f"Найдено вакансий: {len(job_elements)}")

    jobs = []
    for job_element in job_elements:
        try:
            job_title = job_element.find_element(By.TAG_NAME, 'h3').text.strip() \
                if job_element.find_elements(By.TAG_NAME, 'h3') else ""
            company_name = job_element.find_element(By.TAG_NAME, 'h4').text.strip() \
                if job_element.find_elements(By.TAG_NAME, 'h4') else ""
            span_elements = job_element.find_elements(By.CSS_SELECTOR, 'button div.truncate span.__variable_22b3a9')
            work_mode = span_elements[2].text.strip() if len(span_elements) >= 3 else ""
            job_link = job_element.get_attribute('href') if job_element.get_attribute('href') else ""

            if job_title and company_name and job_link:
                jobs.append({
                    'title': job_title,
                    'company': company_name,
                    'work_mode': work_mode,
                    'link': job_link
                })

        except Exception as e:
            print(f"Ошибка при извлечении данных: {e}")

    return jobs

def quit_driver(driver):
    """Закрывает браузер."""
    driver.quit()

def scrape_jobs(url="https://jobstash.xyz/jobs", chrome_driver_path="chromedriver/chromedriver.exe", headless=True, max_pages=2):
    """Основная функция для запуска парсинга вакансий."""
    driver = init_driver(chrome_driver_path, headless)
    try:
        driver.get(url)
        close_popup_if_present(driver)
        scroll_and_wait(driver, max_pages)
        jobs = parse_jobs(driver)
        return jobs
    finally:
        quit_driver(driver)
