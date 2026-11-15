# InsightFlow Django version — codebase and presentation walkthrough

This guide explains the **styled Django copy**. It is separate from `InsightFlow-Django`, which remains the first Django version, and from the original Vue/FastAPI project. The styled copy keeps the Django API and data model while presenting the workspace with the original InsightFlow dark teal, left-project-navigation, and chat-composer design.

## 1. How to explain the project

> “InsightFlow is a private data-science workspace. A user signs in, creates or opens a project, and can upload a CSV to that project. Django handles authentication, project records, permissions, and uploads. The interface previews the CSV and lets the user type a question. The AI/data-analysis response is not connected yet, so the current chat only demonstrates the interaction design. The project uses Django models and the ORM, server-rendered templates, JSON endpoints for Postman, and an ASGI route prepared for real-time notifications.”

Be clear that **PostgreSQL is configured as the intended database**, but this local demo currently uses SQLite so it can run without external database credentials. The WebSocket and performance-test code are included, but their runtime dependencies must be installed before demonstrating those parts. Email verification and an AI response service are not implemented in this version.

## 2. How Django handles a normal request

Use this sequence when describing a request:

```text
Browser or Postman
  → Django server
  → middleware (security, session, CSRF, authentication)
  → config/urls.py
  → core/urls.py
  → view function or class
  → form validation and/or model ORM
  → SQLite in this demo / PostgreSQL when configured
  → HTML template or JSON response
  → browser or Postman
```

For example, `GET /api/projects/` is matched in `core/urls.py` to `ProjectListCreateView`. Its `get()` method checks the logged-in user and queries projects they own or belong to. Django turns the returned Python dictionary into JSON. For the web page `/`, the `home()` function queries projects, selects the current project, and passes those values to `templates/home.html`; Django renders the HTML and sends it to the browser.

### Django’s MTV terms

- **Model**: Python classes that describe database records and relationships (`core/models.py`).
- **Template**: HTML with Django template tags and variables (`templates/`).
- **View**: Python code that receives the request, applies rules, reads or changes models, then returns HTML or JSON (`core/views.py`).
- **URL configuration**: maps a URL and HTTP method flow to a view (`config/urls.py`, then `core/urls.py`).

Django often calls this the **MTV** pattern (Model–Template–View). It is closely related to MVC; Django’s “view” performs much of the controller job found in MVC.

## 3. Source files, one by one

### Project configuration: `config/`

- **`config/__init__.py`** — marks `config` as a Python package so Django can import it.
- **`config/settings.py`** — central project configuration. It reads this folder’s `.env`; chooses SQLite for the local demo or PostgreSQL from `DATABASE_URL`; registers Django and the `core` app; installs middleware; sets templates, authentication, password rules, timezone, static/media folders, session-cookie names, and ASGI channel-layer settings. The distinct cookie names avoid clashes with the other local InsightFlow servers.
- **`config/urls.py`** — top-level URL table. `/admin/` opens Django’s admin; the empty prefix includes the application routes. In debug mode it serves uploaded media locally.
- **`config/wsgi.py`** — WSGI entry point for conventional synchronous HTTP hosting.
- **`config/asgi.py`** — ASGI entry point. It routes HTTP to Django and WebSocket connections through Channels authentication and `core/routing.py`.

### Application: `core/`

- **`core/__init__.py`** — marks the app as a Python package.
- **`core/apps.py`** — gives Django the application name and default primary-key type.
- **`core/models.py`** — database blueprint. `User` extends Django’s user model and signs in by unique email; `Project` has an owner; `Membership` records a project-specific role; `Invitation` tracks invite status; `Notification` stores a message; `Dataset` stores metadata and a CSV file path. Foreign keys describe relations and define what happens to dependent records when a related record is deleted.
- **`core/forms.py`** — forms that validate browser/API input. `SignUpForm`, `ProjectForm`, `AvatarForm`, and `DatasetForm` are ModelForms, meaning Django maps their fields to model fields. The dataset form limits files to CSVs under 10 MB.
- **`core/views.py`** — application behavior. Function-based views handle health, CSRF, signup/login/logout, account, avatar, dataset, and invitation endpoints. `ProjectListCreateView` and `ProjectDetailView` are class-based views for project GET/POST/detail. Web pages and JSON APIs both end here.
- **`core/urls.py`** — application URL table, connecting web routes and API routes to view functions/classes.
- **`core/serializers.py`** — converts a project model into the small JSON representation returned by the API, including the current user’s project role.
- **`core/context_processors.py`** — adds the signed-in user’s private/shared projects to template context on every page, so the sidebar can render consistently.
- **`core/admin.py`** — registers account, project, membership, invitation, notification, and dataset records in Django’s admin site.
- **`core/consumers.py`** — Channels WebSocket consumer. It rejects anonymous connections, places each authenticated user in a private notification group, then sends notification events to that user’s socket.
- **`core/routing.py`** — maps the WebSocket path `/ws/notifications/` to `NotificationConsumer`.
- **`core/migrations/0001_initial.py`** — database instructions generated from the models. Django applies this file with `migrate` to create the tables.
- **`core/migrations/__init__.py`** — marks the migrations folder as a Python package.

