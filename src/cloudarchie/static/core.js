"use strict";

// CloudArchie front end, shared helpers and data access.
// Three ways to get data:
//   server  - same-origin API (cloudarchie serve)
//   remote  - an API hosted elsewhere (window.CLOUDARCHIE_API_BASE, set at export time)
//   static  - everything embedded in the page (window.CLOUDARCHIE_DATA); plans are recorded runs
// User-provided text is always inserted with textContent, never as HTML.

const CA = (() => {
  const DATA = window.CLOUDARCHIE_DATA || null;
  const API_BASE = (window.CLOUDARCHIE_API_BASE || "").replace(/\/$/, "");
  const MODE = API_BASE ? "remote" : DATA ? "static" : "server";

  const $ = (id) => document.getElementById(id);

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false || child === "") continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function fill(node, ...children) {
    node.replaceChildren();
    return append(node, children);
  }

  function store(key, value) {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(value));
    } catch { /* storage is a convenience only */ }
  }
  function recall(key) {
    try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
  }

  function setHash(hash) {
    try { history.replaceState(null, "", hash); } catch { /* some frames refuse; harmless */ }
  }

  const number = (v) => (typeof v === "number" ? v.toLocaleString("en-US") : String(v));
  const plural = (n, word, many = `${word}s`) => `${number(n)} ${n === 1 ? word : many}`;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function getJSON(path) {
    const res = await fetch(API_BASE + path);
    if (!res.ok) throw new Error(`${path}: ${res.status}`);
    return res.json();
  }

  function staticSpecKey(specYaml) {
    return DATA && DATA.spec_index ? DATA.spec_index[specYaml] : undefined;
  }

  // Reads a text/event-stream response body and calls onEvent for every event.
  async function readEvents(res, onEvent) {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const data = chunk.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
        if (data) onEvent(JSON.parse(data));
      }
    }
  }

  const api = {
    mode: MODE,
    meta: () => (MODE === "static" ? DATA.meta : getJSON("/api/meta")),
    samples: () => (MODE === "static" ? DATA.samples : getJSON("/api/samples")),
    patterns: () => (MODE === "static" ? DATA.patterns : getJSON("/api/patterns")),
    catalog: () => (MODE === "static" ? DATA.catalog : getJSON("/api/catalog")),
    async pattern(id) {
      if (MODE === "static") {
        const yaml = DATA.pattern_yaml[id];
        return yaml === undefined ? null : { id, spec_yaml: yaml };
      }
      try { return await getJSON(`/api/patterns/${encodeURIComponent(id)}`); } catch { return null; }
    },
    async design(specYaml, provider) {
      if (MODE === "static") {
        const key = staticSpecKey(specYaml);
        const body = key && DATA.designs[`${key}.${provider}`];
        return body
          ? { ok: true, body }
          : { ok: false, body: { errors: [{ where: "demo", message: "This public demo shows the built-in examples and samples. Run cloudarchie serve to edit specs." }] } };
      }
      try {
        const res = await fetch(API_BASE + "/api/design", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ spec_yaml: specYaml, provider }),
        });
        return { ok: res.ok, body: await res.json() };
      } catch (err) {
        return { ok: false, body: { errors: [{ where: "network", message: String(err) }] } };
      }
    },
    // Runs a plan; onEvent receives every pipeline event. Resolves when the stream ends.
    async plan({ text, file, mode, region, sampleId }, onEvent) {
      if (MODE === "static") {
        const run = sampleId && DATA.runs[sampleId];
        if (!run) {
          onEvent({ type: "error", message: "This public demo can only replay the samples. Run CloudArchie yourself to plan your own app." });
          return;
        }
        for (const event of run.events) {
          await sleep(event.type === "stage" && event.status === "running" ? 420 : 160);
          onEvent(event);
        }
        return;
      }
      const form = new FormData();
      if (file) form.append("file", file, file.name);
      else form.append("text", text || "");
      form.append("mode", mode || "auto");
      if (region) form.append("region", region);
      let res;
      try {
        res = await fetch(API_BASE + "/api/plan", { method: "POST", body: form });
      } catch (err) {
        onEvent({ type: "error", message: `Could not reach the server: ${err}` });
        return;
      }
      if (!res.ok) {
        let message = res.statusText;
        try { message = (await res.json()).errors.map((e) => e.message).join(" "); } catch { /* keep status */ }
        onEvent({ type: "error", message });
        return;
      }
      await readEvents(res, onEvent);
    },
  };

  // Downloads work everywhere except sandboxed hosts, which get clipboard copies instead.
  const CLIPBOARD_ONLY = Boolean(DATA && DATA.clipboard_only);
  async function deliver({ filename, text, type, label, status }) {
    if (!CLIPBOARD_ONLY) {
      const url = URL.createObjectURL(new Blob([text], { type }));
      const a = el("a", { href: url, download: filename });
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = `${label} copied`;
    } catch {
      status.textContent = "Copying is blocked here";
    }
    setTimeout(() => { status.textContent = ""; }, 2500);
  }

  const FIDELITY_HELP = {
    exact: "Same concept with comparable features on this provider.",
    close: "Does the same job, with differences worth knowing (see note).",
    partial: "Covers part of the capability; something else is needed for the rest.",
  };
  function fidelityBadge(f) {
    return f ? el("span", { class: `badge ${f}`, title: FIDELITY_HELP[f], text: f }) : null;
  }

  // Colours that identify each provider in pills and labels (not their logos).
  const PROVIDER_COLOURS = { aws: "#ff9900", azure: "#0078d4", gcp: "#1a73e8", oss: "#0d9488" };
  const STAGE_COLOURS = {
    code: "#3B48CC", build: "#6D28D9", ship: "#0E7490", serve: "#8C4FFF",
    run: "#ED7100", integrate: "#E7157B", store: "#1D7A02", operate: "#DD344C",
  };

  return {
    DATA, MODE, CLIPBOARD_ONLY, $, el, fill, store, recall, setHash, number, plural, sleep,
    api, deliver, fidelityBadge, FIDELITY_HELP, PROVIDER_COLOURS, STAGE_COLOURS,
    meta: null, // filled in by app.js
  };
})();
