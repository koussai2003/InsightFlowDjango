"""Initialize the private account schema or bootstrap a new administrator."""
import argparse
from getpass import getpass
from pathlib import Path

from accounts import Registration, Role, connect, create_account


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    commands.add_parser("create-admin").add_argument("email")
    args = parser.parse_args()
    with connect() as db:
        if args.command == "init":
            db.execute((Path(__file__).parent / "database/accounts.sql").read_text())
        else:
            data = Registration(email=args.email, password=getpass("New administrator password: "))
            create_account(db, data, Role.admin)
            print("Administrator created.")


if __name__ == "__main__":
    main()
