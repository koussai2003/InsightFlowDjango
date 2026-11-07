import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import supabase_accounts as api

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("DATABASE_URL",os.environ["INSIGHTFLOW_TEST_DATABASE_URL"])
    with api.connect() as db:
        db.execute("CREATE SCHEMA IF NOT EXISTS auth; CREATE TABLE IF NOT EXISTS auth.users(id uuid PRIMARY KEY)")
        db.execute((Path(__file__).parents[1]/"database/supabase_auth.sql").read_text())
        db.execute((Path(__file__).parents[1]/"database/projects.sql").read_text())
    uid=str(uuid4()); email=uid+"@example.com"
    state={"confirmed":False,"password":"original password 123", "deleted":False,"calls":[]}
    def identity():return {"id":uid,"email":email,"email_confirmed_at":"2026-01-01" if state["confirmed"] else None}
    def session():return {"access_token":"test-token-"+uid,"expires_in":3600,"user":identity()}
    def auth(method,path,body=None,token=None):
        state["calls"].append((method,path))
        if path=="signup":return {"user":identity()}
        if path=="verify":
            if body["token"]!="123456":raise HTTPException(400,"Incorrect or expired verification code")
            state["confirmed"]=True
            return session()
        if path=="token?grant_type=password":
            if not state["confirmed"] or body["password"]!=state["password"]:raise HTTPException(400,"Cannot sign in")
            return session()
        if path=="user" and method=="GET":return identity()
        if path=="user" and method=="PUT":
            if "password" in body:state["password"]=body["password"]
            return identity()
        return {}
    monkeypatch.setattr(api,"auth",auth)
    monkeypatch.setattr(api,"validate_session",lambda db,token,uid:None)
    with api.connect() as db:db.execute("INSERT INTO auth.users(id) VALUES(%s)",(uid,))
    with TestClient(api.app,base_url="https://testserver",headers={"X-InsightFlow":"1"}) as client:
        yield client,state,uid,email


def register(client,email):
    return client.post("/api/accounts",json={"email":email,"password":"original password 123","confirm_password":"original password 123"})


def verify(client,email):
    return client.post("/api/accounts/verify",json={"email":email,"code":"123456"})


def test_signup_requires_verification(setup):
    client,state,uid,email=setup
    assert register(client,email).status_code==202
    assert client.get("/api/me").status_code==401
    with api.connect() as db:assert not db.execute("SELECT 1 FROM insightflow.auth_profiles WHERE id=%s",(uid,)).fetchone()
    assert client.post("/api/session",json={"email":email,"password":state["password"]}).status_code==400
    assert client.post("/api/accounts/verify",json={"email":email,"code":"000000"}).status_code==400
    assert verify(client,email).status_code==200
    assert client.get("/api/me").json()["role"]=="data_scientist"
    assert client.get("/api/admin/accounts").status_code==403
    assert client.get("/api/workspaces/review").status_code==410
    assert client.delete("/api/session").status_code==204
    assert client.get("/api/me").status_code==401


def test_confirmation_and_link_validation(setup):
    client,state,uid,email=setup
    assert client.post("/api/accounts",json={"email":email,"password":"original password 123","confirm_password":"wrong"}).status_code==422
    assert client.post("/api/session/link",json={"access_token":"a"*30}).status_code==403
    assert client.get("/api/me").status_code==401


def test_password_and_delete_require_code(setup):
    client,state,uid,email=setup
    verify(client,email)
    password=state["password"]
    data={"current_password":password,"new_password":"new valid password 123","confirm_password":"new valid password 123"}
    assert client.post("/api/me/security/request",json=data).status_code==200
    assert client.post("/api/me/security/verify",json={**data,"code":"000000"}).status_code==400
    assert state["password"]==password
    assert client.post("/api/me/security/verify",json={**data,"code":"123456"}).status_code==200
    assert client.get("/api/me").status_code==401
    assert client.post("/api/session",json={"email":email,"password":state["password"]}).status_code==200
    for project in client.get('/api/projects').json():
        assert client.request('DELETE','/api/projects/'+project['id'],json={'confirmation':project['name']}).status_code==204
    assert client.post("/api/me/security/request",json={"current_password":state["password"],"delete_account":True}).status_code==200
    data={"current_password":state["password"],"code":"123456"}
    assert client.post("/api/me/security/verify",json=data).status_code==400
    assert client.post("/api/me/security/verify",json={**data,"delete_confirmation":"DELETE"}).status_code==200
    assert client.get("/api/me").status_code==401
    with api.connect() as db:assert not db.execute("SELECT 1 FROM auth.users WHERE id=%s",(uid,)).fetchone()


