# Dedolytics B2B Outreach Pipeline

A hyper-personalized, fully automated AI sales outreach engine designed for Dedolytics. This Python pipeline scrapes targeted SMB local leads, uses the Google Gemini LLM to construct bespoke HTML data-consulting infographics for their specific industry, and cleanly dispatches them via Google Workspace SMTP.

## Architecture

The system is composed of three sequential bots, managed by a master Python orchestrator:

1.  **Bot 1: SMB Scraper (`smb_scraper.py` / `import_custom_leads.py`)**
    *   Finds and extracts local businesses and their contact emails based on target keywords (e.g., "Gyms in Mississauga", "Boutiques in Toronto").
    *   Alternatively, ingests manually curated CSV lists of target businesses.
    *   Saves validated leads to the `smb_leads` SQLite database (`crm_database.db`).

2.  **Bot 2: AI Infographic Generator (`infographic_bot.py`)**
    *   Iterates over all "new" leads in the database.
    *   Prompts the `gemini-2.5-flash` model to act as a world-class graphic designer, generating raw HTML code.
    *   Injects niche-specific data pitches (e.g., "Food Variance Tracking" for restaurants vs "Member Churn" for gyms).
    *   Outputs strictly styled, responsive, email-friendly CSS layouts holding the Dedolytics logo and the `$0 First Month` value proposition.

3.  **Bot 3: SMTP Dispatcher (`smb_outreach.py`)**
    *   Filters the database for un-sent, generated HTML payloads.
    *   Wraps the raw code in a professional email container.
    *   Rotates through multiple Google Workspace sender accounts (`hello@`, `ops@`, `contact@`) to distribute the sending volume and avoid spam flags.
    *   Executes absolute database blocklisting (`email_sent = 'yes'`) and strict OS-level (`fcntl`) process locking to mathematically guarantee a recipient never receives a duplicate or concurrent email.

## Setup & Dependencies

1.  Clone the repository and initialize the Python virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install google-generativeai python-dotenv duckduckgo-search beautifulsoup4 playwright
    playwright install
    ```

2.  Create a `.env` file in the root directory and populate your credentials:
    ```env
    GEMINI_API_KEY="your_google_ai_studio_key"
    DB_PATH="crm_database.db"

    EMAIL_1_ADDRESS="hello@dedolytics.org"
    EMAIL_1_PASSWORD="your_app_password"

    EMAIL_2_ADDRESS="ops@dedolytics.org"
    EMAIL_2_PASSWORD="your_app_password"

    EMAIL_3_ADDRESS="contact@dedolytics.org"
    EMAIL_3_PASSWORD="your_app_password"
    ```

## Execution

### Master Pipeline Orchestrator

To run the entire system start-to-finish (Scrape -> Generate -> Dispatch):

```bash
source venv/bin/activate
python run_smb_pipeline.py
```

### Emergency Stop
If you need to instantly abort an active run (e.g. rate-limit errors or infinite loops), execute the bash failsafe script to forcefully kill all lingering python processes:
```bash
./kill_all.sh
```

## Testing / Development

To generate a sample infographic and send a test mock-up to your personal inbox without touching the production database:

```bash
source venv/bin/activate
python test_smb_infographics.py your.email@example.com
```

## Author
Developed by the Dedolytics Engineering Team (2026).
