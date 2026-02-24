import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from bs4 import BeautifulSoup
import urllib.parse
import time
import db
import random


async def search_duckduckgo_for_manager(company_name):
    """
    Searches DuckDuckGo for the Head of Data / Director of Analytics at a specific company.
    DuckDuckGo is used here because it has fewer aggressive bot protections than Google.
    """
    query = f'"{company_name}" ("Head of Data" OR "Director of Analytics" OR "VP of Data" OR "Hiring Manager") LinkedIn'
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    print(f"      [Search] Querying: {query}")

    manager_name = None
    manager_title = "Data Leader"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_async(page)

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 3.0))  # Be polite to DDG

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Parse DDG HTML results
            results = soup.find_all("a", class_="result__snippet")
            titles = soup.find_all("h2", class_="result__title")

            if titles:
                # We just take the absolute first result as the most likely candidate
                first_title_text = titles[0].text.strip()

                # LinkedIn titles usually look like: "John Doe - Head of Data - Stripe | LinkedIn"
                if "-" in first_title_text:
                    parts = first_title_text.split("-")
                    manager_name = parts[0].strip()
                    if len(parts) > 1:
                        manager_title = parts[1].replace(" | LinkedIn", "").strip()

                # Basic sanity check to ensure we didn't just grab a company page
                if manager_name and (
                    company_name.lower() in manager_name.lower() or "linkedin" in manager_name.lower()
                ):
                    manager_name = None  # False positive

        except Exception as e:
            print(f"      [-] Search failed for {company_name}: {e}")
        finally:
            await browser.close()

    return manager_name, manager_title


def generate_email_permutations(name, company_name):
    """
    Given a person's name and a company, generates the most common corporate email formats.
    e.g. John Doe at Stripe -> jdoe@stripe.com, john.doe@stripe.com, john@stripe.com
    """
    if not name or len(name.split()) < 2:
        return None

    parts = name.lower().split()
    first = parts[0]
    last = parts[-1]

    # Strip common corporate suffixes from company name to guess the domain
    clean_company = company_name.lower()
    for suffix in [" inc", " llc", " corp", " ltd", " group", " solutions", ",", "."]:
        clean_company = clean_company.replace(suffix, "")

    domain = clean_company.replace(" ", "") + ".com"

    # We will just return the most common B2B format (first.last@domain.com) for simplicity
    # A robust system would ping these against an SMTP verifier
    best_guess = f"{first}.{last}@{domain}"
    return best_guess


def run_enrichment_cycle():
    """Reads unenriched jobs, searches for managers, and updates the DB."""
    print(f"\n--- Starting Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # Query all 'new' jobs that don't have a contact yet
    conn = db.get_connection()
    cursor = conn.cursor()
    # We check if a contact exists for the job. If not, we enrich.
    cursor.execute(
        """
        SELECT j.id, j.company 
        FROM jobs j
        LEFT JOIN contacts c ON j.id = c.job_id
        WHERE j.status = 'new' AND c.id IS NULL
    """
    )
    unenriched_jobs = cursor.fetchall()
    conn.close()

    print(f"[*] Found {len(unenriched_jobs)} jobs needing contact enrichment.")

    success_count = 0

    for job_id, company in unenriched_jobs:
        print(f"\n[*] Enriching: {company}")

        # 1. Search for Manager
        name, title = asyncio.run(search_duckduckgo_for_manager(company))

        if name:
            print(f"      [+] Found Manager: {name} ({title})")
            # 2. Guess Email
            email = generate_email_permutations(name, company)
            print(f"      [+] Generated Email: {email}")

            # 3. Save to DB
            db.add_contact(job_id, name, email, title)
            success_count += 1

            # Flag job as enriched so outreach picks it up
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'enriched' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()

        else:
            print(f"      [-] Could not definitively find a manager for {company}.")

    print(f"\n[*] Enrichment Complete. Successfully enriched {success_count} contacts.")
    print(f"--- Finished Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    db.init_db()
    run_enrichment_cycle()
