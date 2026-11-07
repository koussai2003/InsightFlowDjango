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

CREATE TABLE IF NOT EXISTS insightflow.account_changes (
    account_id bigint PRIMARY KEY REFERENCES insightflow.accounts(id) ON DELETE CASCADE,
    code_hash text NOT NULL,
    new_code_hash text,
    new_email text,
    new_password_hash text,
    attempts integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '10 minutes'
);
ALTER TABLE insightflow.account_changes ENABLE ROW LEVEL SECURITY;

ALTER TABLE insightflow.account_changes ADD COLUMN IF NOT EXISTS delete_account boolean NOT NULL DEFAULT false;
