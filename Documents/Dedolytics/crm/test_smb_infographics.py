import os
import sys
from dotenv import load_dotenv
from infographic_bot import generate_smb_infographic_html
from smb_outreach import wrap_infographic_in_email, send_html_email
import time

load_dotenv()

sender_1 = {"email": os.getenv("EMAIL_1_ADDRESS"), "pass": os.getenv("EMAIL_1_PASSWORD"), "name": "Paul (Hello)"}
sender_2 = {"email": os.getenv("EMAIL_2_ADDRESS"), "pass": os.getenv("EMAIL_2_PASSWORD"), "name": "Ed (Contact)"}
sender_3 = {"email": os.getenv("EMAIL_3_ADDRESS"), "pass": os.getenv("EMAIL_3_PASSWORD"), "name": "Will (Ops)"}

senders = [sender_1, sender_2, sender_3]

TEST_BUSINESSES = [{"name": "Iron Gym Mississauga", "category": "Fitness Center / Gym"}]

print("--- Starting SMB Infographic Tests ---")

for biz in TEST_BUSINESSES:
    name = biz["name"]
    cat = biz["category"]
    print(f"\n[*] Prompting Gemini for {name} ({cat})...")

    # 1. Generate Raw HTML Visual from Gemini
    raw_html = generate_smb_infographic_html(name, cat)

    if not raw_html:
        print(f"[-] Failed to generate HTML for {name}.")
        continue

    print(f"    [+] Generated Graphic.")

    # 2. Wrap it in the email container
    final_email_body = wrap_infographic_in_email(raw_html)

    subject = f"TEST: Mockup Dashboard for {name}"

    target_email = sys.argv[1] if len(sys.argv) > 1 else "kk3shah@uwaterloo.ca"

    print(f"    [>] Target Address: {target_email}")

    for idx, sender in enumerate(senders):
        print(f"    [>] ({idx+1}/3) Dispatching from {sender['email']}...")

        success = send_html_email(
            to_address=target_email,
            subject=f"TEST: Mockup Dashboard for {name} (via {sender['email']})",
            html_body=final_email_body,
            sender_email=sender["email"],
            sender_password=sender["pass"],
            sender_name=sender["name"],
        )

        if success:
            print(f"    [+] Dispatched successfully from {sender['email']}.")
        else:
            print(f"    [-] Dispatch failed from {sender['email']}.")

        time.sleep(3)  # Anti limit

print("\n--- Testing Complete ---")
