"""Supabase Auth-backed accounts. Passwords and email tokens belong to Supabase."""
import hashlib
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from account_models import Signup, Credentials, SecurityChange, RoleChange, Role, connect, database

app = FastAPI(title="InsightFlow")
COOKIE = "insightflow_auth"


def auth(method, path, body=None, token=None):
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        raise HTTPException(503, "Supabase authentication is not configured")
    headers = {"apikey": key}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        response = httpx.request(method, url + "/auth/v1/" + path, json=body, headers=headers, timeout=15)
    except httpx.HTTPError:
        raise HTTPException(503, "Authentication service is unavailable. Try again shortly") from None
    data = response.json() if response.content else {}
    if not response.is_success:
        code = data.get("error_code", data.get("code", ""))
        messages = {
            "email_address_not_authorized": "The test email sender only supports Supabase team addresses. Configure SMTP to register other users.",
            "over_email_send_rate_limit": "Email sending limit reached. Please wait before requesting another email.",
            "email_not_confirmed": "Confirm your email before signing in. Check your inbox or resend the verification email.",
            "invalid_credentials": "Incorrect email or password.",
            "otp_expired": "The verification code is incorrect or expired.",
            "user_already_exists": "This email is already registered.",
            "email_exists": "This email is already registered.",
        }
        message = messages.get(code, "Authentication request failed. Check your details and try again.")
        raise HTTPException(429 if response.status_code == 429 else 400, message)
    return data


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@app.middleware("http")
async def protect_writes(request: Request, call_next):
    if request.method in {"POST", "PATCH", "DELETE"} and request.headers.get("X-InsightFlow") != "1":
        return JSONResponse({"detail": "Missing request header"}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_input(request, error):
    return JSONResponse({"detail": ". ".join(f"{e['loc'][-1]}: {e['msg']}" for e in error.errors())}, status_code=422)


@app.exception_handler(httpx.HTTPError)
async def unavailable(request, error):
    return JSONResponse({"detail": "Authentication service unavailable"}, status_code=503)


def profile(db, identity):
    if not identity.get("email_confirmed_at"):
        raise HTTPException(403, "Verify your email first")
    uid = str(UUID(identity["id"]))
    row = db.execute("""INSERT INTO insightflow.auth_profiles(id,email) VALUES (%s,%s)
        ON CONFLICT(id) DO UPDATE SET email=excluded.email RETURNING id,email,role""", (uid, identity["email"].lower())).fetchone()
    return {**row, "id": str(row["id"])}


def validate_session(db, token, uid):
    # /user or /verify has already authenticated the JWT. Check revocation too.
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        sid = str(UUID(claims["session_id"]))
    except (ValueError, KeyError, IndexError):
        raise HTTPException(401, "Sign in again to continue") from None
    if not db.execute("SELECT 1 FROM auth.sessions WHERE id=%s AND user_id=%s", (sid, uid)).fetchone():
        raise HTTPException(401, "Your session has ended. Sign in again")


def establish(db, response, session):
    token = session.get("access_token")
    if not token or not session.get("user"):
        raise HTTPException(400, "Email verification is not complete")
    validate_session(db, token, session["user"]["id"])
    person = profile(db, session["user"])
    seconds = min(int(session.get("expires_in", 3600)), 3600)
    db.execute("""INSERT INTO insightflow.auth_sessions(token_hash,profile_id,expires_at)
        VALUES (%s,%s,now() + %s * interval '1 second') ON CONFLICT(token_hash) DO NOTHING""", (digest(token), person["id"], seconds))
    response.set_cookie(COOKIE, token, max_age=seconds, httponly=True, secure=os.getenv("INSIGHTFLOW_LOCAL_HTTP") != "1", samesite="strict", path="/")
    return person


def signed_in(insightflow_auth: str | None = Cookie(default=None), db=Depends(database)):
    if not insightflow_auth:
        raise HTTPException(401, "Sign in to continue")
    row = db.execute("""SELECT p.id,p.email,p.role FROM insightflow.auth_sessions s
        JOIN insightflow.auth_profiles p ON p.id=s.profile_id
        WHERE token_hash=%s AND expires_at>now()""", (digest(insightflow_auth),)).fetchone()
    if not row:
        raise HTTPException(401, "Sign in to continue")
    try:
        identity = auth("GET", "user", token=insightflow_auth)
    except HTTPException as exc:
        if exc.status_code == 503: raise
        raise HTTPException(401, "Sign in again to continue") from None
    if identity.get("id") != str(row["id"]) or not identity.get("email_confirmed_at"):
        raise HTTPException(401, "Sign in again to continue")
    validate_session(db, insightflow_auth, identity["id"])
    return {**row, "id": str(row["id"]), "email": identity["email"], "token": insightflow_auth}


def public(person):
    return {k: person[k] for k in ("id", "email", "role")}


class EmailRequest(BaseModel):
    email: EmailStr


class SignupVerification(EmailRequest):
    code: str = Field(pattern=r"^\d{6,10}$")


class LinkSession(BaseModel):
    access_token: str = Field(min_length=20, max_length=8192)


@app.post("/api/accounts", status_code=202)
def register(data: Signup):
    if auth("GET", "settings").get("mailer_autoconfirm"):
        raise HTTPException(503, "Enable Confirm email in Supabase before accepting signups")
    auth("POST", "signup", {"email": str(data.email).lower(), "password": data.password})
    return {"message": "Check your inbox to verify your email."}


@app.post("/api/accounts/resend")
def resend(data: EmailRequest):
    auth("POST", "resend", {"type": "signup", "email": str(data.email).lower()})
    return {"message": "Verification email requested. Check your inbox."}


@app.post("/api/accounts/verify")
def verify_signup(data: SignupVerification, response: Response, db=Depends(database)):
    session = auth("POST", "verify", {"type": "email", "email": str(data.email).lower(), "token": data.code})
    return establish(db, response, session)


@app.post("/api/session/link")
def link_session(data: LinkSession, response: Response, db=Depends(database)):
    identity = auth("GET", "user", token=data.access_token)
    return establish(db, response, {"access_token": data.access_token, "user": identity, "expires_in": 3600})


@app.post("/api/session")
def login(data: Credentials, response: Response, db=Depends(database)):
    return establish(db, response, auth("POST", "token?grant_type=password", {"email": str(data.email).lower(), "password": data.password}))


@app.delete("/api/session", status_code=204)
def logout(response: Response, user=Depends(signed_in), db=Depends(database)):
    auth("POST", "logout?scope=local", token=user["token"])
    db.execute("DELETE FROM insightflow.auth_sessions WHERE token_hash=%s", (digest(user["token"]),))
    response.delete_cookie(COOKIE, path="/")


@app.get("/api/me")
def me(user=Depends(signed_in)):
    return public(user)


@app.get("/api/admin/accounts")
def accounts(user=Depends(signed_in), db=Depends(database)):
    if user["role"] != Role.admin: raise HTTPException(403, "Administrator access required")
    return db.execute("SELECT id,email,role FROM insightflow.auth_profiles ORDER BY email").fetchall()


@app.patch("/api/admin/accounts/{account_id}")
def change_role(account_id: UUID, data: RoleChange, user=Depends(signed_in), db=Depends(database)):
    if user["role"] != Role.admin: raise HTTPException(403,"Administrator access required")
    db.execute("LOCK TABLE insightflow.auth_profiles IN SHARE ROW EXCLUSIVE MODE")
    row=db.execute("SELECT role FROM insightflow.auth_profiles WHERE id=%s",(user["id"],)).fetchone()
    if not row or row["role"] != Role.admin: raise HTTPException(403,"Administrator access required")
    if str(account_id)==user["id"] and data.role != Role.admin: raise HTTPException(409,"Ask another administrator to change your role")
    row=db.execute("UPDATE insightflow.auth_profiles SET role=%s WHERE id=%s RETURNING id,email,role",(data.role.value,account_id)).fetchone()
    if not row: raise HTTPException(404,"Account not found")
    return row


@app.get("/api/workspaces/{workspace}")
def workspace(workspace: str, user=Depends(signed_in)):
    roles={"preparation":Role.scientist,"review":Role.reviewer}
    if workspace not in roles: raise HTTPException(404,"Workspace not found")
    if user["role"] != roles[workspace]: raise HTTPException(403,"This account does not have permission")
    return {"title":"Dataset " + workspace}


class VerifySecurity(BaseModel):
    code: str = Field(pattern=r"^\d{6,10}$")
    new_email_code: str | None = Field(default=None, pattern=r"^\d{6,10}$")
    new_password: str | None = Field(default=None,min_length=12,max_length=128)
    confirm_password: str | None = None
    current_password: str = Field(min_length=1,max_length=128)
    delete_confirmation: str | None = None


def check_password(user,password):
    fresh=auth("POST","token?grant_type=password",{"email":user["email"],"password":password})
    if fresh.get("user",{}).get("id") != user["id"]: raise HTTPException(403,"Account identity mismatch")
    auth("POST","logout?scope=local",token=fresh["access_token"])


def protect_last_admin(db,user):
    current=db.execute("SELECT role FROM insightflow.auth_profiles WHERE id=%s",(user["id"],)).fetchone()
    if current and current["role"]==Role.admin and db.execute("SELECT count(*) AS n FROM insightflow.auth_profiles WHERE role='administrator'").fetchone()["n"]<=1:
        raise HTTPException(409,"Assign another administrator before deleting your account")


@app.post("/api/me/security/request")
def security_request(data: SecurityChange,user=Depends(signed_in),db=Depends(database)):
    check_password(user,data.current_password)
    db.execute("SELECT id FROM insightflow.auth_profiles WHERE id=%s FOR UPDATE",(user["id"],))
    if db.execute("SELECT 1 FROM insightflow.auth_requests WHERE profile_id=%s AND created_at>now()-interval '60 seconds'",(user["id"],)).fetchone():
        raise HTTPException(429,"Wait one minute before requesting another email")
    action="delete" if data.delete_account else "email" if data.new_email else "password"
    if action=="delete": protect_last_admin(db,user)
    email=str(data.new_email).lower() if data.new_email else None
    if email==user["email"].lower(): raise HTTPException(400,"Enter a different email address")
    if action=="email":
        auth("PUT","user",{"email":email},token=user["token"])
    else:
        auth("POST","otp",{"email":user["email"],"create_user":False})
    db.execute("""INSERT INTO insightflow.auth_requests(profile_id,action,new_email) VALUES (%s,%s,%s)
        ON CONFLICT(profile_id) DO UPDATE SET action=excluded.action,new_email=excluded.new_email,
        created_at=now(),attempts=0,old_verified=false""",(user["id"],action,email))
    return {"message":"Check your email for verification."}


@app.post("/api/me/security/verify")
def security_verify(data: VerifySecurity,response: Response,user=Depends(signed_in),db=Depends(database)):
    db.execute("LOCK TABLE insightflow.auth_profiles IN SHARE ROW EXCLUSIVE MODE")
    change=db.execute("SELECT * FROM insightflow.auth_requests WHERE profile_id=%s AND created_at>now()-interval '10 minutes' FOR UPDATE",(user["id"],)).fetchone()
    if not change or change["attempts"]>=5: raise HTTPException(400,"Request a new verification email")
    if change["action"]=="delete" and data.delete_confirmation!="DELETE": raise HTTPException(400,"Type DELETE to confirm")
    if change["action"]=="password" and (not data.new_password or data.new_password!=data.confirm_password): raise HTTPException(400,"New passwords must match")
    check_password(user,data.current_password)
    db.execute("UPDATE insightflow.auth_requests SET attempts=attempts+1 WHERE profile_id=%s",(user["id"],))
    # Commit before remote verification so failures consume an attempt.
    db.commit()
    if change["action"]=="email":
        if not data.new_email_code: raise HTTPException(400,"Enter both verification codes")
        if not change["old_verified"]:
            auth("POST","verify",{"type":"email_change","email":user["email"],"token":data.code})
            db.execute("UPDATE insightflow.auth_requests SET old_verified=true WHERE profile_id=%s",(user["id"],));db.commit()
        verified=auth("POST","verify",{"type":"email_change","email":change["new_email"],"token":data.new_email_code})
    else:
        verified=auth("POST","verify",{"type":"email","email":user["email"],"token":data.code})
    if verified.get("user",{}).get("id")!=user["id"]: raise HTTPException(403,"Verification does not match this account")
    db.execute("LOCK TABLE insightflow.auth_profiles IN SHARE ROW EXCLUSIVE MODE")
    # Recheck the request after network calls to reject concurrent replacement.
    live=db.execute("SELECT * FROM insightflow.auth_requests WHERE profile_id=%s FOR UPDATE",(user["id"],)).fetchone()
    if not live or live["created_at"]!=change["created_at"]: raise HTTPException(409,"Account request changed; start again")
    if change["action"]=="password":
        auth("PUT","user",{"password":data.new_password,"current_password":data.current_password},token=verified["access_token"])
    if change["action"]=="email":
        if verified["user"]["email"].lower()!=change["new_email"]: raise HTTPException(400,"Verify both email addresses first")
        db.execute("UPDATE insightflow.auth_profiles SET email=%s WHERE id=%s",(change["new_email"],user["id"]))
    if change["action"]=="delete": protect_last_admin(db,user)
    auth("POST","logout?scope=global",token=verified["access_token"])
    db.execute("DELETE FROM insightflow.auth_sessions WHERE profile_id=%s",(user["id"],))
    db.execute("DELETE FROM insightflow.auth_requests WHERE profile_id=%s",(user["id"],))
    if change["action"]=="delete":
        # The server's private PostgreSQL connection owns this operation; no admin key is exposed.
        db.execute("DELETE FROM auth.users WHERE id=%s",(user["id"],))
        db.execute("DELETE FROM insightflow.auth_profiles WHERE id=%s",(user["id"],))
    response.delete_cookie(COOKIE,path="/")
    return {"message":"Account deleted." if change["action"]=="delete" else "Account updated. Please sign in again."}


import psycopg
@app.exception_handler(psycopg.OperationalError)
async def database_error(request,error):
    return JSONResponse({"detail":"Database temporarily unavailable. Try again shortly."},status_code=503)

build=Path(__file__).parent/"web"/"dist"
if build.is_dir(): app.mount("/",StaticFiles(directory=build,html=True),name="web")
