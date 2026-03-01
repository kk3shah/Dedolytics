#!/usr/bin/env python3
"""
Dedolytics Email Metrics CLI.

Displays email campaign performance metrics and syncs open tracking data
from the remote tracking server into the local CRM database.

Usage:
  python metrics.py              Show today's metrics
  python metrics.py --week       Show last 7 days
  python metrics.py --month      Show last 30 days
  python metrics.py --all        Show all-time metrics
  python metrics.py --sync       Sync opens from tracking server first, then show metrics
  python metrics.py --sync-only  Just sync opens, don't display metrics
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Ensure we're running from the crm/ directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

import db


# ─── Sync from Tracking Server ───────────────────────────────────────────────


def sync_opens():
    """
    Pulls open events from the tracking server and syncs them to the local
    email_events table in the CRM database.
    """
    tracking_url = os.getenv("TRACKING_BASE_URL", "")
    if not tracking_url:
        print("[!] TRACKING_BASE_URL not set in .env — cannot sync opens.")
        return 0

    # Get the last sync timestamp (so we only fetch new opens)
    last_sync = db.get_state("last_tracking_sync", "2000-01-01T00:00:00")

    try:
        api_url = f"{tracking_url.rstrip('/')}/api/opens"
        print(f"[*] Syncing opens from {api_url} (since {last_sync})...")
        resp = requests.get(api_url, params={"since": last_sync}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[!] Failed to reach tracking server: {e}")
        print(f"    Is the tracking server running at {tracking_url}?")
        return 0

    opens = data.get("opens", {})
    if not opens:
        print("[*] No new opens to sync.")
        return 0

    synced = db.sync_opens_from_tracking(opens)

    # Update last sync time
    db.set_state("last_tracking_sync", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    print(f"[+] Synced {synced} new opens from tracking server ({data.get('count', 0)} total received).")
    return synced


# ─── Metrics Display ─────────────────────────────────────────────────────────


def display_metrics(days=None, label="All Time"):
    """Fetches and displays formatted email metrics."""
    metrics = db.get_email_metrics(days=days)

    print()
    print("=" * 62)
    print(f"  DEDOLYTICS EMAIL METRICS — {label}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 62)

    if metrics["total_sent"] == 0:
        print()
        print("  No emails tracked yet. Run the pipeline to start sending!")
        print("=" * 62)
        print()
        return

    # ── Delivery ──
    print()
    print("  DELIVERY")
    print(f"    Emails Sent:      {metrics['total_sent']}")
    print(f"    Delivered:        {metrics['delivered']}  ({metrics['delivery_rate']}%)")
    print(f"    Bounced:          {metrics['total_bounced']}  ({metrics['bounce_rate']}%)")
    if metrics["hard_bounces"] or metrics["soft_bounces"]:
        print(f"      Hard bounces:   {metrics['hard_bounces']}")
        print(f"      Soft bounces:   {metrics['soft_bounces']}")

    # ── Engagement ──
    print()
    print("  ENGAGEMENT")
    print(f"    Emails Opened:    {metrics['total_opened']}  ({metrics['open_rate']}% open rate)")
    if metrics["total_open_events"] > metrics["total_opened"]:
        reopens = round(metrics["total_open_events"] / metrics["total_opened"], 1) if metrics["total_opened"] > 0 else 0
        print(f"    Total Opens:      {metrics['total_open_events']}  ({reopens}x per email)")
    if metrics["avg_hours_to_open"] is not None:
        if metrics["avg_hours_to_open"] < 1:
            print(f"    Avg Time to Open: {int(metrics['avg_hours_to_open'] * 60)} min")
        elif metrics["avg_hours_to_open"] < 48:
            print(f"    Avg Time to Open: {metrics['avg_hours_to_open']} hrs")
        else:
            print(f"    Avg Time to Open: {round(metrics['avg_hours_to_open'] / 24, 1)} days")

    # ── By Email Type ──
    if metrics["by_type"]:
        print()
        print("  BY EMAIL TYPE")
        type_labels = {
            "initial": "Initial Email",
            "followup_1": "Follow-up #1",
            "followup_2": "Follow-up #2",
            "followup_3": "Follow-up #3",
        }
        for event_type, data in sorted(metrics["by_type"].items()):
            label_str = type_labels.get(event_type, event_type)
            rate = round(data["opened"] / data["sent"] * 100, 1) if data["sent"] > 0 else 0
            print(f"    {label_str:18s}  {data['sent']:>4d} sent  ->  {data['opened']:>4d} opened  ({rate}%)")

    # ── Daily Breakdown ──
    if metrics["daily"]:
        print()
        print("  DAILY BREAKDOWN (Last 30 Days)")
        print(f"    {'Date':<12s} {'Sent':>6s} {'Opened':>8s} {'Rate':>7s} {'Bounced':>9s}")
        print(f"    {'─' * 12} {'─' * 6} {'─' * 8} {'─' * 7} {'─' * 9}")
        for day in metrics["daily"][:14]:  # Show max 14 days
            rate = round(day["opened"] / day["sent"] * 100, 1) if day["sent"] > 0 else 0
            print(f"    {day['date']:<12s} {day['sent']:>6d} {day['opened']:>8d} {rate:>6.1f}% {day['bounced']:>9d}")

    # ── Recent Opens ──
    recent = db.get_recent_opens(limit=10)
    if recent:
        print()
        print("  RECENT OPENS (Last 10)")
        for o in recent:
            time_str = o["opened_at"] or "unknown"
            type_label = o["event_type"].replace("_", " ").title()
            opens_str = f" ({o['open_count']}x)" if o["open_count"] > 1 else ""
            print(f"    {o['company_name'][:30]:<30s}  {type_label:<14s}  {time_str}{opens_str}")

    print()
    print("=" * 62)
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]

    # Ensure tables exist
    try:
        db.init_db()
    except Exception:
        pass

    # Handle --sync / --sync-only
    if "--sync" in args or "--sync-only" in args:
        sync_opens()
        if "--sync-only" in args:
            return

    # Determine time range
    if "--week" in args:
        display_metrics(days=7, label="Last 7 Days")
    elif "--month" in args:
        display_metrics(days=30, label="Last 30 Days")
    elif "--all" in args:
        display_metrics(days=None, label="All Time")
    else:
        # Default: today
        display_metrics(days=1, label="Today")


if __name__ == "__main__":
    main()
