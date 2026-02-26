"""
Legacy entry point — now delegates to daily_pipeline.py.

Usage:
  python run_smb_pipeline.py              # Full run
  python run_smb_pipeline.py --dry-run    # Simulate (no emails sent)
"""
import sys

print("\n[*] Redirecting to daily_pipeline.py (new orchestrator)...\n")

from daily_pipeline import run_pipeline

dry_run = "--dry-run" in sys.argv
run_pipeline(dry_run=dry_run)
