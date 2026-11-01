#!/usr/bin/env python3
"""Run a test case's setup SQL on the test database (the Compose MySQL container).

  python scripts/test_setup.py TC-SPM43-AC01
  python scripts/test_setup.py base            # just the reset to seed data

docs/testing/setup/ is mounted into the container as /setup (infra/docker-compose.yml),
so this needs no MySQL client on the host and works the same in PowerShell and bash.
Every file empties all tables and reloads the seed: anything else in the database is lost.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "docs" / "testing" / "setup"
COMPOSE = ROOT / "infra" / "docker-compose.yml"


def run(name: str) -> None:
    if not (SETUP / f"{name}.sql").exists():
        raise SystemExit(f"No setup file docs/testing/setup/{name}.sql. Build them with: python scripts/build_test_setup.py")
    command = [
        "docker", "compose", "-f", str(COMPOSE), "exec", "-T", "mysql",
        "sh", "-c", f"mysql -uroot -pconnectsphere --default-character-set=utf8mb4 < /setup/{name}.sql",
    ]
    result = subprocess.run(command, cwd=ROOT, stderr=subprocess.PIPE)
    detail = result.stderr.decode(errors="replace").replace(
        "mysql: [Warning] Using a password on the command line interface can be insecure.", ""
    ).strip()
    if result.returncode != 0:
        raise SystemExit(f"{name}: setup failed. {detail}")
    print(f"{name}: database reset to its setup")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for case in sys.argv[1:]:
        run(case)
