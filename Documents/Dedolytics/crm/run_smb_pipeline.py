import os
import time

print("\n==================================")
print("  DEDOLYTICS SMB B2B PIPELINE")
print("==================================\n")

print("\n--- STEP 1: Scrape New SMB Leads ---")
print("[SKIPPED] Database already saturated with 170+ manual and scraped leads.")
# os.system("python smb_scraper.py")

print("\n--- STEP 2: Generate AI Infographics ---")
os.system("python infographic_bot.py")

print("\n--- STEP 3: Dispatch SMB Outreach (With Idempotency) ---")
os.system("python smb_outreach.py")

print("\n--- ENTIRE SMB PIPELINE COMPLETE ---")
