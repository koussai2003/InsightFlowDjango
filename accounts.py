"""InsightFlow account API. Use a server-only Supabase PostgreSQL connection."""
import hashlib
import hmac
import smtplib
import ssl
from email.message import EmailMessage
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
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

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


class Signup(Registration):
    confirm_password: str

    @model_validator(mode="after")
    def matching(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords must match")
        return self


class SecurityChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=128)
    new_email: EmailStr | None = None
    new_password: str | None = Field(default=None, min_length=12, max_length=128)
    confirm_password: str | None = None

    @model_validator(mode="after")
    def valid(self):
        if (self.new_email is None) == (self.new_password is None):
            raise ValueError("Choose one change at a time")
        if self.new_password is not None and self.new_password != self.confirm_password:
            raise ValueError("Passwords must match")
        return self


class VerifyChange(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    new_email_code: str | None = Field(default=None, pattern=r"^\d{6}$")


def code_hash(code):
    key = os.environ.get("EMAIL_CODE_SECRET")
    if not key or len(key) < 32:
        raise HTTPException(503, "Email verification is not configured yet")
    return hmac.new(key.encode(), code.encode(), hashlib.sha256).hexdigest()


def send_code(email, code):
    if not all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")):
        raise HTTPException(503, "Email delivery is not configured yet")
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email
    message["Subject"] = "InsightFlow account verification"
    message.set_content(f"Your account change code is {code}. It expires in 10 minutes. If you did not request this change, ignore this email.")
    try:
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, "Could not send verification email. Please try again later") from None


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
def register(data: Signup, db=Depends(database)):
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


@app.post("/api/me/security/request")
def request_change(data: SecurityChange, user=Depends(signed_in), db=Depends(database)):
    account = db.execute("SELECT * FROM insightflow.accounts WHERE id=%s FOR UPDATE", (user["id"],)).fetchone()
    try:
        hasher.verify(account["password_hash"], data.current_password)
    except VerifyMismatchError:
        raise HTTPException(400, "Current password is incorrect") from None
    previous = db.execute("SELECT 1 FROM insightflow.account_changes WHERE account_id=%s AND created_at > now() - interval '60 seconds'", (user["id"],)).fetchone()
    if previous:
        raise HTTPException(429, "Wait one minute before requesting another code")
    email = str(data.new_email).lower() if data.new_email else None
    if email and (email == account["email"] or db.execute("SELECT 1 FROM insightflow.accounts WHERE email=%s", (email,)).fetchone()):
        raise HTTPException(409, "Choose a different, unused email address")
    code = f"{secrets.randbelow(1000000):06d}"
    other = f"{secrets.randbelow(1000000):06d}" if email else None
    hashed, other_hash = code_hash(code), code_hash(other) if other else None
    send_code(account["email"], code)
    if email:
        send_code(email, other)
    db.execute("DELETE FROM insightflow.account_changes WHERE account_id=%s", (user["id"],))
    db.execute("""INSERT INTO insightflow.account_changes(account_id,code_hash,new_code_hash,new_email,new_password_hash)
                  VALUES (%s,%s,%s,%s,%s)""", (user["id"], hashed, other_hash, email, hasher.hash(data.new_password) if data.new_password else None))
    return {"message": "Verification codes sent"}


@app.post("/api/me/security/verify")
def verify_change(data: VerifyChange, response: Response, user=Depends(signed_in), db=Depends(database)):
    db.execute("SELECT id FROM insightflow.accounts WHERE id=%s FOR UPDATE", (user["id"],))
    change = db.execute("SELECT * FROM insightflow.account_changes WHERE account_id=%s AND expires_at > now() FOR UPDATE", (user["id"],)).fetchone()
    if not change or change["attempts"] >= 5:
        raise HTTPException(400, "Code expired or too many attempts. Request a new code")
    valid = hmac.compare_digest(change["code_hash"], code_hash(data.code))
    if change["new_email"]:
        valid = valid and bool(data.new_email_code) and hmac.compare_digest(change["new_code_hash"], code_hash(data.new_email_code))
    if not valid:
        db.execute("UPDATE insightflow.account_changes SET attempts=attempts+1 WHERE account_id=%s", (user["id"],))
        db.commit()  # Persist failed attempts despite the HTTP error.
        raise HTTPException(400, "Incorrect verification code")
    try:
        db.execute("UPDATE insightflow.accounts SET email=COALESCE(%s,email), password_hash=COALESCE(%s,password_hash) WHERE id=%s", (change["new_email"], change["new_password_hash"], user["id"]))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "That email is already registered") from None
    db.execute("DELETE FROM insightflow.account_changes WHERE account_id=%s", (user["id"],))
    db.execute("DELETE FROM insightflow.sessions WHERE account_id=%s", (user["id"],))
    response.delete_cookie(COOKIE, path="/")
    return {"message": "Account updated. Sign in again."}


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
