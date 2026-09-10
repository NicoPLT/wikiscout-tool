"""CLI entrypoint for the scheduled, checkpointed update."""
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
    if result["status"] == "partial":
        print(
            "::warning title=Aggiornamento parziale::"
            f"Salvati {result['succeeded']} aggiornamenti; "
            f"{result['failed']} falliti e {result['deferred']} rinviati. "
            "I checkpoint verranno ripresi automaticamente."
        )
    # A partial run has persisted useful data and is an expected recoverable
    # outcome when a free external source rate-limits a cloud runner.
    sys.exit(1 if result["status"] == "error" else 0)
