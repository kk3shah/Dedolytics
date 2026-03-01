import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "crm_database.db")


def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initializes the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create jobs table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        description TEXT,
        department TEXT,
        hiring_manager TEXT,
        link TEXT UNIQUE NOT NULL,
        location TEXT,
        date_found DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new' -- 'new', 'enriched', 'emailed', 'replied', 'ignored'
    )
    """
    )

    # Create contacts table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        name TEXT,
        email TEXT,
        phone TEXT,
        title TEXT,
        linkedin_url TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    )
    """
    )

    # Create email logs
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS email_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contact_id INTEGER,
        job_id INTEGER,
        email_sent_from TEXT,
        date_sent DATETIME DEFAULT CURRENT_TIMESTAMP,
        template_used TEXT,
        subject TEXT,
        FOREIGN KEY(contact_id) REFERENCES contacts(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    )
    """
    )

    # Create smb_leads table (New Pipeline)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS smb_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL,
        category TEXT,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        address TEXT,
        website TEXT,
        business_description TEXT,
        infographic_html TEXT,
        status TEXT DEFAULT 'new', -- 'new', 'generated', 'emailed'
        last_emailed_date DATE,
        email_sent TEXT DEFAULT 'no',
        followup_count INTEGER DEFAULT 0,
        next_followup_date DATE,
        date_scraped DATE,
        source TEXT DEFAULT 'places',
        last_error TEXT
    )
    """
    )

    # Create email_events table for open/bounce tracking
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

    # Create pipeline_state table for key-value config (e.g. last sync time)
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS pipeline_state (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def upsert_job(title, company, link, description="", location="", department=None, hiring_manager=None):
    """Inserts a new job. Returns job_id if NEW, None if it already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
        INSERT INTO jobs (title, company, description, department, hiring_manager, link, location)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (title, company, description, department, hiring_manager, link, location),
        )
        job_id = cursor.lastrowid
        conn.commit()
        return job_id
    except sqlite3.IntegrityError:
        # Link already exists, skip
        return None
    finally:
        conn.close()


def update_job_description(job_id, description):
    """Updates the job description later."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET description = ? WHERE id = ?", (description, job_id))
    conn.commit()
    conn.close()


def add_contact(job_id, name, email, title, phone="", linkedin_url=""):
    """Adds a contact to a specific job."""
    if not email:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT INTO contacts (job_id, name, email, phone, title, linkedin_url)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
        (job_id, name, email, phone, title, linkedin_url),
    )
    contact_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return contact_id


def get_pending_outreach_jobs():
    """Gets jobs that have been enriched with a contact and are ready for outreach."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    SELECT j.id, j.title, j.company, c.id, c.name, c.email, j.description 
    FROM jobs j
    JOIN contacts c ON j.id = c.job_id
    WHERE j.status = 'enriched' AND c.email IS NOT NULL
    """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_job_emailed(job_id):
    """Marks a job as emailed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    UPDATE jobs SET status = 'emailed' WHERE id = ?
    """,
        (job_id,),
    )
    conn.commit()
    conn.close()


def log_email(job_id, contact_id, email_sent_from, template_used, subject):
    """Logs the email dispatch event."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT INTO email_logs (job_id, contact_id, email_sent_from, template_used, subject)
    VALUES (?, ?, ?, ?, ?)
    """,
        (job_id, contact_id, email_sent_from, template_used, subject),
    )
    conn.commit()
    conn.close()


# --- SMB Leads Pipeline Functions ---


def add_smb_lead(
    company_name, category, email, website="", phone="", address="", source="places", business_description=""
):
    """Inserts a new SMB lead. Ignores if email already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """
        INSERT INTO smb_leads (company_name, category, email, website, phone, address, source, date_scraped, business_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (company_name, category, email, website, phone, address, source, today, business_description),
        )
        lead_id = cursor.lastrowid
        conn.commit()
        return lead_id
    except sqlite3.IntegrityError:
        return None  # Email already exists
    finally:
        conn.close()


def get_pending_smb_infographics():
    """Gets SMB leads that need an infographic generated."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, company_name, category, email, website, business_description, address FROM smb_leads WHERE status = 'new'"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_smb_infographic(lead_id, html_content):
    """Saves the generated infographic HTML and updates status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE smb_leads SET infographic_html = ?, status = 'generated' WHERE id = ?", (html_content, lead_id)
    )
    conn.commit()
    conn.close()


