-- ============================================================
-- SENTINEL PostgreSQL Schema
-- Production-grade, audit-complete, multi-site capable
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- USERS (operators, safety officers, admins)
-- ============================================================

CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('operator','safety_officer','manager','auditor','admin')),
    site_ids        UUID[],                  -- sites this user has access to
    active          BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SITES & ZONES
-- ============================================================

CREATE TABLE sites (
    site_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_code       TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    country         TEXT NOT NULL,
    timezone        TEXT NOT NULL,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE zones (
    zone_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id         UUID NOT NULL REFERENCES sites(site_id),
    zone_code       TEXT NOT NULL,
    name            TEXT NOT NULL,
    zone_type       TEXT NOT NULL,
    floor           INTEGER DEFAULT 0,
    geom_json       JSONB,
    max_occupancy   INTEGER,
    hazard_classes  TEXT[],
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(site_id, zone_code)
);

CREATE INDEX idx_zones_site ON zones(site_id);

-- ============================================================
-- INCIDENTS
-- ============================================================

CREATE TABLE incidents (
    incident_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id             UUID NOT NULL REFERENCES sites(site_id),
    zone_id             UUID REFERENCES zones(zone_id),
    event_id            UUID UNIQUE,
    incident_type       TEXT NOT NULL,
    severity            TEXT NOT NULL CHECK (severity IN ('minor','moderate','major','critical','catastrophic')),
    status              TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','investigating','remediated','closed')),
    description         TEXT NOT NULL,
    root_cause          TEXT,
    contributing_factors TEXT[],
    injuries            INTEGER DEFAULT 0,
    fatalities          INTEGER DEFAULT 0,
    remediation_taken   TEXT[],
    regulatory_report_required BOOLEAN DEFAULT FALSE,
    regulatory_reference TEXT,
    correlation_id      UUID,
    occurred_at         TIMESTAMPTZ NOT NULL,
    closed_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_incidents_site_zone ON incidents(site_id, zone_id);
CREATE INDEX idx_incidents_severity  ON incidents(severity);
CREATE INDEX idx_incidents_occurred  ON incidents(occurred_at DESC);
CREATE INDEX idx_incidents_correlation ON incidents(correlation_id);

-- ============================================================
-- AGENT RESULTS
-- ============================================================

CREATE TABLE agent_results (
    result_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id            UUID UNIQUE NOT NULL,
    agent_id            TEXT NOT NULL,
    agent_version       TEXT NOT NULL,
    result_type         TEXT NOT NULL,
    site_id             UUID REFERENCES sites(site_id),
    zone_id             UUID REFERENCES zones(zone_id),
    correlation_id      UUID,
    causation_id        UUID,
    confidence          NUMERIC(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    processing_time_ms  INTEGER NOT NULL,
    risk_score          NUMERIC(5,2) CHECK (risk_score BETWEEN 0 AND 100),
    payload             JSONB NOT NULL,
    schema_version      TEXT NOT NULL DEFAULT 'v1',
    input_event_ids     UUID[],
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_results_agent ON agent_results(agent_id, created_at DESC);
CREATE INDEX idx_agent_results_zone  ON agent_results(zone_id, created_at DESC);
CREATE INDEX idx_agent_results_corr  ON agent_results(correlation_id);
CREATE INDEX idx_agent_results_payload ON agent_results USING gin(payload);

-- ============================================================
-- RISK HISTORY
-- ============================================================

CREATE TABLE risk_history (
    risk_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id            UUID UNIQUE NOT NULL,
    site_id             UUID NOT NULL REFERENCES sites(site_id),
    zone_id             UUID NOT NULL REFERENCES zones(zone_id),
    score               NUMERIC(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    severity            TEXT NOT NULL CHECK (severity IN ('negligible','low','moderate','high','critical','catastrophic')),
    contributors        JSONB NOT NULL,
    explanation_summary TEXT,
    input_analysis_ids  UUID[],
    correlation_id      UUID,
    computed_at         TIMESTAMPTZ NOT NULL,
    ttl_seconds         INTEGER DEFAULT 30,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_risk_history_zone     ON risk_history(zone_id, computed_at DESC);
CREATE INDEX idx_risk_history_severity ON risk_history(severity, computed_at DESC);
CREATE INDEX idx_risk_history_site     ON risk_history(site_id, computed_at DESC);

-- ============================================================
-- ACTIONS
-- ============================================================

CREATE TABLE actions (
    action_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_event_id    UUID UNIQUE NOT NULL,
    result_event_id     UUID,
    site_id             UUID REFERENCES sites(site_id),
    zone_id             UUID REFERENCES zones(zone_id),
    risk_id             UUID REFERENCES risk_history(risk_id),
    action_type         TEXT NOT NULL,
    requested_by        TEXT NOT NULL,
    priority            TEXT NOT NULL CHECK (priority IN ('low','normal','high','emergency')),
    status              TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending_approval','approved','rejected','executing','completed','failed','expired')),
    reason              TEXT NOT NULL,
    approval_required   BOOLEAN NOT NULL,
    approver_roles      TEXT[],
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    rejected_by         TEXT,
    rejected_reason     TEXT,
    executed_by         TEXT,
    executed_at         TIMESTAMPTZ,
    parameters          JSONB,
    affected_workers    TEXT[],
    affected_permits    UUID[],
    audit_reference     TEXT,
    expires_at          TIMESTAMPTZ,
    correlation_id      UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_actions_zone   ON actions(zone_id, created_at DESC);
CREATE INDEX idx_actions_status ON actions(status);
CREATE INDEX idx_actions_risk   ON actions(risk_id);

-- ============================================================
-- AUDIT LOG (append-only, never updated)
-- ============================================================

CREATE TABLE audit_logs (
    audit_id        BIGSERIAL PRIMARY KEY,
    event_id        UUID NOT NULL,
    event_type      TEXT NOT NULL,
    source          TEXT NOT NULL,
    actor           TEXT,
    site_id         UUID,
    zone_id         UUID,
    correlation_id  UUID,
    causation_id    UUID,
    schema_version  TEXT NOT NULL,
    payload_hash    TEXT GENERATED ALWAYS AS (encode(sha256(payload::text::bytea), 'hex')) STORED,
    payload         JSONB NOT NULL,
    kafka_offset    BIGINT,
    kafka_partition INTEGER,
    kafka_topic     TEXT,
    logged_at       TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (logged_at);

CREATE TABLE audit_logs_2026_06 PARTITION OF audit_logs FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE audit_logs_2026_07 PARTITION OF audit_logs FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE INDEX idx_audit_event_id    ON audit_logs(event_id);
CREATE INDEX idx_audit_correlation ON audit_logs(correlation_id);
CREATE INDEX idx_audit_logged_at   ON audit_logs(logged_at DESC);
CREATE INDEX idx_audit_zone        ON audit_logs(zone_id, logged_at DESC);
