#!/bin/bash
echo "[*] EMERGENCY HALT INITIATED..."
pkill -9 -f "python.*smb_scraper.py" || echo "[-] smb_scraper not running"
pkill -9 -f "python.*infographic_bot.py" || echo "[-] infographic_bot not running"
pkill -9 -f "python.*smb_outreach.py" || echo "[-] smb_outreach not running"
pkill -9 -f "python.*run_smb_pipeline.py" || echo "[-] pipeline not running"
echo "[+] All Dedolytics SMB CRM python scripts forcefully terminated."
