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
]


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(smb_leads)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    print(f"[*] Existing columns: {sorted(existing_cols)}")

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

    conn.close()
    print(f"\n[*] Migration complete. Added {added} new column(s).")


if __name__ == "__main__":
    migrate()
