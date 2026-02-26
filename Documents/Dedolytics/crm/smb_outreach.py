"""
Dedolytics SMB Outreach Bot — Initial emails + automated follow-ups.

Sends AI-generated infographic emails to new leads, then sends up to 3
templated follow-up emails at 7-day intervals.

Safety: OS-level file lock prevents concurrent execution. DB-level
email_sent='yes' prevents duplicate sends to the same address.
"""

import os
import sys
import time
import smtplib
from email.message import EmailMessage
import db
import random
import fcntl
from dotenv import load_dotenv

load_dotenv()

# ─── SMTP Accounts ───────────────────────────────────────────────────────────
EMAIL_ACCOUNTS = [
    {"email": os.getenv("EMAIL_1_ADDRESS"), "password": os.getenv("EMAIL_1_PASSWORD")},
    {"email": os.getenv("EMAIL_2_ADDRESS"), "password": os.getenv("EMAIL_2_PASSWORD")},
    {"email": os.getenv("EMAIL_3_ADDRESS"), "password": os.getenv("EMAIL_3_PASSWORD")},
]

SENDER_NAMES = ["Paul", "Ed", "Will"]

CALENDAR_LINK = "https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ2HePxAUUQzDdORvH9M7ZxCnczzZHTq6w_Ubpjy2STAQTLqYfAgCC9bqNidQSiguEqe1_1kJ_lx"

# ─── Follow-Up Templates ─────────────────────────────────────────────────────

FOLLOWUP_TEMPLATES = [
    # Follow-up 1 (7 days after initial email)
    {
        "subject": "Quick follow-up — {company_name} analytics offer",
        "body": """
        <html>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4;">
            <div style="width: 100%; max-width: 600px; margin: 20px auto; padding: 30px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; font-family: Arial, Helvetica, sans-serif; box-sizing: border-box;">
                <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics" width="120" style="display: block; margin: 0 auto 20px;" />
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Hi there,</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">I recently sent over a custom analytics overview we prepared specifically for <strong>{company_name}</strong>. Did you get a chance to take a look?</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">We specialize in helping {category} businesses unlock hidden profits through data — and the first month is completely free, no strings attached.</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">If you have 15 minutes this week, I'd love to walk you through what we found.</p>
                <div style="text-align: center; margin: 25px 0;">
                    <a href="{calendar_link}" style="display: inline-block; padding: 12px 24px; background-color: #0056b3; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 5px;">Book a Free 15-Min Call</a>
                </div>
                <p style="color: #999999; font-size: 12px; margin-top: 30px;">Dedolytics — Data & AI for small businesses | <a href="https://www.dedolytics.org" style="color: #0056b3;">dedolytics.org</a></p>
            </div>
        </body>
        </html>
        """,
    },
    # Follow-up 2 (14 days after initial email)
    {
        "subject": "Still available — free pilot dashboard for {company_name}",
        "body": """
        <html>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4;">
            <div style="width: 100%; max-width: 600px; margin: 20px auto; padding: 30px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; font-family: Arial, Helvetica, sans-serif; box-sizing: border-box;">
                <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics" width="120" style="display: block; margin: 0 auto 20px;" />
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Hi,</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Just a quick note — the free pilot offer we put together for <strong>{company_name}</strong> is still available.</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Here's what that includes:</p>
                <ul style="color: #333333; font-size: 15px; line-height: 1.8;">
                    <li>A custom data dashboard built for your {category} business</li>
                    <li>First month completely free ($0)</li>
                    <li>No IT department or technical knowledge needed</li>
                </ul>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Only 8.8% of small businesses actively use AI today — we help you get ahead of the curve.</p>
                <div style="text-align: center; margin: 25px 0;">
                    <a href="{calendar_link}" style="display: inline-block; padding: 12px 24px; background-color: #28a745; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 5px;">Schedule a Free Data Audit</a>
                </div>
                <p style="color: #999999; font-size: 12px; margin-top: 30px;">Dedolytics — Data & AI for small businesses | <a href="https://www.dedolytics.org" style="color: #0056b3;">dedolytics.org</a></p>
            </div>
        </body>
        </html>
        """,
    },
    # Follow-up 3 / final (21 days after initial email)
    {
        "subject": "Last chance — {company_name} custom analytics (closing out)",
        "body": """
        <html>
        <body style="margin: 0; padding: 0; background-color: #f4f4f4;">
            <div style="width: 100%; max-width: 600px; margin: 20px auto; padding: 30px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; font-family: Arial, Helvetica, sans-serif; box-sizing: border-box;">
                <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics" width="120" style="display: block; margin: 0 auto 20px;" />
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Hi,</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">I wanted to reach out one last time about the custom analytics we prepared for <strong>{company_name}</strong>.</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">I completely understand if the timing isn't right — running a {category} business keeps you busy. But if data-driven decisions are something you'd like to explore in the future, our door is always open.</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">The offer: <strong>$0 for the first month</strong>, then $499/month — a fraction of the cost of hiring a data engineer.</p>
                <div style="text-align: center; margin: 25px 0;">
                    <a href="{calendar_link}" style="display: inline-block; padding: 12px 24px; background-color: #0056b3; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 5px;">Book a Call (No Pressure)</a>
                </div>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">Wishing you continued success,</p>
                <p style="color: #333333; font-size: 15px; line-height: 1.6;">— The Dedolytics Team</p>
                <p style="color: #999999; font-size: 12px; margin-top: 30px;"><a href="https://www.dedolytics.org" style="color: #0056b3;">dedolytics.org</a></p>
            </div>
        </body>
        </html>
        """,
    },
]


