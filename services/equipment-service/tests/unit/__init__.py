import os
import sys
import tempfile
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[2]
ROOT = SERVICE.parents[1]
sys.path[:0] = [str(SERVICE), str(ROOT)]

_db = Path(tempfile.gettempdir()) / f"{SERVICE.name}-unit.sqlite"
try:
    _db.unlink()
except FileNotFoundError:
    pass
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
# Calls to other services are best effort; point them at a closed port so a unit test can never
# reach (or notify through) a service running on the developer's machine. 0.0.0.0 rather than
# 127.0.0.1: Windows takes about two seconds to refuse a closed 127.0.0.1 port, 0.0.0.0 almost none.
for _name in ("USER_SERVICE_URL", "EVENT_SERVICE_URL", "VENUE_SERVICE_URL", "NOTIFICATION_SERVICE_URL"):
    os.environ.setdefault(_name, "http://0.0.0.0:9")
