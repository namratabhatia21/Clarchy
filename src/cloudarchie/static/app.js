"use strict";

// CloudArchie UI. Everything shown comes from /api/design, which validates the spec with
// the same models as the CLI. User-provided text is always inserted with textContent.

const FIDELITY_HELP = {
  exact: "Same concept with comparable features on this provider.",
  close: "Does the same job, with differences worth knowing (see note).",
  partial: "Covers part of the capability; something else is needed for the rest.",
};
const TIER_NAMES = {
  external: "Outside the cloud", edge: "Edge", entry: "Entry point", compute: "Compute",
  integration: "Integration", data: "Data", platform: "Shared service",
};
const DRAFT_KEY = "cloudarchie.draft";

const state = {
  meta: null,
  patterns: [],
  patternId: null,
  patternYaml: "",
  provider: "aws",
  design: null,
  selectedId: null,
  view: "diagram",
  requestSeq: 0,
};

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
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function store(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch { /* storage unavailable: drafts are a convenience only */ }
}
function recall(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

function formatNumber(value) {
  return typeof value === "number" ? value.toLocaleString("en-US") : String(value);
}

function download(filename, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function slug() {
  return (state.design?.name || state.patternId || "architecture").toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

// ---------- rendering ----------

function renderProviders() {
  const nav = $("provider-tabs");
  nav.replaceChildren(...state.meta.providers.map((p) =>
    el("button", {
      class: "provider-tab", type: "button", role: "tab",
      "aria-selected": String(p.id === state.provider),
      disabled: !p.enabled,
      title: p.enabled ? `Show on ${p.name}` : `${p.name} mapping is planned`,
      onclick: () => { state.provider = p.id; renderProviders(); runDesign(); },
    }, p.name, p.reviewed ? null : el("span", { class: "unreviewed", title: "Not yet reviewed by a specialist", text: "●" })),
  ));
}

function renderPatternList() {
  $("pattern-list").replaceChildren(...state.patterns.map((p) =>
    el("li", {}, el("button", {
      class: "pattern-card", type: "button",
      "aria-current": String(p.id === state.patternId),
      onclick: () => loadPattern(p.id),
    }, el("strong", { text: p.name }), el("span", { text: p.summary || "" }))),
  ));
}

function renderReference() {
  $("ref-capabilities").replaceChildren(...Object.entries(state.meta.capabilities).flatMap(([name, cap]) => [
    el("dt", { text: name }), el("dd", { text: `${TIER_NAMES[cap.tier]}: ${cap.description}` }),
  ]));
  $("ref-regions").replaceChildren(...Object.entries(state.meta.regions).flatMap(([key, label]) => [
    el("dt", { text: key }), el("dd", { text: label }),
  ]));
}

function renderHeader(d) {
  $("design-name").textContent = d ? d.name : "Fix the spec to see a design";
  $("design-summary").textContent = d?.summary || "";
  const r = d?.requirements || {};
  const chips = [
    d && ["Region", d.region.code ? `${d.region.label} (${d.region.code})` : `${d.region.label} (self-hosted)`],
    r.users != null && ["Users", formatNumber(r.users)],
    r.peak_rps != null && ["Peak", `${formatNumber(r.peak_rps)} req/s`],
    r.data_gb != null && ["Data", `${formatNumber(r.data_gb)} GB`],
    r.data_growth_gb_per_month != null && ["Growth", `${formatNumber(r.data_growth_gb_per_month)} GB/mo`],
    d && ["Availability", `${r.availability_target}%`],
    r.compliance?.length && ["Compliance", r.compliance.join(", ")],
    r.monthly_budget_usd != null && ["Budget", `$${formatNumber(r.monthly_budget_usd)}/mo`],
  ].filter(Boolean);
  $("requirements").replaceChildren(...chips.map(([k, v]) => el("li", {}, el("b", { text: `${k}: ` }), v)));
  for (const id of ["dl-svg", "dl-md"]) $(id).disabled = !d;
}

function renderDiagram(d) {
  const canvas = $("diagram");
  canvas.innerHTML = d.svg; // generated server-side; all text in it is XML-escaped
  for (const node of canvas.querySelectorAll("g.node")) {
    const id = node.dataset.id;
    const comp = d.components.find((c) => c.id === id);
    node.setAttribute("tabindex", "0");
    node.setAttribute("role", "button");
    node.setAttribute("aria-label", comp.service ? `${comp.service}: ${comp.label}` : comp.label);
    node.addEventListener("click", () => select(id));
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(id); }
    });
  }
  $("icon-note").textContent = d.official_icons
    ? "Using the official icon package configured on the server."
    : d.kind === "self-hosted"
      ? "Lettered badges are used for open-source software."
      : `Lettered badges stand in for official icons (set CLOUDARCHIE_ICONS_${d.provider.toUpperCase()} on the server to use them).`;
}

