# InsightFlow: Accounts, Authentication & Access Control

InsightFlow uses **Django 5.2 LTS** and **PostgreSQL** for user authentication, session management, and role-based access control.

---

## Architecture & Data Models

### User Model (`accounts.User`)
- Inherits from `AbstractUser` with `username = None`.
- Unique identifier: lower-cased `email`.
- Roles (`role` field):
  - `data_scientist` (default for new registrations)
  - `reviewer`
  - `administrator`
- New accounts are created inactive (`is_active = False`) and activated only after email verification.

### Security Requests (`accounts.SecurityRequest`)
- Tracks sensitive account changes: `email`, `password`, or `delete`.
- At most one active security request per user.
- 6-digit codes are stored as SHA-256 hashes (never in plaintext).
- Codes expire in 10 minutes.
- Maximum 5 failed attempts before lockout.
- 60-second rate limit between requests.
- Email changes require two codes: one sent to the current email and one to the new email.
- Account deletion requires typing `DELETE`. The last remaining administrator is protected from deleting their own account.
- Any successful sensitive change invalidates all active sessions for the user across all devices.

---

## Setup & Running Locally

### 1. Requirements & Environment
Ensure Python 3.12+ is installed, then install dependencies:

```bash
pip install -r requirements.txt
# or for tests:
pip install -r requirements-dev.txt
```

Create or configure `.env` in the repository root:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
# Optional: SMTP email settings (defaults to console email backend if omitted)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=InsightFlow <noreply@insightflow.app>
```

### 2. Database Migrations
Run Django migrations to create tables:
```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### 3. Promoting an Administrator
To promote an existing, verified account to administrator:
```bash
python manage.py promote_admin user@example.com
```

### 4. Running the Development Server
```bash
python manage.py runserver
```
Visit http://127.0.0.1:8000/ to access the application.

---

## Role-Based Access Control

- **Data Scientist**:
  - Home directs to `/workspaces/preparation`
  - Forbidden from `/workspaces/review` (403) and `/manage/accounts` (403)
- **Reviewer**:
  - Home directs to `/workspaces/review`
  - Forbidden from `/workspaces/preparation` (403) and `/manage/accounts` (403)
- **Administrator**:
  - Home directs to `/manage/accounts`
  - Can change roles of other users
  - Cannot demote themselves
  - Forbidden from `/workspaces/*` (403)

---

## Testing

Run tests using pytest or Django's test runner:
```bash
pytest
# or
python manage.py test accounts
```
All tests use the in-memory email backend (`locmem`).
