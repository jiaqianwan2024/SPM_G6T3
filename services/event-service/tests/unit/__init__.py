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
# Published notifications are best effort; point them at a closed port so a unit
# test can never write into a notification-service running on the developer's machine.
os.environ.setdefault("NOTIFICATION_SERVICE_URL", "http://127.0.0.1:9")