def get_ready_smb_emails():
    """Gets SMB leads with generated infographics that have never been emailed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, company_name, category, email, infographic_html 
        FROM smb_leads 
        WHERE status = 'generated' 
        AND email_sent != 'yes'
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_smb_emailed(lead_id):
    """Marks an SMB lead as emailed permanently by setting email_sent = 'yes' and scheduling first follow-up."""
    conn = get_connection()
    cursor = conn.cursor()
    todayStr = datetime.now().strftime("%Y-%m-%d")
    # Schedule first follow-up for 7 days from now
    from datetime import timedelta

    followup_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute(
        "UPDATE smb_leads SET status = 'emailed', last_emailed_date = ?, email_sent = 'yes', next_followup_date = ? WHERE id = ?",
        (todayStr, followup_date, lead_id),
    )
    conn.commit()
    conn.close()


def get_all_existing_emails():
    """Returns a set of all emails currently in the database for fast dedup."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM smb_leads")
    emails = {row[0] for row in cursor.fetchall()}
    conn.close()
    return emails


def get_today_new_leads_count():
    """Returns count of leads scraped today."""
    conn = get_connection()
    cursor = conn.cursor()
    todayStr = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM smb_leads WHERE date_scraped = ?", (todayStr,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_followup_leads():
    """Gets leads that are due for a follow-up email (emailed, <3 follow-ups, due date reached)."""
    conn = get_connection()
    cursor = conn.cursor()
    todayStr = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        """
        SELECT id, company_name, category, email, followup_count
        FROM smb_leads
        WHERE email_sent = 'yes'
        AND followup_count < 3
        AND next_followup_date IS NOT NULL
        AND next_followup_date <= ?
        """,
        (todayStr,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_followup_sent(lead_id):
    """Increments followup_count and schedules next follow-up in 7 days."""
    conn = get_connection()
    cursor = conn.cursor()
    from datetime import timedelta

    next_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute(
        """
        UPDATE smb_leads
        SET followup_count = followup_count + 1,
            next_followup_date = ?,
            last_emailed_date = ?
        WHERE id = ?
        """,
        (next_date, datetime.now().strftime("%Y-%m-%d"), lead_id),
    )
    conn.commit()
    conn.close()


def set_lead_error(lead_id, error_msg):
    """Stores the last error for a lead (for debugging)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE smb_leads SET last_error = ? WHERE id = ?", (str(error_msg)[:500], lead_id))
    conn.commit()
    conn.close()


# --- Email Tracking & Metrics Functions ---


def create_email_event(lead_id, event_type, tracking_id):
    """Records a new email send event with its unique tracking ID."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute(
            "INSERT INTO email_events (lead_id, event_type, tracking_id, sent_at) VALUES (?, ?, ?, ?)",
            (lead_id, event_type, tracking_id, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # tracking_id already exists (shouldn't happen with UUIDs)
    finally:
        conn.close()


def record_email_open(tracking_id, user_agent="", ip_address=""):
    """Records an email open event. Sets opened_at on first open, increments open_count."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        UPDATE email_events
        SET opened = 'yes',
            opened_at = CASE WHEN opened_at IS NULL THEN ? ELSE opened_at END,
            open_count = open_count + 1,
            user_agent = COALESCE(?, user_agent),
            ip_address = COALESCE(?, ip_address)
        WHERE tracking_id = ?
        """,
        (now, user_agent or None, ip_address or None, tracking_id),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def record_bounce(tracking_id, bounce_status, bounce_message):
    """Records a bounce event for a tracked email."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE email_events SET bounce_status = ?, bounce_message = ? WHERE tracking_id = ?",
        (bounce_status, str(bounce_message)[:500], tracking_id),
    )
    conn.commit()
    conn.close()


def get_email_metrics(days=None):
    """Returns comprehensive email metrics as a dict."""
    conn = get_connection()
    cursor = conn.cursor()

    date_filter = ""
    if days:
        date_filter = f"AND sent_at >= datetime('now', '-{days} days')"

    # Total sent
    cursor.execute(f"SELECT COUNT(*) FROM email_events WHERE 1=1 {date_filter}")
    total_sent = cursor.fetchone()[0]

    # Total opened (unique emails opened)
    cursor.execute(f"SELECT COUNT(*) FROM email_events WHERE opened = 'yes' {date_filter}")
    total_opened = cursor.fetchone()[0]

    # Total re-opens (sum of open_count for opened emails)
    cursor.execute(f"SELECT COALESCE(SUM(open_count), 0) FROM email_events WHERE opened = 'yes' {date_filter}")
    total_open_events = cursor.fetchone()[0]

    # Bounces
    cursor.execute(f"SELECT COUNT(*) FROM email_events WHERE bounce_status IS NOT NULL {date_filter}")
    total_bounced = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM email_events WHERE bounce_status = 'hard_bounce' {date_filter}")
    hard_bounces = cursor.fetchone()[0]

    cursor.execute(f"SELECT COUNT(*) FROM email_events WHERE bounce_status = 'soft_bounce' {date_filter}")
    soft_bounces = cursor.fetchone()[0]

    # Average time to open (in hours)
    cursor.execute(
        f"""
        SELECT AVG(
            (julianday(opened_at) - julianday(sent_at)) * 24
        ) FROM email_events
        WHERE opened = 'yes' AND opened_at IS NOT NULL {date_filter}
        """
    )
    avg_hours_to_open = cursor.fetchone()[0]

    # By event type (initial, followup_1, followup_2, followup_3)
    cursor.execute(
        f"""
        SELECT event_type,
               COUNT(*) as sent,
               SUM(CASE WHEN opened = 'yes' THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN bounce_status IS NOT NULL THEN 1 ELSE 0 END) as bounced
        FROM email_events
        WHERE 1=1 {date_filter}
        GROUP BY event_type
        ORDER BY event_type
        """
    )
    by_type = {}
    for row in cursor.fetchall():
        by_type[row[0]] = {"sent": row[1], "opened": row[2], "bounced": row[3]}

    # Daily breakdown (last 30 days)
    cursor.execute(
        """
        SELECT DATE(sent_at) as day,
               COUNT(*) as sent,
               SUM(CASE WHEN opened = 'yes' THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN bounce_status IS NOT NULL THEN 1 ELSE 0 END) as bounced
        FROM email_events
        WHERE sent_at >= datetime('now', '-30 days')
        GROUP BY DATE(sent_at)
        ORDER BY day DESC
        """
    )
    daily = [{"date": row[0], "sent": row[1], "opened": row[2], "bounced": row[3]} for row in cursor.fetchall()]

    conn.close()

    open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
    bounce_rate = (total_bounced / total_sent * 100) if total_sent > 0 else 0
    delivered = total_sent - total_bounced
    delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0

    return {
        "total_sent": total_sent,
        "delivered": delivered,
        "delivery_rate": round(delivery_rate, 1),
        "total_opened": total_opened,
        "total_open_events": total_open_events,
        "open_rate": round(open_rate, 1),
        "total_bounced": total_bounced,
        "hard_bounces": hard_bounces,
        "soft_bounces": soft_bounces,
        "bounce_rate": round(bounce_rate, 1),
        "avg_hours_to_open": round(avg_hours_to_open, 1) if avg_hours_to_open else None,
        "by_type": by_type,
        "daily": daily,
    }


def get_recent_opens(limit=20):
    """Returns the most recent email opens with lead details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.tracking_id, e.opened_at, e.user_agent, e.ip_address,
               e.event_type, e.open_count, l.company_name, l.email
        FROM email_events e
        JOIN smb_leads l ON e.lead_id = l.id
        WHERE e.opened = 'yes'
        ORDER BY e.opened_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "tracking_id": r[0],
            "opened_at": r[1],
            "user_agent": r[2],
            "ip_address": r[3],
            "event_type": r[4],
            "open_count": r[5],
            "company_name": r[6],
            "email": r[7],
        }
        for r in rows
    ]


