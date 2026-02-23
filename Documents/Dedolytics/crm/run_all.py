import sqlite3
import time
import subprocess
import db
import outreach_bot


def count_new_jobs():
    conn = sqlite3.connect("crm_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def run_all():
    print("==================================================")
    print("   Starting CRM: Scraper & Outreach Master Flow    ")
    print("==================================================")

    # Run the scraper
    print("\n[1/3] Starting Scraper Bot... (This will run for 5-10 minutes)")
    try:
        # Run scraper bot synchronously
        subprocess.run(["python", "scraper_bot.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Scraper bot encountered an error: {e}")
        return

    # Check database for new jobs
    print("\n[2/3] Checking database for scraped jobs...")
    time.sleep(2)  # Give DB a moment to settle

    new_jobs_count = count_new_jobs()
    print(f"[*] Found {new_jobs_count} new job(s) pending outreach.")

    # Conditional outreach
    if new_jobs_count >= 3:
        print("\n[3/3] Threshold met (>= 3). Starting Outreach Bot...")
        outreach_bot.run_outreach_cycle()
    else:
        print("\n[3/3] Threshold NOT met (< 3). Outreach aborted for this cycle.")
        print("      The Scraper will need to find more jobs next time it runs.")

    print("\n==================================================")
    print("               Master Flow Complete                ")
    print("==================================================")


if __name__ == "__main__":
    db.init_db()
    run_all()
