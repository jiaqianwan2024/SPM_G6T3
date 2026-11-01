#!/usr/bin/env python3
"""Build docs/testing/setup/: the SQL each acceptance test case runs on the test
database first ("Run setup/TC-...sql on testDB" in its pre-conditions).

base.sql puts every table in all six databases back to the seeded demo data
(scripts/seed.py): it empties them, then inserts the seed. Dates are written as
offsets from the moment the file is loaded (@now), so "an event in 14 days" is
14 days away whenever it runs. Firebase sign-ins are not touched; the seeded
user rows keep their user_id and firebase_uid.

There is one TC-<id>.sql per test case a Playwright spec names, holding its raw SQL
so it runs on its own in any MySQL client. Each empties every table, then inserts
users, organisations and only the seeded records that case uses (needs.json), each
with what it depends on, plus any rows beyond the seed (EXTRA). base.sql stays for
running a whole spec. records.json files the seed's INSERTs by record, so --cases-only
can rewrite the TC- files without touching the database.

Building base.sql rebuilds the database you point it at: a full backup is
written to backups/ first, every table is emptied, and the seed is run. Run it
after `python scripts/migrate.py` whenever a migration or the seed changes.

  python scripts/build_test_setup.py              # back up, reset, reseed, write every file
  python scripts/build_test_setup.py --cases-only # rewrite the TC- files only

Load a case's setup (the folder is mounted into the MySQL container as /setup):

  python scripts/test_setup.py TC-SPM43-AC01
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pymysql.converters
from sqlalchemy import MetaData, create_engine, text

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from build_test_catalogue import ids_in_text, title_without_ids  # noqa: E402
from clean_test_data import back_up  # noqa: E402
from seed import URLS, schedule_anchor, seed_all  # noqa: E402

SETUP = ROOT / "docs" / "testing" / "setup"
CATALOGUE = ROOT / "docs" / "testing" / "test-cases.csv"
E2E = ROOT / "e2e"
# Where docker-compose mounts SETUP inside the MySQL container.
CONTAINER_DIR = "/setup"
DATABASES = ["user", "event", "venue", "equipment", "registration", "notification"]
KEEP_TABLES = {"alembic_version"}
ROWS_PER_INSERT = 100

# Indirect user stories (developer tooling) have no acceptance test cases.
INDIRECT = {"SPM-18", "SPM-19", "SPM-48", "SPM-49", "SPM-51", "SPM-107", "SPM-109", "SPM-123", "SPM-124", "SPM-125"}
# test(...), test.describe(...), test.skip(...), test.fixme(...) titles.
TITLE = re.compile(r"""test(?:\.describe|\.skip|\.fixme)?\(\s*['"`](TC-[^'"`]*)""")

# Rows a case needs beyond the seed, run after base.sql. Every current spec
# either builds its own events or mocks its empty states, so none are needed yet.
EXTRA: dict[str, str] = {}

# The seeded records each case uses, as {case: [record, ...]}. A record brings what it
# depends on: an event brings its venue, equipment and registration window.
NEEDS = SETUP / "needs.json"
RECORDS = SETUP / "records.json"
CORE_TABLES = {"organisations", "users"}
# Which record a table's rows belong to: the first of these columns the table has.
OWNERS = [
    ("notification_id", "notification"),
    ("attendee_registration_id", "registration"),
    ("change_request_id", "change-request"),
    ("review_id", "review"),
    ("event_id", "event"),
    ("venue_id", "venue"),
    ("equipment_id", "equipment"),
]
# Other records a row points at, which must be loaded before it.
POINTS_AT = {"event_id": "event", "venue_id": "venue", "equipment_id": "equipment"}


def story_of(case_id: str) -> str:
    return "SPM-" + re.match(r"TC-SPM0*(\d+)-", case_id).group(1)


def spec_cases() -> dict[str, tuple[str, str]]:
    """Each TC- ID the specs name -> (spec file, title words), in spec order."""
    cases: dict[str, tuple[str, str]] = {}
    for spec in sorted(E2E.glob("*.spec.js")):
        for title in TITLE.findall(spec.read_text(encoding="utf-8")):
            for case_id in ids_in_text(title):
                if case_id.startswith("TC-SPM") and story_of(case_id) not in INDIRECT:
                    cases.setdefault(case_id, (spec.name, title_without_ids(title)))
    return cases


def scenarios() -> dict[str, str]:
    if not CATALOGUE.exists():
        return {}
    with CATALOGUE.open(encoding="utf-8-sig", newline="") as handle:
        return {row["Test Case ID"]: row["Test Scenario"] for row in csv.DictReader(handle)}


# --- base.sql ------------------------------------------------------------------


def tables_in_order(engine) -> list[str]:
    """Parents before children, so the venue triggers see the rows they look up."""
    meta = MetaData()
    meta.reflect(bind=engine)
    return [table.name for table in meta.sorted_tables if table.name not in KEEP_TABLES]


def reset_and_seed() -> None:
    for name in DATABASES:
        engine = create_engine(URLS[name])
        with engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table in tables_in_order(engine):
                conn.execute(text(f"DELETE FROM `{table}`"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    seed_all()


def literal(value, now: dt.datetime) -> str:
    """A value as SQL. Datetimes and dates become offsets from @now."""
    if value is None:
        return "NULL"
    if isinstance(value, dt.datetime):
        seconds = round((value - now).total_seconds())
        return f"@now + INTERVAL {seconds} SECOND"
    if isinstance(value, dt.date):
        return f"DATE(@now) + INTERVAL {(value - now.date()).days} DAY"
    if isinstance(value, (bytes, bytearray)):
        return "0x" + value.hex() if value else "''"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    return pymysql.converters.escape_item(str(value), "utf8mb4")


def dump(name: str, now: dt.datetime) -> tuple[list[str], list[str]]:
    """(the database's DELETEs, its INSERTs)."""
    engine = create_engine(URLS[name])
    deletes, inserts = [], []
    with engine.connect() as conn:
        for table in tables_in_order(engine):
            deletes.append(f"DELETE FROM `{name}`.`{table}`;")
            result = conn.exec_driver_sql(f"SELECT * FROM `{table}`")
            columns = ", ".join(f"`{column}`" for column in result.keys())
            rows = [f"({', '.join(literal(value, now) for value in row)})" for row in result]
            for start in range(0, len(rows), ROWS_PER_INSERT):
                chunk = ",\n  ".join(rows[start:start + ROWS_PER_INSERT])
                inserts.append(f"INSERT INTO `{name}`.`{table}` ({columns}) VALUES\n  {chunk};")
    return deletes, inserts


def write_base() -> int:
    # The seed's own anchor, which @now below matches when the file is loaded.
    now = schedule_anchor()
    deletes, inserts = [], []
    for name in DATABASES:
        database_deletes, database_inserts = dump(name, now)
        deletes += database_deletes
        inserts += database_inserts
    body = "\n".join(
        [
            "-- ConnectSphere seed data for acceptance tests. Generated by scripts/build_test_setup.py",
            "-- from scripts/seed.py; do not edit by hand. Empties every table in the six databases",
            "-- (alembic_version aside), then inserts the seed. Dates are offsets from the latest 10:00 SGT",
            "-- (02:00 UTC) before it is loaded, as in scripts/seed.py, so events start on the hour.",
            "SET NAMES utf8mb4;",
            "SET @now = TIMESTAMP(DATE(UTC_TIMESTAMP() - INTERVAL 2 HOUR)) + INTERVAL 2 HOUR;",
            "SET FOREIGN_KEY_CHECKS = 0;",
            *deletes,
            *inserts,
            "SET FOREIGN_KEY_CHECKS = 1;",
            "",
        ]
    )
    (SETUP / "base.sql").write_text(body, encoding="utf-8", newline="\n")
    return len(inserts)


# --- records.json --------------------------------------------------------------


def write_records() -> int:
    """The seed's INSERTs filed under the record they belong to (each event, venue,
    equipment item, registration and notification), with what each record needs loaded
    before it. The TC- files for cases in NEEDS are written from this."""
    with create_engine(URLS["user"]).connect() as conn:
        now = conn.execute(text("SELECT UTC_TIMESTAMP()")).scalar()
    deletes: list[str] = []
    core: list[str] = []
    records: dict[str, list[str]] = {}
    depends: dict[str, set[str]] = {}
    for name in DATABASES:
        engine = create_engine(URLS[name])
        with engine.connect() as conn:
            for table in tables_in_order(engine):
                deletes.append(f"DELETE FROM `{name}`.`{table}`;")
                result = conn.exec_driver_sql(f"SELECT * FROM `{table}`")
                columns = list(result.keys())
                column_list = ", ".join(f"`{column}`" for column in columns)
                for row in result.mappings():
                    values = ", ".join(literal(row[column], now) for column in columns)
                    insert = f"INSERT INTO `{name}`.`{table}` ({column_list}) VALUES ({values});"
                    if table in CORE_TABLES:
                        core.append(insert)
                        continue
                    owner = next(((column, kind) for column, kind in OWNERS if column in columns), None)
                    if owner is None:
                        raise SystemExit(f"{name}.{table} has seeded rows but no record to file them under")
                    record = f"{owner[1]}-{row[owner[0]]}"
                    records.setdefault(record, []).append(insert)
                    needs = depends.setdefault(record, set())
                    for column, kind in POINTS_AT.items():
                        if column in columns and row[column] and f"{kind}-{row[column]}" != record:
                            needs.add(f"{kind}-{row[column]}")
    RECORDS.write_text(
        json.dumps(
            {
                "deletes": deletes,
                "core": core,
                "records": dict(sorted(records.items())),
                "depends": {record: sorted(needs) for record, needs in sorted(depends.items())},
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return len(records)


def load_order(needs: list[str], depends: dict[str, list[str]]) -> list[str]:
    """The records a case asked for, each after what it depends on, each once."""
    ordered: list[str] = []

    def visit(record: str) -> None:
        if record in ordered:
            return
        if record not in depends:
            raise SystemExit(f"NEEDS names {record}, which is not in {RECORDS.name}")
        for parent in depends[record]:
            visit(parent)
        ordered.append(record)

    for record in needs:
        visit(record)
    return ordered


# --- TC- files -----------------------------------------------------------------


def write_cases() -> int:
    cases = spec_cases()
    named = scenarios()
    needs = json.loads(NEEDS.read_text(encoding="utf-8"))
    missing = sorted(set(cases) - set(needs))
    if missing:
        raise SystemExit(f"{NEEDS.name} has no entry for: {', '.join(missing)}")
    seed = json.loads(RECORDS.read_text(encoding="utf-8"))
    for stale in SETUP.glob("TC-*.sql"):
        if stale.stem not in cases:
            stale.unlink()
    for case_id, (spec, title) in cases.items():
        lines = [
            f"-- {case_id} ({story_of(case_id)}): {named.get(case_id) or title}",
            f"-- Automated in e2e/{spec}. Run on the test database before the test:",
            f"--   python scripts/test_setup.py {case_id}",
        ]
        lines += [
            "-- Empties every table, then loads users, organisations and the records this case uses.",
            "-- Generated from scripts/seed.py; do not edit by hand. Dates are offsets from the time it is loaded.",
            "SET NAMES utf8mb4;",
            "SET @now = UTC_TIMESTAMP();",
            "SET FOREIGN_KEY_CHECKS = 0;",
            *seed["deletes"],
            "-- Users and organisations",
            *seed["core"],
        ]
        for record in load_order(needs[case_id], seed["depends"]):
            lines += [f"-- {record}", *seed["records"][record]]
        lines.append("SET FOREIGN_KEY_CHECKS = 1;")
        if case_id in EXTRA:
            lines += ["-- Rows this case needs beyond the seed.", EXTRA[case_id].strip()]
        (SETUP / f"{case_id}.sql").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases-only", action="store_true", help="Rewrite the TC- files; leave the database and base.sql.")
    args = parser.parse_args()
    SETUP.mkdir(parents=True, exist_ok=True)
    if not args.cases_only:
        print(f"backup written to {back_up().relative_to(ROOT)}")
        reset_and_seed()
        print(f"{(SETUP / 'base.sql').relative_to(ROOT)}: {write_base()} INSERT statements")
        print(f"{RECORDS.relative_to(ROOT)}: {write_records()} seeded records")
    print(f"{SETUP.relative_to(ROOT)}: {write_cases()} test case setup files")


if __name__ == "__main__":
    main()
