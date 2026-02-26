import sqlite3


def migrate():
    conn = sqlite3.connect("crm_database.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE smb_leads ADD COLUMN email_sent TEXT DEFAULT 'no'")
        conn.commit()
        print("[+] Added email_sent column to smb_leads successfully.")

        # Retroactively mark already-emailed leads so they aren't hit again
        cursor.execute("UPDATE smb_leads SET email_sent = 'yes' WHERE status = 'emailed'")
        updated = cursor.rowcount
        conn.commit()
        print(f"[+] Retroactively marked {updated} previously emailed leads as 'yes'.")

    except sqlite3.OperationalError as e:
        print(f"[-] OperationalError during migration: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
