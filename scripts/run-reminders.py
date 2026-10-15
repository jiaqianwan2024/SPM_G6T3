#!/usr/bin/env python3
"""Run the approaching-event reminder check now (SPM-95).

The same call a daily scheduler makes, so it is also how to show the behaviour in
the demo without waiting for a schedule to fire. Run it from cron (or any
scheduler) once a day for the real thing:

    0 8 * * *  python scripts/run-reminders.py

It sends INTERNAL_SERVICE_KEY, the shared secret every service is started with
(scripts/dev-backend.py sets a dev value). Safe to run more than once a day: a
reminder is raised once per event per start date.
"""

import json
import os
import sys
import urllib.error
import urllib.request

EVENT_SERVICE_URL = os.environ.get("EVENT_SERVICE_URL", "http://127.0.0.1:8002")


def main() -> int:
    key = os.environ.get("INTERNAL_SERVICE_KEY", "dev-only-service-key")
    request = urllib.request.Request(
        f"{EVENT_SERVICE_URL}/events/reminders/run", method="POST", headers={"X-Service-Key": key}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"The reminder check was refused: {exc.code} {exc.read().decode(errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach event-service at {EVENT_SERVICE_URL}: {exc.reason}", file=sys.stderr)
        return 1
    print(f"Lead time {result['leadDays']} days. Looked at {result['checked']} event(s).")
    for row in result["reminded"]:
        outstanding = ", ".join(f"{item['category']} ({item['status']})" for item in row["outstanding"])
        print(f"  {row['eventId']} {row['eventName']}: {outstanding}. Sent: {', '.join(row['sent']) or 'nothing'}")
    for row in result["skipped"]:
        print(f"  skipped {row['eventId']}: {row['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
