-- Multi-Agent Travel Platform schema (created automatically by SQLAlchemy on startup)

CREATE TABLE users (
  id UUID PRIMARY KEY,
  display_name VARCHAR(120) NOT NULL,
  email VARCHAR(255) UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE travel_requests (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  payload JSONB NOT NULL,
  raw_text TEXT,
  status VARCHAR(40) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE workflows (
  id UUID PRIMARY KEY,
  request_id UUID NOT NULL REFERENCES travel_requests(id),
  status VARCHAR(40) NOT NULL,
  selected_agents JSONB NOT NULL,
  dag JSONB NOT NULL,
  error TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_executions (
  id UUID PRIMARY KEY,
  workflow_id UUID NOT NULL REFERENCES workflows(id),
  agent_id VARCHAR(64) NOT NULL,
  stage VARCHAR(64) NOT NULL,
  status VARCHAR(40) NOT NULL,
  attempt INTEGER NOT NULL,
  input_payload JSONB NOT NULL,
  output_payload JSONB,
  error TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE TABLE travel_plans (
  id UUID PRIMARY KEY,
  workflow_id UUID NOT NULL UNIQUE REFERENCES workflows(id),
  feasibility VARCHAR(32) NOT NULL,
  summary JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
