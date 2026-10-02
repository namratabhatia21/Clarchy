// Clarchy's API, on the same Cloudflare Worker that serves the site (wrangler.jsonc).
// Only /api/* reaches this code (assets.run_worker_first); every other path is served from
// site/ as static files. It keeps sign-ups, free-diagram credits and the Pro waitlist in
// D1 (binding DB). Plans themselves run in the visitor's browser and are never sent here.
//
//   GET  /api/config            { accounts, free_diagrams }; accounts is false when the ACCOUNTS
//                               variable is "off", and the page then asks nothing and limits nothing
//   POST /api/signup            { name, company, email, updates, website }  -> standing
//   GET  /api/me?id=            standing, or 404 when the id is unknown
//   POST /api/spend             { id }  -> 200 with standing, or 402 when no credits are left
//   POST /api/waitlist          { id }  -> joins the Pro waitlist
//   GET  /api/admin/leads.csv   Authorization: Bearer <ADMIN_TOKEN>; off without the secret
//
// "standing" is { id, plan, used, remaining, free_diagrams, waitlisted }; remaining is null
// on Pro.

import { CONSENT_TEXT } from "./consent.mjs";

const MAX_BODY_BYTES = 4096;
const SIGNUPS_PER_HOUR = 10;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});
const now = () => new Date().toISOString();

// The sign-up form and the free-diagram limit can be paused without a code change.
const accountsOn = (env) => String(env.ACCOUNTS ?? "on").trim().toLowerCase() !== "off";

function freeDiagrams(env) {
  const n = Number(env.FREE_DIAGRAMS);
  return Number.isInteger(n) && n >= 0 ? n : 3;
}

function text(value, max) {
  return typeof value === "string" ? value.trim().replace(/\s+/g, " ").slice(0, max) : "";
}

async function readJson(request) {
  if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY_BYTES) {
    throw new HttpError(413, "That request is too large.");
  }
  const body = await request.text();
  if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) throw new HttpError(413, "That request is too large.");
  let value = null;
  try { value = JSON.parse(body); } catch { /* handled below */ }
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new HttpError(400, "Send a JSON object.");
  return value;
}

// Browsers send Origin on every POST; requests from other sites are refused.
function sameOrigin(request) {
  const origin = request.headers.get("Origin");
  return origin !== null && origin === new URL(request.url).origin;
}