# ─── Email Sending ────────────────────────────────────────────────────────────


def send_html_email(to_address, subject, html_body, sender_email, sender_password, sender_name):
    """Sends an HTML email via Google Workspace SMTP."""
    if not sender_email or not sender_password:
        print("      [!] Email simulation (Credentials missing)")
        return True

    try:
        msg = EmailMessage()
        msg.set_content("Please enable HTML to view this email.")
        msg.add_alternative(html_body, subtype="html")

        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = to_address

        # Always BCC the founder for tracking
        msg["Bcc"] = "hello@dedolytics.org"

        # Connect to Gmail SMTP server
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"      [-] Failed to send SMTP email to {to_address} from {sender_email}: {e}")
        return False


def wrap_infographic_in_email(infographic_html):
    """Wraps the naked infographic HTML in a minimalist layout with NO conversational text."""
    return f"""
    <html>
      <body style="margin: 0; padding: 0; background-color: #f4f4f4; display: flex; justify-content: center;">
        <!-- Clean, centered container -->
        <div style="width: 100%; max-width: 600px; margin: 20px auto; background-color: transparent;">
            {infographic_html}
        </div>
      </body>
    </html>
    """


def _get_valid_accounts():
    """Returns valid email accounts with credentials."""
    valid = [acc for acc in EMAIL_ACCOUNTS if acc["email"] and acc["password"]]
    if not valid:
        print("[!] No valid Google Workspace accounts found in .env. Will run simulation.")
        valid = [{"email": "simulation@example.com", "password": ""}]
    return valid


def _acquire_lock():
    """Acquires OS-level execution lock. Returns lock fd or exits if already locked."""
    lock_file_path = "/tmp/dedolytics_outreach_lock.lock"
    try:
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_WRONLY)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("\n[CRITICAL ERROR] The Outreach process is ALREADY RUNNING.")
        print("[!] Terminating immediately to prevent firing duplicate emails.")
        sys.exit(1)


# ─── Initial Outreach ────────────────────────────────────────────────────────


