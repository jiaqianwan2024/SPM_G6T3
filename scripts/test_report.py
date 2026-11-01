#!/usr/bin/env python3
"""Fill the team's test-case template with the latest results: test-reports/test-results.csv.

Joins the raw results in test-reports/ (e2e.jsonl from Playwright, unit.jsonl and
integration.jsonl from scripts/record_unittest.py) with the design half in
docs/testing/test-cases.csv.

    python scripts/test_report.py           # write test-reports/test-results.csv and story-summary.csv
    python scripts/test_report.py --save    # also keep dated copies in docs/testing/results/

Acceptance rows are per test case ID, following docs/testing/traceability.md: a case
is Pass only when every test for that ID passes, a skipped test keeps it Blocked,
and a case none of whose tests ran is Not Executed. Unit and integration tests have
no case IDs, so each test is its own row.

story-summary.csv rolls the rows up: one per user story, plus one per service for
unit and integration tests. A story takes the worst status of its cases, so it is
Pass only when every case passed.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from build_test_catalogue import CATALOGUE, ids_in_text, title_without_ids

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "test-reports"
OUTPUT = REPORTS / "test-results.csv"
STORY_OUTPUT = REPORTS / "story-summary.csv"
SAVED = ROOT / "docs" / "testing" / "results"
SGT = timezone(timedelta(hours=8))

COLUMNS = [
    "Test Case ID",
    "Test Level",
    "Story",
    "Test Scenario",
    "Pre-conditions",
    "Test Steps",
    "Test Data",
    "Expected Result",
    "Created By",
    "Date of Creation",
    "Actual Result",
    "Pass/Fail/Not Executed/Blocked",
    "Remarks",
    "Executed By",
    "Date of Execution",
]
PRECONDITIONS = {
    "unit": "Isolated SQLite database per test; calls to other services are mocked.",
    "integration": "Each service runs in its own process against its own SQLite database.",
}
LEVELS = {"unit": "Unit", "integration": "Integration"}
# Worst first: a story or case takes the first of these that any of its parts has.
STATUS_ORDER = ["Fail", "Blocked", "Not Executed", "Pass"]
STATUS = "Pass/Fail/Not Executed/Blocked"
STORY_COLUMNS = [
    "Story",
    "Test Level",
    "Test Cases",
    "Pass",
    "Fail",
    "Blocked",
    "Not Executed",
    "Story Status",
    "Failed Cases",
    "Blocked Cases",
    "Remarks",
    "Executed By",
    "Date of Execution",
]


def _read_jsonl(name: str) -> list[dict] | None:
    path = REPORTS / f"{name}.jsonl"
    if not path.exists():
        return None
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _executed_by() -> str:
    if os.getenv("GITHUB_ACTIONS"):
        return f"GitHub Actions run #{os.getenv('GITHUB_RUN_NUMBER', '?')} ({os.getenv('GITHUB_ACTOR', 'unknown')})"
    name = subprocess.run(["git", "config", "user.name"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return name or getpass.getuser()


def _sgt(iso_times: list[str]) -> str:
    times = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in iso_times if value]
    return max(times).astimezone(SGT).strftime("%d/%m/%Y %H:%M") if times else ""


def _ci_excluded_stories() -> set[int]:
    """Story numbers `npm run test:acceptance` leaves out with --grep-invert."""
    scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    return {int(n) for n in re.findall(r"SPM-0*(\d+)", scripts.get("test:acceptance", ""))}


def _story_number(story: str) -> int | None:
    match = re.fullmatch(r"SPM-0*(\d+)", story.strip())
    return int(match.group(1)) if match else None


def _clip(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _sentence(method: str) -> str:
    words = method.removeprefix("test_").replace("_", " ").strip()
    return words[:1].upper() + words[1:]


# ---------- acceptance (Playwright) ----------

def _outcome(test: dict) -> str:
    if test["status"] == test.get("expectedStatus", "passed") and test["status"] != "skipped":
        return "Pass"
    if test["status"] in ("skipped", "interrupted"):
        return "Blocked"
    return "Fail"


def acceptance_rows(catalogue: list[dict], results: list[dict] | None, executed_by: str) -> list[dict]:
    by_case: dict[str, list[dict]] = {}
    unnamed: dict[str, int] = {}
    for test in results or []:
        ids = ids_in_text(test["title"])
        if not ids:
            stem = Path(test["file"]).name.removesuffix(".spec.js")
            unnamed[stem] = unnamed.get(stem, 0) + 1
            ids = [f"E2E-{stem}-{unnamed[stem]:02d}"]
            test["unnamed"] = True
        for case_id in ids:
            by_case.setdefault(case_id, []).append(test)

    excluded = _ci_excluded_stories()
    designed = {row["Test Case ID"]: row for row in catalogue}
    rows = []
    for case_id in list(designed) + [i for i in by_case if i not in designed]:
        design = designed.get(case_id, {})
        tests = by_case.get(case_id, [])
        row = {column: design.get(column, "") for column in COLUMNS}
        row["Test Case ID"] = case_id
        row["Test Level"] = "Acceptance"
        if not design and tests:
            title = tests[0]["title"] if tests[0].get("unnamed") else title_without_ids(tests[0]["title"])
            # The outermost describe block, e.g. "Lead dashboard prototype", stands in for the story.
            describes = [part for part in tests[0]["path"].split(" › ")[:-1] if not part.endswith(".spec.js")]
            row["Story"] = describes[0] if describes else Path(tests[0]["file"]).name.removesuffix(".spec.js")
            row["Test Scenario"] = row["Expected Result"] = title
            row["Pre-conditions"] = "Fresh seeded database and running app (npm run test:prepare)."
            row["Remarks"] = "Not in docs/testing/test-cases.csv yet. "

        if not tests:
            row["Pass/Fail/Not Executed/Blocked"] = "Not Executed"
            if results is None:
                row["Remarks"] = "Browser tests were not run."
            elif _story_number(row["Story"]) in excluded:
                row["Remarks"] = f"{row['Story']} is excluded from CI by npm run test:acceptance."
            else:
                row["Remarks"] = "Not part of this run."
            rows.append(row)
            continue

        outcomes = [_outcome(test) for test in tests]
        status = min(outcomes, key=STATUS_ORDER.index)
        row["Pass/Fail/Not Executed/Blocked"] = status
        if status == "Pass":
            row["Actual Result"] = row["Expected Result"] or f"All {len(tests)} tests passed."
        else:
            row["Actual Result"] = _clip(
                "; ".join(
                    f"{title_without_ids(test['title'])}: {test['error'] or test['status']}"
                    for test, outcome in zip(tests, outcomes)
                    if outcome == status
                ),
                600,
            )
        files = sorted({test["file"] for test in tests})
        remarks = [f"{len(tests)} test{'s' if len(tests) > 1 else ''} in {', '.join(files)}."]
        retried = [test for test in tests if test.get("retry")]
        if retried and status == "Pass":
            remarks.append(f"{len(retried)} passed only on a retry (flaky).")
        if status == "Fail":
            remarks.append("Screenshot, video and trace are in the playwright-report artifact.")
        row["Remarks"] += " ".join(remarks)
        row["Executed By"] = executed_by
        row["Date of Execution"] = _sgt([test.get("finishedAt", "") for test in tests])
        rows.append(row)
    return rows


# ---------- unit and integration (unittest) ----------

def _test_file(suite: str, group: str, test_id: str) -> str:
    module = test_id.rsplit(".", 2)[0]
    if suite == "unit":
        return f"services/{group}/{module.replace('.', '/')}.py"
    return f"tests/integration/{module.replace('.', '/')}.py"


def first_commits_of_tests() -> dict[tuple[str, str], tuple[str, str]]:
    """(file, test method) -> author and date of the commit that added the method."""
    log = subprocess.run(
        ["git", "log", "--reverse", "--format=@@@%an|%ad", "--date=short", "-p", "-U0", "--",
         "services/*/tests/*", "tests/integration"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    author = day = current = ""
    for line in log.splitlines():
        if line.startswith("@@@"):
            author, day = line[3:].split("|", 1)
        elif line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("+") and current:
            match = re.match(r"\+\s*(?:async\s+)?def (test_\w+)", line)
            if match:
                seen.setdefault((current, match.group(1)), (author, day))
    return seen


def unittest_rows(suite: str, results: list[dict], commits: dict, executed_by: str) -> list[dict]:
    prefix = "UT" if suite == "unit" else "IT"
    rows = []
    for test in results:
        module, cls, method = test["id"].rsplit(".", 2)
        group = test.get("group") or ""
        author, day = commits.get((_test_file(suite, group, test["id"]), method), ("", ""))
        scenario = _sentence(method)
        expected = test.get("description") or scenario
        status = {"passed": "Pass", "skipped": "Blocked"}.get(test["status"], "Fail")
        short_group = group.removesuffix("-service")
        rows.append({
            "Test Case ID": f"{prefix}-{short_group + '-' if short_group else ''}{module.rsplit('.', 1)[-1]}.{cls}.{method}",
            "Test Level": LEVELS[suite],
            # Integration tests run workflows across every service rather than belonging to one.
            "Story": group or "All services",
            "Test Scenario": scenario,
            "Pre-conditions": PRECONDITIONS[suite],
            "Test Steps": "",
            "Test Data": "",
            "Expected Result": expected,
            "Created By": author,
            "Date of Creation": datetime.fromisoformat(day).strftime("%d/%m/%Y") if day else "",
            "Actual Result": expected if status == "Pass" else _clip(test.get("error") or test["status"]),
            "Pass/Fail/Not Executed/Blocked": status,
            "Remarks": f"Skipped: {test['error']}" if status == "Blocked" else _test_file(suite, group, test["id"]),
            "Executed By": executed_by,
            "Date of Execution": _sgt([test.get("finishedAt", "")]),
        })
    return rows


# ---------- story summary ----------

def _story_sort_key(story: dict) -> tuple:
    level = ["Acceptance", "Unit", "Integration"].index(story["Test Level"])
    number = _story_number(story["Story"])
    return (level, number is None, number or 0, story["Story"])


def _parse_sgt(value: str) -> datetime:
    return datetime.strptime(value, "%d/%m/%Y %H:%M")


def _cases_with(cases: list[dict], status: str, level: str) -> str:
    """Acceptance stories name their cases; unit and integration rows give a count, not 400 test names."""
    if level == "Acceptance":
        return _clip(", ".join(case["Test Case ID"] for case in cases if case[STATUS] == status), 500)
    n = sum(case[STATUS] == status for case in cases)
    return f"{n} test{'s' if n > 1 else ''}" if n else ""


def story_rows(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["Test Level"], row["Story"] or "(no story)"), []).append(row)

    stories = []
    for (level, story), cases in groups.items():
        counts = {status: sum(case[STATUS] == status for case in cases) for status in STATUS_ORDER}
        status = min((case[STATUS] for case in cases), key=STATUS_ORDER.index)
        remarks = []
        if counts["Not Executed"]:
            reasons = {case["Remarks"] for case in cases if case[STATUS] == "Not Executed"}
            if counts["Not Executed"] == len(cases) and len(reasons) == 1:
                remarks.append(reasons.pop())
            else:
                remarks.append(f"{counts['Not Executed']} of {len(cases)} cases not run.")
        if any("flaky" in case["Remarks"] for case in cases):
            remarks.append("Some cases passed only on a retry (flaky).")
        ran = [case for case in cases if case["Date of Execution"]]
        stories.append({
            "Story": story,
            "Test Level": level,
            "Test Cases": len(cases),
            **counts,
            "Story Status": status,
            "Failed Cases": _cases_with(cases, "Fail", level),
            "Blocked Cases": _cases_with(cases, "Blocked", level),
            "Remarks": " ".join(remarks),
            "Executed By": ran[0]["Executed By"] if ran else "",
            "Date of Execution": max((case["Date of Execution"] for case in ran), key=_parse_sgt) if ran else "",
        })
    return sorted(stories, key=_story_sort_key)


# ---------- output ----------

def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    # utf-8-sig so Excel opens the file with the right encoding.
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    except PermissionError:
        # Windows locks a file while Excel has it open.
        raise SystemExit(f"Can't write {path.relative_to(ROOT)}: close it in Excel, then run this again.")


def story_markdown(stories: list[dict]) -> str:
    acceptance = [story for story in stories if story["Test Level"] == "Acceptance"]
    counts = {status: sum(story["Story Status"] == status for story in acceptance) for status in STATUS_ORDER}
    lines = [
        "", "### User stories", "",
        f"{len(acceptance)} stories: " + ", ".join(f"{counts[s]} {s}" for s in STATUS_ORDER[::-1]) + ".", "",
        "<details><summary>Every story</summary>", "",
        "| Story | Status | Pass | Fail | Blocked | Not Executed | Failed or blocked cases |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for story in acceptance:
        problems = ", ".join(filter(None, [story["Failed Cases"], story["Blocked Cases"]]))
        lines.append(
            f"| {story['Story']} | {story['Story Status']} | {story['Pass']} | {story['Fail']} | "
            f"{story['Blocked']} | {story['Not Executed']} | {_clip(problems, 200)} |"
        )
    lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def summary_markdown(rows: list[dict]) -> str:
    levels = ["Acceptance", "Unit", "Integration"]
    lines = ["## Test results", "", "| Level | " + " | ".join(STATUS_ORDER[::-1]) + " | Total |",
             "|---|" + "---:|" * (len(STATUS_ORDER) + 1)]
    for level in levels:
        mine = [row for row in rows if row["Test Level"] == level]
        if not mine:
            continue
        counts = [sum(row["Pass/Fail/Not Executed/Blocked"] == s for row in mine) for s in STATUS_ORDER[::-1]]
        lines.append(f"| {level} | " + " | ".join(map(str, counts)) + f" | {len(mine)} |")
    failed = [row for row in rows if row["Pass/Fail/Not Executed/Blocked"] == "Fail"]
    if failed:
        lines += ["", f"### Failed ({len(failed)})", "", "| Test case | Actual result |", "|---|---|"]
        for row in failed[:50]:
            actual = row["Actual Result"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {row['Test Case ID']} | {_clip(actual, 200)} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the test-case template CSV from the latest results.")
    parser.add_argument("--save", action="store_true", help="also keep a dated copy in docs/testing/results/")
    args = parser.parse_args()

    if not CATALOGUE.exists():
        raise SystemExit(f"Missing {CATALOGUE.relative_to(ROOT)}. Run: python scripts/build_test_catalogue.py")
    with CATALOGUE.open(encoding="utf-8-sig", newline="") as handle:
        catalogue = list(csv.DictReader(handle))

    executed_by = _executed_by()
    e2e = _read_jsonl("e2e")
    rows = acceptance_rows(catalogue, e2e, executed_by)
    sources = {"e2e": e2e}
    commits = None
    for suite in ("unit", "integration"):
        results = _read_jsonl(suite)
        sources[suite] = results
        if results:
            commits = commits if commits is not None else first_commits_of_tests()
            rows += unittest_rows(suite, results, commits, executed_by)

    stories = story_rows(rows)
    REPORTS.mkdir(exist_ok=True)
    _write_csv(OUTPUT, COLUMNS, rows)
    _write_csv(STORY_OUTPUT, STORY_COLUMNS, stories)

    summary = (
        summary_markdown(rows)
        + story_markdown(stories)
        + "\nFull tables: the `test-results` artifact (test-results.csv and story-summary.csv).\n"
    )
    print(summary)
    missing = [name for name, results in sources.items() if results is None]
    if missing:
        print(f"no results found for: {', '.join(missing)} (run those tests first to include them)")
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(rows)} rows)")
    print(f"wrote {STORY_OUTPUT.relative_to(ROOT)} ({len(stories)} rows)")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(summary)

    if args.save:
        SAVED.mkdir(parents=True, exist_ok=True)
        now = datetime.now(SGT)
        stamp = f"{now:%Y-%m-%d}"
        if (SAVED / f"test-results-{stamp}.csv").exists():
            stamp = f"{now:%Y-%m-%d-%H%M}"
        for source in (OUTPUT, STORY_OUTPUT):
            target = SAVED / f"{source.stem}-{stamp}.csv"
            shutil.copyfile(source, target)
            print(f"saved a copy to {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