function fidelityBadge(f) {
  return f ? el("span", { class: `badge ${f}`, title: FIDELITY_HELP[f], text: f }) : el("span", { class: "muted", text: "—" });
}

function renderServices(d) {
  $("services-body").replaceChildren(...d.components.map((c) =>
    el("tr", { "data-id": c.id, onclick: () => select(c.id), class: c.id === state.selectedId ? "selected" : null },
      el("td", {}, el("strong", { text: c.label })),
      el("td", { text: c.service || "Outside the cloud" }),
      el("td", {}, el("code", { text: c.capability })),
      el("td", {}, fidelityBadge(c.fidelity)),
      el("td", {}, c.rationale
        ? c.rationale
        : el("span", { class: "muted" }, el("span", { class: "badge generic", text: "generic" }), " ", c.capability_description)),
    )));
}

function renderInspector() {
  const d = state.design;
  const comp = d?.components.find((c) => c.id === state.selectedId);
  const panel = $("inspector");
  panel.hidden = !comp;
  document.querySelector(".layout").classList.toggle("inspecting", Boolean(comp));
  for (const node of document.querySelectorAll("#diagram g.node")) {
    node.classList.toggle("selected", node.dataset.id === state.selectedId);
  }
  for (const row of document.querySelectorAll("#services-body tr")) {
    row.classList.toggle("selected", row.dataset.id === state.selectedId);
  }
  if (!comp) return;

  const byId = Object.fromEntries(d.components.map((c) => [c.id, c]));
  const name = (id) => byId[id].service ? `${byId[id].label} (${byId[id].service})` : byId[id].label;
  const sizing = Object.entries(comp.sizing || {});

  // el() drops empty children; replaceChildren() would print them as "null"/"false".
  $("inspector-body").replaceChildren(el("div", {},
    el("h3", { text: comp.service || comp.label }),
    el("p", { class: "sub", text: comp.service ? comp.label : "Outside the cloud" }),
    el("div", { class: "row" },
      el("span", { class: "badge tier", text: TIER_NAMES[comp.tier] }),
      el("code", { text: comp.capability }),
      comp.fidelity && fidelityBadge(comp.fidelity)),

    el("h4", { text: "Why this choice" }),
    comp.rationale
      ? el("p", { text: comp.rationale })
      : el("p", { class: "note" }, el("b", { text: "Generic reason only. " }),
        `${comp.capability_description} No pattern-specific rationale has been written for this component yet.`),

    comp.fidelity && el("h4", { text: "How close is the match" }),
    comp.fidelity && el("p", { text: FIDELITY_HELP[comp.fidelity] }),
    comp.note && el("p", { class: "note", text: comp.note }),

    comp.alternatives.length > 0 && el("h4", { text: "Alternatives to consider" }),
    comp.alternatives.length > 0 && el("ul", {}, comp.alternatives.map((a) => el("li", { text: a }))),

    comp.connections.length > 0 && el("h4", { text: "Connections" }),
    comp.connections.length > 0 && el("ul", {}, comp.connections.map((c) =>
      el("li", { text: (c.to ? `→ ${name(c.to)}` : `← ${name(c.from)}`) + (c.label ? `: ${c.label}` : "") }))),

    el("h4", { text: "Sizing assumptions" }),
    sizing.length
      ? el("table", {}, el("tbody", {}, sizing.map(([k, v]) =>
        el("tr", {}, el("td", { text: k.replaceAll("_", " ") }), el("td", { text: formatNumber(v) })))))
      : el("p", { class: "muted", text: "None given. Cost estimates will ask for these." }),

    comp.docs && el("h4", { text: "Official documentation" }),
    comp.docs && el("p", {}, el("a", { href: comp.docs, target: "_blank", rel: "noopener noreferrer", text: comp.docs })),
  ));
}

