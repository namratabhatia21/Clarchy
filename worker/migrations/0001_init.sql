-- Leads and free-diagram usage for clarchy.com (Cloudflare D1, SQLite).
-- Apply with: npx wrangler d1 migrations apply clarchy --remote   (or --local for wrangler dev)

-- One row per person who signed up on the site. `id` is a random UUID that the visitor's
-- browser keeps; it is the only key the page ever sends back.
CREATE TABLE IF NOT EXISTS leads (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  company TEXT NOT NULL,
  updates_opt_in INTEGER NOT NULL DEFAULT 0,  -- 1 only if they ticked the updates box
  consent_text TEXT,                          -- the exact wording they saw for that box
  consent_at TEXT,                            -- when they last made that choice
  plan TEXT NOT NULL DEFAULT 'free',          -- 'free' or 'pro' (turned on by hand)
  pro_requested_at TEXT,                      -- when they joined the Pro waitlist
  created_at TEXT NOT NULL,
  last_seen_at TEXT,
  ip_hash TEXT                                -- salted SHA-256 of the IP, for rate limiting only
);

-- One row per diagram planned from the visitor's own brief.
CREATE TABLE IF NOT EXISTS usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS usage_by_lead ON usage(lead_id);
CREATE INDEX IF NOT EXISTS leads_by_ip ON leads(ip_hash, created_at);
