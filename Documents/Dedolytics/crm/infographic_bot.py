"""
Dedolytics Infographic Bot — Gemini-powered personalized email generation.

Generates a unique HTML infographic for each lead using their business name,
category, website description, and address. Each email feels hand-crafted
while being fully automated.
"""

import os
import time
import db
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = genai.GenerativeModel("gemini-2.5-flash")

CALENDAR_LINK = (
    "https://calendar.google.com/calendar/u/0/appointments/schedules/"
    "AcZssZ2HePxAUUQzDdORvH9M7ZxCnczzZHTq6w_Ubpjy2STAQTLqYfAgCC9bqNidQSiguEqe1_1kJ_lx"
)


def _build_personalized_prompt(company_name, category, business_description="", address=""):
    """
    Builds a highly personalized Gemini prompt using all available context
    about the business. The more context we have, the more personal the output.
    """

    # Build the business context block
    context_lines = [f"Business Name: {company_name}", f"Industry: {category}"]
    if address:
        context_lines.append(f"Location: {address}")
    if business_description:
        context_lines.append(f"About Them: {business_description}")

    business_context = "\n".join(context_lines)

    # Personalization guidance based on whether we have a description
    if business_description:
        personalization_instruction = f"""
PERSONALIZATION (CRITICAL — this is what makes the email feel hand-crafted):
- You know this about them: "{business_description}"
- Reference something specific from their description in your opening line.
  For example, if they mention "family-owned since 1985", acknowledge their legacy.
  If they say "specializing in Thai cuisine", mention Thai-specific analytics.
- The 3 dashboard metrics you propose MUST connect to what they actually do,
  not generic category metrics. Make the owner think "they actually looked at my business."
"""
    else:
        personalization_instruction = f"""
PERSONALIZATION:
- You don't have a specific description, so use the business name and category
  to infer what they likely do. Reference their name and location naturally.
- Propose 3 dashboard metrics that are highly specific to the {category} industry
  in their local market.
"""

    prompt = f"""You are writing a personalized cold email infographic for Dedolytics (www.dedolytics.org),
a data & AI consulting firm that builds custom analytics dashboards for small businesses.

TARGET BUSINESS:
{business_context}

{personalization_instruction}

GENERATE a single self-contained HTML email (no JavaScript, inline CSS only) with these sections:

1. HEADER
   - Dedolytics logo: <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics" width="140" style="display:block;margin:0 auto 15px;" />
   - A personalized headline that mentions {company_name} by name.
     NOT generic — make it feel like it was written for them specifically.

2. THE HOOK (2-3 sentences)
   - A short, compelling opening that shows you understand their specific business.
   - Reference their description/specialty if available, or make a smart inference from their category and location.
   - Transition into: "Here's what a custom data stack could unlock for you."

3. THREE CUSTOM DASHBOARDS (the core value prop)
   - Each dashboard should have: a title, a 1-2 sentence description of what it tracks,
     and a concrete example of the insight it would surface.
   - These MUST be specific to THIS business's category and context.
     Bad: "Sales Tracking Dashboard" (too generic).
     Good: "Peak Hour Labor vs. Revenue Optimizer" (specific, actionable).
   - Use small visual elements (colored borders, icons via Unicode, subtle backgrounds)
     to make each dashboard card visually distinct.

4. AI ADVANTAGE (brief, impactful)
   - Only 8.8% of small businesses actively use AI (2025).
   - 68% claim to use it, but 60% struggle to apply it daily.
   - Dedolytics bridges the gap — we build and manage your entire data + AI stack
     so you don't need an IT department, AI budget, or technical staff.

5. RISK-FREE OFFER
   - First Month: $0 — free pilot dashboard, no commitment.
   - After that: $499/month — fully managed data & AI stack.
   - Frame it: "Less than the cost of a single part-time analyst."

6. CALL TO ACTION
   - One prominent button: "Schedule a Free 15-Min Call"
   - Must link to: {CALENDAR_LINK}
   - Button style: display:inline-block; padding:14px 28px; background-color:#0056b3;
     color:#ffffff; text-decoration:none; font-weight:bold; border-radius:6px;
     font-size:16px; text-align:center;

DESIGN RULES:
- Wrap everything in: <div style="width:100%;max-width:600px;margin:0 auto;padding:20px;
  box-sizing:border-box;background-color:#ffffff;border:1px solid #e0e0e0;border-radius:8px;
  font-family:Arial,Helvetica,sans-serif;">
- Every child element must have box-sizing:border-box
- Color scheme: white background (#ffffff), dark text (#222), muted blue accents (#0056b3),
  light gray section backgrounds (#f8f9fa). No neon. No gradients.
- Font sizes: 14-16px body, 20-22px headers. Line height 1.6.
- word-wrap:break-word; overflow-wrap:break-word on all text.
- Contact email if needed: contact@dedolytics.org (NOT info@)

OUTPUT: Raw HTML only. No markdown. No ```html blocks. No explanation text.
Just the literal HTML starting with <div and ending with </div>."""

    return prompt


def generate_smb_infographic_html(company_name, category, business_description="", address=""):
    """
    Generates a personalized HTML infographic for a specific business using Gemini.
    """
    prompt = _build_personalized_prompt(company_name, category, business_description, address)

    try:
        response = MODEL.generate_content(prompt, request_options={"timeout": 90})
        text = response.text.strip()

        # Clean up markdown blocks if Gemini wraps them
        if text.startswith("```html"):
            text = text.replace("```html", "", 1)
        if text.startswith("```"):
            text = text.replace("```", "", 1)
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()

        # Basic validation — must contain HTML
        if "<div" not in text.lower():
            print(f"      [-] Gemini returned non-HTML for {company_name}")
            return None

        return text
    except Exception as e:
        print(f"      [-] Gemini failed for {company_name}: {e}")
        return None


def run_infographic_cycle():
    """Reads pending SMB leads and generates a personalized infographic for each."""
    print(f"\n--- Starting SMB Infographic Bot at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    pending_leads = db.get_pending_smb_infographics()

    if not pending_leads:
        print("[*] No new SMB leads require infographics. Exiting.")
        return

    print(f"[*] Found {len(pending_leads)} local businesses awaiting custom infographics.\n")

    success_count = 0
    fail_count = 0

    for lead_id, company_name, category, email, website, business_description, address in pending_leads:
        desc_preview = f' | "{business_description[:60]}..."' if business_description else " | (no description)"
        print(f"[*] Generating for {company_name} [{category}]{desc_preview}")

        html_payload = generate_smb_infographic_html(
            company_name=company_name,
            category=category,
            business_description=business_description or "",
            address=address or "",
        )

        if html_payload:
            db.save_smb_infographic(lead_id, html_payload)
            print(f"      [+] Personalized infographic saved ({len(html_payload)} chars)")
            success_count += 1
        else:
            print(f"      [-] Failed for {company_name}")
            db.set_lead_error(lead_id, "Gemini infographic generation failed")
            fail_count += 1

        time.sleep(3)  # Rate limiting for Gemini

    print(f"\n[*] Infographic Engine Complete.")
    print(f"    Generated: {success_count} | Failed: {fail_count}")
    print(f"--- Finished Infographic Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    run_infographic_cycle()
