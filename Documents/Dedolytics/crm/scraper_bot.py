import asyncio
import os
import json
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
import urllib.parse
import time
import schedule
import db
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Search keywords for Dedolytics target audience
KEYWORDS = ["Data Analyst", "Senior Data Analyst", "Analytics Engineer", "Data Engineer"]

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


async def extract_context_with_gemini(description_text, company, title):
    """Uses Gemini to extract the department and hiring manager from the raw JD."""
    if not os.getenv("GEMINI_API_KEY"):
        return "Analytics", None

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    You are an expert at parsing B2B job descriptions.
    I am providing you a Job Description for a "{title}" role at "{company}".
    
    Extract two things from the text:
    1. "department": What department this role falls under (e.g., Marketing, Engineering, Product, Finance, Operations, Sales, IT). If not explicitly stated, guess based on context. Return ONLY the 1-2 word department name. Default to "Analytics" if totally unsure.
    2. "hiring_manager": If the job description explicitly mentions who this role reports to BY NAME AND TITLE or JUST TITLE (e.g., "reports to Jane Doe, VP of Data" or "reporting to the Director of Demand Gen"), extract that exact title or name+title. If it is NOT explicitly mentioned or just says "reports to the manager", return null.
    
    Return the result EXCLUSIVELY as valid JSON. Do not include markdown blocks or any other text.
    
    Format:
    {{
      "department": "string",
      "hiring_manager": "string or null"
    }}
    
    Job Description:
    {description_text}
    """

    try:
        response = model.generate_content(prompt)
        # Clean potential markdown formatting
        raw_text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(raw_text)

        dept = data.get("department", "Analytics")
        mgr = data.get("hiring_manager")
        return dept, mgr
    except Exception as e:
        print(f"      [-] Gemini parsing failed: {e}")
        return "Analytics", None


async def scrape_linkedin_jobs(keyword):
    """
    Scrapes the public (unlogged) LinkedIn Jobs portal for a given keyword.
    Now performs a 'Deep Scrape' by visiting individual job pages.
    """
    url_keyword = urllib.parse.quote(keyword)
    # f_TPR=r259200 filters for jobs posted in the last 3 days
    url = f"https://www.linkedin.com/jobs/search?keywords={url_keyword}&location=United%20States&geoId=103644278&f_TPR=r259200&trk=public_jobs_jobs-search-bar_search-submit&position=1&pageNum=0"

    print(f"[*] Starting scrape for keyword: {keyword} (Filter: Last 3 Days)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_async(page)

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector("ul.jobs-search__results-list", timeout=10000)

            # Scroll down to load more jobs
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            job_cards = soup.select("ul.jobs-search__results-list > li")
            print(f"[*] Found {len(job_cards)} job listings for '{keyword}'")

            # To avoid an instant IP ban, we will only deep-scrape the first 5 new jobs per keyword per run
            scrape_count = 0

            for card in job_cards:
                if scrape_count >= 5:
                    print("      [!] Reached deep-scrape limit (5) for this keyword to avoid bans. Moving on.")
                    break

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
                        continue

                    location = location_elem.text.strip() if location_elem else "Unknown"
                    link = link_elem.get("href", "").split("?")[0]

                    # 1. Insert placeholder to see if it's NEW
                    job_id = db.upsert_job(title, company, link, description="", location=location)

                    if job_id:
                        print(f"[+] NEW JOB: {title} at {company}")
                        scrape_count += 1

                        # 2. Deep Scrape the Job Description
                        try:
                            jd_page = await context.new_page()
                            await stealth_async(jd_page)

                            # Add random delay to prevent rate limit
                            delay = random.uniform(2.0, 5.0)
                            print(f"      [~] Waiting {delay:.1f}s before fetching description...")
                            await asyncio.sleep(delay)

                            await jd_page.goto(link, wait_until="domcontentloaded")
                            await jd_page.wait_for_selector(
                                ".description__text, .show-more-less-html__markup", timeout=8000
                            )

                            jd_html = await jd_page.content()
                            jd_soup = BeautifulSoup(jd_html, "html.parser")

                            desc_elem = jd_soup.select_one(".description__text, .show-more-less-html__markup")
                            description_text = desc_elem.text.strip() if desc_elem else "Failed to parse JD HTML."

                            # Clean up extremely long JDs
                            if len(description_text) > 8000:
                                description_text = description_text[:8000]

                            await jd_page.close()

                            # 3. Parse with Gemini
                            print("      [~] Handing JD to Gemini for Department & Manager extraction...")
                            dept, mgr = await extract_context_with_gemini(description_text, company, title)

                            print(f"      [+] Parsed Context -> Dept: {dept} | Mgr: {mgr}")

                            # 4. Final DB Update (db.py needs an update_job_context function, or we use a raw inline query)
                            conn = db.get_connection()
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE jobs SET description = ?, department = ?, hiring_manager = ? WHERE id = ?",
                                (description_text, dept, mgr, job_id),
                            )
                            conn.commit()
                            conn.close()

                        except Exception as e:
                            print(f"      [-] Failed to deep-scrape description: {e}")

                except Exception as e:
                    print(f"[-] Error parsing job card: {e}")

        except Exception as e:
            print(f"[-] Failed to load LinkedIn for {keyword}: {e}")
        finally:
            await browser.close()


def run_scraper_cycle():
    """Runs the scraper for all keywords sequentially."""
    print(f"\n--- Starting Scraper Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    db.init_db()

    for kw in KEYWORDS:
        asyncio.run(scrape_linkedin_jobs(kw))
        time.sleep(5)

    print(f"--- Finished Scraper Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    run_scraper_cycle()
