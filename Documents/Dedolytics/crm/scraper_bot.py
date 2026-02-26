import os
import csv
import time
import db

TARGETS_FILE = "targets.csv"


def run_ingestion_cycle():
    """Reads targets.csv and inserts them into the database as pending 'jobs'."""
    print(f"\n--- Starting Target Ingestion Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    db.init_db()

    if not os.path.exists(TARGETS_FILE):
        print(f"[-] Could not find {TARGETS_FILE}. Creating a template...")
        with open(TARGETS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Company", "Target Persona", "Industry Note"])
            writer.writerow(["Nike", "VP of Data", "Retail"])
            writer.writerow(["Patagonia", "Director of Supply Chain Analytics", "Supply Chain"])
        print(f"[*] Created {TARGETS_FILE} template. Please fill it with your target accounts and re-run.")
        return

    try:
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0

            for row in reader:
                company = row.get("Company", "").strip()
                persona = row.get("Target Persona", "").strip()
                industry = row.get("Industry Note", "").strip()

                if not company or not persona:
                    continue

                # We reuse the 'jobs' table schema for our ABM Targets
                # Title -> Persona
                # Description -> Industry Note (used by Outreach Bot to pick the right case study)

                # Create a pseudo-link to act as the UNIQUE constraint
                fake_link = f"abm://{company.replace(' ', '').lower()}/{persona.replace(' ', '').lower()}"

                job_id = db.upsert_job(
                    title=persona,
                    company=company,
                    link=fake_link,
                    description=industry,
                    department="ABM Data",
                    hiring_manager="Null",
                )

                if job_id:
                    print(f"[+] Loaded New Target: {persona} at {company}")
                    count += 1
                else:
                    # Exists already
                    pass

            print(f"[*] Successfully ingested {count} new targets into the pipeline.")

    except Exception as e:
        print(f"[-] Failed to read {TARGETS_FILE}: {e}")

    print(f"--- Finished Ingestion Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    run_ingestion_cycle()
