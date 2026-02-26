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


def add_smb_lead(company_name, category, email, website="", phone="", address="", source="places"):
    """Inserts a new SMB lead. Ignores if email already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """
        INSERT INTO smb_leads (company_name, category, email, website, phone, address, source, date_scraped)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (company_name, category, email, website, phone, address, source, today),
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
    cursor.execute("SELECT id, company_name, category, email, website FROM smb_leads WHERE status = 'new'")
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


if __name__ == "__main__":
    init_db()
