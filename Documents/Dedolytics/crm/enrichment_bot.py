import time
import db
import random
from ddgs import DDGS


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


def generate_email_permutations(name, company_name):
    """
    Given a person's name and a company, generates the most common corporate email formats.
    """
    if not name or len(name.split()) < 2:
        return None

    parts = name.lower().split()
    first = parts[0]
    last = parts[-1]

    domain = get_company_domain(company_name)
    best_guess = f"{first}.{last}@{domain}"
    return best_guess


def enrich_via_ddgs(company_name):
    """
    Uses DuckDuckGo Search API to find the LinkedIn profile of the Head of Data.
    Entirely reverse-engineers the B2B enrichment process for free.
    """
    query = (
        f'site:linkedin.com/in/ "{company_name}" "Head of Data" OR "Director of Analytics" OR "Data Analytics Manager"'
    )
    print(f"      [Enrich] Querying DDGS: {query}")

    manager_name = None
    manager_title = "Data Leader"

    try:
        results = DDGS().text(query, max_results=3)
        for res in results:
            title_text = res.get("title", "")
            body_text = res.get("body", "")

            # We are looking for a standard LinkedIn profile title
            if (" - " in title_text or " – " in title_text) and "LinkedIn" in title_text:
                # STRICT VALIDATION: Ensure the company is actually mentioned in this profile snippet.
                # E.g., if scraping 'Roilogy', ensure 'roilogy' is in the title or body.
                comp_lower = company_name.lower()
                comp_first_word = comp_lower.split()[0].replace(",", "").replace(".", "")

                # If even the first word of the company name isn't in the result, it's a false positive.
                if (
                    len(comp_first_word) > 2
                    and comp_first_word not in title_text.lower()
                    and comp_first_word not in body_text.lower()
                ):
                    continue

                # E.g. "John Doe - Head of Data & AI at Stripe | LinkedIn"
                doc_title = title_text.replace(" | LinkedIn", "")
                parts = doc_title.replace(" – ", " - ").split(" - ")

                manager_name = parts[0].strip()
                if len(parts) > 1:
                    manager_title = parts[1].strip()

                # Sanity check: Ensure we didn't accidentally extract a company as a name
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
                    break  # Found a valid person

    except Exception as e:
        print(f"      [-] DDGS search failed: {e}")

    if manager_name:
        email = generate_email_permutations(manager_name, company_name)
        return manager_name, email, manager_title

    return None, None, None


def run_enrichment_cycle():
    """Reads unenriched jobs, scrapes web for managers, and updates the DB."""
    print(f"\n--- Starting B2B Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

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

        # 1. Search Web via DDGS
        name, email, title = enrich_via_ddgs(company)

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

        time.sleep(random.uniform(1.5, 3.0))  # Be polite to DDGS API

    print(f"\n[*] Enrichment Complete. Successfully enriched {success_count} contacts.")
    print(f"--- Finished Enrichment Engine at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    db.init_db()
    run_enrichment_cycle()
