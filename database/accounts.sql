CREATE SCHEMA IF NOT EXISTS insightflow;
REVOKE ALL ON SCHEMA insightflow FROM PUBLIC;
CREATE TABLE IF NOT EXISTS insightflow.accounts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'data_scientist'
        CHECK (role IN ('data_scientist', 'reviewer', 'administrator'))
);
CREATE TABLE IF NOT EXISTS insightflow.sessions (
    token_hash text PRIMARY KEY,
    account_id bigint NOT NULL REFERENCES insightflow.accounts(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_account ON insightflow.sessions(account_id);
ALTER TABLE insightflow.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE insightflow.sessions ENABLE ROW LEVEL SECURITY;
