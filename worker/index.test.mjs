// Tests for the Worker API: node --no-warnings --test worker/
// D1 is stood in for by Node's built-in SQLite, loaded with the real migrations.

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { beforeEach, describe, it } from "node:test";

import { CONSENT_TEXT } from "./consent.mjs";
import worker from "./index.mjs";

const ORIGIN = "https://clarchy.com";

// The parts of the D1 API the Worker uses: prepare().bind().first() / .all() / .run().
function fakeD1() {
  const db = new DatabaseSync(":memory:");
  const dir = new URL("./migrations/", import.meta.url);
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".sql")).sort()) {
    db.exec(readFileSync(new URL(file, dir), "utf8"));
  }
  const statement = (sql, params = []) => ({
    bind: (...values) => statement(sql, values),
    first: async () => {
      const row = db.prepare(sql).get(...params);
      return row ? { ...row } : null;
    },
    all: async () => ({ results: db.prepare(sql).all(...params).map((row) => ({ ...row })), success: true }),
    run: async () => {
      const info = db.prepare(sql).run(...params);
      return { success: true, meta: { changes: Number(info.changes), last_row_id: Number(info.lastInsertRowid) } };
    },
  });
  return { prepare: (sql) => statement(sql), sql: db };
}

let env;
beforeEach(() => {
  env = {
    DB: fakeD1(),
    ASSETS: { fetch: async () => new Response("static file") },
    FREE_DIAGRAMS: "3",
  };
});

function call(method, path, { body, origin = ORIGIN, ip = "203.0.113.7", headers = {} } = {}) {
  const init = { method, headers: { ...headers } };
  if (origin) init.headers.Origin = origin;
  if (ip) init.headers["CF-Connecting-IP"] = ip;
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = typeof body === "string" ? body : JSON.stringify(body);
  }
  return worker.fetch(new Request(`${ORIGIN}${path}`, init), env);
}

const person = (overrides = {}) => ({ name: "Asha Rao", company: "Northwind", email: "asha@northwind.example", updates: false, ...overrides });

async function signUp(overrides = {}, options = {}) {
  const res = await call("POST", "/api/signup", { body: person(overrides), ...options });
  return { status: res.status, body: await res.json() };
}

describe("config and routing", async () => {
  it("exports only the fetch handler, as the Workers runtime requires", async () => {
    const module = await import("./index.mjs");
    assert.deepEqual(Object.keys(module), ["default"]);
  });

  it("reports that accounts are on, with the free allowance", async () => {
    const res = await call("GET", "/api/config");
    assert.equal(res.status, 200);
    assert.deepEqual(await res.json(), { accounts: true, free_diagrams: 3 });
  });

  it("serves everything outside /api/ from the static files", async () => {
    const res = await call("GET", "/pricing");
    assert.equal(await res.text(), "static file");
  });

  it("answers unknown API routes with 404", async () => {
    const res = await call("GET", "/api/nothing");
    assert.equal(res.status, 404);
    assert.ok((await res.json()).error);
  });
});

describe("sign-up", () => {
  it("creates a free account with every diagram still available", async () => {
    const { status, body } = await signUp({ updates: true });
    assert.equal(status, 201);
    assert.match(body.id, /^[0-9a-f-]{36}$/);
    assert.deepEqual({ plan: body.plan, used: body.used, remaining: body.remaining }, { plan: "free", used: 0, remaining: 3 });
    const row = env.DB.sql.prepare("SELECT * FROM leads").get();
    assert.equal(row.email, "asha@northwind.example");
    assert.equal(row.updates_opt_in, 1);
    assert.equal(row.consent_text, CONSENT_TEXT);
    assert.equal(row.ip_hash.length, 32);
    assert.ok(!JSON.stringify(row).includes("203.0.113.7"), "the IP itself is never stored");
  });

  it("leaves updates off unless the box was ticked", async () => {
    await signUp({ updates: "yes" });
    assert.equal(env.DB.sql.prepare("SELECT updates_opt_in FROM leads").get().updates_opt_in, 0);
  });

  it("returns the same account for the same email, keeping its usage", async () => {
    const first = await signUp();
    await call("POST", "/api/spend", { body: { id: first.body.id } });
    const again = await signUp({ email: "ASHA@Northwind.example", name: "Asha R." });
    assert.equal(again.status, 200);
    assert.equal(again.body.id, first.body.id);
    assert.equal(again.body.used, 1);
    assert.equal(env.DB.sql.prepare("SELECT COUNT(*) AS n FROM leads").get().n, 1);
  });

  it("checks the name, company and email", async () => {
    for (const bad of [{ name: "" }, { company: "  " }, { email: "not-an-email" }, { email: "a@b" }]) {
      const { status, body } = await signUp(bad);
      assert.equal(status, 400, JSON.stringify(bad));
      assert.ok(body.error);
    }
  });

  it("rejects the hidden field that only bots fill in", async () => {
    assert.equal((await signUp({ website: "https://spam.example" })).status, 400);
  });

  it("limits new sign-ups from one network to ten an hour", async () => {
    for (let i = 0; i < 10; i += 1) assert.equal((await signUp({ email: `p${i}@example.com` })).status, 201);
    assert.equal((await signUp({ email: "p10@example.com" })).status, 429);
    assert.equal((await signUp({ email: "p10@example.com" }, { ip: "198.51.100.2" })).status, 201);
    assert.equal((await signUp({ email: "p1@example.com" })).status, 200, "returning people are never blocked");
  });

  it("refuses requests from other sites and malformed bodies", async () => {
    assert.equal((await signUp({}, { origin: "https://evil.example" })).status, 403);
    assert.equal((await signUp({}, { origin: null })).status, 403);
    assert.equal((await call("POST", "/api/signup", { body: "not json" })).status, 400);
    assert.equal((await call("POST", "/api/signup", { body: "[]" })).status, 400);
    assert.equal((await call("POST", "/api/signup", { body: { name: "x".repeat(5000) } })).status, 413);
  });
});