def sync_opens_from_tracking(opens_by_tracking_id):
    """
    Syncs open events from the tracking server into local email_events table.
    opens_by_tracking_id: dict of tracking_id -> {first_opened_at, total_opens, user_agent, ip_address}
    Returns number of newly synced opens.
    """
    conn = get_connection()
    cursor = conn.cursor()
    synced = 0
    for tracking_id, data in opens_by_tracking_id.items():
        cursor.execute(
            """
            UPDATE email_events
            SET opened = 'yes',
                opened_at = CASE WHEN opened_at IS NULL THEN ? ELSE opened_at END,
                open_count = ?,
                user_agent = COALESCE(?, user_agent),
                ip_address = COALESCE(?, ip_address)
            WHERE tracking_id = ? AND (opened = 'no' OR open_count < ?)
            """,
            (
                data["first_opened_at"],
                data["total_opens"],
                data.get("user_agent") or None,
                data.get("ip_address") or None,
                tracking_id,
                data["total_opens"],
            ),
        )
        if cursor.rowcount > 0:
            synced += 1
    conn.commit()
    conn.close()
    return synced


def get_state(key, default=None):
    """Gets a value from the pipeline_state key-value store."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM pipeline_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default
    except Exception:
        return default
    finally:
        conn.close()


def set_state(key, value):
    """Sets a value in the pipeline_state key-value store."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO pipeline_state (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
