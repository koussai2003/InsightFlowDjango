ALTER TABLE insightflow.auth_profiles ADD COLUMN IF NOT EXISTS workspace_initialized boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS insightflow.projects (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 80),
 owner_id uuid NOT NULL REFERENCES insightflow.auth_profiles(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS insightflow.project_members (
 project_id uuid NOT NULL REFERENCES insightflow.projects(id) ON DELETE CASCADE,
 profile_id uuid NOT NULL REFERENCES insightflow.auth_profiles(id) ON DELETE CASCADE,
 role text NOT NULL CHECK(role IN ('moderator','data_scientist','reviewer')),
 PRIMARY KEY(project_id,profile_id)
);
CREATE INDEX IF NOT EXISTS project_members_profile ON insightflow.project_members(profile_id);
CREATE TABLE IF NOT EXISTS insightflow.project_invitations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), project_id uuid NOT NULL REFERENCES insightflow.projects(id) ON DELETE CASCADE,
 email text NOT NULL CHECK(email=lower(email)), role text NOT NULL CHECK(role IN ('moderator','data_scientist','reviewer')),
 invited_by uuid REFERENCES insightflow.auth_profiles(id) ON DELETE SET NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','revoked')),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL DEFAULT now()+interval '7 days'
);
CREATE UNIQUE INDEX IF NOT EXISTS project_pending_invite ON insightflow.project_invitations(project_id,email) WHERE status='pending';
CREATE INDEX IF NOT EXISTS project_invitation_email ON insightflow.project_invitations(email);
ALTER TABLE insightflow.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE insightflow.project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE insightflow.project_invitations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON insightflow.projects, insightflow.project_members, insightflow.project_invitations FROM PUBLIC;
