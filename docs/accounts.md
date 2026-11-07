# Running the account workflow

IF-8 and IF-11 use FastAPI, Vue and Supabase PostgreSQL. FastAPI owns password verification and sessions. The browser calls the API on its own origin. Public signup creates a data scientist account. A reviewer can enter the review workspace, a data scientist can enter dataset preparation, and an administrator can list users and change roles. Dataset processing and reviews belong to later stories.

## Configure the database

In the team's Supabase dashboard, choose **Connect**, then copy the direct PostgreSQL connection URI (or session pooler URI for an IPv4 host). Set the server environment variable `DATABASE_URL` to that URI with the password URL-encoded and SSL enabled. For example:

    postgresql://USERNAME:PASSWORD@HOST:5432/postgres?sslmode=require

Apply the setup with an account that owns the application's private schema and tables. Prefer a dedicated application schema owner with only the necessary database privileges. Keep the `insightflow` schema private in the Supabase Data API settings. Credentials and session hashes belong only on the API server.

## Start the app

Use Python 3.11+ and Node 22+. In an activated Python virtual environment at the repository root:

    python -m pip install -r requirements.txt
    python manage_accounts.py init
    python manage_accounts.py create-admin admin@example.com
    npm --prefix web ci
    npm --prefix web run build
    python -m uvicorn accounts:app

The admin command prompts for a password and only creates a new account. Use a separate email to try public registration. For local HTTP on loopback, set `INSIGHTFLOW_LOCAL_HTTP=1` before starting the server. Visit http://127.0.0.1:8000. Use HTTPS with the default secure cookie setting when deploying. For frontend development, start the API and run `npm --prefix web run dev` in a second terminal.

## Verify the stories

Run the integration tests against a dedicated, disposable PostgreSQL database. They initialize the schema and create test users. Set `INSIGHTFLOW_TEST_DATABASE_URL` to that database's URI, then run:

    python -m pip install -r requirements-dev.txt
    python -m pytest

For a manual review, create an account, try its email again, and sign in. In a separate browser session, sign in as administrator and change the first account to Reviewer. Refresh the first browser. It should offer the review workspace. A direct request to an unauthorized API endpoint returns 403. API writes require the X-InsightFlow header with value 1. Sessions expire after eight hours.

## Verified account changes

Signup requires `confirm_password` matching the password. Signed-in users can change their email or password under Account settings. Both changes require the current password. Email changes require independent codes sent to the old and new address; password changes require a code sent to the current address. Codes expire in 10 minutes, allow five failed attempts, and can be requested once per minute. Successful changes invalidate every existing session. Password recovery for users who forgot their current password is not included.

Apply the updated schema with `python manage_accounts.py init`. Configure these server-only environment variables before sending real email:

- `SMTP_HOST`, `SMTP_PORT` (defaults to 587, STARTTLS required)
- `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (a sender verified with your email provider)
- `EMAIL_CODE_SECRET` (a stable random secret of at least 32 characters, generated securely)

Never commit these values. Missing mail configuration returns an explicit unavailable message and leaves account details unchanged. Tests replace email delivery with an in-memory mailbox; actual delivery requires your provider credentials. This implementation keeps the existing custom account system in Supabase PostgreSQL; it does not use Supabase Auth. Signup email verification remains a separate feature.

## Delete account

Select Delete account in Account settings, enter the current password, request a code, then enter the emailed code and type DELETE. Only the account owner can complete this action. Deletion permanently removes the account, all sessions and pending verification codes. The last administrator must assign another administrator first. Email/password change codes cannot authorize deletion. Apply `python manage_accounts.py init` for the additional challenge column. Real email configuration is required. Future dataset-related tables will need an explicit ownership/retention policy before they are integrated with deletion.

## Start the connected local preview

Save your Supabase Session pooler URI as `DATABASE_URL=...` in the ignored root `.env` file. Percent-encode special characters in the password and include `?sslmode=require`. Run `python start_app.py`, then visit http://127.0.0.1:8018. This launcher binds only to your computer and uses local HTTP cookies. The `.env` file must never be committed.
