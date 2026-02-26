import sqlite3
import time
import subprocess
import db
import outreach_bot
import enrichment_bot


def count_enriched_jobs():
    conn = sqlite3.connect("crm_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'enriched'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def run_all():
    print("==================================================")
    print("   Starting CRM: Scrape -> Enrich -> Outreach Flow ")
    print("==================================================")

    # 1. Run the scraper
    print("\n[1/4] Starting Target Ingestion Bot... (Reading targets.csv)")
    try:
        # Run scraper bot synchronously
        subprocess.run(["python", "scraper_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Ingestion bot encountered an error: {e}")
        return

    # 2. Run the Enrichment Engine
    print("\n[2/4] Starting Enrichment Bot... (Searching internet for Hiring Managers)")
    try:
        enrichment_bot.run_enrichment_cycle()
    except Exception as e:
        print(f"\n[-] Enrichment bot encountered an error: {e}")
        return

    # 3. Check database for enriched jobs
    print("\n[3/4] Checking database for enriched jobs...")
    time.sleep(2)  # Give DB a moment to settle

    enriched_count = count_enriched_jobs()
    print(f"[*] Found {enriched_count} job(s) successfully enriched with contacts.")

    # 4. Conditional outreach
    if enriched_count >= 5:
        print("\n[4/4] Threshold met (>= 5). Starting Outreach Bot...")
        outreach_bot.run_outreach_cycle()
    else:
        print("\n[4/4] Threshold NOT met (< 5). Outreach aborted for this cycle.")
        print("      The Scraper & Enrichment engine will need to find more jobs next time it runs.")

    print("\n==================================================")
    print("               Master Flow Complete                ")
    print("==================================================")


if __name__ == "__main__":
    db.init_db()
    run_all()
