import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
import urllib.parse
import time
import schedule
import db

# Search keywords for Dedolytics target audience
KEYWORDS = ["Director of Analytics", "CTO", "Analytics Manager", "Analytics Lead", "Head of Data"]


async def enrich_contact(company_name, job_title):
    """
    Placeholder for an enrichment service like Hunter.io or Apollo API.
    Since raw job boards don't post hiring manager emails, a real production system
    would take the `company_name` and `job_title` here, query Apollo/Hunter, and return
    a real person's name and email.
    """
    # Returning None for now to ensure NO fake data is inserted into the DB during testing
    return None


async def scrape_linkedin_jobs(keyword):
    """
    Scrapes the public (unlogged) LinkedIn Jobs portal for a given keyword.
    Note: Public scraping is heavily rate-limited and layout changes often.
    For high volume, a premium API or authenticated session is highly recommended.
    """
    url_keyword = urllib.parse.quote(keyword)
    url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location=United%20States&geoId=103644278&trk=public_jobs_jobs-search-bar_search-submit&position=1&pageNum=0"

    print(f"[*] Starting scrape for keyword: {keyword}")

    async with async_playwright() as p:
        # Launching Chromium in headless mode (change to headless=False to debug)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Apply stealth to evade basic bot detection
        await stealth_async(page)

        try:
            await page.goto(url, wait_until="domcontentloaded")
            # Wait for job cards to load
            await page.wait_for_selector("ul.jobs-search__results-list", timeout=10000)

            # Scroll down to load more jobs (simulating user behavior)
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Parse the job listings
            job_cards = soup.select("ul.jobs-search__results-list > li")
            print(f"[*] Found {len(job_cards)} job listings for '{keyword}'")

            for card in job_cards:
                try:
                    title_elem = card.find("h3", class_="base-search-card__title")
                    company_elem = card.find("h4", class_="base-search-card__subtitle")
                    location_elem = card.find("span", class_="job-search-card__location")
                    link_elem = card.find("a", class_="base-card__full-link")

                    if not title_elem or not company_elem or not link_elem:
                        continue

                    title = title_elem.text.strip()
                    company = company_elem.text.strip()

                    # Ensure we don't scrape our current clients/restricted targets
                    BLACKLISTED_COMPANIES = ["petvalu", "retailogists"]
                    if any(blacklisted in company.lower() for blacklisted in BLACKLISTED_COMPANIES):
                        print(f"[*] Skipping blacklisted company: {company}")
                        continue

                    location = location_elem.text.strip() if location_elem else "Unknown"
                    link = link_elem.get("href", "").split("?")[0]  # Remove tracking params

                    # Store in Database
                    # `db.upsert_job` returns the ID if new, or None if it existed
                    job_id = db.upsert_job(title, company, link, description="", location=location)

                    if job_id:
                        print(f"[+] NEW JOB: {title} at {company}")
                        # If the job is new, try to find a contact
                        contact = await enrich_contact(company, title)
                        if contact:
                            db.add_contact(
                                job_id,
                                contact["name"],
                                contact["email"],
                                contact["title"],
                                contact["phone"],
                                contact["linkedin"],
                            )
                except Exception as e:
                    print(f"[-] Error parsing job card: {e}")

        except Exception as e:
            print(f"[-] Failed to load LinkedIn for {keyword}: {e}")
        finally:
            await browser.close()


def run_scraper_cycle():
    """Runs the scraper for all keywords sequentially."""
    print(f"\n--- Starting Scraper Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # Initialize DB (if not exists)
    db.init_db()

    for kw in KEYWORDS:
        # Run the async scraper via asyncio
        asyncio.run(scrape_linkedin_jobs(kw))

        # Avoid hammering the server too quickly
        time.sleep(5)

    print(f"--- Finished Scraper Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    # If run manually, run once
    run_scraper_cycle()

    # To run this 24/7 without cron, uncomment below and keep process alive:
    # schedule.every(4).hours.do(run_scraper_cycle)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)
