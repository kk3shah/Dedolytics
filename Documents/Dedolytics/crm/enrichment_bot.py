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

    # Generic email regex
    email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    matches = re.findall(email_pattern, text)

    # Prioritize emails containing the company domain, else take the first found
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

        # Look through all snippets
        for res in results:
            title_text = res.get("title", "")
            body_text = res.get("body", "")

            # Check Title
            found = extract_email_from_text(title_text, domain)
            if found:
                return found

            # Check Body
            found = extract_email_from_text(body_text, domain)
            if found:
                return found

    except Exception as e:
        print(f"      [-] DDGS email hunt failed: {e}")

    return None


def find_manager_profile(company_name, job_title, department, db_manager):
    """Finds the manager's name dynamically based on job properties."""
    if db_manager and db_manager.lower() != "null":
        # JD explicitly stated the manager
        return db_manager, "Hiring Manager"

    # Build dynamic search keywords based on the scraped job title
    title_kws = "Data"
    if "analyst" in job_title.lower() or "analytics" in job_title.lower():
        title_kws = '"Analytics" OR "Data"'
    elif "engineer" in job_title.lower():
        title_kws = '"Engineering" OR "Data"'

    dept_kw = f'"{department}"' if department else ""

    query = (
        f'site:linkedin.com/in/ "{company_name}" {dept_kw} ({title_kws}) ("Manager" OR "Director" OR "Head" OR "VP")'
    )
    print(f"      [Enrich] Discovering Manager: {query}")

    manager_name = None
    manager_title = "Data/Analytics Leader"

    try:
        results = DDGS().text(query, max_results=3)
        for res in results:
            title_text = res.get("title", "")
            body_text = res.get("body", "")

            if (" - " in title_text or " – " in title_text) and "LinkedIn" in title_text:
                comp_lower = company_name.lower()
                comp_first_word = comp_lower.split()[0].replace(",", "").replace(".", "")

                if (
                    len(comp_first_word) > 2
                    and comp_first_word not in title_text.lower()
                    and comp_first_word not in body_text.lower()
                ):
                    continue

                doc_title = title_text.replace(" | LinkedIn", "")
                parts = doc_title.replace(" – ", " - ").split(" - ")

                # Raw name might include "(Head of Data)" or ", Ph.D"
                manager_name_raw = parts[0].strip()
                manager_name = re.split(r"[\(\|\,]", manager_name_raw)[0].strip()

                if len(parts) > 1:
                    manager_title = parts[1].strip()

                lower_name = manager_name.lower()
                if (
                    comp_lower in lower_name
                    or comp_first_word in lower_name
                    or "jobs" in lower_name
                    or "hiring" in lower_name
                    or "linkedin" in lower_name
                ):
                    manager_name = None
                    continue
                else:
                    break

    except Exception as e:
        print(f"      [-] DDGS search failed: {e}")

    return manager_name, manager_title


def generate_fallback_email(name, company_name):
    """If true scraping fails, fallback to generating the most likely format."""
    if not name or len(name.split()) < 2:
        return None
    parts = name.lower().split()
    first = parts[0]
    last = parts[-1]
    domain = get_company_domain(company_name)
    return f"{first}.{last}@{domain}"


def run_enrichment_cycle():
    """Reads unenriched jobs, dynamically hunts managers & exact emails, updates DB."""
    print(f"\n--- Starting B2B Dynamic Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT j.id, j.title, j.company, j.department, j.hiring_manager
        FROM jobs j
        LEFT JOIN contacts c ON j.id = c.job_id
        WHERE j.status = 'new' AND c.id IS NULL
    """
    )
    unenriched_jobs = cursor.fetchall()
    conn.close()

    print(f"[*] Found {len(unenriched_jobs)} jobs needing contextual enrichment.")

    success_count = 0

    for job_id, title, company, dept, hiring_mgr in unenriched_jobs:
        print(f"\n[*] Context: {title} @ {company} (Dept: {dept})")

        # 1. Dynamically Find Manager
        name, mgr_title = find_manager_profile(company, title, dept, hiring_mgr)

        if name:
            print(f"      [+] Found Manager: {name} ({mgr_title})")
            time.sleep(random.uniform(1.5, 3.0))

            # 2. Hunt for Actual Email
            email = hunt_actual_email(name, company)
            if email:
                print(f"      [+] Extracted Real Email: {email}")
            else:
                email = generate_fallback_email(name, company)
                print(f"      [~] Web scraping failed. Using format: {email}")

            # 3. Save to DB
            db.add_contact(job_id, name, email, mgr_title)
            success_count += 1

            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'enriched' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
        else:
            print(f"      [-] Could not identify a manager profile.")

        time.sleep(random.uniform(1.5, 3.0))

    print(f"\n[*] Enrichment Complete. Successfully enriched {success_count} contacts.")
    print(f"--- Finished Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    db.init_db()
    run_enrichment_cycle()
