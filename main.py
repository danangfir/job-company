import json
import asyncio
from typing import List, Dict
from httpx import AsyncClient, Response
from parsel import Selector
from loguru import logger as log
from selenium import webdriver
import chromedriver_autoinstaller
import time

chromedriver_autoinstaller.install()


def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    return driver


async def create_client():
    return AsyncClient(
        http2=True,
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/96.0.4664.110 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        },
    )


def strip_text(text: str) -> str:
    return text.strip().replace('\n', "") if text else ""


def parse_jobs(html: str) -> Dict:
    selector = Selector(html)
    total_result = selector.xpath("//span[contains(@class, 'job-count')]/text()").get()
    total_result = int(total_result.replace(",", "").replace("+", "")) if total_result else None
    data = []

    for element in selector.xpath("//section[contains(@class, 'results-list')]/ul/li"):
        data.append({
            "title": strip_text(element.xpath(".//div/a/span/text()").get()),
            "company": strip_text(element.xpath(".//div/div[contains(@class, 'info')]/h4/a/text()").get()),
            "address": strip_text(element.xpath(".//div/div[contains(@class, 'info')]/div/span/text()").get()),
            "timeAdded": element.xpath(".//div/div[contains(@class, 'info')]/div/time/@datetime").get(),
            "joburl": strip_text(element.xpath(".//div/a/@href").get().split("?")[0]),
            "companyUrl": strip_text(
                element.xpath(".//div/div[contains(@class, 'info')]/h4/a/@href").get().split("?")[0]),
            "salary": strip_text(element.xpath(".//span[contains(@class, 'salary')]/text()").get()),
        })

    return {"data": data, "total_result": total_result}


async def scrape_jobs(url: str) -> List[Dict]:
    client = await create_client()
    try:
        response = await client.get(url)
        parsed_data = parse_jobs(response.text)
        data = parsed_data["data"]
        log.success(f"Scraped {len(data)} jobs from LinkedIn job pages")
        return data
    finally:
        await client.aclose()


def scroll_down(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait to load page
        time.sleep(3)

        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def navigate_pages(driver, url):
    driver.get(url)
    time.sleep(3)  # Wait for page to load

    scroll_down(driver)
    page_source = driver.page_source
    return page_source


async def run(url: str):
    driver = init_driver()
    try:
        page_source = navigate_pages(driver, url)
    finally:
        driver.quit()

    job_search_data = parse_jobs(page_source)
    with open("company_jobs.json", "w", encoding="utf-8") as file:
        json.dump(job_search_data["data"], file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    url = ("https://www.linkedin.com/jobs/search/?currentJobId=3874652737&f_C=13336409&geoId=92000000&origin"
           "=COMPANY_PAGE_JOBS_CLUSTER_EXPANSION&originToLandingJobPostings=3874652737,3910794166,3943987844,"
           "3943990200,3910788604,3939317270,3874652736,3939314830,3819586247")
    asyncio.run(run(url))
