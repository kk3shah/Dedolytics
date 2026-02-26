from dotenv import load_dotenv
import os
import sys

# Patch time.sleep out to prevent delays in test
import time

time.sleep = lambda x: None

load_dotenv()
from outreach_bot import send_email, generate_abm_email_with_gemini

sender_email = os.getenv("EMAIL_1_ADDRESS")
sender_password = os.getenv("EMAIL_1_PASSWORD")

if not sender_email or not sender_password:
    print("Cannot send test. Missing EMAIL_1_ADDRESS or EMAIL_1_PASSWORD.")
    sys.exit(1)

html_body = generate_abm_email_with_gemini(
    persona="VP of Data",
    company="Acme Corp",
    contact_name="John Doe",
    industry_note="Retail/eCommerce",
    sender_name="Paul",
)

# Extract Subject
lines = html_body.split("\n", 1)
subject = lines[0].replace("Subject:", "").strip() if "Subject:" in lines[0] else "Analytics at Acme Corp"
body_content = lines[1].strip() if len(lines) > 1 else html_body

print(f"Sending test email to hello@dedolytics.org with subject: {subject}")

success = send_email("hello@dedolytics.org", subject, body_content, sender_email, sender_password, "Paul")

if success:
    print("Test HTML emailed successfully! Check hello@dedolytics.org inbox.")
else:
    print("Failed to send test email.")
