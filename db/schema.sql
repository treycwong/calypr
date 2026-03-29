-- Calypr MVP Database Schema
-- Run this against your Neon database

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clerk_id TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL,
  github_username TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  repo TEXT NOT NULL,
  price_cents INTEGER NOT NULL DEFAULT 14900,
  stripe_price_id TEXT,
  preview_url TEXT,
  status TEXT NOT NULL DEFAULT 'available',
  latest_version TEXT DEFAULT '1.0.0',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS purchases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  template_id TEXT NOT NULL REFERENCES templates(id),
  stripe_session_id TEXT NOT NULL UNIQUE,
  stripe_event_id TEXT UNIQUE,
  amount_cents INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  github_repo_access BOOLEAN NOT NULL DEFAULT false,
  purchased_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  refunded_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS support_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  template_id TEXT REFERENCES templates(id),
  github_issue_number INTEGER,
  subject TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customization_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  template_id TEXT NOT NULL REFERENCES templates(id),
  stripe_session_id TEXT UNIQUE,
  github_issue_number INTEGER,
  brief TEXT NOT NULL,
  business_name TEXT,
  target_audience TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS failed_operations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  operation_type TEXT NOT NULL,
  reference_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  error TEXT,
  retries INTEGER NOT NULL DEFAULT 0,
  resolved BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_purchases_user ON purchases(user_id);
CREATE INDEX idx_purchases_stripe_session ON purchases(stripe_session_id);
CREATE INDEX idx_purchases_stripe_event ON purchases(stripe_event_id);
CREATE INDEX idx_purchases_status ON purchases(status);
CREATE INDEX idx_support_tickets_user ON support_tickets(user_id);
CREATE INDEX idx_customization_requests_user ON customization_requests(user_id);
CREATE INDEX idx_failed_operations_resolved ON failed_operations(resolved) WHERE NOT resolved;

-- Seed templates
INSERT INTO templates (id, name, repo, price_cents, status, latest_version) VALUES
  ('launchpad', 'Launchpad', 'calypr/launchpad', 14900, 'coming-soon', '1.0.0'),
  ('atelier', 'Atelier', 'calypr/atelier', 14900, 'coming-soon', '1.0.0'),
  ('meridian', 'Meridian', 'calypr/meridian', 14900, 'coming-soon', '1.0.0')
ON CONFLICT (id) DO NOTHING;
