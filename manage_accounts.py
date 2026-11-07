"""Initialize application tables or promote an already verified account."""
import argparse
from pathlib import Path
from account_models import connect
from start_app import load_settings

if __name__ == "__main__":
    load_settings()
    parser=argparse.ArgumentParser()
    commands=parser.add_subparsers(dest="command",required=True)
    commands.add_parser("init")
    commands.add_parser("promote-admin").add_argument("email")
    args=parser.parse_args()
    with connect() as db:
        if args.command=="init":
            db.execute((Path(__file__).parent/"database/supabase_auth.sql").read_text())
            db.execute((Path(__file__).parent/"database/projects.sql").read_text())
        else:
            row=db.execute("UPDATE insightflow.auth_profiles SET role='administrator' WHERE email=%s RETURNING id",(args.email.lower(),)).fetchone()
            if not row:raise SystemExit("Register, verify email and sign in first.")
            print("Administrator role assigned.")
