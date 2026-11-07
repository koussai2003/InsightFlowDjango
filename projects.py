"""Private project membership; platform privileges never imply project access."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from account_models import database

ProjectRole = Literal['moderator', 'data_scientist', 'reviewer']

class ProjectName(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if not value.strip(): raise ValueError('Enter a project name')
        return value.strip()

class MemberRole(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: ProjectRole

class Invite(MemberRole):
    email: EmailStr

class Transfer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profile_id: UUID

class DeleteProject(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmation: str

def create_project(db, uid, name):
    project = db.execute('INSERT INTO insightflow.projects(name,owner_id) VALUES (%s,%s) RETURNING *',(name,uid)).fetchone()
    db.execute("INSERT INTO insightflow.project_members VALUES (%s,%s,'data_scientist')",(project['id'],uid))
    return {**project, 'role':'owner'}

def ensure_personal_project(db, uid):
    row=db.execute('SELECT workspace_initialized FROM insightflow.auth_profiles WHERE id=%s FOR UPDATE',(uid,)).fetchone()
    if row and not row['workspace_initialized']:
        create_project(db,uid,'My workspace')
        db.execute('UPDATE insightflow.auth_profiles SET workspace_initialized=true WHERE id=%s',(uid,))

def membership(db, pid, uid, lock=False):
    # The same project lock serializes invitations, member changes and ownership transfer.
    project=db.execute('SELECT * FROM insightflow.projects WHERE id=%s'+(' FOR UPDATE' if lock else ''),(pid,)).fetchone()
    if not project: raise HTTPException(404,'Project not found')
    member=db.execute('SELECT role FROM insightflow.project_members WHERE project_id=%s AND profile_id=%s',(pid,uid)).fetchone()
    if not member: raise HTTPException(404,'Project not found')
    return {**project,'role':'owner' if str(project['owner_id'])==str(uid) else member['role']}

def manager(project, target_role=None):
    if project['role'] not in ('owner','moderator'): raise HTTPException(403,'Project owner or moderator access required')
    if target_role in ('owner','moderator') and project['role']!='owner':
        raise HTTPException(403,'Only the project owner can manage moderators')

def protect_owned_projects(db, uid):
    if db.execute('SELECT 1 FROM insightflow.projects WHERE owner_id=%s LIMIT 1',(uid,)).fetchone():
        raise HTTPException(409,'Transfer ownership or delete your projects before deleting your account')

def project_router(signed_in):
    router=APIRouter(prefix='/api')

    @router.get('/projects')
    def list_projects(user=Depends(signed_in),db=Depends(database)):
        ensure_personal_project(db,user['id'])
        return db.execute("""SELECT p.*,CASE WHEN p.owner_id=m.profile_id THEN 'owner' ELSE m.role END AS role
            FROM insightflow.projects p JOIN insightflow.project_members m ON p.id=m.project_id
            WHERE m.profile_id=%s ORDER BY p.created_at,p.id""",(user['id'],)).fetchall()

    @router.post('/projects',status_code=201)
    def new_project(data:ProjectName,user=Depends(signed_in),db=Depends(database)):
        return create_project(db,user['id'],data.name)

    @router.get('/projects/{pid}')
    def detail(pid:UUID,user=Depends(signed_in),db=Depends(database)):
        return membership(db,pid,user['id'])

    @router.get('/projects/{pid}/workspaces/{workspace}')
    def access(pid:UUID,workspace:str,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'])
        allowed={'preparation':('owner','moderator','data_scientist'),'review':('owner','moderator','reviewer')}
        if workspace not in allowed: raise HTTPException(404,'Workspace not found')
        if project['role'] not in allowed[workspace]: raise HTTPException(403,'Your project role does not allow this action')
        return {'project_id':pid,'role':project['role'],'workspace':workspace}

    @router.get('/projects/{pid}/members')
    def members(pid:UUID,user=Depends(signed_in),db=Depends(database)):
        membership(db,pid,user['id'])
        return db.execute("""SELECT a.id,a.email,CASE WHEN p.owner_id=a.id THEN 'owner' ELSE m.role END AS role
            FROM insightflow.project_members m JOIN insightflow.auth_profiles a ON a.id=m.profile_id
            JOIN insightflow.projects p ON p.id=m.project_id WHERE p.id=%s ORDER BY a.email""",(pid,)).fetchall()

    @router.patch('/projects/{pid}/members/{uid}')
    def set_role(pid:UUID,uid:UUID,data:MemberRole,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'],True); manager(project,data.role)
        target=db.execute('SELECT role FROM insightflow.project_members WHERE project_id=%s AND profile_id=%s',(pid,uid)).fetchone()
        if not target: raise HTTPException(404,'Member not found')
        if uid==project['owner_id']: raise HTTPException(409,'Use ownership transfer to change the owner')
        manager(project,target['role'])
        db.execute('UPDATE insightflow.project_members SET role=%s WHERE project_id=%s AND profile_id=%s',(data.role,pid,uid))
        db.execute("UPDATE insightflow.project_invitations SET status='revoked' WHERE project_id=%s AND invited_by=%s AND status='pending'",(pid,uid))
        return {'message':'Project role updated'}

    @router.delete('/projects/{pid}/members/{uid}',status_code=204)
    def remove(pid:UUID,uid:UUID,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'],True)
        if uid==project['owner_id']: raise HTTPException(409,'Transfer ownership before leaving')
        target=db.execute('SELECT role FROM insightflow.project_members WHERE project_id=%s AND profile_id=%s',(pid,uid)).fetchone()
        if not target: raise HTTPException(404,'Member not found')
        if str(uid)!=user['id']: manager(project,target['role'])
        db.execute('DELETE FROM insightflow.project_members WHERE project_id=%s AND profile_id=%s',(pid,uid))
        db.execute("UPDATE insightflow.project_invitations SET status='revoked' WHERE project_id=%s AND invited_by=%s AND status='pending'",(pid,uid))

    @router.post('/projects/{pid}/transfer')
    def transfer(pid:UUID,data:Transfer,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'],True)
        if project['role']!='owner': raise HTTPException(403,'Only the owner can transfer ownership')
        if str(data.profile_id)==user['id']: raise HTTPException(400,'Choose another member')
        if not db.execute('SELECT 1 FROM insightflow.project_members WHERE project_id=%s AND profile_id=%s',(pid,data.profile_id)).fetchone():
            raise HTTPException(400,'The new owner must already be a project member')
        db.execute('UPDATE insightflow.projects SET owner_id=%s WHERE id=%s',(data.profile_id,pid))
        db.execute("UPDATE insightflow.project_members SET role='moderator' WHERE project_id=%s AND profile_id=%s",(pid,user['id']))
        db.execute("UPDATE insightflow.project_invitations SET status='revoked' WHERE project_id=%s AND invited_by=%s AND status='pending'",(pid,user['id']))
        return {'message':'Ownership transferred. You are now a moderator.'}

    @router.delete('/projects/{pid}',status_code=204)
    def delete(pid:UUID,data:DeleteProject,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'],True)
        if project['role']!='owner': raise HTTPException(403,'Only the owner can delete this project')
        if data.confirmation!=project['name']: raise HTTPException(400,'Type the project name to confirm deletion')
        db.execute('DELETE FROM insightflow.projects WHERE id=%s',(pid,))

    @router.post('/projects/{pid}/invitations',status_code=201)
    def invite(pid:UUID,data:Invite,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'],True); manager(project,data.role)
        email=str(data.email).lower()
        if db.execute('SELECT 1 FROM insightflow.project_members m JOIN insightflow.auth_profiles a ON a.id=m.profile_id WHERE m.project_id=%s AND lower(a.email)=%s',(pid,email)).fetchone():
            raise HTTPException(409,'This person is already a project member')
        db.execute("UPDATE insightflow.project_invitations SET status='revoked' WHERE project_id=%s AND email=%s AND status='pending' AND expires_at<=now()",(pid,email))
        if db.execute("SELECT 1 FROM insightflow.project_invitations WHERE project_id=%s AND email=%s AND status='pending'",(pid,email)).fetchone():
            raise HTTPException(409,'A pending invitation already exists for this email')
        return db.execute('INSERT INTO insightflow.project_invitations(project_id,email,role,invited_by) VALUES (%s,%s,%s,%s) RETURNING id,email,role,expires_at',(pid,email,data.role,user['id'])).fetchone()

    @router.get('/projects/{pid}/invitations')
    def sent(pid:UUID,user=Depends(signed_in),db=Depends(database)):
        manager(membership(db,pid,user['id']))
        return db.execute("SELECT id,email,role,expires_at FROM insightflow.project_invitations WHERE project_id=%s AND status='pending' AND expires_at>now() ORDER BY created_at",(pid,)).fetchall()

    @router.delete('/projects/{pid}/invitations/{iid}',status_code=204)
    def revoke(pid:UUID,iid:UUID,user=Depends(signed_in),db=Depends(database)):
        project=membership(db,pid,user['id'],True); manager(project)
        row=db.execute("SELECT role FROM insightflow.project_invitations WHERE id=%s AND project_id=%s AND status='pending'",(iid,pid)).fetchone()
        if not row: raise HTTPException(404,'Invitation not found')
        manager(project,row['role'])
        db.execute("UPDATE insightflow.project_invitations SET status='revoked' WHERE id=%s",(iid,))

    @router.get('/invitations')
    def inbox(user=Depends(signed_in),db=Depends(database)):
        return db.execute("""SELECT i.id,i.project_id,p.name,i.role,i.expires_at FROM insightflow.project_invitations i
            JOIN insightflow.projects p ON p.id=i.project_id WHERE i.email=%s AND i.status='pending' AND i.expires_at>now()
            ORDER BY i.created_at""",(user['email'].lower(),)).fetchall()

    @router.post('/invitations/{iid}/{action}')
    def respond(iid:UUID,action:Literal['accept','decline'],user=Depends(signed_in),db=Depends(database)):
        row=db.execute('SELECT project_id FROM insightflow.project_invitations WHERE id=%s AND email=%s',(iid,user['email'].lower())).fetchone()
        if not row: raise HTTPException(404,'Invitation not found')
        db.execute('SELECT id FROM insightflow.projects WHERE id=%s FOR UPDATE',(row['project_id'],))
        invite=db.execute("SELECT * FROM insightflow.project_invitations WHERE id=%s AND email=%s AND status='pending' AND expires_at>now() FOR UPDATE",(iid,user['email'].lower())).fetchone()
        if not invite: raise HTTPException(409,'Invitation expired or already handled')
        if action=='accept':
            db.execute('INSERT INTO insightflow.project_members(project_id,profile_id,role) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',(invite['project_id'],user['id'],invite['role']))
        db.execute('UPDATE insightflow.project_invitations SET status=%s WHERE id=%s',('accepted' if action=='accept' else 'declined',iid))
        return {'project_id':invite['project_id'],'message':'Invitation '+('accepted' if action=='accept' else 'declined')}
    return router
