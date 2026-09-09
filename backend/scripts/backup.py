"""Encrypted backup/restore. Use --generate-key once and store the key safely."""
import argparse
import gzip
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cryptography.fernet import Fernet
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-key", action="store_true")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--output", type=Path)
    operation.add_argument("--restore", type=Path)
    operation.add_argument("--restore-json", type=Path)
    args = parser.parse_args()
    if args.generate_key:
        print(Fernet.generate_key().decode())
        return
    load_dotenv()
    key = os.environ.get("BACKUP_ENCRYPTION_KEY")
    if not key and not args.restore_json:
        parser.error("Configurare BACKUP_ENCRYPTION_KEY")
    cipher = Fernet(key.encode()) if key else None
    from app.db.session import SessionLocal
    from app.services.backup_service import export_data, restore_data
    with SessionLocal() as db:
        if args.restore_json:
            restore_data(db, json.loads(args.restore_json.read_text(encoding="utf-8")))
            print("Ripristino completato")
        elif args.restore:
            payload = json.loads(gzip.decompress(cipher.decrypt(args.restore.read_bytes())))
            restore_data(db, payload)
            print("Ripristino completato")
        elif args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            data = gzip.compress(json.dumps(export_data(db), ensure_ascii=False).encode())
            args.output.write_bytes(cipher.encrypt(data))
            print("Backup cifrato creato")
        else:
            parser.error("Specificare --output oppure --restore")


if __name__ == "__main__":
    main()
