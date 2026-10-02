"use strict";

// Sign-up, log-in, free-diagram credits and the Pro waitlist, backed by the API of the
// Worker that serves clarchy.com (worker/index.mjs). The header's account button works
// whenever that API answers /api/config. The first action on the home page asks who you are,
// and free diagrams are counted, only while accounts are on there; on a copy without the API
// (GitHub Pages, `clarchy serve`, a fragment host) the button hides and nothing is gated.
// When the API has trouble mid-visit the page fails open: planning keeps working.

const Access = (() => {
  const { $, store, recall } = CA;
  const KEY = "clarchy.lead";
  const CONTACT = "mailto:namrata.bhatia@clarchy.com?subject=Clarchy%20Pro";
  // api: the Worker's API answered, so visitors can sign up and log in.
  // enabled: accounts are on, so the home page asks first and free diagrams are counted.
  // settled: the API was asked and accounts are off (or failed), so no credit line will show.
  const state = { api: false, enabled: false, settled: false, freeDiagrams: 3, lead: null };
  let asking = null; // { promise, resolve } while the sign-up form is open
  let PERSON = ""; // the account button's person outline, shown while nobody is logged in
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

  // Keeps the visitor's standing, and the name and email they typed on this device (the API
  // never sends them back), so the header can say who is logged in.
  function remember(standing, profile = {}) {
    const before = state.lead;
    const kept = before && standing && before.id === standing.id ? { name: before.name, email: before.email } : {};
    state.lead = standing && standing.id ? { ...standing, ...kept, ...profile } : null;
    store(KEY, state.lead);
    render();
  }

  // ---------- what the page shows ----------
  function render() {
    for (const count of document.querySelectorAll("[data-free-count]")) count.textContent = String(state.freeDiagrams);
    // The page keeps the credit line's space until the API answers (site.py), so it
    // appears without moving anything.
    const line = $("credit-line");
    const lead = state.lead;
    if (line && state.enabled) {
      let text;
      if (!lead) text = `Your first ${CA.plural(state.freeDiagrams, "diagram")} are free.`;
      else if (lead.plan === "pro") text = "Pro: unlimited diagrams.";
      else if (lead.remaining > 0) text = `${lead.remaining} of ${CA.plural(lead.free_diagrams, "free diagram")} left.`;
      else text = "No free diagrams left. Samples, examples and re-planning stay free.";
      line.replaceChildren(text, " ", CA.el("a", { href: CA.href("pricing"), text: "Pricing" }));
      line.classList.remove("pending");
      line.hidden = false;
    } else if (line && state.settled) {
      line.hidden = true;
    }
    const status = $("waitlist-status");
    const button = $("waitlist-button");
    const waitlisted = Boolean(lead && (lead.waitlisted || lead.plan === "pro"));
    if (status) {
      status.hidden = !waitlisted;
      status.textContent = lead && lead.plan === "pro" ? "Pro is on for your account." : "You're on the list. We'll email you when Pro opens.";
    }
    if (button) button.hidden = waitlisted;
    renderAccount();
  }

  // ---------- the header's account button ----------
  function renderAccount() {
    const account = $("account");
    if (!account) return;
    account.hidden = state.settled && !state.api;
    const lead = state.lead;
    const name = lead && (lead.name || (lead.email || "").split("@")[0]);
    const button = $("account-button");
    button.classList.toggle("signed-in", Boolean(lead));
    $("account-label").textContent = lead ? (name ? name.split(" ")[0] : "Account") : "Log in / Sign up";
    button.setAttribute("aria-label", lead ? `Account${name ? ` of ${name}` : ""}` : "Log in or sign up");
    const mark = $("account-mark");
    if (lead && name) mark.textContent = name.trim().charAt(0).toUpperCase();
    else if (!mark.querySelector("svg")) mark.innerHTML = PERSON;
    if (!lead) closeMenu();
    $("account-name").textContent = lead ? lead.name || "" : "";
    $("account-email").textContent = lead ? lead.email || "" : "";
    let plan = "";
    if (lead && lead.plan === "pro") plan = "Pro: unlimited diagrams";
    else if (lead && state.enabled) plan = `${lead.remaining} of ${CA.plural(lead.free_diagrams, "free diagram")} left`;
    else if (lead) plan = "Free plan";
    $("account-plan").textContent = plan;
  }

  function closeMenu() {
    const menu = $("account-menu");
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    $("account-button").setAttribute("aria-expanded", "false");
  }

  function bindAccount() {
    const button = $("account-button");
    if (!button || button.dataset.bound) return;
    button.dataset.bound = "true";
    PERSON = $("account-mark").innerHTML;
    button.addEventListener("click", () => {
      if (!state.lead) { open("signup", "Sign up"); return; }
      const menu = $("account-menu");
      menu.hidden = !menu.hidden;
      button.setAttribute("aria-expanded", String(!menu.hidden));
    });
    $("account-logout").addEventListener("click", () => {
      remember(null);
      button.focus();
    });
    $("account-menu").addEventListener("click", (e) => { if (e.target.closest("a")) closeMenu(); });
    document.addEventListener("click", (e) => { if (!e.target.closest("#account")) closeMenu(); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("account-menu").hidden) { closeMenu(); button.focus(); }
    });
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

  // The form signs up (name, company, email) or logs in (email only).
  function setMode(mode) {
    const form = $("signup-form");
    form.dataset.mode = mode;
    for (const button of $("form-modes").querySelectorAll("button")) {
      button.setAttribute("aria-pressed", String(button.dataset.mode === mode));
    }
    // Hidden fields are disabled, so the browser doesn't ask for them.
    for (const field of form.querySelectorAll("[data-signup-only]")) {
      field.hidden = mode === "login";
      for (const input of field.querySelectorAll("input")) input.disabled = mode === "login";
    }
    if (mode === "login") {
      $("signup-title").textContent = "Log in";
      $("signup-lead").textContent = "Use the email you signed up with. Your account and free diagrams carry over to this device.";
    } else {
      $("signup-title").textContent = form.dataset.title || "Sign up";
      $("signup-lead").textContent = state.enabled
        ? `Clarchy is in early access. Tell us who you are and your first ${CA.plural(state.freeDiagrams, "diagram")} are free.`
        : "Clarchy is in early access. Tell us who you are and we'll keep your account for when Pro opens.";
    }
    $("signup-submit").textContent = mode === "login" ? "Log in" : "Continue";
    formError("");
  }

  // Opens the form; resolves true once the visitor is signed up or logged in, false if they
  // close it.
  function open(mode, title) {
    if (!asking) {
      let resolve;
      const promise = new Promise((r) => { resolve = r; });
      asking = { promise, resolve };
      closeMenu();
      $("signup-form").dataset.title = title;
      setMode(mode);
      $("signup-dialog").showModal();
      $("signup-form").elements[mode === "login" ? "email" : "name"].focus();
    }
    return asking.promise;
  }

  // Before an action that needs an account: resolves true at once if accounts are off or the
  // visitor already has one.
  function ask() {
    if (!state.enabled || state.lead) return Promise.resolve(true);
    return open("signup", "Before you start");
  }

  async function submitSignup(e) {
    e.preventDefault();
    const form = $("signup-form");
    if (!form.reportValidity()) return;
    const f = form.elements;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    formError("");
    const login = form.dataset.mode === "login";
    try {
      const res = login
        ? await call("POST", "/api/login", { email: f.email.value, website: f.website.value })
        : await call("POST", "/api/signup", {
          name: f.name.value, company: f.company.value, email: f.email.value,
          updates: f.updates.checked, website: f.website.value,
        });
      if (res.ok) {
        const email = f.email.value.trim().toLowerCase();
        remember(res.data, login ? { email } : { name: f.name.value.trim(), email });
      } else if (res.status < 500 || (login && res.status === 503 && res.data.error)) {
        formError(res.data.error || "That didn't work. Check the details and try again.");
        return;
      } else {
        throw new Error(`API ${res.status}`);
      }
      // Settle before closing: the close handler would otherwise report a cancel.
      finishAsking(true);
      $("signup-dialog").close();
    } catch {
      if (!state.enabled) {
        // Nothing waits on this form (it was opened from the header): say so and stay.
        formError("Clarchy can't reach its server right now. Try again in a moment.");
        return;
      }
      state.enabled = false; // the API is in trouble: don't block the visitor
      state.settled = true;
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
    if (!node || node.closest(".poster, #signup-dialog")) return null;
    return node;
  }

  function replay(node) {
    if (node.matches("textarea, input:not([type='file']):not([type='checkbox']), select")) node.focus();
    else node.click();
  }

  function bindGate() {
    const root = $("plan-start");
    if (!root || root.dataset.gated) return;
    root.dataset.gated = "true";
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
    for (const button of $("form-modes").querySelectorAll("button")) {
      button.addEventListener("click", () => {
        setMode(button.dataset.mode);
        $("signup-form").elements.email.focus();
      });
    }
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
  }

  // Called whenever a page appears (app.js): the home page's first action asks who you
  // are, and Pricing's waitlist button works.
  function attach() {
    const button = $("waitlist-button");
    if (button && !button.dataset.bound) {
      button.dataset.bound = "true";
      button.addEventListener("click", joinWaitlist);
    }
    if (state.enabled) bindGate();
    render();
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
    if (!state.api) { window.location.href = CONTACT; return "mail"; }
    if (!state.lead && !(await open("signup", "Join the Pro waitlist"))) return "cancelled";
    if (!state.lead) return "cancelled";
    try {
      const res = await call("POST", "/api/waitlist", { id: state.lead.id });
      if (res.ok) { remember(res.data); return "joined"; }
    } catch { /* below */ }
    window.location.href = CONTACT;
    return "mail";
  }

  async function init() {
    bindDialogs();
    bindAccount();
    const off = () => { state.settled = true; render(); };
    if (CA.MODE !== "static") { off(); return; }
    try {
      const res = await call("GET", "/api/config");
      if (!res.ok || typeof res.data.accounts !== "boolean") { off(); return; }
      state.api = true;
      state.enabled = res.data.accounts;
      state.settled = !state.enabled;
      state.freeDiagrams = res.data.free_diagrams;
    } catch {
      off();
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
    attach();
  }

  return { init, attach, spend, ask, open, joinWaitlist, get enabled() { return state.enabled; } };
})();
