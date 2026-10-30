"""Trim local MySQL back to the demo data plus one example event per status.

Acceptance tests leave hundreds of AUTO-... events behind. This keeps the seeded
demo events (e1, e2, ...) and, for each status none of them is in, the test event
with the most history attached. Every other event goes, along with its bookings,
equipment requests and reservations, registrations and notifications. Users,
organisations, venues and equipment are left alone.

Run through `python scripts/migrate.py --clean-test-data`, which seeds first so
the demo events always exist. A full backup is written to backups/ before anything
is deleted.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import bindparam, create_engine, text

from seed import URLS

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups"
DATABASES = ["user", "event", "venue", "equipment", "registration", "notification"]
# Notifications kept per user and type, newest first.
NOTICES_KEPT = 2

# event-service tables keyed by event_id, deleted before events (no foreign key cascades).
EVENT_CHILD_TABLES = [
    "event_assignments",
    "event_change_requests",
    "event_field_changes",
    "event_readiness_items",
    "event_reschedules",
    "event_reviews",
    "event_safety_handoffs",
    "event_safety_reviews",
    "event_status_history",
]
# Rows that make an example event worth keeping: the more of its story it carries, the better.
HISTORY = [
    ("event", "event_status_history"),
    ("event", "event_reviews"),
    ("event", "event_change_requests"),
    ("event", "event_safety_reviews"),
    ("venue", "venue_bookings"),
    ("equipment", "equipment_requests"),
    ("registration", "attendee_registrations"),
]


def _engine(name: str):
    return create_engine(URLS[name])


def _is_seeded(event_id: str) -> bool:
    return event_id[:1] == "e" and event_id[1:].isdigit()


def _history_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for database, table in HISTORY:
        with _engine(database).connect() as conn:
            rows = conn.execute(text(f"SELECT event_id, COUNT(*) FROM {table} GROUP BY event_id"))
            for event_id, n in rows:
                counts[event_id] = counts.get(event_id, 0) + n
    return counts


def choose_events_to_keep() -> tuple[list[str], list[tuple]]:
    """The demo events, plus the richest test event for each status they don't cover."""
    with _engine("event").connect() as conn:
        events = conn.execute(text("SELECT event_id, name, status, created_at FROM events")).all()
    counts = _history_counts()
    keep = [row.event_id for row in events if _is_seeded(row.event_id)]
    covered = {row.status for row in events if _is_seeded(row.event_id)}
    examples = {}
    for row in events:
        if row.status in covered:
            continue
        best = examples.get(row.status)
        rank = (counts.get(row.event_id, 0), row.created_at or datetime.min)
        if best is None or rank > (counts.get(best.event_id, 0), best.created_at or datetime.min):
            examples[row.status] = row
    keep += [row.event_id for row in examples.values()]
    return keep, sorted(((row.status, row.name) for row in examples.values()))


def _delete(conn, sql: str, keep: list[str]) -> int:
    statement = text(sql).bindparams(bindparam("keep", expanding=True))
    return conn.execute(statement, {"keep": keep}).rowcount


def delete_everything_else(keep: list[str]) -> dict[str, int]:
    removed = {}
    with _engine("event").begin() as conn:
        removed["event_clarification_replies"] = _delete(
            conn,
            "DELETE r FROM event_clarification_replies r JOIN event_reviews v ON v.review_id = r.review_id "
            "WHERE v.event_id NOT IN :keep",
            keep,
        )
        for table in EVENT_CHILD_TABLES:
            removed[table] = _delete(conn, f"DELETE FROM {table} WHERE event_id NOT IN :keep", keep)
        removed["events"] = _delete(conn, "DELETE FROM events WHERE event_id NOT IN :keep", keep)
    with _engine("venue").begin() as conn:
        removed["venue_bookings"] = _delete(conn, "DELETE FROM venue_bookings WHERE event_id NOT IN :keep", keep)
    with _engine("equipment").begin() as conn:
        # Reservations go before the requests they belong to.
        removed["equipment_reservations"] = _delete(
            conn,
            "DELETE s FROM equipment_reservations s LEFT JOIN equipment_requests q ON q.request_id = s.request_id "
            "WHERE s.event_id NOT IN :keep OR q.event_id NOT IN :keep",
            keep,
        )
        removed["equipment_requests"] = _delete(
            conn, "DELETE FROM equipment_requests WHERE event_id NOT IN :keep", keep
        )
    with _engine("registration").begin() as conn:
        removed["attendee_registrations"] = _delete(
            conn, "DELETE FROM attendee_registrations WHERE event_id NOT IN :keep", keep
        )
        removed["registration_windows"] = _delete(
            conn, "DELETE FROM registration_windows WHERE event_id NOT IN :keep", keep
        )
    with _engine("notification").begin() as conn:
        removed["notifications"] = _delete(
            conn, "DELETE FROM notifications WHERE event_id IS NOT NULL AND event_id NOT IN :keep", keep
        )
        removed["notifications"] += conn.execute(
            text(
                "DELETE n FROM notifications n JOIN ("
                "  SELECT notification_id, ROW_NUMBER() OVER ("
                "    PARTITION BY user_id, type ORDER BY created_at DESC, notification_id DESC) AS rn"
                "  FROM notifications"
                ") ranked ON ranked.notification_id = n.notification_id WHERE ranked.rn > :kept"
            ),
            {"kept": NOTICES_KEPT},
        ).rowcount
    return removed


def back_up() -> Path:
    """Dump all six databases through the Compose MySQL container."""
    BACKUP_DIR.mkdir(exist_ok=True)
    path = BACKUP_DIR / f"db-before-clean-{datetime.now():%Y%m%d-%H%M%S}.sql"
    command = [
        "docker", "compose", "-f", str(ROOT / "infra" / "docker-compose.yml"), "exec", "-T", "mysql",
        "mysqldump", "-uroot", "-pconnectsphere", "--single-transaction", "--routines", "--triggers",
        "--databases", *DATABASES,
    ]
    with path.open("wb") as out:
        result = subprocess.run(command, cwd=ROOT, stdout=out, stderr=subprocess.PIPE)
    if result.returncode != 0 or path.stat().st_size == 0:
        path.unlink(missing_ok=True)
        detail = result.stderr.decode(errors="replace").replace("mysqldump: [Warning] Using a password", "").strip()
        raise SystemExit(f"Backup failed, nothing was deleted. {detail}")
    return path


def clean_test_data(assume_yes: bool = False) -> None:
    keep, examples = choose_events_to_keep()
    with _engine("event").connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM events")).scalar()
    print(f"keeping {len(keep)} of {total} events: the demo events plus one example for")
    for status, name in examples:
        print(f"  {status:<18} {name}")
    if total == len(keep):
        print("nothing to clean")
        return
    if not assume_yes:
        if not sys.stdin.isatty():
            raise SystemExit("Refusing to delete without a terminal to confirm. Re-run with --yes.")
        try:
            answer = input(f"delete the other {total - len(keep)} events and everything attached to them? [y/N] ")
        except EOFError:  # Git Bash can report a terminal that has no input behind it
            answer = ""
        if answer.strip().lower() != "y":
            print("cancelled, nothing deleted")
            return
    print(f"backup written to {back_up().relative_to(ROOT)}")
    removed = delete_everything_else(keep)
    for table, n in removed.items():
        if n:
            print(f"  removed {n:>5} from {table}")
    print("clean complete")
