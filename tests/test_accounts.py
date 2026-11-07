"""Checks for the real Supabase HTTP boundary without sending emails."""
import httpx
import pytest
from fastapi import HTTPException
import supabase_accounts as api


def test_email_restriction_is_explained(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL","https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","test-key")
    monkeypatch.setattr(httpx,"request",lambda *a,**k:httpx.Response(400,json={"error_code":"email_address_not_authorized"}))
    with pytest.raises(HTTPException) as error:api.auth("POST","signup",{})
    assert "team addresses" in error.value.detail


def test_auth_unavailable_is_not_silent(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL","https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","test-key")
    def fail(*a,**k):raise httpx.ConnectTimeout("offline")
    monkeypatch.setattr(httpx,"request",fail)
    with pytest.raises(HTTPException) as error:api.auth("GET","user")
    assert error.value.status_code==503


def test_revoked_session_rejected():
    import base64,json
    from uuid import uuid4
    payload=base64.urlsafe_b64encode(json.dumps({"session_id":str(uuid4())}).encode()).decode().rstrip("=")
    class DB:
        def execute(self,*a):return self
        def fetchone(self):return None
    with pytest.raises(HTTPException) as error:api.validate_session(DB(),"header."+payload+".signature",str(uuid4()))
    assert error.value.status_code==401
