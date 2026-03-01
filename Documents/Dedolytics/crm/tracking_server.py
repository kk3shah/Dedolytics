#!/usr/bin/env python3
"""
Dedolytics Email Tracking Server.

A lightweight Flask server that serves invisible 1x1 tracking pixels
embedded in outgoing emails. When a recipient opens an email, their
email client loads the pixel image, and this server logs the open event.

Endpoints:
  GET /pixel/<tracking_id>.png  — Serves 1x1 transparent GIF, logs open
  GET /api/opens?since=ISO_TS   — Returns aggregated opens for pipeline sync
  GET /metrics                  — HTML dashboard with email performance metrics

Deployment:
  Local:  python tracking_server.py                    (port 5123)
  Prod:   gunicorn tracking_server:app -b 0.0.0.0:5123 (deploy to Render/Railway/Fly.io)

The server uses its own lightweight SQLite DB (tracking_events.db) to store
open events. The daily pipeline syncs these back to the main CRM DB via /api/opens.
"""

import os
import sqlite3
from datetime import datetime

from flask import Flask, Response, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Tracking server uses its own DB (separate from the CRM DB)
TRACKING_DB = os.getenv("TRACKING_DB_PATH", os.path.join(os.path.dirname(__file__), "tracking_events.db"))

# 1x1 transparent GIF — smallest possible valid image (43 bytes)
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


# ─── Database ────────────────────────────────────────────────────────────────