### Browser interface

- **`templates/base.html`** — shared HTML frame. For a signed-in user it draws the left sidebar, project search, account link, sign-out form, top bar, and theme button. It loads the shared CSS and JavaScript. For a signed-out user it displays the authentication layout.
- **`templates/home.html`** — project workspace: selected project name/role, question composer, suggestions, and CSV preview table.
- **`templates/login.html`** — sign-in form.
- **`templates/form.html`** — shared account-creation and new-project form page.
- **`templates/account.html`** — account profile page, including avatar upload and account role.
- **`static/app.css`** — dark teal theme, responsive layout, sidebar, cards, composer, chat bubbles, project list, and settings styles. It has a light-theme override too.
- **`static/app.js`** — client-side interactions: project-name filtering, theme persistence, prompt bubbles, simple CSV parsing/preview, and uploading a selected file to the Django endpoint.

### Operations and supporting files

- **`manage.py`** — command-line entry point for Django commands such as `migrate`, `createsuperuser`, and `runserver`.
- **`requirements.txt`** — Python dependencies: Django, Channels/Daphne for WebSockets, Psycopg for PostgreSQL, Pillow for `ImageField`, and Locust for load testing.
- **`.env`** — local, ignored settings. It currently selects SQLite and a demo-only secret key. Do not commit secrets or use the demo key in deployment.
- **`.env.example`** — template for configuring the project on another machine.
- **`postman/InsightFlow-Django.postman_collection.json`** — ready-to-import request collection for the health, CSRF, signup, login, and project endpoints.
- **`locustfile.py`** — small Locust workload that repeatedly requests the health and CSRF endpoints. This is a performance-test script, not a test result.
- **`README.md`** — short setup, endpoint, and requirement summary.

## 4. Important Python/Django syntax in this code

- `from django... import ...` — imports Django tools used by the file.
- `class Project(models.Model):` — declares a database-backed model. Django’s ORM uses the class fields to build queries and migrations.
- `models.ForeignKey(User, on_delete=models.PROTECT, ...)` — many project records can refer to one user; `PROTECT` stops deleting an owner while their project still exists. `CASCADE` removes dependent records; `SET_NULL` keeps the record but clears the reference.
- `class Meta:` — model options, here enforcing one membership per user/project pair.
- `def home(request):` — a function-based view (FBV). `request` contains the HTTP method, user, cookies, form body, and files.
- `class ProjectListCreateView(View):` — a class-based view (CBV). Django calls `get()` for GET and `post()` for POST.
- `@require_GET` / `@require_POST` — decorators that limit a function to the named HTTP method; another method receives HTTP 405.
- `@login_required` — protects a web/API view unless Django has authenticated the session.
- `@method_decorator(login_required, name="dispatch")` — applies the login check to a class-based view’s shared request entry point.
- `form = ProjectForm(data)` and `form.is_valid()` — bind submitted values to a form and run field/model validation. `form.save(commit=False)` builds a model but lets the view attach the owner before writing it.
- `transaction.atomic()` — groups the project and membership inserts so they succeed or fail together.
- `Q(owner=user) | Q(memberships__user=user)` — ORM query with an OR condition; it restricts visible projects to owned or joined projects.
- `JsonResponse({...}, status=201)` — sends JSON and an HTTP status. `201` means a record was created.
- `render(request, "home.html", context)` — renders a template with values from the context dictionary.
- `path("api/projects/", View.as_view())` — connects a URL to a class-based view. `.as_view()` adapts the class to Django’s request/response interface.
- `{% csrf_token %}` — inserts a security token in forms to prevent forged cross-site POST requests.
- `{{ project.name }}` — prints an escaped value in a Django template; `{% if %}` and `{% for %}` provide template logic.

## 5. How to run the styled project

Open PowerShell in this directory:

