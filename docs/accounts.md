# Supabase Auth account workflow

The running app uses Supabase Auth for passwords, signup verification and email tokens. Application roles are stored in private `insightflow.auth_profiles` rows keyed by the Supabase user UUID. Legacy custom account tables are not used by the application and have not been migrated or deleted.

## Configuration

Set these values in the ignored root `.env` file:

- `DATABASE_URL`: Session pooler URI, URL-encoded password, `sslmode=require`.
- `SUPABASE_URL`: project API URL.
- `SUPABASE_PUBLISHABLE_KEY`: project publishable API key.

In Supabase Authentication enable Confirm email and Secure email change. Set Site URL to `http://127.0.0.1:8018` for the local demo. Use the deployed HTTPS URL for a public deployment.

The built-in email sender is limited to organization team addresses and a low email rate. The current dashboard requires custom SMTP to edit email templates. Its default signup template sends a confirmation link. The app handles that link and also provides code entry for templates containing `{{ .Token }}`. Custom SMTP is required for general public registrations and to customize signup, Magic link/OTP, and Change email templates to show codes. Email-code account changes cannot be demonstrated with link-only templates.

## Start

    python -m pip install -r requirements.txt
    python manage_accounts.py init
    npm --prefix web ci
    npm --prefix web run build
    python start_app.py

Visit http://127.0.0.1:8018. Register, open the confirmation email, and follow its link. Alternatively enter the code if configured in the email template. No application profile or session is created before email verification. To bootstrap an administrator after registration and verification:

    python manage_accounts.py promote-admin admin@example.com

Public signups always receive the data scientist role. Roles are never taken from editable user metadata. Sessions use HttpOnly cookies, expire within one hour, and require a valid Supabase user and non-revoked Supabase session. Sign in again when expired; automatic token refresh is not implemented.

## Sensitive account changes

All changes require the current password. Email changes request confirmation at both addresses through Supabase secure email change. Password changes and deletion request an email OTP. The backend verifies the OTP and account identity before acting. Password values are never stored in application tables. Deletion additionally requires typing DELETE, protects the last administrator, revokes sessions, and deletes the Supabase Auth identity using the server-only PostgreSQL connection. The backend database role therefore requires access to the relevant auth tables; never expose that connection to the browser. Future Storage ownership must be handled before deleting users with uploaded files.

Code-based changes require SMTP templates with `{{ .Token }}`. Pending requests expire after ten minutes and permit five failed attempts. Supabase also enforces its own token lifetime and request limits. Wrong or expired codes cannot modify the account.

## Tests

Set `INSIGHTFLOW_TEST_DATABASE_URL` to a disposable PostgreSQL database and run `python -m pytest`. Tests mock the Supabase HTTP boundary and exercise the API with a real database, including pending signup, wrong codes, role permissions, password changes, deletion, and session revocation. Real email delivery must be checked in the recipient inbox; automated tests do not claim delivery.
