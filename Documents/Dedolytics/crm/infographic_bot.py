import os
import time
import db
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def generate_smb_infographic_html(company_name, category):
    """
    Prompts Gemini to generate a beautiful HTML/CSS infographic snippet tailored to the business category.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    You are a world-class graphic designer specializing in data visualization. 
    You work for 'Dedolytics' (www.dedolytics.org), a data consulting firm specializing in Power BI, SQL, and Snowflake.
    
    Your task is to generate a highly professional, modern, self-contained HTML/CSS 'Infographic' 
    for a local business called '{company_name}' which is in the '{category}' industry.
    
    This infographic will be embedded directly into a cold email, so it must be clean, use inline CSS or a single <style> block,
    and be visually striking without relying on external javascript. Use professional fonts like Arial or Helvetica.
    
    CRITICAL REQUIREMENTS:
    1. At the very top, clearly display the Dedolytics logo: <img src="https://www.dedolytics.org/assets/images/logo.jpeg" alt="Dedolytics Logo" width="150" style="display: block; margin: 0 auto; margin-bottom: 20px;" />
    2. The title should be something like "Unlock Hidden Profits for [Company Name]" or similar.
    3. Include 3 highly specific, realistic 'metrics' or 'dashboards' that Dedolytics could specifically build for a '{category}'. 
       (e.g., if it's a Restaurant, mention 'Food Waste Variance Tracking', 'Peak Hour Labor Optimization', 'Menu Item Profitability').
    4. You MUST include a dedicated 'AI Advantage' section in the infographic that states these exact facts to educate the owner:
       - Only 8.8% of small businesses were actively using AI as of late 2025.
       - 68% claim to use AI, but 60% struggle to apply it to daily operations.
       - State clearly that Dedolytics bridges this gap: We build and run your AI data stack when you have NO AI budget, NO IT department, and NO in-house AI talent.
    5. You MUST include a 'Pricing / Risk-Free Offer' section that explicitly states:
       - First Month: $0 (Completely free pilot dashboard).
       - Thereafter: $499 / month (Fully managed data & AI stack).
       - Frame this as a fraction of the cost of hiring a single data engineer.
    5. PROFESSIONAL COLOR SCHEME: DO NOT use neon colors. Use a highly professional, minimalist, and clean corporate theme. Use a white or very light gray background (`#ffffff` or `#f8f9fa`) with dark, high-contrast text (`#111111` or `#333333`) to guarantee 100% readability. Use muted brand colors (like slate blue or dark gray) for borders or accents.
    6. Contact Information: If you include a generic email, use contact@dedolytics.org NOT info@dedolytics.org.
    7. The final output must ONLY be the raw HTML code. Do NOT wrap it in ```html markdown blocks. Do not add any conversational text before or after the code. Just output the literal <html> string.
    8. You MUST include exactly one Call-To-Action button anywhere in your layout. It MUST use this exact href: `<a href="https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ2HePxAUUQzDdORvH9M7ZxCnczzZHTq6w_Ubpjy2STAQTLqYfAgCC9bqNidQSiguEqe1_1kJ_lx" style="...">Schedule a Data Audit</a>`. 
       - BUTTON STYLING: You MUST style this link to look like a highly visible, professional button. Use inline CSS: `display: inline-block; padding: 12px 24px; background-color: #0056b3; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 5px; margin-top: 15px; text-align: center;`. (You can use a professional green like #28a745 instead, but the text MUST be white `#ffffff` and bold so it never blends in).
    9. Layout Constraints (CRITICAL FIX FOR OVERFLOW): You MUST wrap your entire graphic in a single parent `<div style="width: 100%; max-width: 600px; margin: 0 auto; padding: 20px; box-sizing: border-box; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px;">`.
       - EVERY SINGLE child element (divs, p, h1, etc.) MUST have `box-sizing: border-box;` applied.
       - NEVER use `width: 100%` if you also have padding or margins without `box-sizing: border-box;`. To be safe, use `max-width: 100%;` instead.
       - Ensure `word-wrap: break-word;` and `overflow-wrap: break-word;` are on all text.
       - Keep font sizes clean: 14px-16px for body, 20px-24px for headers.
    """

    try:
        # Enforce a strict 60_second timeout on the internal gRPC connection
        response = model.generate_content(prompt, request_options={"timeout": 60})
        text = response.text.strip()
        # Clean up if Gemini accidentally outputs markdown blocks
        if text.startswith("```html"):
            text = text.replace("```html", "").replace("```", "").strip()
        elif text.startswith("```"):
            text = text.replace("```", "").strip()
        return text
    except Exception as e:
        print(f"      [-] Gemini gRPC connection failed or timed out for {company_name}: {e}")
        return None


def run_infographic_cycle():
    """Reads pending SMB leads and generates an infographic for each."""
    print(f"\n--- Starting SMB Infographic Bot at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    pending_leads = db.get_pending_smb_infographics()

    if not pending_leads:
        print("[*] No new SMB leads require infographics. Exiting.")
        return

    print(f"[*] Found {len(pending_leads)} local businesses awaiting custom infographics.")

    success_count = 0

    for lead_id, company_name, category, email, website in pending_leads:
        print(f"\n[*] Generating bespoke {category} infographic for {company_name}...")

        html_payload = generate_smb_infographic_html(company_name, category)

        if html_payload:
            db.save_smb_infographic(lead_id, html_payload)
            print(f"      [+] Infographic generated and saved successfully!")
            success_count += 1
        else:
            print(f"      [-] Failed to generate structural HTML for {company_name}")

        time.sleep(3)  # Rate limiting for Gemini

    print(f"\n[*] Infographic Engine Complete. Processed {success_count} payloads.")
    print(f"--- Finished Infographic Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")


if __name__ == "__main__":
    run_infographic_cycle()
