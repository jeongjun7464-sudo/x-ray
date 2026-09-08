import json,time
import pytest
from fastapi.testclient import TestClient
from app.core.auth import AuthenticationError,extract_bearer_token,issue_session_token,verify_session_token
from app.core.config import settings
from app.main import app,limiter
client=TestClient(app);SECRET="a-secure-test-secret-that-is-longer-than-32-characters"
@pytest.fixture(autouse=True)
def reset(monkeypatch):
    limiter._events.clear();monkeypatch.setattr(settings,"auth_enforced",False);monkeypatch.setattr(settings,"auth_allow_legacy_headers",True);monkeypatch.setattr(settings,"auth_demo_tokens_enabled",True);monkeypatch.setattr(settings,"auth_session_secret",SECRET);monkeypatch.setattr(settings,"environment","development")
def test_valid_issue_verify_and_max_ttl():
    token,p=issue_session_token("anon-user","radiologist",SECRET,99999,now=1000);verified=verify_session_token(token,SECRET,now=1001);assert verified.role=="RADIOLOGIST" and p.expires_at==4600
def test_tampered_expired_future_and_disallowed_role_blocked():
    token,_=issue_session_token("anon-user","USER",SECRET,10,now=100)
    for candidate,now,code in ((token+"x",101,"INVALID_SIGNATURE"),(token,111,"SESSION_EXPIRED")):
        with pytest.raises(AuthenticationError) as exc:verify_session_token(candidate,SECRET,now=now)
        assert exc.value.code==code
    future,_=issue_session_token("anon-user","USER",SECRET,10,now=200)
    with pytest.raises(AuthenticationError) as exc:verify_session_token(future,SECRET,now=100)
    assert exc.value.code=="FUTURE_ISSUED_TOKEN"
    with pytest.raises(AuthenticationError):issue_session_token("anon-user","ROOT",SECRET)
def test_empty_secret_and_bearer_format():
    with pytest.raises(AuthenticationError):issue_session_token("anon-user","USER","")
    assert extract_bearer_token("Bearer abc.def")=="abc.def"
    for value in (None,"Basic abc","Bearer","Bearer a b"):
        with pytest.raises(AuthenticationError):extract_bearer_token(value)
def test_enforced_missing_and_forged_header_401(monkeypatch):
    monkeypatch.setattr(settings,"auth_enforced",True);assert client.get("/api/admin/dashboard",headers={"X-Role":"ADMIN"}).status_code==401
def test_enforced_valid_role_and_permission_403(monkeypatch):
    monkeypatch.setattr(settings,"auth_enforced",True);admin,_=issue_session_token("admin-demo","ADMIN",SECRET);user,_=issue_session_token("user-demo","USER",SECRET)
    assert client.get("/api/admin/dashboard",headers={"Authorization":"Bearer "+admin}).status_code==200
    denied=client.get("/api/admin/dashboard",headers={"Authorization":"Bearer "+user});assert denied.status_code==403 and "AUTHORIZATION_DENIED" in denied.text
def test_public_api_without_token(monkeypatch):
    monkeypatch.setattr(settings,"auth_enforced",True);assert client.get("/api/health").status_code==200
def test_demo_token_disabled_and_token_not_echoed(monkeypatch):
    monkeypatch.setattr(settings,"auth_demo_tokens_enabled",False);assert client.post("/api/auth/demo-token",json={"anonymous_user_id":"demo-user","role":"USER"}).status_code==404
    monkeypatch.setattr(settings,"auth_demo_tokens_enabled",True);response=client.post("/api/auth/demo-token",json={"anonymous_user_id":"demo-user","role":"USER"});assert response.status_code==200;token=response.json()["access_token"];assert token not in str(response.headers)
    me=client.get("/api/auth/me",headers={"Authorization":"Bearer "+token}).json();assert "access_token" not in me and me["subject"]=="demo-user"
def test_auth_consistency_rules_block_insecure_production(monkeypatch):
    from app.services.consistency.engine import ConsistencyEngine
    monkeypatch.setattr(settings,"environment","production");monkeypatch.setattr(settings,"auth_enforced",False);monkeypatch.setattr(settings,"auth_session_secret","");monkeypatch.setattr(settings,"auth_demo_tokens_enabled",True);monkeypatch.setattr(settings,"auth_allow_legacy_headers",True)
    result=ConsistencyEngine().validate({},categories=["AUTH_SECURITY"]);failed={item["rule_id"] for item in result["findings"] if item["status"]=="FAIL"}
    assert {"AUTH-001","AUTH-002","AUTH-003","AUTH-004"}.issubset(failed);assert result["high_risk_block"] is True
