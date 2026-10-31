#!/usr/bin/env python3
"""Build docs/testing/test-cases.csv, the design half of the team's test-case template.

One row per acceptance test case ID. The ID, story and scenario come from
docs/testing/traceability.md (plus any TC- ID a Playwright test uses that the
table doesn't list yet); Created By and Date of Creation come from the first
commit that added the ID to e2e/. Pre-conditions, Test Steps, Test Data and
Expected Result are for the team to write.

Safe to re-run: a value already in the CSV is never overwritten, so hand-written
steps survive. New IDs are appended, and IDs no spec uses any more are reported.
"""

from __future__ import annotations

import csv
import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACEABILITY = ROOT / "docs" / "testing" / "traceability.md"
CATALOGUE = ROOT / "docs" / "testing" / "test-cases.csv"
E2E = ROOT / "e2e"

COLUMNS = [
    "Test Case ID",
    "Story",
    "Test Scenario",
    "Pre-conditions",
    "Test Steps",
    "Test Data",
    "Expected Result",
    "Created By",
    "Date of Creation",
]
DEFAULT_PRECONDITION = "Fresh seeded database and running app (npm run test:prepare)."
TEST_TITLE = re.compile(r"""test\(\s*['"`](TC-[^'"`]*)""")
# A full ID, then any short forms that borrow its prefix: "TC-SPM08-AC01, AC01b" or
# "TC-SPM116-AC03 and AC04" name two cases each.
ID_RUN = re.compile(r"(TC-[A-Za-z0-9]+)-([A-Z]+\d+[a-z]?)((?:\s*(?:,|;|\band\b)\s*[A-Z]+\d+[a-z]?\b)*)")


def ids_in_text(text: str) -> list[str]:
    ids = []
    for prefix, first, rest in ID_RUN.findall(text):
        ids.append(f"{prefix}-{first}")
        ids += [f"{prefix}-{short}" for short in re.findall(r"[A-Z]+\d+[a-z]?", rest)]
    return list(dict.fromkeys(ids))


def title_without_ids(title: str) -> str:
    """The words after a test title's leading IDs."""
    match = ID_RUN.match(title)
    return title[match.end():].strip() if match else title.strip()


def from_traceability() -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for line in TRACEABILITY.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[2].startswith("TC-"):
            continue
        story, criterion = cells[0], cells[1]
        for case_id in ids_in_text(cells[2]):
            case = cases.setdefault(case_id, {"Story": story, "criteria": []})
            if criterion not in case["criteria"]:
                case["criteria"].append(criterion)
    return cases


def from_specs() -> dict[str, str]:
    """TC- IDs the Playwright tests use, with the first test title found for each."""
    titles: dict[str, str] = {}
    for spec in sorted(E2E.glob("*.spec.js")):
        for title in TEST_TITLE.findall(spec.read_text(encoding="utf-8")):
            for case_id in ids_in_text(title):
                titles.setdefault(case_id, title_without_ids(title))
    return titles


def first_commits() -> dict[str, tuple[str, str]]:
    """Author and date of the commit that first added each TC- ID under e2e/."""
    log = subprocess.run(
        ["git", "log", "--reverse", "--format=@@@%an|%ad", "--date=short", "-p", "-U0", "--", "e2e"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout
    seen: dict[str, tuple[str, str]] = {}
    author = day = ""
    for line in log.splitlines():
        if line.startswith("@@@"):
            author, day = line[3:].split("|", 1)
        elif line.startswith("+") and not line.startswith("+++"):
            for case_id in ids_in_text(line):
                seen.setdefault(case_id, (author, day))
    return seen


def _story_of(case_id: str) -> str:
    match = re.match(r"TC-SPM0*(\d+)-", case_id)
    return f"SPM-{match.group(1)}" if match else case_id.split("-")[1]


def _uk_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


def main() -> None:
    traced = from_traceability()
    titles = from_specs()
    commits = first_commits()

    existing: dict[str, dict] = {}
    if CATALOGUE.exists():
        with CATALOGUE.open(encoding="utf-8-sig", newline="") as handle:
            existing = {row["Test Case ID"]: row for row in csv.DictReader(handle)}

    ids = list(existing) + [i for i in list(traced) + list(titles) if i not in existing]
    ids = list(dict.fromkeys(ids))
    rows = []
    for case_id in ids:
        trace = traced.get(case_id, {})
        scenario = " / ".join(trace.get("criteria", [])) or titles.get(case_id, "")
        author, day = commits.get(case_id, ("", ""))
        generated = {
            "Test Case ID": case_id,
            "Story": trace.get("Story") or _story_of(case_id),
            "Test Scenario": scenario,
            "Pre-conditions": DEFAULT_PRECONDITION,
            "Test Steps": "",
            "Test Data": "",
            "Expected Result": scenario,
            "Created By": author,
            "Date of Creation": _uk_date(day),
        }
        kept = existing.get(case_id, {})
        rows.append({column: kept.get(column) or generated[column] for column in COLUMNS})

    CATALOGUE.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel opens the file with the right encoding.
    with CATALOGUE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    added = len(ids) - len(existing)
    print(f"{CATALOGUE.relative_to(ROOT)}: {len(rows)} test cases ({added} new)")
    stale = sorted(set(existing) - set(traced) - set(titles))
    if stale:
        print("no spec or traceability row uses these any more:", ", ".join(stale))
    unsigned = [row["Test Case ID"] for row in rows if not row["Created By"]]
    if unsigned:
        print(f"{len(unsigned)} cases have no commit adding their ID under e2e/; fill Created By by hand")


if __name__ == "__main__":
    main()