describe("credits", () => {
  it("allows three diagrams on the free plan, then answers 402", async () => {
    const { body } = await signUp();
    const remaining = [];
    for (let i = 0; i < 3; i += 1) {
      const res = await call("POST", "/api/spend", { body: { id: body.id } });
      assert.equal(res.status, 200);
      remaining.push((await res.json()).remaining);
    }
    assert.deepEqual(remaining, [2, 1, 0]);
    const over = await call("POST", "/api/spend", { body: { id: body.id } });
    assert.equal(over.status, 402);
    assert.deepEqual(await over.json(), {
      ok: false, id: body.id, plan: "free", used: 3, remaining: 0, free_diagrams: 3, waitlisted: false,
    });
  });

  it("never runs out on Pro", async () => {
    const { body } = await signUp();
    env.DB.sql.prepare("UPDATE leads SET plan = 'pro' WHERE id = ?").run(body.id);
    for (let i = 0; i < 5; i += 1) {
      const res = await call("POST", "/api/spend", { body: { id: body.id } });
      assert.equal(res.status, 200);
      assert.equal((await res.json()).remaining, null);
    }
  });

  it("follows the configured allowance", async () => {
    env.FREE_DIAGRAMS = "1";
    const { body } = await signUp();
    assert.equal(body.remaining, 1);
    assert.equal((await call("POST", "/api/spend", { body: { id: body.id } })).status, 200);
    assert.equal((await call("POST", "/api/spend", { body: { id: body.id } })).status, 402);
  });

  it("reports standing for a known visitor and 404 otherwise", async () => {
    const { body } = await signUp();
    const res = await call("GET", `/api/me?id=${body.id}`);
    assert.equal(res.status, 200);
    assert.equal((await res.json()).remaining, 3);
    assert.equal((await call("GET", "/api/me?id=00000000-0000-0000-0000-000000000000")).status, 404);
    assert.equal((await call("GET", "/api/me?id=' OR 1=1 --")).status, 404);
    assert.equal((await call("POST", "/api/spend", { body: { id: 42 } })).status, 404);
  });
});

describe("Pro waitlist", () => {
  it("records the first request and keeps it", async () => {
    const { body } = await signUp();
    assert.equal(body.waitlisted, false);
    const res = await call("POST", "/api/waitlist", { body: { id: body.id } });
    assert.equal(res.status, 200);
    assert.equal((await res.json()).waitlisted, true);
    assert.equal((await (await call("GET", `/api/me?id=${body.id}`)).json()).waitlisted, true);
    const first = env.DB.sql.prepare("SELECT pro_requested_at FROM leads").get().pro_requested_at;
    assert.ok(first);
    await call("POST", "/api/waitlist", { body: { id: body.id } });
    assert.equal(env.DB.sql.prepare("SELECT pro_requested_at FROM leads").get().pro_requested_at, first);
  });
});

describe("lead export", () => {
  it("is off until an admin token is configured", async () => {
    assert.equal((await call("GET", "/api/admin/leads.csv")).status, 404);
  });

  it("needs the exact token", async () => {
    env.ADMIN_TOKEN = "s3cret-token";
    assert.equal((await call("GET", "/api/admin/leads.csv")).status, 401);
    const wrong = { headers: { Authorization: "Bearer s3cret-tokem" } };
    assert.equal((await call("GET", "/api/admin/leads.csv", wrong)).status, 401);
  });

  it("exports every lead with usage, safe to open in a spreadsheet", async () => {
    env.ADMIN_TOKEN = "s3cret-token";
    const { body } = await signUp({ name: "=HYPERLINK(\"x\")", company: "Acme, Inc.", updates: true });
    await call("POST", "/api/spend", { body: { id: body.id } });
    const res = await call("GET", "/api/admin/leads.csv", { headers: { Authorization: "Bearer s3cret-token" } });
    assert.equal(res.status, 200);
    assert.match(res.headers.get("content-type"), /text\/csv/);
    const [header, row] = (await res.text()).trim().split("\r\n");
    assert.equal(header, "created_at,name,company,email,updates_opt_in,plan,pro_requested_at,last_seen_at,diagrams");
    assert.ok(row.includes(`"'=HYPERLINK(""x"")"`), row);
    assert.ok(row.includes('"Acme, Inc."'));
    assert.ok(row.endsWith(",1"));
  });
});
