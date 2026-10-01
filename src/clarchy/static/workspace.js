"use strict";

// The result workspace: one architecture shown on every provider. Used for plan results
// and for examples. Each instance owns its DOM (cloned from #workspace-template) and state.

const STAGE_HELP = {
  code: "Where every change starts",
  build: "Turns code into tested artifacts",
  ship: "Stores and releases what was built",
  serve: "How traffic reaches the app",
  run: "Where the code runs",
  integrate: "How parts work together",
  store: "Where the data lives",
  operate: "Identity, secrets and visibility",
};
const TIER_NAMES = {
  external: "Outside the cloud", delivery: "Build and deploy", edge: "Edge", entry: "Entry point",
  compute: "Compute", integration: "Integration", data: "Data", platform: "Shared service",
};

class Workspace {
  constructor(root, { editable = false } = {}) {
    this.root = root;
    root.replaceChildren(document.getElementById("workspace-template").content.cloneNode(true));
    this.q = (sel) => root.querySelector(sel);
    this.qa = (sel) => root.querySelectorAll(sel);
    this.editable = editable && CA.canEdit();
    this.cache = new Map();
    this.state = {
      specYaml: "", originalYaml: "", provider: "aws", view: "diagram", design: null,
      selectedId: null, workflow: 0, step: -1, playing: null, seq: 0, zoomed: false, term: 12,
    };
    root.dataset.provider = this.state.provider;

    for (const tab of this.qa(".ws-view-tab")) {
      tab.addEventListener("click", () => this.setView(tab.dataset.view));
    }
    this.q(".inspector-close").addEventListener("click", () => this.select(null));
    this.q(".zoom-toggle").addEventListener("click", () => this.setZoom(!this.state.zoomed));
    root.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.state.selectedId) this.select(null);
    });
    const menu = this.q(".ws-actions .menu");
    for (const button of this.qa(".menu-list [data-action]")) {
      button.addEventListener("click", () => { menu.open = false; this.download(button.dataset.action); });
    }
    document.addEventListener("click", (e) => { if (menu.open && !menu.contains(e.target)) menu.open = false; });
    if (CA.CLIPBOARD_ONLY) this.q(".menu-label").textContent = "Copy";

    const editor = this.q(".spec-editor");
    editor.readOnly = !this.editable;
    this.q(".editor-readonly").hidden = this.editable;
    this.q(".editor-hint").hidden = !this.editable;
    this.q(".editor-reset").hidden = !this.editable;
    let debounce;
    editor.addEventListener("input", () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this.state.specYaml = editor.value; this.refresh(); }, 400);
    });
    editor.addEventListener("keydown", (e) => {
      if (e.key !== "Tab" || editor.readOnly) return;
      e.preventDefault();
      editor.setRangeText("  ", editor.selectionStart, editor.selectionEnd, "end");
      editor.dispatchEvent(new Event("input"));
    });
    this.q(".editor-reset").addEventListener("click", () => this.load(this.state.originalYaml, { view: "spec" }));
    this.q('[data-wf="prev"]').addEventListener("click", () => { this.stopPlaying(); this.stepTo(this.state.step - 1); });
    this.q('[data-wf="next"]').addEventListener("click", () => { this.stopPlaying(); this.stepTo(this.state.step + 1); });
    this.q('[data-wf="play"]').addEventListener("click", () => this.togglePlay());
    this.renderProviders();
  }

  // A new design opens on the diagram; Reset in the spec editor stays where it is.
  async load(specYaml, { provider, view = "diagram" } = {}) {
    this.state.specYaml = specYaml;
    this.state.originalYaml = specYaml;
    this.state.design = null;
    this.state.selectedId = null;
    this.state.workflow = 0;
    this.state.step = -1;
    this.stopPlaying();
    if (provider) this.setProvider(provider, { refresh: false });
    this.setView(view);
    this.q(".spec-editor").value = specYaml;
    await this.refresh();
  }

  setProvider(id, { refresh = true } = {}) {
    this.state.provider = id;
    this.root.dataset.provider = id;
    this.renderProviders();
    if (refresh) this.refresh();
  }

  // Fit the diagram to the page, or show it at its real size and scroll around it.
  setZoom(zoomed) {
    this.state.zoomed = zoomed;
    this.q(".ws-canvas").classList.toggle("zoomed", zoomed);
    const button = this.q(".zoom-toggle");
    button.setAttribute("aria-pressed", String(zoomed));
    button.textContent = zoomed ? "Fit to width" : "Actual size";
  }

  setView(view) {
    this.state.view = view;
    for (const tab of this.qa(".ws-view-tab")) tab.setAttribute("aria-selected", String(tab.dataset.view === view));
    for (const section of this.qa(".ws-view")) section.hidden = section.dataset.view !== view;
    if (view !== "workflows") this.stopPlaying();
  }

  async refresh() {
    const seq = ++this.state.seq;
    const { specYaml, provider } = this.state;
    const key = `${provider}\n${specYaml}`;
    let result = this.cache.get(key);
    if (!result) {
      result = await CA.api.design(specYaml, provider);
      if (result.ok) this.cache.set(key, result);
    }
    if (seq !== this.state.seq) return;
    if (!result.ok) {
      this.renderErrors(result.body.errors || [{ where: "server", message: "Request failed" }]);
      return;
    }
    this.state.design = result.body;
    const ids = new Set(result.body.components.map((c) => c.id));
    if (!ids.has(this.state.selectedId)) this.state.selectedId = null;
    this.renderErrors([]);
    this.render();
  }

  render() {
    const d = this.state.design;
    this.renderHeader(d);
    this.renderNotes(d);
    this.renderReview(d);
    this.renderDiagram(d);
    this.renderBill(d);
    this.renderCost(d);
    this.renderWorkflows(d);
    this.renderInspector();
  }

  // ---------- header ----------
  renderHeader(d) {
    const { el, fill, number, money } = CA;
    this.q(".ws-name").textContent = d.name;
    const summary = this.q(".ws-summary");
    summary.textContent = d.summary || "";
    summary.hidden = !d.summary;
    const p = d.provenance;
    const origin = p && p.mode === "ai" ? `AI design (${p.model})`
      : p && p.mode === "rules" ? "Rule-based draft" : "Reference architecture";
    const r = d.requirements || {};
    const cost = d.cost && d.cost.available ? d.cost : null;
    const items = [
      origin,
      d.region.code ? `${d.region.label} (${d.region.code})` : d.region.label,
      r.users != null && `${number(r.users)} users`,
      r.peak_rps != null && `${number(r.peak_rps)} req/s peak`,
      r.data_gb != null && `${number(r.data_gb)} GB data`,
      `${r.availability_target}% availability`,
      r.compliance && r.compliance.length && r.compliance.join(", "),
      cost && el("b", { text: `≈ ${money(cost.monthly)} a month` }),
    ].filter(Boolean);
    fill(this.q(".ws-meta"), items.map((item) => el("span", {}, item)));

    // The drawing's title block, as on an architect's sheet.
    const providers = (CA.meta && CA.meta.providers) || [];
    const index = providers.findIndex((p) => p.id === this.state.provider);
    this.q(".tb-name").textContent = d.name;
    this.q(".tb-provider").textContent = d.provider_name;
    this.q(".tb-region").textContent = d.region.code || d.region.label;
    this.q(".tb-region").title = d.region.label;
    this.q(".tb-count").textContent = String(d.components.length);
    this.q(".tb-sheet").textContent = index >= 0 ? `${index + 1} of ${providers.length}` : "1";
  }

  renderNotes(d) {
    const { el, fill, plural } = CA;
    const assumptions = d.assumptions || [];
    const questions = d.open_questions || [];
    const box = this.q(".ws-review-notes");
    box.hidden = !assumptions.length && !questions.length;
    const parts = [assumptions.length && plural(assumptions.length, "assumption"),
      questions.length && plural(questions.length, "question") + " to confirm"].filter(Boolean);
    this.q(".review-title").textContent = parts.join(" and ");
    const list = (title, items) => items.length
      ? el("section", {}, el("h3", { text: title }), el("ul", {}, items.map((t) => el("li", { text: t }))))
      : null;
    fill(this.q(".ws-notes"), list("What was assumed", assumptions), list("Questions to confirm", questions));
  }

  renderReview(d) {
    this.q(".ws-review").textContent = d.reviewed ? "" : `${d.provider_name} choices are an unreviewed draft.`;
  }

  renderProviders() {
    const { el, fill } = CA;
    const providers = (CA.meta && CA.meta.providers) || [];
    fill(this.q(".ws-provider-bar"), providers.map((p) => el("button", {
      type: "button", role: "tab", class: "ws-provider-tab", "data-id": p.id,
      "aria-selected": String(p.id === this.state.provider),
      onclick: () => this.setProvider(p.id),
    }, p.name)));
  }

  // ---------- diagram + inspector ----------
  wireNodes(canvas, onSelect) {
    const d = this.state.design;
    for (const node of canvas.querySelectorAll("g.node")) {
      const comp = d.components.find((c) => c.id === node.dataset.id);
      if (!comp) continue;
      node.setAttribute("tabindex", "0");
      node.setAttribute("role", "button");
      node.setAttribute("aria-label", comp.service ? `${comp.service}: ${comp.label}` : comp.label);
      node.addEventListener("click", () => onSelect(comp.id));
      node.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(comp.id); }
      });
    }
  }

  placeDiagram(canvas, svgText) {
    canvas.innerHTML = svgText; // generated by Clarchy; every text node in it is XML-escaped
    CA.cropDiagram(canvas.querySelector("svg"));
  }

  renderDiagram(d) {
    const canvas = this.q(".ws-canvas");
    this.placeDiagram(canvas, d.svg);
    this.wireNodes(canvas, (id) => this.select(this.state.selectedId === id ? null : id));
    this.q(".icon-note").textContent = d.official_icons ? "Icons come from the official package configured on the server." : "";
  }

  select(id) {
    this.state.selectedId = id;
    this.renderInspector();
  }

  costOf(id) {
    const cost = this.state.design && this.state.design.cost;
    return cost && cost.available ? cost.lines.find((l) => l.component === id) : null;
  }

  renderInspector() {
    const { el, fill, number, money, fidelityBadge, FIDELITY_HELP } = CA;
    const d = this.state.design;
    const comp = d && d.components.find((c) => c.id === this.state.selectedId);
    const panel = this.q(".inspector");
    panel.hidden = !comp;
    this.q(".ws-diagram").classList.toggle("inspecting", Boolean(comp));
    for (const node of this.qa(".ws-canvas g.node")) node.classList.toggle("selected", node.dataset.id === this.state.selectedId);
    if (!comp) return;
    const byId = Object.fromEntries(d.components.map((c) => [c.id, c]));
    const name = (id) => (byId[id].service ? `${byId[id].label} (${byId[id].service})` : byId[id].label);
    const sizing = Object.entries(comp.sizing || {});
    const stageName = comp.stage && CA.meta.stages[comp.stage];
    const line = this.costOf(comp.id);
    fill(this.q(".inspector-body"),
      el("h3", { text: comp.service || comp.label }),
      el("p", { class: "sub", text: comp.service ? comp.label : "Outside the cloud" }),
      el("div", { class: "row" },
        el("span", { class: "tag neutral", text: stageName || TIER_NAMES[comp.tier] }),
        fidelityBadge(comp.fidelity),
        line && el("span", { class: "tag neutral", text: `≈ ${money(line.monthly)}/mo` })),
      el("h4", { text: "Why it is here" }),
      el("p", { text: comp.rationale || comp.capability_description }),
      comp.evidence && comp.evidence.length > 0 && el("h4", { text: "From your requirements" }),
      (comp.evidence || []).map((q) => el("blockquote", { class: "evidence", text: `“${q}”` })),
      comp.fidelity && comp.fidelity !== "exact" && el("h4", { text: "How close is the match" }),
      comp.fidelity && comp.fidelity !== "exact" && el("p", { text: FIDELITY_HELP[comp.fidelity] }),
      comp.note && el("p", { class: "note", text: comp.note }),
      comp.alternatives.length > 0 && el("h4", { text: "Alternatives" }),
      comp.alternatives.length > 0 && el("p", { text: comp.alternatives.join(", ") }),
      comp.connections.length > 0 && el("h4", { text: "Connections" }),
      comp.connections.length > 0 && el("ul", {}, comp.connections.map((c) =>
        el("li", { text: (c.to ? `→ ${name(c.to)}` : `← ${name(c.from)}`) + (c.label ? `: ${c.label}` : "") }))),
      sizing.length > 0 && el("h4", { text: "Sizing" }),
      sizing.length > 0 && el("table", {}, el("tbody", {}, sizing.map(([k, v]) =>
        el("tr", {}, el("td", { text: k.replaceAll("_", " ") }), el("td", { text: number(v) }))))),
      comp.docs && el("p", { class: "docs-link" }, el("a", { href: comp.docs, target: "_blank", rel: "noopener noreferrer", text: "Documentation ↗" })),
    );
  }

  // ---------- services list ----------
  renderBill(d) {
    const { el, fill, money, fidelityTag } = CA;
    const sections = Object.entries(CA.meta.stages).map(([key, label]) => {
      const comps = d.components.filter((c) => c.stage === key);
      if (!comps.length) return null;
      return el("section", { class: "bill-stage" },
        el("div", { class: "bill-stage-name" }, label, el("small", { text: STAGE_HELP[key] || "" })),
        el("div", { class: "bill-rows" }, comps.map((c) => {
          const line = this.costOf(c.id);
          return el("button", {
            type: "button", class: "bill-row",
            onclick: () => { this.setView("diagram"); this.select(c.id); },
          },
          el("span", { class: "svc" }, el("b", { text: c.service || c.label }), el("span", { text: c.label })),
          el("span", { class: "why", text: c.rationale || c.capability_description }),
          el("span", { class: "end" }, fidelityTag(c.fidelity), line ? el("span", { class: "row-cost", text: `${money(line.monthly)}/mo` }) : null));
        })));
    });
    fill(this.q(".bill"), sections);
  }

  // ---------- cost ----------
  renderCost(d) {
    const { el, fill, money, plural } = CA;
    const box = this.q(".cost");
    const cost = d.cost;
    if (!cost || !cost.available) {
      fill(box, el("div", { class: "cost-empty" },
        el("h3", { text: "No price estimate for this provider" }),
        el("p", { text: (cost && cost.message) || "Prices are not available yet." })));
      return;
    }
    const terms = cost.terms;
    if (!terms.some((t) => t.months === this.state.term)) this.state.term = terms[0].months;
    const term = terms.find((t) => t.months === this.state.term);
    const save = term.committed != null ? term.on_demand - term.committed : null;

    const termButtons = el("div", { class: "segmented", role: "group", "aria-label": "Period" }, terms.map((t) => el("button", {
      type: "button", "aria-pressed": String(t.months === this.state.term),
      onclick: () => { this.state.term = t.months; this.renderCost(this.state.design); },
    }, t.label)));

    const stats = el("div", { class: "cost-stats" },
      el("div", { class: "stat" },
        el("span", { class: "stat-label", text: `On demand, ${term.label}` }),
        el("b", { class: "stat-value", text: money(term.on_demand) }),
        el("span", { class: "stat-sub", text: `${money(cost.monthly)} in the first month` })),
      el("div", { class: "stat" },
        el("span", { class: "stat-label", text: term.commitment ? `With ${term.commitment} commitments` : "With commitments" }),
        term.committed != null
          ? [el("b", { class: "stat-value", text: money(term.committed) }),
            el("span", { class: "stat-sub good", text: `Save ${money(save)} (${Math.round((save / term.on_demand) * 100)}%)` })]
          : [el("b", { class: "stat-value muted", text: "–" }),
            el("span", { class: "stat-sub", text: cost.break_even_months
              ? `A 1-year commitment pays off after about ${plural(cost.break_even_months, "month")}`
              : "Commitments start at 1 year" })]));

    const table = el("table", { class: "cost-table" },
      el("thead", {}, el("tr", {}, ["Period", "On demand", "With commitments", "You save"].map((h) => el("th", { text: h })))),
      el("tbody", {}, terms.map((t) => el("tr", { class: t.months === this.state.term ? "current" : null },
        el("td", { text: t.label }),
        el("td", { text: money(t.on_demand) }),
        el("td", { text: t.committed != null ? money(t.committed) : "–" }),
        el("td", { class: "good", text: t.committed != null ? money(t.on_demand - t.committed) : "–" })))));

    const lines = [...cost.lines].sort((a, b) => b.monthly - a.monthly);
    const breakdown = el("div", { class: "cost-lines" }, lines.map((line) => el("details", { class: "cost-line" },
      el("summary", {},
        el("span", { class: "svc" }, el("b", { text: line.service }), el("span", { text: line.label })),
        line.commitment ? el("span", { class: "tag neutral", title: line.commitment, text: "Commitment eligible" }) : el("span"),
        el("span", { class: "amount", text: `${money(line.monthly)}/mo` })),
      el("table", { class: "cost-items" }, el("tbody", {}, line.items.map((item) => el("tr", {},
        el("td", {}, item.name, item.basis ? el("small", { text: item.basis }) : null),
        el("td", { class: "num", text: `${CA.number(item.quantity)} × ${money(item.unit_price, { cents: true })} / ${item.unit}` }),
        el("td", { class: "num", text: money(item.monthly, { cents: true }) }))))),
      line.pricing_url && el("a", { class: "price-link", href: line.pricing_url, target: "_blank", rel: "noopener noreferrer", text: "Pricing page ↗" }))));

    fill(box,
      el("div", { class: "cost-head" }, termButtons,
        el("span", { class: `cost-source ${cost.verified ? "verified" : ""}`, text: cost.verified ? "Prices from the provider's price list" : "Approximate list prices" })),
      stats,
      table,
      el("h3", { class: "cost-subhead", text: "Monthly breakdown" }),
      breakdown,
      el("div", { class: "cost-notes" },
        el("p", { text: `${cost.price_region} list prices in ${cost.currency}, as of ${cost.as_of} (${cost.source}).` }),
        cost.commitment_notes.length > 0 && el("ul", {}, cost.commitment_notes.map((n) => el("li", { text: n }))),
        el("ul", {}, cost.assumptions.map((n) => el("li", { text: n }))),
        cost.calculator && el("p", {}, "Check with the ", el("a", { href: cost.calculator, target: "_blank", rel: "noopener noreferrer", text: "official calculator ↗" }))));
  }

  // ---------- workflows ----------
  renderWorkflows(d) {
    const { el, fill } = CA;
    const wfs = d.workflows || [];
    if (this.state.workflow >= wfs.length) this.state.workflow = 0;
    fill(this.q(".wf-tabs"), wfs.map((w, i) => el("button", {
      type: "button", role: "tab", class: "chip wf-tab", "aria-selected": String(i === this.state.workflow),
      onclick: () => { this.stopPlaying(); this.state.workflow = i; this.state.step = -1; this.renderWorkflows(this.state.design); },
    }, w.name)));
    const canvas = this.q(".wf-canvas");
    this.placeDiagram(canvas, d.svg);
    this.wireNodes(canvas, (id) => { this.setView("diagram"); this.select(id); });
    const wf = wfs[this.state.workflow];
    const byId = Object.fromEntries(d.components.map((c) => [c.id, c]));
    if (!wf) {
      fill(this.q(".wf-steps"), el("li", { class: "hint", text: "This design has no workflows yet." }));
      this.q(".wf-controls").hidden = true;
      return;
    }
    this.q(".wf-controls").hidden = false;
    const service = (id) => (byId[id] ? byId[id].service || byId[id].label : id);
    fill(this.q(".wf-steps"), wf.steps.map((step, i) => {
      // Generated steps read "Source → Target: what happens"; lead with what happens.
      const m = step.text.match(/^(.+?) → (.+?): (.+)$/);
      const text = m ? m[3].charAt(0).toUpperCase() + m[3].slice(1) : step.text;
      const path = step.components.filter((id) => byId[id]).map(service).join(" → ");
      return el("li", {
        class: "wf-step", tabindex: "0",
        "aria-current": i === this.state.step ? "step" : null,
        onclick: () => { this.stopPlaying(); this.stepTo(i); },
        onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.stopPlaying(); this.stepTo(i); } },
      }, el("div", {}, el("div", { class: "wf-text", text }), path && el("div", { class: "wf-path", text: path })));
    }));
    this.updatePosition();
    this.highlight(this.state.step >= 0 ? wf.steps[this.state.step] : null);
  }

  updatePosition() {
    const wf = (this.state.design.workflows || [])[this.state.workflow];
    this.q(".wf-position").textContent = wf
      ? (this.state.step >= 0 ? `Step ${this.state.step + 1} of ${wf.steps.length}` : `${wf.steps.length} steps`)
      : "";
  }

  stepTo(index) {
    const wf = (this.state.design.workflows || [])[this.state.workflow];
    if (!wf) return;
    this.state.step = Math.max(0, Math.min(index, wf.steps.length - 1));
    const items = this.qa(".wf-step");
    items.forEach((item, i) => {
      if (i === this.state.step) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    if (items[this.state.step]) items[this.state.step].scrollIntoView({ block: "nearest" });
    this.updatePosition();
    this.highlight(wf.steps[this.state.step]);
  }

  highlight(step) {
    const canvas = this.q(".wf-canvas");
    canvas.classList.toggle("focusing", Boolean(step));
    const lit = new Set(step ? step.components : []);
    for (const node of canvas.querySelectorAll("g.node")) node.classList.toggle("lit", lit.has(node.dataset.id));
    for (const edge of canvas.querySelectorAll("[data-from]")) {
      edge.classList.toggle("lit", lit.has(edge.dataset.from) && lit.has(edge.dataset.to));
    }
  }

  togglePlay() {
    if (this.state.playing) { this.stopPlaying(); return; }
    const wf = (this.state.design.workflows || [])[this.state.workflow];
    if (!wf) return;
    if (this.state.step >= wf.steps.length - 1) this.state.step = -1;
    this.q('[data-wf="play"]').textContent = "Pause";
    const tick = () => {
      if (this.state.step >= wf.steps.length - 1) { this.stopPlaying(); return; }
      this.stepTo(this.state.step + 1);
    };
    tick();
    this.state.playing = setInterval(tick, 2400);
  }

  stopPlaying() {
    if (this.state.playing) clearInterval(this.state.playing);
    this.state.playing = null;
    const button = this.q('[data-wf="play"]');
    if (button) button.textContent = "Play";
  }

  // ---------- errors & downloads ----------
  renderErrors(errors) {
    const { el, fill } = CA;
    fill(this.q(".errors"), errors.map((e) => el("li", {}, el("b", { text: e.where }), e.message)));
    const invalid = errors.length > 0;
    this.q(".spec-editor").classList.toggle("invalid", invalid);
    this.q(".status-dot").classList.toggle("invalid", invalid);
    const banner = this.q(".ws-banner");
    banner.hidden = !invalid;
    banner.textContent = invalid
      ? `The spec has ${errors.length === 1 ? "a problem" : `${errors.length} problems`}. ${this.state.design ? "Showing the last valid design, dimmed. " : ""}See the Spec tab.`
      : "";
    for (const canvas of this.qa(".canvas")) canvas.classList.toggle("stale", invalid && Boolean(this.state.design));
  }

  download(kind) {
    const d = this.state.design;
    if (!d) return;
    const slug = d.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "architecture";
    const files = {
      svg: { filename: `${slug}.${d.provider}.svg`, text: d.svg, type: "image/svg+xml", label: "Diagram" },
      md: { filename: `${slug}.${d.provider}.md`, text: d.explanation_md, type: "text/markdown", label: "Explanation" },
      yaml: { filename: `${slug}.yaml`, text: this.state.specYaml, type: "application/yaml", label: "Spec" },
    };
    CA.deliver({ ...files[kind], status: this.q(".dl-status") });
  }
}
