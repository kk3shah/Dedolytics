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

# Load our 3 email accounts
EMAIL_ACCOUNTS = [
    {"email": os.getenv("EMAIL_1_ADDRESS"), "password": os.getenv("EMAIL_1_PASSWORD")},
    {"email": os.getenv("EMAIL_2_ADDRESS"), "password": os.getenv("EMAIL_2_PASSWORD")},
    {"email": os.getenv("EMAIL_3_ADDRESS"), "password": os.getenv("EMAIL_3_PASSWORD")},
]

SENDER_NAMES = ["Paul", "Ed", "Will"]


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


def run_smb_outreach():
    """Reads SMB leads with generated infographics and dispatches them with idempotency checks."""
    print(f"\n--- Starting SMB Outreach Bot at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # OS-Level execution lock to prevent duplicate processes from running simultaneously
    lock_file_path = "/tmp/dedolytics_outreach_lock.lock"
    try:
        lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_WRONLY)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("\n[CRITICAL ERROR] The Outreach process is ALREADY RUNNING.")
        print("[!] Terminating immediately to prevent firing duplicate emails to the same addresses.")
        sys.exit(1)

    # get_ready_smb_emails only returns rows where last_emailed_date is NOT today
    ready_leads = db.get_ready_smb_emails()

    if not ready_leads:
        print("[*] No un-emailed infographics ready for dispatch today. Exiting.")
        return

    print(f"[*] Found {len(ready_leads)} fully generated SMB leads ready to email.")

    success_count = 0
    valid_accounts = [acc for acc in EMAIL_ACCOUNTS if acc["email"] and acc["password"]]

    if not valid_accounts:
        print("[!] No valid Google Workspace accounts found in .env. Will run simulation.")
        valid_accounts = [{"email": "simulation@example.com", "password": ""}]

    for i, (lead_id, company_name, category, email, infographic_html) in enumerate(ready_leads):
        sender_account = valid_accounts[i % len(valid_accounts)]
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]
        sender_name = random.choice(SENDER_NAMES)

        subject = f"Unlocking hidden profits at {company_name} (Custom Analytics)"

        print(
            f"\n[*] Dispatching Custom Infographic to {company_name} ({email}) (Using {sender_email} as {sender_name})"
        )

        final_html_body = wrap_infographic_in_email(infographic_html)

        # Send via SMTP
        if send_html_email(email, subject, final_html_body, sender_email, sender_password, sender_name):
            print(f"      [+] Infographic Emailed Successfully to {email} via {sender_email}")

            # Mark idempotency lock lock
            db.mark_smb_emailed(lead_id)
            success_count += 1

        time.sleep(2)  # Modest anti-spam delay between sends

    print(f"\n[*] Outreach Complete. Successfully blasted {success_count} SMB infographics.")
    print(f"--- Finished Outreach Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    run_smb_outreach()
