import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import EmailMessage
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


import time

# Configure APIs
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

import random

SENDER_NAMES = ["Paul", "Ed", "Will"]


def generate_abm_email_with_gemini(persona, company, contact_name, industry_note, sender_name):
    """
    Uses Gemini to craft a hyper-personalized HTML ABM email based on the Dedolytics case studies.
    """
    if not os.getenv("GEMINI_API_KEY"):
        return "Subject: Chat about Data\nHi, let's chat about data at your company."

    model = genai.GenerativeModel("gemini-2.5-flash")

    first_name = contact_name.split()[0] if contact_name else persona

    # Dynamic Case Study Injection Based on Dedolytics Portfolio
    case_study_text = ""
    case_study_url = ""
    if "retail" in industry_note.lower() or "merchandising" in industry_note.lower():
        case_study_text = "We recently built a 'RedSticker' Power BI dashboard for a similar retail enterprise that tracked over $5.1M in markdowns and caught budget overruns at the category level before they escalated."
        case_study_url = "https://www.dedolytics.org/projects/redsticker.html"
    elif "supply chain" in industry_note.lower() or "inventory" in industry_note.lower():
        case_study_text = "We recently deployed a Replenishment Intelligence Suite for a partner that maintained a 96.79% CSL across $88.86M in stock while identifying critical allocation gaps."
        case_study_url = "https://www.dedolytics.org/projects/inventory.html"
    else:
        case_study_text = "We recently built an Executive Command Center for a partner that gave the C-suite instant, automated visibility into KPI variance, cutting decision latency from days to hours."
        case_study_url = "https://www.dedolytics.org/projects/executive.html"

    prompt = f"""
    You are {sender_name}, a Partner at Dedolytics (https://www.dedolytics.org), a premium data consulting firm specializing in Power BI, SQL, and Snowflake.
    
    Write a highly professional, short, punchy cold email to {first_name} (the {persona}) at {company} in RAW HTML format.
    
    Instructions:
    1. Do not use generic corporate jargon. Be extremely direct and value-focused.
    2. Start the very first line of your output with "Subject: " followed by a catchy subject line.
    3. The rest of your output must be the raw HTML code for the email body. DO NOT output markdown code blocks (e.g. no ```html). Just the HTML.
    4. Use professional fonts (font-family: Arial, Helvetica, sans-serif;) and styling that looks clean and modern.
    
    Content requirements:
    - Paragraph 1: Acknowledge their role scaling data operations at {company}.
    - Paragraph 2: Mention this exact scenario, and hyperlink the relevant phase to the case study URL: "{case_study_text}". (Link: {case_study_url})
    - Paragraph 3: End with a low-friction call to action asking for a quick 10-minute chat next week to show them the semantic model. Include this exact HTML anchor tag to let them book time: <a href="https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ2HePxAUUQzDdORvH9M7ZxCnczzZHTq6w_Ubpjy2STAQTLqYfAgCC9bqNidQSiguEqe1_1kJ_lx">Book some time with us</a>
    
    Formatting and Signature requirement:
    - At the bottom of the email, include a highly professional email signature for {sender_name}.
    - The signature MUST include the Dedolytics logo image: <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics Logo" width="150" />
    - The signature must include your title (Partner), company name hyperlinked (Dedolytics), and website URL.
    - Structure it cleanly using HTML tables or divs for a premium feel.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean up if Gemini accidentally outputs markdown blocks
        if "```html" in text:
            text = text.replace("```html", "").replace("```", "").strip()
        return text
    except Exception as e:
        print(f"      [-] Gemini email generation failed: {e}")
        fallback = f"Subject: Data Analytics at {company}\n\nHi {first_name},\n\nI noticed your role scaling the data team at {company}. We build premium Power BI & Snowflake dashboards that track millions in variance. {case_study_text} \n\nOpen to a quick intro chat?\n\nBest,\n{sender_name}"
        return fallback


def send_email(to_address, subject, html_body, sender_email, sender_password, sender_name):
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


def run_outreach_cycle():
    """Reads enriched jobs, generates ABM emails, and dispatches them."""
    print(f"\n--- Starting ABM AI Outreach Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # get_pending_outreach_jobs returns: j.id, j.title (persona), j.company, c.id, c.name, c.email, j.description (industry_note)
    pending_jobs = db.get_pending_outreach_jobs()

    print(f"[*] Found {len(pending_jobs)} enriched targets ready for ABM outreach.")

    success_count = 0

    # Filter out empty accounts
    valid_accounts = [acc for acc in EMAIL_ACCOUNTS if acc["email"] and acc["password"]]

    if not valid_accounts:
        print("[!] No valid email accounts found in .env. Will run simulation.")
        valid_accounts = [{"email": "simulation@example.com", "password": ""}]

    for i, (job_id, persona, company, contact_id, contact_name, email, industry_note) in enumerate(pending_jobs):
        sender_account = valid_accounts[i % len(valid_accounts)]
        sender_email = sender_account["email"]
        sender_password = sender_account["password"]

        sender_name = random.choice(SENDER_NAMES)

        print(
            f"\n[*] Drafting ABM HTML Email for {contact_name} ({persona}) at {company} (Using {sender_email} as {sender_name})"
        )

        # 1. Generate Email Content
        raw_email = generate_abm_email_with_gemini(persona, company, contact_name, industry_note, sender_name)

        lines = raw_email.split("\n", 1)
        subject = lines[0].replace("Subject:", "").strip() if "Subject:" in lines[0] else f"Analytics at {company}"
        html_body = lines[1].strip() if len(lines) > 1 else raw_email

        print(f"      [~] Subject: {subject}")
        print("      [~] HTML Generation successful. Dispatching...")

        # 2. Send via SMTP
        if send_email(email, subject, html_body, sender_email, sender_password, sender_name):
            print(f"      [+] Email Sent Successfully to {email} via {sender_email}")

            # 3. Log and Update DB Status
            db.log_email(job_id, contact_id, sender_email, "ABM_Dynamic_Case_Study", subject)
            db.mark_job_emailed(job_id)
            success_count += 1

        time.sleep(2)  # Anti-spam delay between emails

    print(f"\n[*] Outreach Complete. Successfully emailed {success_count} prospects.")
    print(f"--- Finished Outreach Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    run_outreach_cycle()