def run_smb_outreach(dry_run: bool = False) -> dict:
    """
    Sends initial infographic emails to leads with status='generated'.
    Returns stats dict.
    """
    print(f"\n--- Starting SMB Outreach Bot at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    if not dry_run:
        _acquire_lock()

    ready_leads = db.get_ready_smb_emails()

    if not ready_leads:
        print("[*] No un-emailed infographics ready for dispatch today.")
        return {"sent": 0, "failed": 0}

    print(f"[*] Found {len(ready_leads)} fully generated SMB leads ready to email.")

    valid_accounts = _get_valid_accounts()
    stats = {"sent": 0, "failed": 0}

    for i, (lead_id, company_name, category, email, infographic_html) in enumerate(ready_leads):
        sender_account = valid_accounts[i % len(valid_accounts)]
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]
        sender_name = random.choice(SENDER_NAMES)

        subject = f"Unlocking hidden profits at {company_name} (Custom Analytics)"

        print(f"\n[*] Dispatching to {company_name} ({email}) via {sender_email} as {sender_name}")

        if dry_run:
            print(f"      [DRY RUN] Would send: '{subject}' to {email}")
            stats["sent"] += 1
            continue

        final_html_body = wrap_infographic_in_email(infographic_html)

        try:
            if send_html_email(email, subject, final_html_body, sender_email, sender_password, sender_name):
                print(f"      [+] Infographic emailed successfully to {email}")
                db.mark_smb_emailed(lead_id)
                stats["sent"] += 1
            else:
                stats["failed"] += 1
                db.set_lead_error(lead_id, "SMTP send returned False")
        except Exception as e:
            print(f"      [-] Error sending to {email}: {e}")
            stats["failed"] += 1
            db.set_lead_error(lead_id, str(e))

        time.sleep(2)  # Anti-spam delay

    print(f"\n[*] Initial Outreach Complete: {stats['sent']} sent, {stats['failed']} failed.")
    print(f"--- Finished Outreach at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    return stats


# ─── Follow-Up Outreach ──────────────────────────────────────────────────────


def run_followup_outreach(dry_run: bool = False) -> dict:
    """
    Sends follow-up emails to leads that were emailed 7+ days ago.
    Max 3 follow-ups per lead, then stops contacting them.
    Returns stats dict.
    """
    print(f"\n--- Starting Follow-Up Outreach at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    followup_leads = db.get_followup_leads()

    if not followup_leads:
        print("[*] No follow-ups due today.")
        return {"sent": 0, "failed": 0}

    print(f"[*] Found {len(followup_leads)} leads due for follow-up.")

    valid_accounts = _get_valid_accounts()
    stats = {"sent": 0, "failed": 0}

    for i, (lead_id, company_name, category, email, followup_count) in enumerate(followup_leads):
        # Pick the right template (0-indexed: followup_count is 0, 1, or 2)
        template_idx = min(followup_count, len(FOLLOWUP_TEMPLATES) - 1)
        template = FOLLOWUP_TEMPLATES[template_idx]

        subject = template["subject"].format(company_name=company_name)
        html_body = template["body"].format(
            company_name=company_name,
            category=category.lower() if category else "local",
            calendar_link=CALENDAR_LINK,
        )

        sender_account = valid_accounts[i % len(valid_accounts)]
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]
        sender_name = random.choice(SENDER_NAMES)

        print(f"\n[*] Follow-up #{followup_count + 1} to {company_name} ({email})")

        if dry_run:
            print(f"      [DRY RUN] Would send: '{subject}' to {email}")
            stats["sent"] += 1
            continue

        try:
            if send_html_email(email, subject, html_body, sender_email, sender_password, sender_name):
                print(f"      [+] Follow-up sent to {email}")
                db.mark_followup_sent(lead_id)
                stats["sent"] += 1
            else:
                stats["failed"] += 1
                db.set_lead_error(lead_id, f"Follow-up {followup_count + 1} SMTP failed")
        except Exception as e:
            print(f"      [-] Error sending follow-up to {email}: {e}")
            stats["failed"] += 1
            db.set_lead_error(lead_id, str(e))

        time.sleep(2)  # Anti-spam delay

    print(f"\n[*] Follow-Up Complete: {stats['sent']} sent, {stats['failed']} failed.")
    print(f"--- Finished Follow-Ups at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    return stats


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("[!] DRY RUN MODE — no emails will actually be sent.\n")
    run_smb_outreach(dry_run=dry_run)
    run_followup_outreach(dry_run=dry_run)
