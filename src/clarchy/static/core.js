"use strict";

// Clarchy front end, shared helpers and data access.
// Three ways to get data:
//   server  - same-origin API (clarchy serve)
//   remote  - an API hosted elsewhere (window.CLARCHY_API_BASE, set at export time)
//   static  - everything embedded in the page (window.CLARCHY_DATA); plans are recorded runs
// User-provided text is always inserted with textContent, never as HTML.

const CA = (() => {
  const DATA = window.CLARCHY_DATA || null;
  const API_BASE = (window.CLARCHY_API_BASE || "").replace(/\/$/, "");
  const MODE = API_BASE ? "remote" : DATA ? "static" : "server";

  const $ = (id) => document.getElementById(id);

  // What this page can do. A static build plans in the browser when it carries the engine.
  const HF_DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct";
  const canPlan = () => MODE !== "static" || Boolean(DATA.engine);
  const canEdit = canPlan;
  const hasRecordedRun = (id) => MODE === "static" && Boolean(DATA.runs && DATA.runs[id]);

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

  // ---------- the in-browser engine (static site) ----------
  // Pyodide runs Clarchy's own Python package in the page, so a static site can plan
  // any text or document. It loads on first use (about 15 MB, cached by the browser).
  const engine = { loading: null, py: null, module: null };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = src;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`could not load ${src}`));
      document.head.append(script);
    });
  }

  function startEngine(progress = () => {}) {
    if (!engine.loading) {
      engine.loading = (async () => {
        const cfg = DATA.engine;
        progress("Downloading the planning engine…");
        if (!window.loadPyodide) await loadScript(cfg.pyodide);
        const py = await window.loadPyodide({ indexURL: cfg.index_url });
        progress("Loading Python packages…");
        await py.loadPackage(cfg.packages);
        const res = await fetch(cfg.bundle);
        if (!res.ok) throw new Error(`could not load ${cfg.bundle} (${res.status})`);
        py.unpackArchive(await res.arrayBuffer(), "zip", { extractDir: "/home/pyodide/engine" });
        py.runPython("import sys; sys.path.insert(0, '/home/pyodide/engine')");
        engine.py = py;
        engine.module = py.pyimport("clarchy.browser");
        return engine;
      })();
      engine.loading.catch(() => { engine.loading = null; });
    }
    return engine.loading;
  }

  async function planInBrowser({ text, file, mode, region, hf }, onEvent) {
    const progress = (t) => onEvent({ type: "progress", text: t });
    try {
      const eng = await startEngine(progress);
      const request = { text, mode: mode === "hf" ? "hf" : "rules", region: region || null, hf: hf || null };
      if (file) {
        const path = `/tmp/upload-${Date.now()}`;
        eng.py.FS.writeFile(path, new Uint8Array(await file.arrayBuffer()));
        request.file_path = path;
        request.file_name = file.name;
        if (/\.pdf$/i.test(file.name)) {
          progress("Loading the PDF reader…");
          await eng.py.loadPackage("micropip");
          await eng.py.runPythonAsync("import micropip\nawait micropip.install('pypdf')");
        }
      }
      progress("Planning…");
      await eng.module.plan(JSON.stringify(request), (json) => onEvent(JSON.parse(json)));
    } catch (err) {
      onEvent({ type: "error", message: `The in-browser engine failed: ${err.message || err}` });
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
        if (body) return { ok: true, body };
        if (!DATA.engine) {
          return { ok: false, body: { errors: [{ where: "demo", message: "This build shows the built-in examples and samples only. Run clarchy serve to edit specs." }] } };
        }
        try {
          const eng = await startEngine();
          return JSON.parse(eng.module.design(specYaml, provider));
        } catch (err) {
          return { ok: false, body: { errors: [{ where: "engine", message: String(err.message || err) }] } };
        }
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
    async plan({ text, file, mode, region, sampleId, hf }, onEvent) {
      if (MODE === "static") {
        const run = sampleId && DATA.runs[sampleId];
        if (run) {
          for (const event of run.events) {
            await sleep(event.type === "stage" && event.status === "running" ? 380 : 140);
            onEvent(event);
          }
          return;
        }
        if (!DATA.engine) {
          onEvent({ type: "error", message: "This build can only replay the samples. Run Clarchy yourself to plan your own app." });
          return;
        }
        await planInBrowser({ text, file, mode, region, hf }, onEvent);
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
  const FIDELITY_LABEL = { exact: "Exact match", close: "Close match", partial: "Partial match" };
  // Every match level, for detail panels.
  function fidelityBadge(f) {
    return f ? el("span", { class: `tag ${f}`, title: FIDELITY_HELP[f], text: FIDELITY_LABEL[f] }) : null;
  }
  // Only the matches worth a second look, for lists: "exact" is the quiet default.
  function fidelityTag(f) {
    return f && f !== "exact" ? el("span", { class: `tag ${f}`, title: FIDELITY_HELP[f], text: f === "close" ? "Close" : "Partial" }) : null;
  }

  // Diagrams carry their own title and notice for downloads; on the page those repeat what
  // is already shown, so crop the view to the diagram body.
  function cropDiagram(svg) {
    if (!svg || !svg.dataset || !svg.dataset.bodyTop) return svg;
    const top = Number(svg.dataset.bodyTop);
    const bottom = Number(svg.dataset.bodyBottom);
    const width = Number(svg.getAttribute("width"));
    if (!(bottom > top) || !width) return svg;
    svg.setAttribute("viewBox", `0 ${top} ${width} ${bottom - top}`);
    svg.setAttribute("height", String(bottom - top));
    return svg;
  }
  // The diagram body without its title and footer; `transparent` drops the white
  // background so the drawing sits on the page's gridded paper.
  function croppedSvgText(text, { transparent = false } = {}) {
    const doc = new DOMParser().parseFromString(text, "image/svg+xml");
    const svg = doc.documentElement;
    if (svg.nodeName !== "svg") return text;
    cropDiagram(svg);
    if (transparent) for (const bg of svg.querySelectorAll(".ca-bg")) bg.remove();
    return new XMLSerializer().serializeToString(svg);
  }

  function money(value, { cents = false } = {}) {
    if (value === null || value === undefined) return "–";
    const digits = cents || Math.abs(value) < 10 ? 2 : 0;
    return value.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  // Colours that identify each provider in pills and labels (not their logos).
  const PROVIDER_COLOURS = { aws: "#ff9900", azure: "#0078d4", gcp: "#1a73e8", oss: "#0d9488" };
  const STAGE_COLOURS = {
    code: "#3B48CC", build: "#6D28D9", ship: "#0E7490", serve: "#8C4FFF",
    run: "#ED7100", integrate: "#E7157B", store: "#1D7A02", operate: "#DD344C",
  };

  return {
    DATA, MODE, CLIPBOARD_ONLY, HF_DEFAULT_MODEL, canPlan, canEdit, hasRecordedRun,
    $, el, fill, store, recall, setHash, number, plural, sleep,
    api, deliver, fidelityBadge, fidelityTag, FIDELITY_HELP, FIDELITY_LABEL, cropDiagram, croppedSvgText, money,
    PROVIDER_COLOURS, STAGE_COLOURS,
    meta: null, // filled in by app.js
  };
})();
