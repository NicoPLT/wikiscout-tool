"""CLI entrypoint; a partial run exits nonzero so CI reports the failure."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.scrapers.jobs import run_nightly_update

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    result = run_nightly_update()
    print(json.dumps(result))
    sys.exit(0 if result["status"] in ("success", "already_running") else 1)