function renderErrors(errors) {
  $("spec-errors").replaceChildren(...errors.map((e) => el("li", {}, el("b", { text: e.where }), e.message)));
  const invalid = errors.length > 0;
  $("spec-editor").classList.toggle("invalid", invalid);
  $("spec-status").classList.toggle("invalid", invalid);
  $("spec-status").title = invalid ? `${errors.length} problem(s)` : "Valid";
  const banner = $("banner");
  banner.hidden = !invalid;
  banner.textContent = invalid
    ? `The spec has ${errors.length} problem${errors.length > 1 ? "s" : ""}. ${state.design ? "Showing the last valid design, dimmed. " : ""}See the Spec tab.`
    : "";
  $("diagram").classList.toggle("stale", invalid && Boolean(state.design));
}

function setView(view) {
  state.view = view;
  for (const tab of document.querySelectorAll(".view-tab")) {
    tab.setAttribute("aria-selected", String(tab.dataset.view === view));
  }
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.dataset.view !== view;
  }
}

function select(id) {
  state.selectedId = state.selectedId === id ? null : id;
  renderInspector();
}

// ---------- data ----------

async function runDesign() {
  const seq = ++state.requestSeq;
  let response, body;
  try {
    response = await fetch("/api/design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec_yaml: $("spec-editor").value, provider: state.provider }),
    });
    body = await response.json();
  } catch (err) {
    if (seq === state.requestSeq) renderErrors([{ where: "network", message: String(err) }]);
    return;
  }
  if (seq !== state.requestSeq) return; // a newer edit superseded this response

  if (!response.ok) {
    renderErrors(body.errors || [{ where: "server", message: body.detail || response.statusText }]);
    if (!state.design) renderHeader(null);
    return;
  }
  state.design = body;
  const note = $("review-note");
  note.hidden = body.reviewed;
  note.replaceChildren(el("b", { text: "Unreviewed mappings. " }),
    `${body.provider_name} service choices have not yet been checked by a specialist. Treat them as a draft.`);
  if (!body.components.some((c) => c.id === state.selectedId)) state.selectedId = null;
  renderErrors([]);
  renderHeader(body);
  renderDiagram(body);
  renderServices(body);
  renderInspector();
}

async function loadPattern(id) {
  const res = await fetch(`/api/patterns/${encodeURIComponent(id)}`);
  if (!res.ok) return;
  const { spec_yaml } = await res.json();
  state.patternId = id;
  state.patternYaml = spec_yaml;
  state.selectedId = null;
  state.design = null;
  $("spec-editor").value = spec_yaml;
  store(DRAFT_KEY, null);
  if (currentPage() === "designer") history.replaceState(null, "", `#/designer?pattern=${id}`);
  renderPatternList();
  await runDesign();
}

let debounce;
function onEdit() {
  clearTimeout(debounce);
  debounce = setTimeout(() => {
    store(DRAFT_KEY, { patternId: state.patternId, yaml: $("spec-editor").value });
    runDesign();
  }, 350);
}

