#!/usr/bin/env python3
"""
Dedolytics Daily Pipeline Orchestrator.

Runs the full lead acquisition → email generation → outreach pipeline
sequentially with comprehensive error handling. Designed to be triggered
once daily at 8:30 AM EST via launchd.

Stages:
  1. SCRAPE  — Google Places API → Playwright email extraction (max 1 hr)
  2. GENERATE — Gemini AI infographic generation for new leads (max 1 hr)
  3. SEND    — Initial emails + follow-up emails
  4. SUMMARY — Log results to crm/logs/YYYY-MM-DD.log

Usage:
  python daily_pipeline.py              # Full run (sends real emails)
  python daily_pipeline.py --dry-run    # Full run but emails are simulated
"""

import os
import sys
import time
import fcntl
import logging
from datetime import datetime
from dotenv import load_dotenv

# Ensure we're running from the crm/ directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

# ─── Logging Setup ────────────────────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")

# Log to both file and stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("pipeline")

# ─── Pipeline Lock ────────────────────────────────────────────────────────────

LOCK_FILE = "/tmp/dedolytics_pipeline.lock"


def acquire_pipeline_lock():
    """Prevents two pipeline instances from running simultaneously."""
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_WRONLY)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        logger.error("PIPELINE ALREADY RUNNING. Another instance holds the lock. Exiting.")
        sys.exit(1)


# ─── Stage Runners ────────────────────────────────────────────────────────────


def run_stage_scrape() -> dict:
    """Stage 1: Scrape new leads via Google Places API + Playwright."""
    logger.info("=" * 60)
    logger.info("STAGE 1: SCRAPE — Google Places API Lead Acquisition")
    logger.info("=" * 60)

    try:
        from smb_scraper import scrape_gta_smbs

        stats = scrape_gta_smbs(target_leads=100)
        logger.info(f"Scraper finished: {stats}")
        return stats
    except Exception as e:
        logger.error(f"STAGE 1 FAILED: {e}", exc_info=True)
        return {"new_leads": 0, "errors": 1, "fatal_error": str(e)}


def run_stage_generate() -> dict:
    """Stage 2: Generate Gemini AI infographics for new leads."""
    logger.info("=" * 60)
    logger.info("STAGE 2: GENERATE — Gemini AI Infographic Generation")
    logger.info("=" * 60)

    try:
        from infographic_bot import run_infographic_cycle

        # run_infographic_cycle doesn't return stats, so we track before/after
        import db

        before_count = len(db.get_pending_smb_infographics())
        logger.info(f"Found {before_count} leads needing infographics.")

        if before_count == 0:
            logger.info("No leads need infographic generation. Skipping.")
            return {"generated": 0, "failed": 0}

        run_infographic_cycle()

        after_count = len(db.get_pending_smb_infographics())
        generated = before_count - after_count
        logger.info(f"Generated {generated} infographics ({after_count} still pending).")
        return {"generated": generated, "still_pending": after_count}

    except Exception as e:
        logger.error(f"STAGE 2 FAILED: {e}", exc_info=True)
        return {"generated": 0, "fatal_error": str(e)}


def run_stage_send(dry_run: bool = False) -> dict:
    """Stage 3: Send initial emails + follow-ups."""
    logger.info("=" * 60)
    logger.info("STAGE 3: SEND — Email Dispatch + Follow-Ups")
    logger.info("=" * 60)

    results = {"initial": {}, "followups": {}}

    # Initial outreach
    try:
        from smb_outreach import run_smb_outreach, run_followup_outreach

        results["initial"] = run_smb_outreach(dry_run=dry_run)
        logger.info(f"Initial outreach: {results['initial']}")
    except Exception as e:
        logger.error(f"Initial outreach FAILED: {e}", exc_info=True)
        results["initial"] = {"sent": 0, "failed": 0, "fatal_error": str(e)}

    # Follow-up outreach
    try:
        from smb_outreach import run_followup_outreach

        results["followups"] = run_followup_outreach(dry_run=dry_run)
        logger.info(f"Follow-up outreach: {results['followups']}")
    except Exception as e:
        logger.error(f"Follow-up outreach FAILED: {e}", exc_info=True)
        results["followups"] = {"sent": 0, "failed": 0, "fatal_error": str(e)}

    return results


# ─── Main Pipeline ────────────────────────────────────────────────────────────


def run_pipeline(dry_run: bool = False):
    """Runs the complete daily pipeline sequentially."""
    pipeline_start = time.time()

    logger.info("")
    logger.info("*" * 60)
    logger.info("  DEDOLYTICS DAILY PIPELINE")
    logger.info(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"  Log:  {log_filename}")
    logger.info("*" * 60)
    logger.info("")

    # Acquire pipeline-level lock
    acquire_pipeline_lock()

    all_results = {}

    # ── Stage 1: Scrape ──
    stage1_start = time.time()
    all_results["scrape"] = run_stage_scrape()
    stage1_elapsed = time.time() - stage1_start
    logger.info(f"Stage 1 completed in {stage1_elapsed / 60:.1f} min\n")

    # ── Stage 2: Generate ──
    stage2_start = time.time()
    all_results["generate"] = run_stage_generate()
    stage2_elapsed = time.time() - stage2_start
    logger.info(f"Stage 2 completed in {stage2_elapsed / 60:.1f} min\n")

    # ── Stage 3: Send ──
    stage3_start = time.time()
    all_results["send"] = run_stage_send(dry_run=dry_run)
    stage3_elapsed = time.time() - stage3_start
    logger.info(f"Stage 3 completed in {stage3_elapsed / 60:.1f} min\n")

    # ── Summary ──
    total_elapsed = time.time() - pipeline_start

    logger.info("")
    logger.info("*" * 60)
    logger.info("  PIPELINE SUMMARY")
    logger.info("*" * 60)
    logger.info(f"  Total time:       {total_elapsed / 60:.1f} min")
    logger.info(
        f"  Stage 1 (Scrape): {stage1_elapsed / 60:.1f} min — {all_results['scrape'].get('new_leads', 0)} new leads"
    )
    logger.info(
        f"  Stage 2 (Gen):    {stage2_elapsed / 60:.1f} min — {all_results['generate'].get('generated', 0)} infographics"
    )

    send_results = all_results.get("send", {})
    initial = send_results.get("initial", {})
    followups = send_results.get("followups", {})
    logger.info(
        f"  Stage 3 (Send):   {stage3_elapsed / 60:.1f} min — {initial.get('sent', 0)} initial, {followups.get('sent', 0)} follow-ups"
    )

    # Check for any fatal errors
    has_errors = any("fatal_error" in v if isinstance(v, dict) else False for v in all_results.values())
    if has_errors:
        logger.warning("  STATUS: COMPLETED WITH ERRORS (check log for details)")
    else:
        logger.info("  STATUS: ALL STAGES COMPLETED SUCCESSFULLY")

    logger.info("*" * 60)
    logger.info("")

    return all_results


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_pipeline(dry_run=dry_run)
