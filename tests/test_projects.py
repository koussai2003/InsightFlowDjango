"""Project isolation tests use a real disposable database and test-only identities."""
import os
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
import supabase_accounts as api
from projects import ensure_personal_project

@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('DATABASE_URL',os.environ['INSIGHTFLOW_TEST_DATABASE_URL'])
    users={}
    with api.connect() as db:
        db.execute('CREATE SCHEMA IF NOT EXISTS auth; CREATE TABLE IF NOT EXISTS auth.users(id uuid PRIMARY KEY)')
        for file in ['supabase_auth.sql','projects.sql']:
            db.execute((Path(__file__).parents[1]/'database'/file).read_text())
        for label in ['owner','other','admin','third']:
            uid=str(uuid4());users[label]={'id':uid,'email':uid+'@example.com','role':'administrator' if label=='admin' else 'data_scientist'}
            db.execute('INSERT INTO auth.users VALUES (%s)',(uid,))
            db.execute('INSERT INTO insightflow.auth_profiles(id,email,role) VALUES (%s,%s,%s)',(uid,users[label]['email'],users[label]['role']))
    def identity(request:Request): return users[request.headers.get('X-Test-User','owner')]
    api.app.dependency_overrides[api.signed_in]=identity
    with TestClient(api.app,headers={'X-InsightFlow':'1'}) as client:
        def as_user(label):client.headers['X-Test-User']=label;return client
        yield client,users,as_user
    api.app.dependency_overrides.clear()
    with api.connect() as db:
        for person in users.values():
            db.execute('DELETE FROM insightflow.projects WHERE owner_id=%s',(person['id'],))
        for person in users.values():
            db.execute('DELETE FROM auth.users WHERE id=%s',(person['id'],))

def owned(client):return client.get('/api/projects').json()[0]['id']
def invite(client,pid,email,role='data_scientist'):
    result=client.post(f'/api/projects/{pid}/invitations',json={'email':email,'role':role})
    assert result.status_code==201,result.text
    return result.json()['id']

def test_private_defaults_and_platform_admin_no_bypass(env):
    c,u,as_user=env;pid=owned(c)
    assert c.get('/api/projects').json()[0]['role']=='owner'
    assert len(c.get('/api/projects').json())==1
    for who in ['other','admin']:
        as_user(who)
        assert all(p['id']!=pid for p in c.get('/api/projects').json())
        for path in ['', '/members', '/invitations', '/workspaces/preparation']:
            assert c.get(f'/api/projects/{pid}'+path).status_code==404
        assert c.post(f'/api/projects/{pid}/invitations',json={'email':u['third']['email'],'role':'reviewer'}).status_code==404
    as_user('owner')
    assert c.post('/api/projects',json={'name':'   '}).status_code==422
    assert c.post('/api/projects',json={'name':'Second project'}).status_code==201
    assert len(c.get('/api/projects').json())==2

def test_invitation_acceptance_email_bound_and_single_use(env):
    c,u,as_user=env;pid=owned(c);iid=invite(c,pid,u['other']['email'],'reviewer')
    as_user('admin');assert c.post(f'/api/invitations/{iid}/accept').status_code==404
    as_user('other');personal=owned(c)
    assert c.get(f'/api/projects/{pid}').status_code==404
    assert c.get('/api/invitations').json()[0]['id']==iid
    assert c.post(f'/api/invitations/{iid}/accept').status_code==200
    assert c.post(f'/api/invitations/{iid}/accept').status_code==409
    assert c.get(f'/api/projects/{pid}').json()['role']=='reviewer'
    assert c.get(f'/api/projects/{personal}').json()['role']=='owner'
    assert c.get(f'/api/projects/{pid}/workspaces/preparation').status_code==403
    assert c.get(f'/api/projects/{pid}/workspaces/review').status_code==200

@pytest.mark.parametrize('end',['revoke','expire','decline'])
def test_inactive_invitations_grant_no_access(env,end):
    c,u,as_user=env;pid=owned(c);iid=invite(c,pid,u['other']['email'])
    if end=='revoke':assert c.delete(f'/api/projects/{pid}/invitations/{iid}').status_code==204
    if end=='expire':
        with api.connect() as db:db.execute("UPDATE insightflow.project_invitations SET expires_at=now()-interval '1 minute' WHERE id=%s",(iid,))
    as_user('other')
    if end=='decline':assert c.post(f'/api/invitations/{iid}/decline').status_code==200
    assert c.post(f'/api/invitations/{iid}/accept').status_code==409
    assert c.get(f'/api/projects/{pid}').status_code==404

def test_moderator_limits_and_revocation_on_demotion(env):
    c,u,as_user=env;pid=owned(c);iid=invite(c,pid,u['other']['email'],'moderator')
    as_user('other');assert c.post(f'/api/invitations/{iid}/accept').status_code==200
    assert c.post(f'/api/projects/{pid}/invitations',json={'email':u['third']['email'],'role':'moderator'}).status_code==403
    assert c.patch(f"/api/projects/{pid}/members/{u['owner']['id']}",json={'role':'reviewer'}).status_code==409
    assert c.post(f'/api/projects/{pid}/transfer',json={'profile_id':u['other']['id']}).status_code==403
    new_invite=invite(c,pid,u['third']['email'])
    as_user('owner');assert c.patch(f"/api/projects/{pid}/members/{u['other']['id']}",json={'role':'reviewer'}).status_code==200
    as_user('third');assert c.post(f'/api/invitations/{new_invite}/accept').status_code==409
    as_user('other');assert c.get(f'/api/projects/{pid}/invitations').status_code==403
    assert c.post(f'/api/projects/{pid}/invitations',json={'email':u['third']['email'],'role':'reviewer'}).status_code==403

def test_ownership_transfer_removal_and_delete(env):
    c,u,as_user=env;pid=owned(c)
    assert c.delete(f"/api/projects/{pid}/members/{u['owner']['id']}").status_code==409
    assert c.post(f'/api/projects/{pid}/transfer',json={'profile_id':u['third']['id']}).status_code==400
    iid=invite(c,pid,u['other']['email']);as_user('other');c.post(f'/api/invitations/{iid}/accept')
    assert c.request('DELETE',f'/api/projects/{pid}',json={'confirmation':'My workspace'}).status_code==403
    as_user('owner');assert c.post(f'/api/projects/{pid}/transfer',json={'profile_id':u['other']['id']}).status_code==200
    assert c.get(f'/api/projects/{pid}').json()['role']=='moderator'
    as_user('other');assert c.get(f'/api/projects/{pid}').json()['role']=='owner'
    assert c.delete(f"/api/projects/{pid}/members/{u['owner']['id']}").status_code==204
    as_user('owner');assert c.get(f'/api/projects/{pid}').status_code==404
    as_user('other');assert c.request('DELETE',f'/api/projects/{pid}',json={'confirmation':'wrong'}).status_code==400
    assert c.request('DELETE',f'/api/projects/{pid}',json={'confirmation':'My workspace'}).status_code==204
    assert c.get(f'/api/projects/{pid}').status_code==404

def test_duplicate_and_invalid_invites(env):
    c,u,as_user=env;pid=owned(c);invite(c,pid,u['other']['email'])
    assert c.post(f'/api/projects/{pid}/invitations',json={'email':u['other']['email'],'role':'reviewer'}).status_code==409
    assert c.post(f'/api/projects/{pid}/invitations',json={'email':u['third']['email'],'role':'owner'}).status_code==422
    assert c.post(f'/api/projects/{pid}/invitations',json={'email':u['owner']['email'],'role':'reviewer'}).status_code==409