async function init() {
  const [meta, patterns] = await Promise.all([
    fetch("/api/meta").then((r) => r.json()),
    fetch("/api/patterns").then((r) => r.json()),
  ]);
  state.meta = meta;
  state.patterns = patterns;
  $("version").textContent = `CloudArchie ${meta.version}`;
  renderProviders();
  renderReference();

  for (const tab of document.querySelectorAll(".view-tab")) {
    tab.addEventListener("click", () => setView(tab.dataset.view));
  }
  $("spec-editor").addEventListener("input", onEdit);
  $("spec-editor").addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    e.preventDefault();
    const t = e.target;
    t.setRangeText("  ", t.selectionStart, t.selectionEnd, "end");
    onEdit();
  });
  $("reset-spec").addEventListener("click", () => state.patternId && loadPattern(state.patternId));
  $("custom-spec").addEventListener("click", () => setView("spec"));
  $("inspector-close").addEventListener("click", () => select(null));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.selectedId) select(null); });
  $("dl-svg").addEventListener("click", () => download(`${slug()}.${state.provider}.svg`, state.design.svg, "image/svg+xml"));
  $("dl-md").addEventListener("click", () => download(`${slug()}.${state.provider}.md`, state.design.explanation_md, "text/markdown"));
  $("dl-yaml").addEventListener("click", () => download(`${slug()}.yaml`, $("spec-editor").value, "application/yaml"));

  window.addEventListener("hashchange", route);
  initCatalogControls();
  route();
  const fromHash = hashParams().get("pattern");
  const draft = recall(DRAFT_KEY);
  const known = (id) => patterns.some((p) => p.id === id);
  if (draft?.yaml && (!fromHash || fromHash === draft.patternId)) {
    state.patternId = known(draft.patternId) ? draft.patternId : null;
    if (state.patternId) {
      const res = await fetch(`/api/patterns/${encodeURIComponent(state.patternId)}`);
      state.patternYaml = (await res.json()).spec_yaml;
    }
    $("spec-editor").value = draft.yaml;
    renderPatternList();
    await runDesign();
  } else {
    await loadPattern(known(fromHash) ? fromHash : patterns[0].id);
  }
}

// ---------- routing ----------

