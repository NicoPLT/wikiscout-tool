"""Genera l'hash bcrypt di una password da mettere in AUTH_PASSWORD_HASH (.env).

Uso:
    python scripts/hash_password.py "la-mia-password"
"""

import sys

sys.path.append(".")

from app.core.security import hash_password  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python scripts/hash_password.py <password>")
        raise SystemExit(1)

    print(hash_password(sys.argv[1]))


if __name__ == "__main__":
    main()
