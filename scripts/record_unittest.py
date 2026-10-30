#!/usr/bin/env python3
"""`python -m unittest`, plus one JSON line per test in test-reports/<suite>.jsonl.

    python scripts/record_unittest.py --suite unit --group venue-service discover -s tests/unit -t .

Everything after the options goes to unittest unchanged, and the exit code is
unittest's, so it drops into existing commands (including `coverage run`).
scripts/test_report.py turns the lines into rows of the test-case CSV.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "test-reports"


class RecordingResult(unittest.TextTestResult):
    records: dict[str, dict] = {}

    def startTest(self, test):
        self._started = time.perf_counter()
        super().startTest(test)

    def _record(self, test, status, err=None, note=""):
        error = note
        if err is not None:
            error = traceback.format_exception_only(err[0], err[1])[-1].strip()
        record = RecordingResult.records.setdefault(
            test.id(),
            {
                "id": test.id(),
                "description": (test.shortDescription() or "").strip(),
                "status": "passed",
                "error": "",
            },
        )
        # A failing subtest fails the whole test; a later pass doesn't undo it.
        if record["status"] in ("failed", "error") and status == "passed":
            return
        record.update(
            status=status,
            error=error or record["error"],
            durationMs=round((time.perf_counter() - getattr(self, "_started", time.perf_counter())) * 1000),
            finishedAt=datetime.now(timezone.utc).isoformat(),
        )

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed", err)

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error", err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", note=reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "passed", note="expected failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "failed", note="expected to fail but passed")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            failed = issubclass(err[0], test.failureException)
            self._record(test, "failed" if failed else "error", err)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--suite", required=True, help="unit or integration: names the output file")
    parser.add_argument("--group", default="", help="e.g. the service the tests belong to")
    parser.add_argument("--fresh", action="store_true", help="empty the output file first")
    options, unittest_args = parser.parse_known_args()

    # Behave like `python -m unittest`: imports resolve from the working directory.
    sys.path[0] = os.getcwd()
    output = REPORTS / f"{options.suite}.jsonl"
    REPORTS.mkdir(exist_ok=True)
    if options.fresh:
        output.write_text("", encoding="utf-8")

    runner = unittest.TextTestRunner(resultclass=RecordingResult)
    program = unittest.main(module=None, argv=["unittest", *unittest_args], testRunner=runner, exit=False)

    with output.open("a", encoding="utf-8") as handle:
        for record in RecordingResult.records.values():
            handle.write(json.dumps({"suite": options.suite, "group": options.group, **record}) + "\n")
    return 0 if program.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
