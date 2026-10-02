-- Failed log-ins (an email that no account uses), kept for an hour so one network can't
-- try email after email to learn who has signed up. Only the salted hash of the IP is
-- stored, never the email that was tried.
CREATE TABLE IF NOT EXISTS failed_logins (
  ip_hash TEXT NOT NULL,
  at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS failed_logins_by_ip ON failed_logins(ip_hash, at);