async function sha256Hex(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// The visitor's IP is never stored, only a salted hash of it, to limit sign-ups per network.
async function ipHash(request, env) {
  const ip = request.headers.get("CF-Connecting-IP");
  return ip ? (await sha256Hex(`${env.IP_SALT || "clarchy"}:${ip}`)).slice(0, 32) : null;
}

async function sameSecret(given, expected) {
  const [a, b] = await Promise.all([sha256Hex(given), sha256Hex(expected)]);
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function findLead(env, id) {
  if (typeof id !== "string" || !ID.test(id)) return null;
  return env.DB.prepare("SELECT id, plan, pro_requested_at FROM leads WHERE id = ?").bind(id).first();
}

async function standing(env, lead) {
  const row = await env.DB.prepare("SELECT COUNT(*) AS used FROM usage WHERE lead_id = ?").bind(lead.id).first();
  const used = Number(row ? row.used : 0);
  const limit = freeDiagrams(env);
  const pro = lead.plan === "pro";
  return {
    id: lead.id,
    plan: pro ? "pro" : "free",
    used,
    remaining: pro ? null : Math.max(0, limit - used),
    free_diagrams: limit,
    waitlisted: Boolean(lead.pro_requested_at),
  };
}

async function signup(request, env) {
  const body = await readJson(request);
  if (text(body.website, 200)) throw new HttpError(400, "Something about that form looks automated.");
  const name = text(body.name, 120);
  const company = text(body.company, 120);
  const email = text(body.email, 254).toLowerCase();
  if (!name || !company) throw new HttpError(400, "Enter your name and company.");
  if (!EMAIL.test(email)) throw new HttpError(400, "Enter a valid email address.");
  const updates = body.updates === true ? 1 : 0;
  const at = now();

  // Signing up again with the same email returns the same account, so credits never reset.
  const existing = await env.DB.prepare("SELECT id, plan, pro_requested_at FROM leads WHERE email = ?").bind(email).first();
  if (existing) {
    await env.DB.prepare(
      "UPDATE leads SET name = ?, company = ?, updates_opt_in = ?, consent_text = ?, consent_at = ?, last_seen_at = ? WHERE id = ?",
    ).bind(name, company, updates, CONSENT_TEXT, at, at, existing.id).run();
    return json(await standing(env, existing));
  }

  const hash = await ipHash(request, env);
  if (hash) {
    const since = new Date(Date.now() - 3600 * 1000).toISOString();
    const recent = await env.DB.prepare("SELECT COUNT(*) AS n FROM leads WHERE ip_hash = ? AND created_at > ?")
      .bind(hash, since).first();
    if (Number(recent ? recent.n : 0) >= SIGNUPS_PER_HOUR) {
      throw new HttpError(429, "Too many sign-ups from this network. Try again in an hour.");
    }
  }
  const lead = { id: crypto.randomUUID(), plan: "free" };
  await env.DB.prepare(
    "INSERT INTO leads (id, email, name, company, updates_opt_in, consent_text, consent_at, plan, created_at, last_seen_at, ip_hash) "
      + "VALUES (?, ?, ?, ?, ?, ?, ?, 'free', ?, ?, ?)",
  ).bind(lead.id, email, name, company, updates, CONSENT_TEXT, at, at, at, hash).run();
  return json(await standing(env, lead), 201);
}

async function me(url, env) {
  const lead = await findLead(env, url.searchParams.get("id"));
  if (!lead) throw new HttpError(404, "Unknown visitor.");
  await env.DB.prepare("UPDATE leads SET last_seen_at = ? WHERE id = ?").bind(now(), lead.id).run();
  return json(await standing(env, lead));
}

async function spend(request, env) {
  const { id } = await readJson(request);
  const lead = await findLead(env, id);
  if (!lead) throw new HttpError(404, "Unknown visitor.");
  const at = now();
  if (lead.plan === "pro") {
    await env.DB.prepare("INSERT INTO usage (lead_id, kind, created_at) VALUES (?, 'plan', ?)").bind(lead.id, at).run();
    return json({ ok: true, ...(await standing(env, lead)) });
  }
  // One statement, so two plans started at once can't both take the last credit.
  const result = await env.DB.prepare(
    "INSERT INTO usage (lead_id, kind, created_at) SELECT ?, 'plan', ? "
      + "WHERE (SELECT COUNT(*) FROM usage WHERE lead_id = ?) < ?",
  ).bind(lead.id, at, lead.id, freeDiagrams(env)).run();
  const ok = Number(result.meta.changes) > 0;
  return json({ ok, ...(await standing(env, lead)) }, ok ? 200 : 402);
}

async function waitlist(request, env) {
  const { id } = await readJson(request);
  const lead = await findLead(env, id);
  if (!lead) throw new HttpError(404, "Unknown visitor.");
  await env.DB.prepare("UPDATE leads SET pro_requested_at = COALESCE(pro_requested_at, ?) WHERE id = ?")
    .bind(now(), lead.id).run();
  return json({ ok: true, ...(await standing(env, await findLead(env, lead.id))) });
}

function csvCell(value) {
  let cell = value === null || value === undefined ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(cell)) cell = `'${cell}`; // keep spreadsheets from running formulas
  return /[",\n\r]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell;
}

async function leadsCsv(request, env) {
  if (!env.ADMIN_TOKEN) throw new HttpError(404, "Not found.");
  if (!(await sameSecret(request.headers.get("Authorization") || "", `Bearer ${env.ADMIN_TOKEN}`))) {
    throw new HttpError(401, "Wrong or missing token.");
  }
  const { results } = await env.DB.prepare(
    "SELECT l.created_at, l.name, l.company, l.email, l.updates_opt_in, l.plan, l.pro_requested_at, "
      + "l.last_seen_at, COUNT(u.id) AS diagrams FROM leads l LEFT JOIN usage u ON u.lead_id = l.id "
      + "GROUP BY l.id ORDER BY l.created_at",
  ).all();
  const columns = ["created_at", "name", "company", "email", "updates_opt_in", "plan", "pro_requested_at", "last_seen_at", "diagrams"];
  const lines = [columns.join(","), ...results.map((row) => columns.map((c) => csvCell(row[c])).join(","))];
  return new Response(`${lines.join("\r\n")}\r\n`, {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": 'attachment; filename="clarchy-leads.csv"',
      "cache-control": "no-store",
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      if (request.method === "POST" && !sameOrigin(request)) {
        throw new HttpError(403, "Requests from other sites are not allowed.");
      }
      switch (`${request.method} ${url.pathname}`) {
        case "GET /api/config":
          return json({ accounts: accountsOn(env), free_diagrams: freeDiagrams(env) });
        case "POST /api/signup":
          return await signup(request, env);
        case "GET /api/me":
          return await me(url, env);
        case "POST /api/spend":
          return await spend(request, env);
        case "POST /api/waitlist":
          return await waitlist(request, env);
        case "GET /api/admin/leads.csv":
          return await leadsCsv(request, env);
        default:
          throw new HttpError(404, "Not found.");
      }
    } catch (err) {
      if (err instanceof HttpError) return json({ error: err.message }, err.status);
      console.error(err);
      return json({ error: "Something went wrong. Try again in a moment." }, 500);
    }
  },
};
