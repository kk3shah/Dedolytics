import time
import db
import random
import re
from ddgs import DDGS


def get_company_domain(company_name):
    clean = company_name.lower()
    for drop in [" inc", " inc.", " llc", " corp", " ltd", " group", " solutions", ",", ".", " & co"]:
        clean = clean.replace(drop, "")
    domain = clean.replace(" ", "") + ".com"
    return domain


def extract_email_from_text(text, domain):
    """Uses regex to find email addresses in a block of text."""
    if not text:
        return None

    email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    matches = re.findall(email_pattern, text)

    best_match = None
    for match in matches:
        match_lower = match.lower()
        if domain in match_lower and not any(x in match_lower for x in ["example", "email", "info", "contact"]):
            return match_lower
        elif best_match is None and not any(x in match_lower for x in ["example", "email", "info"]):
            best_match = match_lower

    return best_match


def hunt_actual_email(name, company_name):
    """Searches the open web for the exact person's email address."""
    domain = get_company_domain(company_name)
    query = f'"{name}" "{company_name}" email "@"'
    print(f"      [Hunt] Searching Web for Email: {query}")

    try:
        results = DDGS().text(query, max_results=5)
        for res in results:
            found = extract_email_from_text(res.get("title", ""), domain)
            if found:
                return found

            found = extract_email_from_text(res.get("body", ""), domain)
            if found:
                return found
    except Exception as e:
        print(f"      [-] DDGS email hunt failed: {e}")

    return None


def find_manager_profile(company_name, persona):
    """Finds the manager's name dynamically using DuckDuckGo."""
    query = f'site:linkedin.com/in/ "{company_name}" "{persona}"'
    print(f"      [Enrich] Discovering Persona: {query}")

    manager_name = None

    try:
        results = DDGS().text(query, max_results=3)
        for res in results:
            title_text = res.get("title", "")
            if (" - " in title_text or " – " in title_text) and "LinkedIn" in title_text:
                doc_title = title_text.replace(" | LinkedIn", "")
                parts = doc_title.replace(" – ", " - ").split(" - ")

                manager_name_raw = parts[0].strip()
                # Clean up LinkedIn titles inside parentheses or after commas
                manager_name = re.split(r"[\(\|\,]", manager_name_raw)[0].strip()

                # Exclude generic company pages or jobs
                lower_name = manager_name.lower()
                if "jobs" in lower_name or "hiring" in lower_name or "linkedin" in lower_name:
                    manager_name = None
                    continue
                else:
                    break
    except Exception as e:
        print(f"      [-] DDGS search failed: {e}")

    return manager_name


def generate_fallback_email(name, company_name):
    """Fallback to generated email format if web scrape fails."""
    if not name or len(name.split()) < 2:
        return None
    parts = name.lower().split()
    first = parts[0]
    last = parts[-1]
    domain = get_company_domain(company_name)
    return f"{first}.{last}@{domain}"


def run_enrichment_cycle():
    """Reads unenriched targets, dynamically hunts managers & exact emails, updates DB."""
    print(f"\n--- Starting Web-Hunt Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.id, j.title, j.company, j.description
        FROM jobs j
        LEFT JOIN contacts c ON j.id = c.job_id
        WHERE j.status = 'new' AND c.id IS NULL
    """
    )
    unenriched_targets = cursor.fetchall()
    conn.close()

    print(f"[*] Found {len(unenriched_targets)} ABM targets needing contextual enrichment.")

    success_count = 0

    for job_id, persona, company, industry_note in unenriched_targets:
        print(f"\n[*] Context: {company} (Seeking: {persona})")

        # 1. Dynamically Find Manager
        name = find_manager_profile(company, persona)

        if name:
            print(f"      [+] Found Contact: {name}")
            time.sleep(random.uniform(1.5, 3.0))

            # 2. Hunt for Actual Email
            email = hunt_actual_email(name, company)
            if email:
                print(f"      [+] Extracted Real Email: {email}")
            else:
                email = generate_fallback_email(name, company)
                print(f"      [~] Web scraping failed. Using format: {email}")

            # 3. Save to DB
            db.add_contact(job_id, name, email, persona)
            success_count += 1

            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'enriched' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
        else:
            print(f"      [-] Could not identify a profile for {persona}.")

        time.sleep(random.uniform(2.0, 4.0))

    print(f"\n[*] Enrichment Complete. Successfully enriched {success_count} contacts.")
    print(f"--- Finished Web-Hunt Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    db.init_db()
    run_enrichment_cycle()
