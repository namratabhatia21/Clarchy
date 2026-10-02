"use strict";

// Sign-up, free-diagram credits and the Pro waitlist, backed by the API of the Worker that
// serves clarchy.com (worker/index.mjs). Accounts are on only when that API answers
// /api/config; on a copy without it (GitHub Pages, `clarchy serve`, a fragment host) nothing
// is gated. When the API has trouble mid-visit the page fails open: planning keeps working.

const Access = (() => {
  const { $, store, recall } = CA;
  const KEY = "clarchy.lead";
  const CONTACT = "mailto:namrata.bhatia@clarchy.com?subject=Clarchy%20Pro";
  const state = { enabled: false, freeDiagrams: 3, lead: null };
  let asking = null; // { promise, resolve } while the sign-up form is open
  let replayTarget = null;

  async function call(method, path, body) {
    const res = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch { /* not JSON */ }
    return { status: res.status, ok: res.ok, data };
  }

  function remember(standing) {
    state.lead = standing && standing.id ? standing : null;
    store(KEY, state.lead);
    render();
  }

  // ---------- what the page shows ----------
  function render() {
    for (const count of document.querySelectorAll("[data-free-count]")) count.textContent = String(state.freeDiagrams);
    const line = $("credit-line");
    const lead = state.lead;
    line.hidden = !state.enabled;
    if (state.enabled) {
      let text;
      if (!lead) text = `Your first ${CA.plural(state.freeDiagrams, "diagram")} are free.`;
      else if (lead.plan === "pro") text = "Pro: unlimited diagrams.";
      else if (lead.remaining > 0) text = `${lead.remaining} of ${CA.plural(lead.free_diagrams, "free diagram")} left.`;
      else text = "No free diagrams left. Samples, examples and re-planning stay free.";
      line.replaceChildren(text, " ", CA.el("a", { href: "#pricing", text: "Pricing" }));
    }
    const status = $("waitlist-status");
    const button = $("waitlist-button");
    const waitlisted = Boolean(lead && (lead.waitlisted || lead.plan === "pro"));
    status.hidden = !waitlisted;
    status.textContent = lead && lead.plan === "pro" ? "Pro is on for your account." : "You're on the list. We'll email you when Pro opens.";
    button.hidden = waitlisted;
  }

  // ---------- the sign-up form ----------
  function formError(message) {
    const box = $("signup-error");
    box.hidden = !message;
    box.textContent = message || "";
  }

  function finishAsking(ok) {
    if (!asking) return;
    const { resolve } = asking;
    asking = null;
    resolve(ok);
  }

  // Resolves true once the visitor has signed up (at once if they already have), false if
  // they close the form.
  function ask() {
    if (!state.enabled || state.lead) return Promise.resolve(true);
    if (!asking) {
      let resolve;
      const promise = new Promise((r) => { resolve = r; });
      asking = { promise, resolve };
      formError("");
      $("signup-dialog").showModal();
      $("signup-form").elements.name.focus();
    }
    return asking.promise;
  }

  async function submitSignup(e) {
    e.preventDefault();
    const form = $("signup-form");
    if (!form.reportValidity()) return;
    const f = form.elements;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    formError("");
    try {
      const res = await call("POST", "/api/signup", {
        name: f.name.value, company: f.company.value, email: f.email.value,
        updates: f.updates.checked, website: f.website.value,
      });
      if (res.ok) {
        remember(res.data);
      } else if (res.status < 500) {
        formError(res.data.error || "That didn't work. Check the details and try again.");
        return;
      } else {
        state.enabled = false; // the API is in trouble: don't block the visitor
        render();
      }
      // Settle before closing: the close handler would otherwise report a cancel.
      finishAsking(true);
      $("signup-dialog").close();
    } catch {
      state.enabled = false;
      render();
      finishAsking(true);
      $("signup-dialog").close();
    } finally {
      button.disabled = false;
    }
  }

  // ---------- the first action on the home page asks who you are ----------
  function interactive(target) {
    const node = target.closest("button, a, input, textarea, select, label, summary");
    if (!node || node.closest(".scroll-cue, #signup-dialog")) return null;
    return node;
  }

  function replay(node) {
    if (node.matches("textarea, input:not([type='file']):not([type='checkbox']), select")) node.focus();
    else node.click();
  }

  function bindGate() {
    const root = $("plan-start");
    const intercept = (e) => {
      if (!state.enabled || state.lead) return;
      const node = e.type === "drop" ? root : interactive(e.target);
      if (!node) return;
      e.preventDefault();
      e.stopPropagation();
      if (e.type === "focusin") e.target.blur();
      if (e.type !== "drop") replayTarget = node;
      ask().then((ok) => {
        const target = replayTarget;
        replayTarget = null;
        if (ok && target && target !== root) replay(target);
      });
    };
    for (const type of ["mousedown", "click", "focusin", "drop"]) root.addEventListener(type, intercept, true);
  }

  function bindDialogs() {
    const signup = $("signup-dialog");
    $("signup-form").addEventListener("submit", submitSignup);
    signup.addEventListener("close", () => finishAsking(Boolean(state.lead)));
    const limit = $("limit-dialog");
    for (const dialog of [signup, limit]) {
      for (const closer of dialog.querySelectorAll("[data-close]")) closer.addEventListener("click", () => dialog.close());
      // A click on the backdrop closes the dialog.
      dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
    }
    $("limit-waitlist").addEventListener("click", async () => {
      const result = await joinWaitlist();
      if (result === "joined") $("limit-text").textContent = "You're on the Pro waitlist. We'll email you when it opens.";
    });
    $("waitlist-button").addEventListener("click", joinWaitlist);
  }

  // ---------- credits and the waitlist ----------
  function showLimit() {
    $("limit-title").textContent = `You've used your ${CA.plural(state.freeDiagrams, "free diagram")}`;
    $("limit-text").textContent = "Samples, examples and re-planning a design stay free. Pro, with unlimited diagrams, is in early access.";
    $("limit-waitlist").hidden = Boolean(state.lead && state.lead.waitlisted);
    $("limit-dialog").showModal();
  }

  // Before a plan from the visitor's own brief. True when it may go ahead.
  async function spend({ retried = false } = {}) {
    if (!state.enabled) return true;
    if (!(await ask())) return false;
    if (!state.enabled || !state.lead) return true;
    try {
      const res = await call("POST", "/api/spend", { id: state.lead.id });
      if (res.ok) { remember(res.data); return true; }
      if (res.status === 402) { remember(res.data); showLimit(); return false; }
      if (res.status === 404 && !retried) { remember(null); return spend({ retried: true }); }
      return true;
    } catch {
      return true;
    }
  }

  async function joinWaitlist() {
    if (!state.enabled) { window.location.href = CONTACT; return "mail"; }
    if (!(await ask()) || !state.lead) return "cancelled";
    try {
      const res = await call("POST", "/api/waitlist", { id: state.lead.id });
      if (res.ok) { remember(res.data); return "joined"; }
    } catch { /* below */ }
    window.location.href = CONTACT;
    return "mail";
  }

  async function init() {
    bindDialogs();
    render();
    if (CA.MODE !== "static") return;
    try {
      const res = await call("GET", "/api/config");
      if (!res.ok || !res.data.accounts) return;
      state.enabled = true;
      state.freeDiagrams = res.data.free_diagrams;
    } catch {
      return;
    }
    const saved = recall(KEY);
    state.lead = saved && saved.id ? saved : null;
    if (state.lead) {
      try {
        const res = await call("GET", `/api/me?id=${encodeURIComponent(state.lead.id)}`);
        if (res.ok) remember(res.data);
        else if (res.status === 404) remember(null);
      } catch { /* keep the saved copy */ }
    }
    bindGate();
    render();
  }

  return { init, spend, ask, joinWaitlist, get enabled() { return state.enabled; } };
})();
