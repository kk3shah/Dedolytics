import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "crm_database.db")

# Each migration: (column_name, column_definition, default_backfill_sql or None)
MIGRATIONS = [
    ("email_sent", "TEXT DEFAULT 'no'", "UPDATE smb_leads SET email_sent = 'yes' WHERE status = 'emailed'"),
    ("phone", "TEXT", None),
    ("address", "TEXT", None),
    ("followup_count", "INTEGER DEFAULT 0", None),
    ("next_followup_date", "DATE", None),
    ("date_scraped", "DATE", None),
    (
        "source",
        "TEXT DEFAULT 'places'",
        "UPDATE smb_leads SET source = 'manual' WHERE source IS NULL OR source = 'places'",
    ),
    ("last_error", "TEXT", None),
    ("business_description", "TEXT", None),
]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── smb_leads column migrations ──
    cursor.execute("PRAGMA table_info(smb_leads)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    print(f"[*] Existing smb_leads columns: {sorted(existing_cols)}")

    added = 0
    for col_name, col_def, backfill_sql in MIGRATIONS:
        if col_name in existing_cols:
            print(f"    [~] Column '{col_name}' already exists, skipping.")
            continue

        try:
            cursor.execute(f"ALTER TABLE smb_leads ADD COLUMN {col_name} {col_def}")
            conn.commit()
            print(f"    [+] Added column '{col_name}' ({col_def})")
            added += 1

            if backfill_sql:
                cursor.execute(backfill_sql)
                updated = cursor.rowcount
                conn.commit()
                print(f"        Backfilled {updated} rows.")
        except sqlite3.OperationalError as e:
            print(f"    [-] Error adding '{col_name}': {e}")

    # ── Create email_events table (for open/bounce tracking) ──
    print("\n[*] Ensuring email_events table exists...")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS email_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            tracking_id TEXT UNIQUE NOT NULL,
            sent_at DATETIME NOT NULL,
            opened TEXT DEFAULT 'no',
            opened_at DATETIME,
            open_count INTEGER DEFAULT 0,
            bounce_status TEXT,
            bounce_message TEXT,
            user_agent TEXT,
            ip_address TEXT,
            FOREIGN KEY(lead_id) REFERENCES smb_leads(id)
        )
        """
    )
    conn.commit()
    print("    [+] email_events table ready.")

    # ── Create pipeline_state table (key-value config store) ──
    print("[*] Ensuring pipeline_state table exists...")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    print("    [+] pipeline_state table ready.")

    conn.close()
    print(f"\n[*] Migration complete. Added {added} new column(s) to smb_leads.")


if __name__ == "__main__":
    migrate()
