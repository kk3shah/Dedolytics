"""
Dedolytics GTA SMB Lead Scraper — Google Places API + Playwright Email Extraction.

Primary source: Google Places Text Search API
Email extraction: Playwright scrapes business websites for contact emails
Fallback: Accepts free-provider emails (Gmail, Hotmail) when no custom domain email found

Designed to run daily at 8:30 AM EST with a 1-hour time limit.
"""

import os
import re
import time
import random
import urllib.parse
import requests
import dns.resolver
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import db

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
MAX_RUN_SECONDS = 3600  # 1 hour hard limit

# ─── GTA Cities ───────────────────────────────────────────────────────────────
GTA_CITIES = [
    "Toronto",
    "Mississauga",
    "Brampton",
    "Vaughan",
    "Markham",
    "Scarborough",
    "Richmond Hill",
    "Oakville",
    "North York",
    "Etobicoke",
    "Ajax",
    "Pickering",
    "Whitby",
    "Burlington",
]

# ─── Business Categories ─────────────────────────────────────────────────────
CATEGORIES = [
    "restaurants",
    "cafes",
    "gyms",
    "dental clinics",
    "physiotherapy clinics",
    "auto repair shops",
    "plumbers",
    "electricians",
    "landscaping companies",
    "cleaning services",
    "boutiques",
    "bakeries",
    "yoga studios",
    "chiropractors",
    "pet stores",
    "optometrists",
    "hair salons",
    "real estate agencies",
    "accounting firms",
    "law firms",
    "veterinary clinics",
    "tutoring centres",
    "daycares",
    "florists",
]

# ─── Email Regex & Filters ───────────────────────────────────────────────────
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

JUNK_EMAIL_RE = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|webp|css|js|woff|ttf|ico)$"
    r"|sentry\.|example\.|domain\.|schema\.|yoursite\.|youremail\."
    r"|yourname\.|test\.|demo\.|sample\.|placeholder\."
    r"|noreply|no-reply|donotreply|do-not-reply|unsubscribe"
    r"|mailer-daemon|postmaster|abuse@|spam@|bounce@"
    r"|wixpress\.com|squarespace\.com|wordpress\.com"
    r"|john\.doe|jane\.doe",
    re.IGNORECASE,
)

JUNK_LOCALPARTS = {
    "youremail",
    "yourname",
    "example",
    "test",
    "demo",
    "sample",
    "name",
    "email",
    "user",
    "noreply",
    "no-reply",
    "donotreply",
}

FREE_PROVIDERS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "yahoo.ca",
    "live.com",
    "icloud.com",
    "me.com",
    "aol.com",
}

PREFERRED_LOCALPARTS = [
    "info",
    "hello",
    "contact",
    "office",
    "admin",
    "reception",
    "book",
    "booking",
    "appointments",
    "enquiries",
    "owner",
    "manager",
]


# ─── Google Places API ────────────────────────────────────────────────────────


