import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from accounts import Registration, Role, app, connect, create_account, hasher


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["INSIGHTFLOW_TEST_DATABASE_URL"])
    with connect() as db:
        db.execute((Path(__file__).parents[1] / "database/accounts.sql").read_text())
    with TestClient(app, base_url="https://testserver", headers={"X-InsightFlow": "1"}) as session:
        yield session


def credentials():
    return {"email": f"{uuid4().hex}@example.com", "password": "a long test password"}


def test_signup_and_duplicates(client):
    data = credentials()
    assert client.post("/api/accounts", json={**data, "password": "short"}).status_code == 422
    assert client.post("/api/accounts", json={**data, "email": "broken"}).status_code == 422
    assert client.post("/api/accounts", json={**data, "role": "administrator"}).status_code == 422
    created = client.post("/api/accounts", json=data)
    assert created.status_code == 201
    assert set(created.json()) == {"email", "id", "role"}
    assert created.json()["role"] == "data_scientist"
    assert client.post("/api/accounts", json={**data, "email": data["email"].upper()}).status_code == 409
    with connect() as db:
        stored = db.execute("SELECT password_hash FROM insightflow.accounts WHERE email=%s",
                            (data["email"],)).fetchone()
        assert hasher.verify(stored["password_hash"], data["password"])


def test_permissions_follow_live_role(client):
    data = credentials()
    person = client.post("/api/accounts", json=data).json()
    route = f"/api/admin/accounts/{person['id']}"
    assert client.get("/api/admin/accounts").status_code == 401
    assert client.patch(route, json={"role": "administrator"}).status_code == 401
    assert client.post("/api/session", json={**data, "password": "wrong"}).status_code == 401
    assert client.post("/api/session", json=data).status_code == 200
    assert client.get("/api/workspaces/preparation").status_code == 200
    assert client.get("/api/workspaces/review").status_code == 403
    assert client.patch(route, json={"role": "administrator"}).status_code == 403
    admin_data = credentials()
    with connect() as db:
        admin_id = create_account(db, Registration(**admin_data), Role.admin)["id"]
    with TestClient(app, base_url="https://testserver", headers={"X-InsightFlow": "1"}) as admin:
        assert admin.post("/api/session", json=admin_data).status_code == 200
        assert admin.patch(route, json={"role": "reviewer"}).status_code == 200
        assert admin.patch(route, json={"role": "invalid"}).status_code == 422
        assert admin.patch(f"/api/admin/accounts/{admin_id}", json={"role": "reviewer"}).status_code == 409
        assert client.get("/api/workspaces/preparation").status_code == 403
        assert client.get("/api/workspaces/review").status_code == 200
        assert client.get("/api/admin/accounts").status_code == 403
        assert admin.patch(route, json={"role": "administrator"}).status_code == 200
        assert client.get("/api/admin/accounts").status_code == 200
        assert admin.patch(route, json={"role": "data_scientist"}).status_code == 200
        assert client.get("/api/admin/accounts").status_code == 403
    assert client.delete("/api/session").status_code == 204
    assert client.get("/api/me").status_code == 401
