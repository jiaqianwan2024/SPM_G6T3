#!/usr/bin/env python3
"""Apply Alembic migrations for every service, then seed demo data."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MYSQL_PORT = 3307

SERVICES = [
    ("user-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/user"),
    ("event-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/event"),
    ("venue-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/venue"),
    ("equipment-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/equipment"),
    ("registration-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/registration"),
    ("notification-service", "mysql+pymysql://connectsphere:connectsphere@localhost:3307/notification"),
]


def wait_for_port(port: int, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise SystemExit(f"Timed out waiting for MySQL on port {port}. Is Docker Compose up?")


def wait_for_mysql(url: str, timeout: int = 60) -> None:
    from sqlalchemy import create_engine, text

    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 — retry until MySQL accepts connections
            last_error = exc
            engine.dispose()
            time.sleep(1)
    raise SystemExit(f"Timed out waiting for {url}: {last_error}")


def upgrade(service: str, url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    cwd = ROOT / "services" / service
    env["PYTHONPATH"] = os.pathsep.join([str(cwd), str(ROOT)])
    print(f"alembic upgrade head  ({service})")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=cwd,
        env=env,
        check=True,
    )


def _require_deps() -> None:
    try:
        import alembic  # noqa: F401
        import pymysql  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            f"Missing dependency ({exc}). Activate the project venv, then run:\n"
            "  pip install -r services/user-service/requirements.txt"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate ConnectSphere MySQL databases.")
    parser.add_argument("--no-seed", action="store_true", help="Skip demo data inserts.")
    parser.add_argument(
        "--clean-test-data",
        action="store_true",
        help="After seeding, delete events left by tests, keeping the demo events plus one example "
        "per status. Backs up to backups/ first.",
    )
    parser.add_argument("--yes", action="store_true", help="Clean without asking for confirmation.")
    args = parser.parse_args()
    if args.clean_test_data and args.no_seed:
        parser.error("--clean-test-data keeps the demo events, so it needs the seed; drop --no-seed.")
    _require_deps()

    print(f"waiting for shared MySQL on :{MYSQL_PORT}")
    wait_for_port(MYSQL_PORT)

    for service, url in SERVICES:
        print(f"checking {service} schema")
        wait_for_mysql(url)
        upgrade(service, url)

    if not args.no_seed:
        from seed import seed_all

        seed_all()
        print("seed complete")
    if args.clean_test_data:
        from clean_test_data import clean_test_data

        clean_test_data(assume_yes=args.yes)
    print("migrate complete")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
