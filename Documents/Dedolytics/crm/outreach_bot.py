import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import db
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Load our 3 email accounts
EMAIL_ACCOUNTS = [
    {"email": os.getenv("EMAIL_1_ADDRESS"), "password": os.getenv("EMAIL_1_PASSWORD")},
    {"email": os.getenv("EMAIL_2_ADDRESS"), "password": os.getenv("EMAIL_2_PASSWORD")},
    {"email": os.getenv("EMAIL_3_ADDRESS"), "password": os.getenv("EMAIL_3_PASSWORD")},
]

# SMTP Config for Gmail / Google Workspace
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here":
    genai.configure(api_key=GEMINI_API_KEY)


def get_email_template(title, company, name, job_description=""):
    """
    Returns the appropriate email subject and body based on the job title.
    Uses Google Gemini API to craft highly personalized emails if available.
    Falls back to strong default templates if API key is missing or fails.
    """
    if GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here":
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            salutation_instruction = (
                f"The target is {name}, who is likely the Hiring Manager or Head of Data at the company '{company}'."
                if name
                else f"You are emailing the Hiring Manager or Head of Data at the company '{company}'."
            )

            prompt = f"""
            You are drafting a professional B2B outreach email for a company called 'Dedolytics'. 
            Dedolytics specializes in Power BI, SQL, and Snowflake architecture, delivering enterprise-grade dashboards, 
            data pipelines, and data engineering solutions.
            
            {salutation_instruction} They are currently hiring for an individual contributor role: '{title}'.
            
            Your goal is to pitch Dedolytics as an alternative or augmentation to hiring this '{title}' full-time. 
            Highlight that using a specialized consulting strike-team avoids the timeline, overhead, and tax costs associated 
            with a standard full-time hire, while providing immediate, expert-level leverage for their data roadmap.
            Crucially, emphasize how Dedolytics brings significantly more robust value execution, speed, and cross-industry 
            experience than a normal single '{title}' candidate could provide.
            
            Job Description context (if any):
            {job_description[:1000]} # Trimmed to avoid excessive context sizes
            
            Rules:
            1. Keep it very concise (under 150 words). Busy executives don't read essays.
            2. Be professional, direct, and authoritative but friendly.
            3. Do NOT include placeholder tags like [Your Name] or [Link]. Sign off as 'The Dedolytics Team' with the URL 'https://dedolytics.org'.
            4. Start the response with 'SUBJECT: <the subject line>' on the first line. The rest should be the body.
            5. If you do not have a specific name, use a professional general greeting like 'Hi there,' or 'Hello team at {company},'. NEVER make up a name.
            """

            response = model.generate_content(prompt)
            output = response.text.strip().split("\n")

            # Parse Subject and Body from Gemini response
            if output[0].startswith("SUBJECT:"):
                subject = output[0].replace("SUBJECT:", "").strip()
                body = "\n".join(output[1:]).strip()
                return subject, body
        except Exception as e:
            print(f"[-] Gemini AI Generation failed, falling back to static templates: {e}")

    # --- FALLBACK STATIC TEMPLATES ---
    title_lower = title.lower()
    greeting = f"Hi {name}," if name else f"Hello team at {company},"
    subject = f"Dedolytics - Enhancing Data Analytics at {company}"
    body = f"{greeting}\n\nI saw {company} is hiring for a {title}.\n\nAs you build out your analytics capabilities, Dedolytics can provide immediate leverage. We specialize in Power BI, SQL, and Snowflake architecture, delivering enterprise-grade dashboards and data pipelines.\n\nHiring us gives you the flexibility of an expert analytics squad without the overhead and tax burdens of a full-time hire.\n\nWould you be open to a quick 15-minute chat to see if we'd be a good fit to support your roadmap?\n\nBest regards,\nThe Dedolytics Team\nhttps://dedolytics.org"

    if "director" in title_lower or "head" in title_lower or "vp" in title_lower:
        subject = f"Accelerating Analytics Roadmap for {company}"
        body = f"{greeting}\n\nI noticed you are hiring a {title} at {company}. As you scale your data initiatives, having a reliable execution partner is critical.\n\nDedolytics has vast experience building high-performing Power BI and Snowflake architectures for enterprises. We act as a dedicated strike team that can immediately augment your data infrastructure, saving you the timeline and tax costs of hiring out a full internal squad from day one.\n\nI'd love to show you some of the complex replenishment and executive dashboards we've built. Do you have 15 minutes next week?\n\nBest,\nThe Dedolytics Team\nhttps://dedolytics.org"

    elif "cto" in title_lower:
        subject = f"Data Engineering & BI Partner for {company}"
        body = f"{greeting}\n\nI saw your open role for {title} at {company}. When scaling technical teams, balancing full-time hires vs external specialized consulting is a big decision.\n\nDedolytics specializes in exactly the data stack you are likely optimizing: Snowflake, SQL, and advanced Power BI. We can deploy scalable data governance and reporting systems much faster than spinning up a new internal team, bypassing standard hiring tax and benefits overhead.\n\nIf you have 10 minutes next week, I'd love to explore how we can act as your analytics extension.\n\nBest,\nThe Dedolytics Team\nhttps://dedolytics.org"

    return subject, body


def send_email(account_index, recipient_email, subject, body):
    """Sends an email using the specified Google Workspace account."""
    account = EMAIL_ACCOUNTS[account_index % len(EMAIL_ACCOUNTS)]
    sender_email = account["email"]
    sender_password = account["password"]

    if not sender_email or not sender_password or sender_password == "your-app-password-here":
        print(f"[-] Missing valid credentials for account {account_index}. Check .env file.")
        return False, sender_email

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True, sender_email
    except Exception as e:
        print(f"[-] Failed to send email to {recipient_email} from {sender_email}: {e}")
        return False, sender_email


def run_outreach_cycle():
    """Finds new jobs and dispatches targeted emails."""
    print(f"\n--- Starting Outreach Cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    pending_jobs = db.get_pending_outreach_jobs()
    print(f"[*] Found {len(pending_jobs)} new jobs requiring outreach.")

    if not pending_jobs:
        return

    account_index = 0

    for row in pending_jobs:
        job_id = row[0]
        title = row[1]
        company = row[2]
        contact_id = row[3]
        name = row[4]
        email = row[5]

        # 1. Generate Template
        subject, body = get_email_template(title, company, name)

        # 2. Send Email
        print(f"[*] Dispatching '{title}' email for {company} to {email}...")
        success, sent_from = send_email(account_index, email, subject, body)

        # 3. Log and Update DB
        if success:
            db.log_email(job_id, contact_id, sent_from, "Standard (Auto-matched)", subject)
            db.mark_job_emailed(job_id)
            print(f"[+] Successfully sent from {sent_from}")

        # Rotate to the next email account for the next iteration
        account_index += 1

    print(f"--- Finished Outreach Cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    # If run manually, run once
    run_outreach_cycle()
