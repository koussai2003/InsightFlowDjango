"""InsightFlow account API. Use a server-only Supabase PostgreSQL connection."""
import hashlib
import os
import secrets
from enum import StrEnum
from pathlib import Path

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, EmailStr, Field

app = FastAPI(title="InsightFlow")
hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
COOKIE = "insightflow_session"


class Role(StrEnum):
    scientist = "data_scientist"
    reviewer = "reviewer"
    admin = "administrator"


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Registration(Credentials):
    password: str = Field(min_length=12, max_length=128)


class RoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def database():
    with connect() as connection:
        yield connection


@app.middleware("http")
async def protect_writes(request: Request, call_next):
    # Browser cross-origin forms cannot add this header. No cross-origin CORS is enabled.
    if request.method in {"POST", "PATCH", "DELETE"} and request.headers.get("X-InsightFlow") != "1":
        return JSONResponse({"detail": "Missing request header"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, error: RequestValidationError):
    # Return field names and validation messages without echoing submitted passwords.
    messages = [f"{item['loc'][-1]}: {item['msg']}" for item in error.errors()]
    return JSONResponse({"detail": ". ".join(messages)}, status_code=422)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def signed_in(insightflow_session: str | None = Cookie(default=None), db=Depends(database)):
    user = db.execute(
        """SELECT a.id, a.email, a.role FROM insightflow.sessions s
           JOIN insightflow.accounts a ON a.id = s.account_id
           WHERE s.token_hash = %s AND s.expires_at > now()""",
        (digest(insightflow_session or ""),),
    ).fetchone()
    if user is None:
        raise HTTPException(401, "Sign in to continue")
    return user


def require_role(role):
    def check(user=Depends(signed_in)):
        if user["role"] != role:
            raise HTTPException(403, "This account does not have permission")
        return user
    return check


def create_account(db, data, role=Role.scientist):
    row = db.execute(
        """INSERT INTO insightflow.accounts(email, password_hash, role) VALUES (%s,%s,%s)
           ON CONFLICT (email) DO NOTHING RETURNING id, email, role""",
        (str(data.email).lower(), hasher.hash(data.password), role.value),
    ).fetchone()
    if row is None:
        raise HTTPException(409, "This email is already registered")
    return row


@app.post("/api/accounts", status_code=201)
def register(data: Registration, db=Depends(database)):
    return create_account(db, data)


@app.post("/api/session")
def login(data: Credentials, response: Response, db=Depends(database)):
    row = db.execute("SELECT * FROM insightflow.accounts WHERE email=%s",
                     (str(data.email).lower(),)).fetchone()
    try:
        hasher.verify(row["password_hash"] if row else dummy_hash, data.password)
    except VerifyMismatchError:
        raise HTTPException(401, "Incorrect email or password") from None
    if not row:
        raise HTTPException(401, "Incorrect email or password")
    token = secrets.token_urlsafe(32)
    db.execute("""INSERT INTO insightflow.sessions(token_hash, account_id, expires_at)
                  VALUES (%s,%s,now() + interval '8 hours')""", (digest(token), row["id"]))
    response.set_cookie(COOKIE, token, max_age=28800, httponly=True, samesite="strict",
                        secure=os.getenv("INSIGHTFLOW_LOCAL_HTTP") != "1", path="/")
    return {key: row[key] for key in ("id", "email", "role")}


@app.delete("/api/session", status_code=204)
def logout(response: Response, insightflow_session: str | None = Cookie(default=None), db=Depends(database)):
    db.execute("DELETE FROM insightflow.sessions WHERE token_hash=%s", (digest(insightflow_session or ""),))
    response.delete_cookie(COOKIE, path="/")


@app.get("/api/me")
def me(user=Depends(signed_in)):
    return user


@app.get("/api/admin/accounts")
def accounts(admin=Depends(require_role(Role.admin)), db=Depends(database)):
    return db.execute("SELECT id,email,role FROM insightflow.accounts ORDER BY email").fetchall()


@app.patch("/api/admin/accounts/{account_id}")
def change_role(account_id: int, data: RoleChange, admin=Depends(require_role(Role.admin)), db=Depends(database)):
    # Serialize administrative changes, then recheck privileges under that lock.
    db.execute("LOCK TABLE insightflow.accounts IN SHARE ROW EXCLUSIVE MODE")
    current = db.execute("SELECT role FROM insightflow.accounts WHERE id=%s", (admin["id"],)).fetchone()
    if not current or current["role"] != Role.admin:
        raise HTTPException(403, "Administrator access required")
    if account_id == admin["id"] and data.role != Role.admin:
        raise HTTPException(409, "Ask another administrator to change your own role")
    row = db.execute("UPDATE insightflow.accounts SET role=%s WHERE id=%s RETURNING id,email,role",
                     (data.role.value, account_id)).fetchone()
    if not row:
        raise HTTPException(404, "Account not found")
    return row


# These role-restricted entry points can be extended by the dataset and review stories.
@app.get("/api/workspaces/preparation")
def preparation(user=Depends(require_role(Role.scientist))):
    return {"title": "Dataset preparation", "email": user["email"]}


@app.get("/api/workspaces/review")
def review(user=Depends(require_role(Role.reviewer))):
    return {"title": "Dataset review", "email": user["email"]}


build = Path(__file__).parent / "web" / "dist"
if build.is_dir():
    app.mount("/", StaticFiles(directory=build, html=True), name="web")
