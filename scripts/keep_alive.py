"""
Keep Render free-tier services awake.

Render's free web services sleep after ~15 minutes of inactivity; the next
request then takes ~30-60s to boot. This script pings the frontend and the
backend health endpoint on a fixed interval so the services stay warm.

Usage:
    python scripts/keep_alive.py                 # forever loop, every 5 min
    python scripts/keep_alive.py --once          # single ping (use for CI cron)
    python scripts/keep_alive.py --interval 240 # custom interval in seconds

Environment variables (override the defaults):
    FRONTEND_URL     e.g. https://opspilot-frontend-re0r.onrender.com
    BACKEND_URL      e.g. https://opspilot-backend-y96j.onrender.com
"""
import argparse
import os
import sys
import time

import requests

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://opspilot-frontend-re0r.onrender.com").rstrip("/")
BACKEND_HEALTH = os.getenv("BACKEND_HEALTH", "https://opspilot-backend-y96j.onrender.com/health")

TIMEOUT = 15


def ping(label: str, url: str) -> bool:
    """GET the URL. 2xx => alive; anything else => WARN. Returns True if alive."""
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if 200 <= resp.status_code < 300:
            print(f"[{time.strftime('%H:%M:%S')}] {label}: HTTP {resp.status_code} — alive ({url})")
            return True
        print(f"[{time.strftime('%H:%M:%S')}] {label}: WARN HTTP {resp.status_code} ({url})")
        return False
    except Exception as exc:
        print(f"[{time.strftime('%H:%M:%S')}] {label}: FAIL {exc} ({url})")
        return False


def tick() -> bool:
    """Ping all targets. Returns True if all alive."""
    frontend_ok = ping("frontend", FRONTEND_URL)
    backend_ok = ping("backend", BACKEND_HEALTH)
    alive = frontend_ok and backend_ok
    print(f"[{time.strftime('%H:%M:%S')}] tick: {'all alive' if alive else 'something is DOWN (see above)'}")
    return alive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Ping once and exit (for CI)")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between pings (default 300)")
    args = parser.parse_args()

    if args.once:
        ok = tick()
        return 0 if ok else 1

    print(f"keep-alive started — pinging every {args.interval}s (Ctrl+C to stop)")
    while True:
        tick()
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
