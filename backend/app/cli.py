import argparse
import getpass
import sqlite3

from app.core.config import settings
from app.db import initialize_database
from app.repositories.auth import AuthRepository
from app.security.passwords import hash_password


def create_owner(username: str) -> int:
    initialize_database(settings.database_path)
    repository = AuthRepository(settings.database_path)
    if repository.owner_count() >= settings.max_owner_accounts:
        raise SystemExit("owner account limit reached")
    password = getpass.getpass("Owner password: ")
    confirmation = getpass.getpass("Confirm owner password: ")
    if password != confirmation:
        raise SystemExit("passwords do not match")
    if len(password) < 12:
        raise SystemExit("owner password must contain at least 12 characters")
    try:
        owner = repository.create_owner(
            username=username,
            password_hash=hash_password(password),
        )
    except sqlite3.IntegrityError as error:
        raise SystemExit("owner username already exists") from error
    print(f"Owner created: {owner['username']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    owner_parser = subparsers.add_parser(
        "create-owner",
        help="create an owner with an interactively entered password",
    )
    owner_parser.add_argument("--username", default="owner")
    args = parser.parse_args()
    if args.command == "create-owner":
        username = str(args.username).strip()
        if not username or not username.isprintable() or len(username) > 64:
            raise SystemExit("username must be printable and 1-64 characters")
        return create_owner(username)
    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