function hashParams() {
  const hash = location.hash.replace(/^#\/?/, "");
  const query = hash.includes("?") ? hash.slice(hash.indexOf("?") + 1) : hash;
  return new URLSearchParams(query);
}

function currentPage() {
  return location.hash.startsWith("#/catalog") ? "catalog" : "designer";
}

function route() {
  const page = currentPage();
  $("page-designer").hidden = page !== "designer";
  $("page-catalog").hidden = page !== "catalog";
  for (const link of document.querySelectorAll(".main-link")) {
    link.toggleAttribute("aria-current", link.dataset.page === page);
    if (link.dataset.page === page) link.setAttribute("aria-current", "page");
  }
  if (page === "catalog") showCatalog();
}

// ---------- service catalog ----------

const TIER_ORDER = ["edge", "entry", "compute", "integration", "data", "platform"];
const TIER_COLOURS = {
  edge: "#8C4FFF", entry: "#E7157B", compute: "#ED7100", integration: "#B0084D", data: "#3B48CC", platform: "#DD344C",
};
const MATCH_FILTERS = {
  all: { label: "All", test: () => true },
  differences: { label: "Has differences", test: (fids) => fids.some((f) => f !== "exact") },
  exact: { label: "Exact everywhere", test: (fids) => fids.every((f) => f === "exact") },
};

const cat = {
  data: null,
  loading: null,
  q: "",
  tiers: new Set(),
  providers: new Set(),
  match: "all",
  sort: "category",
  open: new Set(),
};

function tokens() {
  return cat.q.toLowerCase().split(/\s+/).filter(Boolean);
}

function visibleProviders() {
  return cat.data.providers.filter((p) => cat.providers.has(p.id));
}

function haystack(cap) {
  const parts = [cap.id, cap.id.replaceAll("-", " "), cap.description, TIER_NAMES[cap.tier]];
  for (const p of visibleProviders()) {
    const svc = cap.services[p.id];
    parts.push(svc.service, ...svc.alternatives);
  }
  return parts.join(" ").toLowerCase();
}

function matches(cap, { ignoreTier = false } = {}) {
  const toks = tokens();
  if (toks.length && !toks.every((t) => haystack(cap).includes(t))) return false;
  if (!ignoreTier && cat.tiers.size && !cat.tiers.has(cap.tier)) return false;
  const fids = visibleProviders().map((p) => cap.services[p.id].fidelity);
  return MATCH_FILTERS[cat.match].test(fids);
}

function differences(cap) {
  return visibleProviders().filter((p) => cap.services[p.id].fidelity !== "exact").length;
}

function highlight(text) {
  const toks = tokens();
  if (!toks.length) return [text];
  const lower = text.toLowerCase();
  const ranges = [];
  for (const t of toks) {
    let i = lower.indexOf(t);
    while (i !== -1) { ranges.push([i, i + t.length]); i = lower.indexOf(t, i + t.length); }
  }
  if (!ranges.length) return [text];
  ranges.sort((a, b) => a[0] - b[0]);
  const out = [];
  let pos = 0;
  for (const [a, b] of ranges) {
    if (a < pos) continue;
    if (a > pos) out.push(text.slice(pos, a));
    out.push(el("mark", { text: text.slice(a, b) }));
    pos = b;
  }
  out.push(text.slice(pos));
  return out;
}

function syncCatalogUrl() {
  const params = new URLSearchParams();
  if (cat.q) params.set("q", cat.q);
  if (cat.tiers.size) params.set("category", [...cat.tiers].join(","));
  if (cat.providers.size !== cat.data.providers.length) params.set("providers", [...cat.providers].join(","));
  if (cat.match !== "all") params.set("match", cat.match);
  if (cat.sort !== "category") params.set("sort", cat.sort);
  const qs = params.toString();
  history.replaceState(null, "", `#/catalog${qs ? `?${qs}` : ""}`);
}

function readCatalogUrl() {
  const params = hashParams();
  const ids = new Set(cat.data.providers.map((p) => p.id));
  cat.q = params.get("q") || "";
  cat.tiers = new Set((params.get("category") || "").split(",").filter((t) => TIER_ORDER.includes(t)));
  const provs = (params.get("providers") || "").split(",").filter((p) => ids.has(p));
  cat.providers = new Set(provs.length ? provs : ids);
  cat.match = MATCH_FILTERS[params.get("match")] ? params.get("match") : "all";
  cat.sort = ["category", "name", "differences"].includes(params.get("sort")) ? params.get("sort") : "category";
  $("catalog-search").value = cat.q;
  $("catalog-sort").value = cat.sort;
}

function pill(label, pressed, onclick, extra = {}) {
  return el("button", { class: "pill", type: "button", "aria-pressed": String(pressed), onclick, ...extra }, label);
}

function renderFilters() {
  const tierCounts = Object.fromEntries(TIER_ORDER.map((t) => [t, 0]));
  for (const cap of cat.data.capabilities) if (matches(cap, { ignoreTier: true })) tierCounts[cap.tier] += 1;
  $("filter-tiers").replaceChildren(...TIER_ORDER.map((t) => pill(
    [el("span", { class: "dot", style: `background:${TIER_COLOURS[t]}` }), TIER_NAMES[t], el("span", { class: "n", text: tierCounts[t] })],
    cat.tiers.has(t),
    () => { cat.tiers.has(t) ? cat.tiers.delete(t) : cat.tiers.add(t); updateCatalog(); },
  )));
  $("filter-providers").replaceChildren(...cat.data.providers.map((p) => pill(
    [p.name, p.reviewed ? null : el("span", { class: "n", title: "Not yet reviewed by a specialist", text: "unreviewed" })],
    cat.providers.has(p.id),
    () => {
      if (cat.providers.has(p.id)) { if (cat.providers.size > 1) cat.providers.delete(p.id); } else cat.providers.add(p.id);
      updateCatalog();
    },
  )));
  $("filter-match").replaceChildren(...Object.entries(MATCH_FILTERS).map(([key, f]) => pill(
    f.label, cat.match === key, () => { cat.match = key; updateCatalog(); },
  )));
}

function serviceRow(p, svc) {
  const hit = tokens().length > 0 && tokens().some((t) => svc.service.toLowerCase().includes(t));
  return [
    el("span", { class: "svc-prov", text: p.name }),
    el("span", { class: `svc-name${hit ? " hit" : ""}`, title: svc.service }, highlight(svc.service)),
    fidelityBadge(svc.fidelity),
  ];
}

function capDetail(cap) {
  return el("div", { class: "cap-detail" }, visibleProviders().map((p) => {
    const svc = cap.services[p.id];
    return el("div", {},
      el("h4", {}, `${p.name}: ${svc.service}`, fidelityBadge(svc.fidelity)),
      svc.note && el("p", { text: svc.note }),
      svc.alternatives.length > 0 && el("p", { class: "alts", text: `Alternatives: ${svc.alternatives.join(", ")}` }),
      svc.docs && el("a", { href: svc.docs, target: "_blank", rel: "noopener noreferrer", text: "Documentation ↗" }));
  }));
}

function renderResults() {
  const list = cat.data.capabilities.filter((cap) => matches(cap));
  const byName = (a, b) => a.id.localeCompare(b.id);
  if (cat.sort === "name") list.sort(byName);
  else if (cat.sort === "differences") list.sort((a, b) => differences(b) - differences(a) || byName(a, b));
  else list.sort((a, b) => TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier));

  $("catalog-count").textContent = `${list.length} of ${cat.data.capabilities.length}`;
  $("catalog-empty").hidden = list.length > 0;
  $("catalog-results").replaceChildren(...list.map((cap) => {
    const open = cat.open.has(cap.id);
    return el("li", { class: "cap-card" },
      el("button", {
        type: "button", "aria-expanded": String(open),
        onclick: () => { open ? cat.open.delete(cap.id) : cat.open.add(cap.id); renderResults(); },
      },
      el("div", { class: "cap-title" },
        el("h3", {}, highlight(cap.id)),
        el("span", { class: "badge tier", style: `color:${TIER_COLOURS[cap.tier]}`, text: TIER_NAMES[cap.tier] })),
      el("p", { class: "cap-desc" }, highlight(cap.description)),
      el("div", { class: "svc-rows" }, visibleProviders().flatMap((p) => serviceRow(p, cap.services[p.id])))),
      open && capDetail(cap));
  }));

  const unreviewed = visibleProviders().filter((p) => !p.reviewed).map((p) => p.name);
  const note = $("catalog-review");
  note.hidden = unreviewed.length === 0;
  note.replaceChildren(el("b", { text: "Unreviewed: " }),
    `${unreviewed.join(", ")} mappings have not yet been checked by a specialist. Treat them as a draft and use the documentation links to verify.`);
}

function updateCatalog() {
  renderFilters();
  renderResults();
  syncCatalogUrl();
}

function initCatalogControls() {
  let timer;
  $("catalog-search").addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { cat.q = e.target.value.trim(); updateCatalog(); }, 120);
  });
  $("catalog-sort").addEventListener("change", (e) => { cat.sort = e.target.value; updateCatalog(); });
}

async function showCatalog() {
  if (!cat.data) {
    cat.loading ||= fetch("/api/catalog").then((r) => r.json());
    cat.data = await cat.loading;
  }
  readCatalogUrl();
  renderFilters();
  renderResults();
}

init();