def test_last_admin_and_missing_second_email_code(setup):
    client,state,uid,email=setup
    verify(client,email)
    with api.connect() as db:
        db.execute("UPDATE insightflow.auth_profiles SET role='administrator' WHERE id=%s",(uid,))
    assert client.post("/api/me/security/request",json={"current_password":state["password"],"delete_account":True}).status_code==409
    assert client.post("/api/me/security/request",json={"current_password":state["password"],"new_email":"new-"+email}).status_code==200
    before=len(state["calls"])
    assert client.post("/api/me/security/verify",json={"code":"123456","current_password":state["password"]}).status_code==400
    assert not any(path=="verify" for method,path in state["calls"][before:])


@pytest.mark.parametrize("role,preparation,review,admin", [
    ("data_scientist", 200, 403, 403),
    ("reviewer", 403, 200, 403),
    ("administrator", 403, 403, 200),
])
def test_role_access_matrix(setup, role, preparation, review, admin):
    client,state,uid,email=setup
    verify(client,email)
    with api.connect() as db:
        db.execute("UPDATE insightflow.auth_profiles SET role=%s WHERE id=%s",(role,uid))
    assert client.get("/api/workspaces/preparation").status_code==410
    assert client.get("/api/workspaces/review").status_code==410
    assert client.get("/api/admin/accounts").status_code==admin
    assert client.get("/api/workspaces/unknown").status_code==410


@pytest.mark.parametrize("role", ["data_scientist", "reviewer"])
def test_non_admin_cannot_promote_self_or_others(setup, role):
    client,state,uid,email=setup
    verify(client,email)
    with api.connect() as db:
        db.execute("UPDATE insightflow.auth_profiles SET role=%s WHERE id=%s",(role,uid))
    for target in [uid,str(uuid4())]:
        assert client.patch(f"/api/admin/accounts/{target}",json={"role":"administrator"}).status_code==403
    assert client.get("/api/me").json()["role"]==role


def test_admin_assigns_all_roles_and_checks_input(setup):
    client,state,uid,email=setup
    verify(client,email)
    target=str(uuid4())
    with api.connect() as db:
        db.execute("UPDATE insightflow.auth_profiles SET role='administrator' WHERE id=%s",(uid,))
        db.execute("INSERT INTO auth.users(id) VALUES (%s)",(target,))
        db.execute("INSERT INTO insightflow.auth_profiles(id,email) VALUES (%s,%s)",(target,target+"@example.com"))
    for role in ["reviewer","administrator","data_scientist"]:
        response=client.patch(f"/api/admin/accounts/{target}",json={"role":role})
        assert response.status_code==200
        assert response.json()["role"]==role
        assert next(row for row in client.get('/api/admin/accounts').json() if row['id']==target)['role']==role
    assert client.patch(f"/api/admin/accounts/{target}",json={"role":"owner"}).status_code==422
    assert client.patch(f"/api/admin/accounts/{target}",json={"role":"reviewer","email":"overwrite@example.com"}).status_code==422
    assert client.patch(f"/api/admin/accounts/{uuid4()}",json={"role":"reviewer"}).status_code==404
    assert client.patch(f"/api/admin/accounts/{uid}",json={"role":"reviewer"}).status_code==409
    assert client.get('/api/me').json()['role']=='administrator'


def test_role_changes_apply_to_existing_session(setup):
    client,state,uid,email=setup
    verify(client,email)
    for role,allowed,blocked in [('administrator','/api/admin/accounts','/api/workspaces/review'),
                                 ('data_scientist','/api/me','/api/admin/accounts')]:
        with api.connect() as db:
            db.execute('UPDATE insightflow.auth_profiles SET role=%s WHERE id=%s',(role,uid))
        assert client.get('/api/me').json()['role']==role
        assert client.get(allowed).status_code==200
        assert client.get(blocked).status_code==(410 if 'workspaces' in blocked else 403)
    assert client.patch(f'/api/admin/accounts/{uid}',json={'role':'administrator'}).status_code==403


def test_anonymous_and_signup_role_injection(setup):
    client,state,uid,email=setup
    assert client.get('/api/admin/accounts').status_code==401
    assert client.patch(f'/api/admin/accounts/{uid}',json={'role':'administrator'}).status_code==401
    assert client.get('/api/workspaces/preparation').status_code==401
    assert client.get('/api/workspaces/review').status_code==401
    assert client.post('/api/accounts',json={'email':email,'password':state['password'],
        'confirm_password':state['password'],'role':'administrator'}).status_code==422
