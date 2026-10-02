# 0011: Sign-ups, free diagrams and the Pro waitlist on the Worker, in D1

**Status:** accepted · 2026-10-02 · works with [0008](0008-plans-run-in-the-browser.md)

## Context

Clarchy is in early access. The founder wants to know who uses it (name, company, email,
and whether they want product updates), to give a few diagrams free and then ask for a
subscription, and to do this with free services only. Plans run in the visitor's browser
(ADR 0008), so there was no server, and clarchy.com was a Cloudflare Worker serving static
files.

## Decision

- **The same Worker gets a small API** (`worker/index.mjs`, plain JavaScript, no
  dependencies). `assets.run_worker_first: ["/api/*"]` sends only API calls to it; every
  other path is still served straight from `site/`.
- **Data lives in Cloudflare D1** (database `clarchy`): a `leads` table (name, company,
  email, the updates choice with the exact consent wording and when it was given, plan,
  Pro waitlist date) and a `usage` table with one row per diagram. Schema changes are
  migrations in `worker/migrations/`.
- **Three free diagrams** (`FREE_DIAGRAMS` in `wrangler.jsonc`). Only plans from the
  visitor's own brief count; samples, examples and re-planning a design stay free. The
  page asks `POST /api/spend` before each such plan; the check and the insert are one
  statement, so two plans started at once can't both take the last credit.
- **Pro is a waitlist for now.** No payments: "Join the Pro waitlist" records the date,
  and Pro is turned on by hand (`plan = 'pro'`), which makes diagrams unlimited.
- **The sign-up form appears on the first action on the home page** (writing a brief,
  attaching, a sample, the example drawing). Menus and reading pages, including Privacy
  and Terms, never ask. The updates box is unticked by default.
- **Identity is a random id kept in the browser.** Signing up again with the same email
  returns the same account, so credits don't reset. There are no passwords and no email
  verification at this stage.
- **Abuse limits without paid services:** same-origin POSTs only, a hidden honeypot field,
  at most 10 new sign-ups an hour per network (a salted hash of the IP; the IP itself is
  never stored), bodies capped at 4 KB, bound SQL parameters everywhere.
- **A switch to pause it.** `ACCOUNTS` in `wrangler.jsonc` set to `"off"` makes
  `/api/config` report accounts off, so the page asks nothing and limits nothing, as on a
  copy without the API. It is off while the site is being tested.
- **Fail open.** The page turns accounts on only when `/api/config` answers. Copies
  without the API (GitHub Pages, `clarchy serve`, fragment hosts) gate nothing, and if
  the API fails mid-visit, planning carries on.

## Consequences

- Everything runs on Cloudflare's free plan (Workers: 100k requests a day; D1: 5 GB,
  5M rows read and 100k rows written a day). If a limit is reached, Cloudflare refuses the
  extra requests rather than billing, and the page fails open.
- The limit is soft: planning happens in the browser, so a determined developer can
  bypass it. That is accepted while the goal is learning who the users are; paid plans
  that need hard limits would move metering to work the server does.
- Emails are unverified, so a sign-up can use someone else's address. Before sending
  newsletters, confirm opt-ins (double opt-in) with whatever mailing tool is chosen.
- The founder reads leads in the Cloudflare dashboard (D1 console) or exports them as CSV
  from `/api/admin/leads.csv` after setting the `ADMIN_TOKEN` secret.