```powershell
cd "C:\Users\selmi\OneDrive\Documents\ChatGPT\InsightFlow\InsightFlow-Django-Original-Style"
```

On a machine with Python and internet access, create an environment and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8021
```

Then open `http://127.0.0.1:8021/`. Sign up at `/signup/`; Django creates an account and its first private project. The current desktop session already has this copy running on port `8021`. The first Django version remains at port `8020`.

For PostgreSQL, set `USE_SQLITE=false` and configure `DATABASE_URL` in `.env` for a database dedicated to this Django version; set `PGSSLMODE=require` for a hosted database that requires TLS. Then run `python manage.py migrate`. The running demo uses SQLite, not PostgreSQL.

For WebSockets, install the requirements and use the ASGI server:

```powershell
daphne -p 8021 config.asgi:application
```

The in-memory channel layer is intended for a single development server. A multi-worker deployment needs a shared channel layer such as Redis.

To open Django’s admin UI, create a superuser using `python manage.py createsuperuser` and visit `/admin/`.

## 6. Demonstrate GET and POST with Postman

Import `postman/InsightFlow-Django.postman_collection.json`. Run its requests in sequence. The collection uses its cookie jar to retain Django’s session cookie and requests/refreshes the CSRF token.

1. **GET** `/api/health/` — confirms the server responds.
2. **GET** `/api/csrf/` — prepares a CSRF token.
3. **POST** `/api/auth/signup/` — creates a test account and its first project. The sample email is generated per run.
4. **POST** `/api/auth/login/` — authenticates and receives a session cookie.
5. **GET** `/api/csrf/` — refreshes the token because Django rotates CSRF state on login.
6. **GET** `/api/projects/` — lists only this account’s accessible projects.
7. **POST** `/api/projects/` with `{"name":"CSV profiling demo"}` — creates another project and returns `201`.
8. **GET** `/api/projects/{{projectId}}/` — reads the created project.
9. **POST** `/api/auth/logout/` — ends the session.

Common status codes: `200` means the request succeeded, `201` means a record was created, `400` means submitted values failed validation, `401` means credentials are invalid, `403` means CSRF or permission protection rejected a request, and `405` means the route does not allow that HTTP method.

## 7. How to explain the requested rubric items

- **PostgreSQL** — Django’s database setting can use PostgreSQL through Psycopg. The local classroom demo uses SQLite so it starts without PostgreSQL credentials; explain that this is a local fallback, not a live PostgreSQL test.
- **CBV and FBV** — both styles appear intentionally. Project list/create uses CBVs (`get` and `post` methods); health/auth/upload/invitation handlers are FBVs.
- **ModelForm** — signup, project, avatar, and CSV forms are generated from models, then validated before saving.
- **Auth** — Django hashes passwords and uses a signed session cookie. `AuthenticationMiddleware` exposes the authenticated user as `request.user`; `login_required` checks it.
- **WebSocket/notifications** — ASGI and Channels code routes an authenticated socket to a user-specific group; a project invitation can create a notification and publish it. The current page does not yet open a WebSocket connection or show a notification bell.
- **ImageField** — profile photos are accepted as image uploads and stored under `media/avatars/`. Pillow is required.
- **Performance test** — Locust can generate concurrent requests to health/CSRF endpoints. Explain the purpose and show the report only after running it; do not present a benchmark result that has not been collected.

## 8. Current scope and honest limitations

Implemented in this version: web sign-up/sign-in, private project creation and listing, JSON project GET/POST endpoints, avatar upload endpoint, CSV upload and local preview, invitation JSON endpoints, data models, and the matching dark workspace layout. The Postman-style account/project flow was exercised on the local demo server.

Not implemented yet: email verification, a connected LLM/data-science assistant, cleaning/EDA/model-training behavior, a full invitations/members management screen, and persistent chat history. WebSocket code is prepared but requires the optional Channels dependencies and an ASGI server to run; the running demo server on port `8021` is the HTTP development server. The Locust script is present but no performance run/result is included. These are future work, not completed features.

## 9. Short oral explanation of code creation

> “We preserved the original Django implementation and copied it into a separate folder for the visual version. We kept its Django models and endpoints, then replaced the plain templates with a shared application shell and added CSS and JavaScript for the original InsightFlow style: dark teal colors, project search/navigation, the account area, and a centered chat-like CSV workspace. Django still owns authentication, validation, database changes and upload handling; the browser JavaScript only manages small interface interactions and CSV preview. We use Postman to exercise the JSON endpoints independently of the interface.”
