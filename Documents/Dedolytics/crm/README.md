# Dedolytics CRM System

This folder contains the dual-bot system consisting of:
1. **The Scraper Bot (`scraper_bot.py`):** Scrapes LinkedIn public jobs using Playwright Stealth and stores them in SQLite.
2. **The Outreach Bot (`outreach_bot.py`):** Reads untouched contacts from SQLite, renders customized email templates based on job titles, and emails them rotating between 3 Google Workspace accounts.

## 1. Initial Setup

Open your terminal, navigate to this `crm` folder, and set up your environment:

```bash
# 1. Create a Python Virtual Environment (recommended for Mac)
# Note: Using python3.10 to ensure compatibility with pre-built library wheels
python3.10 -m venv venv

# 2. Activate the virtual environment
source venv/bin/activate

# 3. Install the python dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers (required for the scraper)
playwright install chromium
```

> **Note:** Every time you manually run the scripts, make sure to activate the environment first using `source venv/bin/activate`.

## 2. Configuration (`.env`)

You **MUST** use [Google App Passwords](https://support.google.com/mail/answer/185833?hl=en) for your 3 email accounts. Regular passwords will fail due to Google's security policies.
1. Go to your Google Account > Security > 2-Step Verification > App Passwords.
2. Generate an App Password for "Mail".
3. Open the `.env` file in this directory and replace `your-app-password-here` with the 16-letter generated passwords.

## 3. Scheduling on Mac (Cron)

You mentioned you want this to run locally on your Mac. The standard way to do this without keeping a terminal window open forever is using `crontab`.

In your terminal, type:
```bash
crontab -e
```

Add these two lines to the bottom of the file (replace `/Users/kushalshah/Documents/Dedolytics/crm` with the exact absolute path if different, and ensure your python path is correct, e.g., `/usr/local/bin/python3` or just `python3`):

```bash
# Run the Scraper Bot every 4 hours to find new jobs continuously
0 */4 * * * cd /Users/kushalshah/Documents/Dedolytics/crm && python3 scraper_bot.py >> scraper.log 2>&1

# Run the Outreach Bot every day at 08:50 AM EST
50 8 * * * cd /Users/kushalshah/Documents/Dedolytics/crm && python3 outreach_bot.py >> outreach.log 2>&1
```

Save and exit. Your Mac will now run these bots automatically in the background as long as it is turned on.

## Database Management
The local SQLite database is stored in `crm_database.db`. You can view it using any free SQLite viewer (like "DB Browser for SQLite" for Mac).
