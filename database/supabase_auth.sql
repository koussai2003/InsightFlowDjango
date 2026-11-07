CREATE SCHEMA IF NOT EXISTS insightflow;
REVOKE ALL ON SCHEMA insightflow FROM PUBLIC;
CREATE TABLE IF NOT EXISTS insightflow.auth_profiles (
 id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE, email text NOT NULL UNIQUE,
 role text NOT NULL DEFAULT 'data_scientist' CHECK(role IN ('data_scientist','reviewer','administrator'))
);
CREATE TABLE IF NOT EXISTS insightflow.auth_sessions (
 token_hash text PRIMARY KEY, profile_id uuid NOT NULL REFERENCES insightflow.auth_profiles(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS auth_sessions_profile ON insightflow.auth_sessions(profile_id);
CREATE TABLE IF NOT EXISTS insightflow.auth_requests (
 profile_id uuid PRIMARY KEY REFERENCES insightflow.auth_profiles(id) ON DELETE CASCADE,
 action text NOT NULL CHECK(action IN ('email','password','delete')), new_email text,
 created_at timestamptz NOT NULL DEFAULT now(), attempts integer NOT NULL DEFAULT 0, old_verified boolean NOT NULL DEFAULT false
);
ALTER TABLE insightflow.auth_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE insightflow.auth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE insightflow.auth_requests ENABLE ROW LEVEL SECURITY;