def search_places(query: str, page_token: str = None) -> tuple[list[dict], str | None]:
    """
    Calls Google Places Text Search API. Returns (list of place dicts, next_page_token or None).
    Each place dict has: name, address, phone, website, place_id.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.id,nextPageToken",
    }
    body = {"textQuery": query, "pageSize": 20}
    if page_token:
        body["pageToken"] = page_token

    try:
        resp = requests.post(PLACES_URL, json=body, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"    [-] Places API error: {e}")
        return [], None

    places = []
    for p in data.get("places", []):
        places.append(
            {
                "name": p.get("displayName", {}).get("text", "").strip(),
                "address": p.get("formattedAddress", "").strip(),
                "phone": p.get("nationalPhoneNumber", "").strip(),
                "website": (p.get("websiteUri") or "").strip(),
                "place_id": p.get("id", ""),
            }
        )

    next_token = data.get("nextPageToken")
    return places, next_token


def fetch_all_places_for_query(query: str, max_pages: int = 3) -> list[dict]:
    """Fetches up to 60 results (3 pages) for a single query."""
    all_places = []
    token = None

    for page_num in range(max_pages):
        places, token = search_places(query, page_token=token)
        all_places.extend(places)

        if not token:
            break
        # Google requires ~2 second wait before using nextPageToken
        time.sleep(2)

    return all_places


# ─── Email Extraction ─────────────────────────────────────────────────────────


def extract_emails_relaxed(html: str, site_url: str = "") -> list[str]:
    """
    Extracts emails from HTML. Two-tier approach:
    1. Custom domain emails matching the website (highest quality)
    2. Free provider emails as fallback (Gmail, Hotmail, etc.)

    Returns sorted list with best emails first.
    """
    raw = set(EMAIL_REGEX.findall(html))
    domain_emails = []
    free_emails = []

    for e in raw:
        e = e.lower()
        if JUNK_EMAIL_RE.search(e):
            continue
        local = e.split("@")[0]
        if local in JUNK_LOCALPARTS:
            continue

        email_domain = e.split("@")[1]

        # Tier 1: custom domain matching the website
        if site_url and _email_matches_site(e, site_url):
            domain_emails.append(e)
        # Tier 2: free providers (fallback)
        elif email_domain in FREE_PROVIDERS:
            free_emails.append(e)
        # Tier 3: other custom domain emails (might still be relevant)
        elif email_domain not in FREE_PROVIDERS:
            domain_emails.append(e)

    # Sort each tier by preferred localparts
    domain_emails.sort(key=_email_rank)
    free_emails.sort(key=_email_rank)

    # Domain emails first, free emails as fallback
    return domain_emails + free_emails


def _email_matches_site(email: str, site_url: str) -> bool:
    """Check if email domain matches the website domain."""
    try:
        email_domain = email.split("@")[1].lower()
        site_host = urllib.parse.urlparse(site_url).netloc.lower().replace("www.", "")
        return (
            email_domain == site_host
            or site_host.endswith("." + email_domain)
            or email_domain.endswith("." + site_host)
        )
    except Exception:
        return False


def _email_rank(email: str) -> int:
    """Rank emails by preferred local parts (lower = better)."""
    local = email.split("@")[0]
    for i, p in enumerate(PREFERRED_LOCALPARTS):
        if local == p or local.startswith(p):
            return i
    return len(PREFERRED_LOCALPARTS)


def verify_mx(email: str) -> bool:
    """Verify MX records exist for the email domain."""
    domain = email.split("@")[-1]
    try:
        records = dns.resolver.resolve(domain, "MX", lifetime=8)
        return len(records) > 0
    except Exception:
        return False


# ─── Website Scraping with Playwright ─────────────────────────────────────────


def scrape_website_for_email(page, base_url: str, max_retries: int = 2) -> list[str]:
    """
    Scrapes a business website for email addresses.
    Tries homepage first, then common contact page slugs.
    Retries on failure.
    """
    slugs = ["", "/contact", "/contact-us", "/about", "/about-us", "/get-in-touch"]

    for slug in slugs:
        url = base_url.rstrip("/") + slug
        for attempt in range(max_retries + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                # Give JS a moment to render
                page.wait_for_timeout(1500)
                html = page.content()
                emails = extract_emails_relaxed(html, base_url)
                if emails:
                    return emails
                break  # Page loaded but no emails — try next slug
            except Exception:
                if attempt < max_retries:
                    time.sleep(2 * (attempt + 1))  # Exponential backoff
                continue

    return []


# ─── Main Scraper ─────────────────────────────────────────────────────────────


def scrape_gta_smbs(target_leads: int = 100) -> dict:
    """
    Main scraper function. Uses Google Places API to find GTA businesses,
    then scrapes their websites for email addresses.

    Returns a result dict with stats.
    """
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"  DEDOLYTICS GTA SMB SCRAPER — Google Places API")
    print(f"  Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Target: {target_leads} new leads | Time limit: {MAX_RUN_SECONDS // 60} min")
    print(f"{'='*60}\n")

    if not PLACES_API_KEY:
        print("[FATAL] GOOGLE_PLACES_API_KEY not set in .env. Aborting.")
        return {"new_leads": 0, "duplicates": 0, "phone_only": 0, "errors": 0, "api_calls": 0, "elapsed_seconds": 0}

    db.init_db()

    # Load all existing emails for fast O(1) dedup
    existing_emails = db.get_all_existing_emails()
    print(f"[*] Loaded {len(existing_emails)} existing emails from DB for dedup.")

    # Build (category, city) query pairs and shuffle for variety
    query_pairs = [(cat, city) for cat in CATEGORIES for city in GTA_CITIES]
    random.shuffle(query_pairs)

    stats = {
        "new_leads": 0,
        "duplicates": 0,
        "phone_only": 0,
        "no_contact": 0,
        "errors": 0,
        "api_calls": 0,
        "websites_scraped": 0,
        "elapsed_seconds": 0,
    }

    browser = None
    try:
        # Launch Playwright once for the entire run
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.set_default_timeout(20000)

        for query_idx, (category, city) in enumerate(query_pairs):
            # ── Time limit check ──
            elapsed = time.time() - start_time
            if elapsed >= MAX_RUN_SECONDS:
                print(f"\n[!] Time limit reached ({MAX_RUN_SECONDS // 60} min). Stopping scraper.")
                break

            # ── Target reached check ──
            if stats["new_leads"] >= target_leads:
                print(f"\n[!] Target reached: {stats['new_leads']} new leads. Stopping scraper.")
                break

            query_text = f"{category} in {city}, Ontario"
            remaining_time = MAX_RUN_SECONDS - elapsed
            print(
                f"\n[{query_idx + 1}/{len(query_pairs)}] '{query_text}' "
                f"(leads: {stats['new_leads']}/{target_leads}, "
                f"time left: {remaining_time / 60:.0f} min)"
            )

            # ── Fetch places from Google ──
            try:
                places = fetch_all_places_for_query(query_text, max_pages=2)
                stats["api_calls"] += 1
                print(f"    [~] Found {len(places)} businesses via Places API")
            except Exception as e:
                print(f"    [-] Places API error: {e}")
                stats["errors"] += 1
                continue

            if not places:
                continue

            # ── Process each business ──
            for place in places:
                # Time check inside inner loop too
                if time.time() - start_time >= MAX_RUN_SECONDS:
                    break
                if stats["new_leads"] >= target_leads:
                    break

                name = place["name"]
                website = place["website"]
                phone = place["phone"]
                address = place["address"]

                if not name:
                    continue

                # ── Try to find email ──
                email = None

                if website:
                    # Scrape website for email
                    try:
                        stats["websites_scraped"] += 1
                        emails = scrape_website_for_email(page, website)
                        if emails:
                            email = emails[0]
                    except Exception as e:
                        stats["errors"] += 1
                        print(f"    [-] Scrape error for {name}: {e}")

                # ── Save the lead ──
                if email:
                    # Check dedup in memory first (faster than DB)
                    if email in existing_emails:
                        stats["duplicates"] += 1
                        continue

                    # Verify MX records
                    if not verify_mx(email):
                        print(f"    [-] MX fail: {email} ({name})")
                        stats["errors"] += 1
                        continue

                    # Save to DB
                    cat_label = category.split()[0].capitalize()
                    lead_id = db.add_smb_lead(
                        company_name=name,
                        category=cat_label,
                        email=email,
                        website=website,
                        phone=phone,
                        address=address,
                        source="places",
                    )

                    if lead_id:
                        existing_emails.add(email)  # Update in-memory set
                        stats["new_leads"] += 1
                        is_free = email.split("@")[1] in FREE_PROVIDERS
                        provider_tag = " (free)" if is_free else ""
                        print(f"    [+] #{stats['new_leads']} {name} <{email}>{provider_tag} [{cat_label}]")
                    else:
                        stats["duplicates"] += 1

                elif phone:
                    # Phone-only lead (no email found) — still valuable
                    stats["phone_only"] += 1
                else:
                    stats["no_contact"] += 1

            # Rate limiting between queries
            time.sleep(1.0)

    except Exception as e:
        print(f"\n[FATAL] Scraper crashed: {e}")
        stats["errors"] += 1
    finally:
        if browser:
            try:
                browser.close()
                pw.stop()
            except Exception:
                pass

    stats["elapsed_seconds"] = round(time.time() - start_time, 1)

    # ── Print summary ──
    print(f"\n{'='*60}")
    print(f"  SCRAPER COMPLETE — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"  New leads saved:    {stats['new_leads']}")
    print(f"  Duplicates skipped: {stats['duplicates']}")
    print(f"  Phone-only (saved): {stats['phone_only']}")
    print(f"  No contact info:    {stats['no_contact']}")
    print(f"  Errors:             {stats['errors']}")
    print(f"  Websites scraped:   {stats['websites_scraped']}")
    print(f"  API calls:          {stats['api_calls']}")
    print(f"  Elapsed time:       {stats['elapsed_seconds'] / 60:.1f} min")
    print(f"{'='*60}\n")

    return stats


if __name__ == "__main__":
    scrape_gta_smbs(target_leads=100)
