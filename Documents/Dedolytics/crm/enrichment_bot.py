import os
import time
import requests
import db
from dotenv import load_dotenv


def get_company_domain(company_name):
    """
    Cleans up a company name to guess its primary domain.
    E.g., "Stripe, Inc." -> "stripe.com"
    """
    clean = company_name.lower()
    for drop in [" inc", " inc.", " llc", " corp", " ltd", " group", " solutions", ",", ".", " & co"]:
        clean = clean.replace(drop, "")
    domain = clean.replace(" ", "") + ".com"
    return domain


def enrich_via_hunter_api(company_name):
    """
    Uses the Hunter.io Domain Search API to find the best contact for outreach.
    Requires HUNTER_API_KEY in the .env file.
    """
    load_dotenv()
    api_key = os.getenv("HUNTER_API_KEY")

    if not api_key:
        print("      [-] Warning: HUNTER_API_KEY not found in .env. Enrichment will fail.")
        return None, None

    domain = get_company_domain(company_name)
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&department=it,executive&api_key={api_key}"

    print(f"      [Enrich] Querying Hunter API for: {domain}")

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            emails = data.get("data", {}).get("emails", [])

            if emails:
                # Prioritize anyone with 'Data', 'Analytics', 'Head', 'Director', or 'VP' in their title
                best_contact = emails[0]  # Default to the first found
                for e in emails:
                    title = str(e.get("position", "")).lower()
                    if any(kw in title for kw in ["data", "analytic", "director", "head", "vp", "chief"]):
                        best_contact = e
                        break

                name = f"{best_contact.get('first_name', '')} {best_contact.get('last_name', '')}".strip()
                email = best_contact.get("value")
                title = best_contact.get("position", "Data Leader")

                # Fallback if name is empty
                if not name:
                    name = "Data Leader"

                return name, email, title
            else:
                print(f"      [-] No emails found for {domain} on Hunter.io")
        else:
            print(f"      [-] API Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"      [-] Enrichment request failed: {e}")

    return None, None, None


def run_enrichment_cycle():
    """Reads unenriched jobs, queries Hunter API, and updates the DB."""
    print(f"\n--- Starting B2B Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    load_dotenv()
    if not os.getenv("HUNTER_API_KEY"):
        print("\n[CRITICAL ERROR] You must add HUNTER_API_KEY to your crm/.env file before running Enrichment.\n")
        return

    # Query all 'new' jobs that don't have a contact yet
    conn = db.get_connection()
    cursor = conn.cursor()
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

    print(f"[*] Found {len(unenriched_jobs)} jobs needing B2B contact enrichment.")

    success_count = 0

    for job_id, company in unenriched_jobs:
        print(f"\n[*] Enriching: {company}")

        # 1. Hit Hunter API
        name, email, title = enrich_via_hunter_api(company)

        if name and email:
            print(f"      [+] Found Contact: {name} ({title}) -> {email}")

            # 2. Save to DB
            db.add_contact(job_id, name, email, title)
            success_count += 1

            # Flag job as enriched
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'enriched' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
        else:
            print(f"      [-] Could not reliably enrich {company}.")

        time.sleep(1)  # Be polite to API rate limits

    print(f"\n[*] Enrichment Complete. Successfully enriched {success_count} contacts.")
    print(f"--- Finished Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    db.init_db()
    run_enrichment_cycle()
