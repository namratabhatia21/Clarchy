"use strict";

// The Services page: every capability with the equivalent service on each provider.

const Services = (() => {
  const { $, el, fill, api } = CA;
  const MATCH_FILTERS = {
    all: { label: "All", test: () => true },
    differences: { label: "Differences", test: (fids) => fids.some((f) => f !== "exact") },
    exact: { label: "Exact", test: (fids) => fids.every((f) => f === "exact") },
  };
  const cat = {
    data: null, loading: null, q: "", stages: new Set(), providers: new Set(),
    match: "all", sort: "stage", open: new Set(),
  };

  const stageOrder = () => Object.keys(CA.meta.stages);
  const tokens = () => cat.q.toLowerCase().split(/\s+/).filter(Boolean);
  const visibleProviders = () => cat.data.providers.filter((p) => cat.providers.has(p.id));

  function haystack(cap) {
    const parts = [cap.id, cap.id.replaceAll("-", " "), cap.description, CA.meta.stages[cap.stage] || ""];
    for (const p of visibleProviders()) parts.push(cap.services[p.id].service, ...cap.services[p.id].alternatives);
    return parts.join(" ").toLowerCase();
  }

  function matches(cap, { ignoreStage = false } = {}) {
    const toks = tokens();
    if (toks.length && !toks.every((t) => haystack(cap).includes(t))) return false;
    if (!ignoreStage && cat.stages.size && !cat.stages.has(cap.stage)) return false;
    return MATCH_FILTERS[cat.match].test(visibleProviders().map((p) => cap.services[p.id].fidelity));
  }

  const differences = (cap) => visibleProviders().filter((p) => cap.services[p.id].fidelity !== "exact").length;

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

  function syncUrl() {
    const params = new URLSearchParams();
    if (cat.q) params.set("q", cat.q);
    if (cat.stages.size) params.set("stage", [...cat.stages].join(","));
    if (cat.providers.size !== cat.data.providers.length) params.set("providers", [...cat.providers].join(","));
    if (cat.match !== "all") params.set("match", cat.match);
    if (cat.sort !== "stage") params.set("sort", cat.sort);
    const qs = params.toString();
    CA.replaceUrl(CA.href("services", null, qs));
  }

  function readUrl(params) {
    const ids = new Set(cat.data.providers.map((p) => p.id));
    cat.q = params.get("q") || "";
    cat.stages = new Set((params.get("stage") || "").split(",").filter((s) => s in CA.meta.stages));
    const provs = (params.get("providers") || "").split(",").filter((p) => ids.has(p));
    cat.providers = new Set(provs.length ? provs : ids);
    cat.match = MATCH_FILTERS[params.get("match")] ? params.get("match") : "all";
    cat.sort = ["stage", "name", "differences"].includes(params.get("sort")) ? params.get("sort") : "stage";
    $("catalog-search").value = cat.q;
    $("catalog-sort").value = cat.sort;
  }

  const item = (children, pressed, onclick) => el("button", { class: "filter-item", type: "button", "aria-pressed": String(pressed), onclick }, children);

  function renderFilters() {
    const counts = Object.fromEntries(stageOrder().map((s) => [s, 0]));
    for (const cap of cat.data.capabilities) if (matches(cap, { ignoreStage: true })) counts[cap.stage] += 1;
    fill($("filter-stages"), stageOrder().map((s) => item(
      [el("span", { class: "dot", style: `background:${CA.STAGE_COLOURS[s]}` }), CA.meta.stages[s], el("span", { class: "n", text: counts[s] })],
      cat.stages.has(s),
      () => { cat.stages.has(s) ? cat.stages.delete(s) : cat.stages.add(s); update(); },
    )));
    fill($("filter-providers"), cat.data.providers.map((p) => item(
      [el("span", { class: "check", "aria-hidden": "true" }), p.name],
      cat.providers.has(p.id),
      () => {
        if (cat.providers.has(p.id)) { if (cat.providers.size > 1) cat.providers.delete(p.id); } else cat.providers.add(p.id);
        update();
      },
    )));
    fill($("filter-match"), Object.entries(MATCH_FILTERS).map(([key, f]) => el("button", {
      type: "button", "aria-pressed": String(cat.match === key), onclick: () => { cat.match = key; update(); },
    }, f.label)));
  }

  function serviceRow(p, svc) {
    const hit = tokens().length > 0 && tokens().some((t) => svc.service.toLowerCase().includes(t));
    return [
      el("span", { class: "svc-prov" }, el("span", { class: "dot", style: `background:${CA.PROVIDER_COLOURS[p.id] || "#64748b"}` }), p.name),
      el("span", { class: `svc-name${hit ? " hit" : ""}`, title: svc.service }, highlight(svc.service)),
      CA.fidelityTag(svc.fidelity) || el("span"),
    ];
  }

  function capDetail(cap) {
    return el("div", { class: "cap-detail" }, visibleProviders().map((p) => {
      const svc = cap.services[p.id];
      return el("div", {},
        el("h3", {}, `${p.name}: ${svc.service}`, CA.fidelityBadge(svc.fidelity)),
        svc.note && el("p", { text: svc.note }),
        svc.alternatives.length > 0 && el("p", { class: "muted", text: `Alternatives: ${svc.alternatives.join(", ")}` }),
        svc.docs && el("a", { href: svc.docs, target: "_blank", rel: "noopener noreferrer", text: "Documentation ↗" }));
    }));
  }

  function renderResults() {
    const order = stageOrder();
    const list = cat.data.capabilities.filter((cap) => matches(cap));
    const byName = (a, b) => a.id.localeCompare(b.id);
    if (cat.sort === "name") list.sort(byName);
    else if (cat.sort === "differences") list.sort((a, b) => differences(b) - differences(a) || byName(a, b));
    else list.sort((a, b) => order.indexOf(a.stage) - order.indexOf(b.stage));

    $("catalog-count").textContent = `${list.length} of ${cat.data.capabilities.length}`;
    $("catalog-empty").hidden = list.length > 0;
    fill($("catalog-results"), list.map((cap) => {
      const open = cat.open.has(cap.id);
      return el("li", { class: "cap-card" },
        el("button", { type: "button", "aria-expanded": String(open), onclick: () => { open ? cat.open.delete(cap.id) : cat.open.add(cap.id); renderResults(); } },
          el("div", { class: "cap-title" },
            el("h2", { title: cap.id }, highlight(cap.title || cap.id)),
            el("span", { class: "cap-stage" }, el("span", { class: "dot", style: `background:${CA.STAGE_COLOURS[cap.stage]}` }), CA.meta.stages[cap.stage])),
          el("p", { class: "cap-desc" }, highlight(cap.description)),
          el("div", { class: "svc-rows" }, visibleProviders().flatMap((p) => serviceRow(p, cap.services[p.id])))),
        open && capDetail(cap));
    }));
    const unreviewed = visibleProviders().filter((p) => !p.reviewed).map((p) => p.name);
    const note = $("catalog-review");
    note.hidden = unreviewed.length === 0;
    note.textContent = `The ${unreviewed.join(", ")} mappings are a draft that a specialist has not reviewed yet; each card links to the documentation.`;
  }

  function update() {
    renderFilters();
    renderResults();
    syncUrl();
  }

  function initControls() {
    if (initControls.done) return;
    initControls.done = true;
    let timer;
    $("catalog-search").addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => { cat.q = e.target.value.trim(); update(); }, 120);
    });
    $("catalog-sort").addEventListener("change", (e) => { cat.sort = e.target.value; update(); });
  }

  async function show(params) {
    if (!cat.data) {
      cat.loading ||= Promise.resolve(api.catalog());
      cat.data = await cat.loading;
    }
    readUrl(params);
    renderFilters();
    renderResults();
  }

  return { initControls, show };
})();
