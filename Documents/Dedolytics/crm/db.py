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
        website TEXT,
        infographic_html TEXT,
        status TEXT DEFAULT 'new', -- 'new', 'generated', 'emailed'
        last_emailed_date DATE,
        email_sent TEXT DEFAULT 'no'
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


def add_smb_lead(company_name, category, email, website=""):
    """Inserts a new SMB lead. Ignores if email already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
        INSERT INTO smb_leads (company_name, category, email, website)
        VALUES (?, ?, ?, ?)
        """,
            (company_name, category, email, website),
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
    """Marks an SMB lead as emailed permanently by setting email_sent = 'yes'."""
    conn = get_connection()
    cursor = conn.cursor()
    todayStr = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        "UPDATE smb_leads SET status = 'emailed', last_emailed_date = ?, email_sent = 'yes' WHERE id = ?",
        (todayStr, lead_id),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
