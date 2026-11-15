# InsightFlow — Django edition

This is a separate Django implementation; it does not replace or edit the Vue/FastAPI project in the parent folder. It demonstrates the requested Django topics: PostgreSQL, function-based and class-based views, ModelForms, Django authentication, WebSocket notifications, `ImageField`, and a Locust performance test.

## Run locally

1. From this folder, create a virtual environment and install `requirements.txt`.
2. `.env` is preconfigured for a local SQLite demo. To use PostgreSQL set `USE_SQLITE=false` and set `DATABASE_URL` to a database dedicated to this Django edition.
3. Run `python manage.py makemigrations core`, then `python manage.py migrate`.
4. Run `python manage.py runserver 127.0.0.1:8021` for the browser/API. For WebSocket support, run `daphne -p 8021 config.asgi:application` instead.
5. Open `http://127.0.0.1:8021/` or import `postman/InsightFlow-Django.postman_collection.json` into Postman. Requests use the cookie jar and CSRF token. Run GET CSRF token, POST sign up, POST sign in, GET refreshed CSRF token, GET projects, POST create project.

## API routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health/` | Health check |
| GET | `/api/csrf/` | Get CSRF token for Postman |
| POST | `/api/auth/signup/` | Create account and private starter project |
| POST | `/api/auth/login/` | Sign in; session cookie is returned |
| POST | `/api/auth/logout/` | End session |
| GET | `/api/me/` | Current account |
| GET, POST | `/api/projects/` | List or create accessible projects (CBV) |
| GET | `/api/projects/<uuid>/` | Read project (CBV) |
| GET, POST | `/api/projects/<uuid>/invitations/` and `/new/` | List or create an invitation (FBV) |
| GET | `/api/invitations/` | Current user's pending invitations |
| POST | `/api/invitations/<uuid>/respond/` | Accept or decline, JSON action |
| POST | `/api/profile/avatar/` | Upload account image (`ImageField`) |
| POST | `/api/projects/<uuid>/datasets/` | Upload CSV file |

## Requirement mapping

- PostgreSQL: `config/settings.py` reads `DATABASE_URL`; SQLite is only a local demo fallback.
- CBV: `ProjectListCreateView` and `ProjectDetailView` implement project GET/POST behavior.
- FBV: health, auth, invitation, image, and dataset endpoints are function-based.
- ModelForm: account signup, project creation, avatar and dataset forms are in `core/forms.py`.
- Auth: Django's password hashing, session login, logout, and `login_required` protect private endpoints.
- WebSocket notifications: `/ws/notifications/` requires an authenticated session; in-memory channels work for one local server. Start the ASGI version using `daphne -p 8020 config.asgi:application` after installing dependencies. For multiple workers configure Redis and install `channels-redis`.
- ImageField: `User.avatar` stores profile images under `media/avatars/`.
- Performance: `locustfile.py` has a small health/CSRF workload. A local 20-user, 30-second run and its limitations are recorded in [the performance report](performance/PERFORMANCE_TEST_REPORT.md); the CSV output is saved in `performance/`.

This is the Django foundation for the account and project collaboration parts of InsightFlow. The CSV route stores uploads; data cleaning, EDA, model training and the prompt assistant still need their own implementation.
