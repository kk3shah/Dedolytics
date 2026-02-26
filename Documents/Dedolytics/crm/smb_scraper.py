import os
import time
import re
import urllib.parse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import db

# Core targeted list for Mississauga SMBs
SEARCH_QUERIES = [
    # Food & Bev
    "restaurants mississauga ontario",
    "bakeries mississauga ontario",
    "cafes mississauga ontario",
    "catering mississauga ontario",
    # Fitness & Health
    "gyms mississauga ontario",
    "yoga studios mississauga ontario",
    "martial arts mississauga ontario",
    "chiropractors mississauga ontario",
    "dental clinics mississauga ontario",
    "physiotherapy mississauga ontario",
    "optometrists mississauga ontario",
    # Retail
    "convenience stores mississauga ontario",
    "boutiques mississauga ontario",
    "florists mississauga ontario",
    "pet stores mississauga ontario",
    "hardware stores mississauga ontario",
    # Auto & Services
    "auto repair shops mississauga ontario",
    "car wash mississauga ontario",
    "plumbers mississauga ontario",
    "electricians mississauga ontario",
    "landscaping mississauga ontario",
    "cleaning services mississauga ontario",
]

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"


def extract_emails_from_text(text):
    return set(re.findall(EMAIL_REGEX, text))


from ddgs import DDGS


def is_valid_domain(href):
    invalid_domains = [
        "duckduckgo",
        "yelp",
        "yellowpages",
        "tripadvisor",
        "facebook",
        "instagram",
        "linkedin",
        "twitter",
        "canpages",
        "411.ca",
        "opentable",
        "kijiji",
        "eventbrite",
        "groupon",
        "reddit",
        "michelin",
        "yably",
        "restaurantji",
    ]
    for d in invalid_domains:
        if d in href.lower():
            return False
    return True


def scrape_duckduckgo_for_smbs(target_leads=100):
    """
    Searches DuckDuckGo via the DDGS python package API to avoid Captcha blocks,
    then uses Playwright to visit the actual business websites to scrape an email address.
    """
    print(f"\n--- Starting SMB Scraper Bot at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    total_new_leads = 0
    db.init_db()

    with sync_playwright() as p:
        # Launch browser headlessly to visit the actual business websites
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        with DDGS() as ddgs:
            for query in SEARCH_QUERIES:
                print(f"\n[*] Searching for: '{query}'")
                category = query.split()[0].capitalize()  # e.g., "Restaurants"

                hrefs = []
                try:
                    # Request up to 30 results per query directly from DDGS
                    results = [r for r in ddgs.text(query, max_results=30)]
                    for res in results:
                        href = res.get("href", "")
                        if href and is_valid_domain(href):
                            hrefs.append(href)
                except Exception as e:
                    print(f"[-] DDGS search failed for '{query}': {e}")

                # Keep top 15 unique domains
                hrefs = list(set(hrefs))[:15]

                print(f"    [~] Found {len(hrefs)} valid local business domains.")

                # Visit each domain to find an email
                for domain in hrefs:
                    if total_new_leads >= target_leads:
                        break

                    print(f"    [>] Scanning {domain} for contact info...")
                    try:
                        page.goto(domain, wait_until="domcontentloaded", timeout=10000)
                        html_content = page.content()

                        emails = extract_emails_from_text(html_content)

                        # Filter out common junk emails
                        valid_emails = [
                            e
                            for e in emails
                            if not e.endswith((".png", ".jpg", ".jpeg", ".gif", "wixpress.com"))
                            and "sentry" not in e
                            and "example" not in e
                            and "domain" not in e
                        ]

                        if valid_emails:
                            primary_email = valid_emails[0].lower()

                            # Guess company name from domain
                            parsed_uri = urllib.parse.urlparse(domain)
                            domain_name = parsed_uri.netloc.replace("www.", "")
                            company_name = domain_name.split(".")[0].capitalize()

                            print(f"        [+] Found email ({primary_email}) for {company_name}")

                            # Save to DB
                            lead_id = db.add_smb_lead(company_name, category, primary_email, domain)
                            if lead_id:
                                print(f"        [+] New SMB Lead Saved to DB! (Total: {total_new_leads + 1})")
                                total_new_leads += 1
                                if total_new_leads >= target_leads:
                                    print(f"\n[***] Reached target of {target_leads} new leads! Stopping scraper.")
                                    break
                            else:
                                print(f"        [-] Email already exists in DB.")
                        else:
                            print(f"        [-] No valid emails found on homepage.")

                    except Exception as e:
                        print(f"        [-] Failed to load {domain}: {e}")

                time.sleep(2)  # Be polite between DDG queries

                if total_new_leads >= target_leads:
                    break

        browser.close()

    print(f"\n--- SMB Scraper Bot Finished at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"Total New Leads Scraped Session: {total_new_leads}")


if __name__ == "__main__":
    scrape_duckduckgo_for_smbs()