def get_tracking_db():
    """Returns a connection to the tracking events database."""
    conn = sqlite3.connect(TRACKING_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_tracking_db():
    """Creates the open_events table if it doesn't exist."""
    conn = get_tracking_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS open_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT NOT NULL,
            opened_at DATETIME NOT NULL,
            user_agent TEXT,
            ip_address TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracking_id ON open_events(tracking_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_opened_at ON open_events(opened_at)")
    conn.commit()
    conn.close()


# ─── Tracking Pixel Endpoint ─────────────────────────────────────────────────


@app.route("/pixel/<tracking_id>.png")
def tracking_pixel(tracking_id):
    """
    Serves a 1x1 transparent pixel and logs the open event.

    Called automatically when a recipient's email client loads images.
    The tracking_id maps back to a specific email_event in the CRM DB.
    """
    try:
        conn = get_tracking_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO open_events (tracking_id, opened_at, user_agent, ip_address) VALUES (?, ?, ?, ?)",
            (
                tracking_id,
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                request.headers.get("User-Agent", ""),
                request.headers.get("X-Forwarded-For", request.remote_addr),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Never fail — always serve the pixel regardless of DB errors

    return Response(
        PIXEL_GIF,
        mimetype="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# ─── Sync API ────────────────────────────────────────────────────────────────


@app.route("/api/opens")
def get_opens():
    """
    Returns aggregated open events for syncing to the CRM database.

    Query params:
      since — ISO timestamp to filter opens after (default: all time)

    Returns JSON with opens grouped by tracking_id:
    {
      "opens": {
        "<tracking_id>": {
          "first_opened_at": "2026-03-01 14:30:00",
          "total_opens": 3,
          "user_agent": "...",
          "ip_address": "..."
        }
      },
      "count": 42
    }
    """
    since = request.args.get("since", "2000-01-01T00:00:00")

    conn = get_tracking_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tracking_id, opened_at, user_agent, ip_address
        FROM open_events
        WHERE opened_at > ?
        ORDER BY opened_at ASC
        """,
        (since,),
    )

    # Group by tracking_id: keep first open's details + total count
    opens = {}
    for row in cursor.fetchall():
        tid = row["tracking_id"]
        if tid not in opens:
            opens[tid] = {
                "first_opened_at": row["opened_at"],
                "total_opens": 0,
                "user_agent": row["user_agent"] or "",
                "ip_address": row["ip_address"] or "",
            }
        opens[tid]["total_opens"] += 1

    conn.close()
    return jsonify({"opens": opens, "count": len(opens)})


# ─── Metrics Dashboard ───────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dedolytics — Email Tracking</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5; color: #333; padding: 24px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        .header {
            text-align: center; margin-bottom: 32px; padding: 24px;
            background: linear-gradient(135deg, #0056b3, #003d82);
            border-radius: 12px; color: white;
        }
        .header h1 { font-size: 24px; margin-bottom: 4px; }
        .header p { opacity: 0.8; font-size: 14px; }
        .card {
            background: white; border-radius: 12px; padding: 24px;
            margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }
        .card h2 { font-size: 16px; color: #555; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; }
        .stat-box {
            text-align: center; padding: 20px 12px;
            background: #f8f9fa; border-radius: 10px;
        }
        .stat-value { font-size: 36px; font-weight: 700; color: #0056b3; }
        .stat-value.green { color: #22863a; }
        .stat-value.red { color: #d32f2f; }
        .stat-value.orange { color: #e67e00; }
        .stat-label { font-size: 12px; color: #888; margin-top: 4px; font-weight: 500; }
        table { width: 100%; border-collapse: collapse; }
        th { padding: 10px 12px; text-align: left; font-size: 12px; color: #888;
             text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #eee; }
        td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
        tr:hover td { background: #f8f9fa; }
        .badge {
            display: inline-block; padding: 3px 10px; border-radius: 12px;
            font-size: 12px; font-weight: 600;
        }
        .badge-green { background: #e6f9e6; color: #22863a; }
        .badge-red { background: #fde8e8; color: #d32f2f; }
        .refresh { text-align: center; color: #aaa; font-size: 12px; margin-top: 16px; }
        .empty { text-align: center; color: #aaa; padding: 40px; font-size: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Dedolytics Email Tracking</h1>
            <p>Real-time open tracking for outbound campaigns</p>
        </div>

        <div class="card">
            <h2>Overview</h2>
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-value">{{ total_unique }}</div>
                    <div class="stat-label">Unique Emails Opened</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value orange">{{ total_events }}</div>
                    <div class="stat-label">Total Open Events</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value green">{{ today_unique }}</div>
                    <div class="stat-label">Opened Today</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{{ avg_opens }}</div>
                    <div class="stat-label">Avg Opens per Email</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Recent Opens (Last 30)</h2>
            {% if recent_opens %}
            <table>
                <thead>
                    <tr>
                        <th>Tracking ID</th>
                        <th>Opened At (UTC)</th>
                        <th>Opens</th>
                        <th>IP Address</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in recent_opens %}
                    <tr>
                        <td><code style="font-size:12px;">{{ row.tracking_id[:12] }}...</code></td>
                        <td>{{ row.opened_at }}</td>
                        <td><span class="badge badge-green">{{ row.count }}</span></td>
                        <td style="font-size:12px;color:#888;">{{ row.ip }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty">No opens recorded yet. Send some emails with tracking pixels!</div>
            {% endif %}
        </div>

        <div class="card">
            <h2>Daily Opens (Last 14 Days)</h2>
            {% if daily_opens %}
            <table>
                <thead>
                    <tr><th>Date</th><th>Unique Opens</th><th>Total Events</th></tr>
                </thead>
                <tbody>
                    {% for row in daily_opens %}
                    <tr>
                        <td>{{ row.date }}</td>
                        <td>{{ row.unique }}</td>
                        <td>{{ row.total }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty">No data yet.</div>
            {% endif %}
        </div>

        <div class="refresh">
            Last refreshed: {{ now }} UTC &mdash; Refresh page for latest data
        </div>
    </div>
</body>
</html>
"""


@app.route("/metrics")
def metrics_dashboard():
    """Renders a live HTML dashboard with email tracking metrics."""
    conn = get_tracking_db()
    cursor = conn.cursor()

    # Total unique tracking IDs opened
    cursor.execute("SELECT COUNT(DISTINCT tracking_id) FROM open_events")
    total_unique = cursor.fetchone()[0]

    # Total open events
    cursor.execute("SELECT COUNT(*) FROM open_events")
    total_events = cursor.fetchone()[0]

    # Today's unique opens
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor.execute(
        "SELECT COUNT(DISTINCT tracking_id) FROM open_events WHERE DATE(opened_at) = ?",
        (today,),
    )
    today_unique = cursor.fetchone()[0]

    # Average opens per email
    avg_opens = round(total_events / total_unique, 1) if total_unique > 0 else 0

    # Recent opens (grouped by tracking_id, last 30)
    cursor.execute(
        """
        SELECT tracking_id, MIN(opened_at) as first_open, COUNT(*) as cnt,
               (SELECT ip_address FROM open_events o2 WHERE o2.tracking_id = o.tracking_id
                ORDER BY opened_at ASC LIMIT 1) as ip
        FROM open_events o
        GROUP BY tracking_id
        ORDER BY first_open DESC
        LIMIT 30
        """
    )
    recent_opens = [
        {
            "tracking_id": row["tracking_id"],
            "opened_at": row["first_open"],
            "count": row["cnt"],
            "ip": row["ip"] or "—",
        }
        for row in cursor.fetchall()
    ]

    # Daily opens (last 14 days)
    cursor.execute(
        """
        SELECT DATE(opened_at) as day,
               COUNT(DISTINCT tracking_id) as unique_opens,
               COUNT(*) as total_events
        FROM open_events
        WHERE opened_at >= datetime('now', '-14 days')
        GROUP BY DATE(opened_at)
        ORDER BY day DESC
        """
    )
    daily_opens = [
        {"date": row["day"], "unique": row["unique_opens"], "total": row["total_events"]} for row in cursor.fetchall()
    ]

    conn.close()

    return render_template_string(
        DASHBOARD_HTML,
        total_unique=total_unique,
        total_events=total_events,
        today_unique=today_unique,
        avg_opens=avg_opens,
        recent_opens=recent_opens,
        daily_opens=daily_opens,
        now=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ─── Health Check ─────────────────────────────────────────────────────────────


@app.route("/")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "dedolytics-tracking", "version": "1.0.0"})


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_tracking_db()
    port = int(os.getenv("TRACKING_PORT", 5123))
    print(f"[*] Dedolytics Tracking Server starting on port {port}")
    print(f"[*] Pixel URL format: http://localhost:{port}/pixel/<tracking_id>.png")
    print(f"[*] Dashboard: http://localhost:{port}/metrics")
    print(f"[*] Sync API:  http://localhost:{port}/api/opens")
    app.run(host="0.0.0.0", port=port, debug=False)
