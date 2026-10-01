"use strict";

// The result workspace: one architecture shown on every provider. Used for plan results
// and for examples. Each instance owns its DOM (cloned from #workspace-template) and state.

const STAGE_HELP = {
  code: "Where every change starts",
  build: "Turns code into tested artifacts",
  ship: "Stores and releases what was built",
  serve: "How traffic reaches the app",
  run: "Where the code runs",
  integrate: "How parts work together asynchronously",
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
    this.editable = editable && CA.MODE !== "static";
    this.cache = new Map();
    this.state = {
      specYaml: "", originalYaml: "", provider: "aws", view: "diagram", design: null,
      selectedId: null, workflow: 0, step: -1, playing: null, seq: 0, zoomed: false,
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
    for (const button of this.qa(".ws-actions [data-action]")) {
      button.addEventListener("click", () => this.download(button.dataset.action));
    }
    const editor = this.q(".spec-editor");
    editor.readOnly = !this.editable;
    this.q(".editor-readonly").hidden = this.editable;
    this.q(".editor-hint").hidden = !this.editable;
    this.q(".editor-reset").hidden = !this.editable;
    let debounce;
    editor.addEventListener("input", () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this.state.specYaml = editor.value; this.refresh(); }, 350);
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
    this.renderWorkflows(d);
    this.renderInspector();
  }

  // ---------- header ----------
  renderHeader(d) {
    const { el, fill, number } = CA;
    this.q(".ws-name").textContent = d.name;
    this.q(".ws-summary").textContent = d.summary || "";
    const p = d.provenance;
    let provenance;
    if (p && p.mode === "ai") {
      provenance = ["Designed by the ", el("b", { text: "AI agent" }), ` (${p.model})`, p.source ? ` from ${p.source}` : "", ". Review it before building."];
    } else if (p && p.mode === "rules") {
      provenance = ["Drafted by the ", el("b", { text: "rule-based planner" }), p.source ? ` from ${p.source}` : "", ". Review it before building."];
    } else {
      provenance = ["Reference architecture from the CloudArchie library."];
    }
    fill(this.q(".ws-provenance"), provenance);
    const r = d.requirements || {};
    const chips = [
      ["Region", d.region.code ? `${d.region.label} (${d.region.code})` : `${d.region.label} (self-hosted)`],
      r.users != null && ["Users", number(r.users)],
      r.peak_rps != null && ["Peak", `${number(r.peak_rps)} req/s`],
      r.data_gb != null && ["Data", `${number(r.data_gb)} GB`],
      r.data_growth_gb_per_month != null && ["Growth", `${number(r.data_growth_gb_per_month)} GB/mo`],
      ["Availability", `${r.availability_target}%`],
      r.compliance && r.compliance.length && ["Compliance", r.compliance.join(", ")],
      r.monthly_budget_usd != null && ["Budget", `$${number(r.monthly_budget_usd)}/mo`],
    ].filter(Boolean);
    fill(this.q(".ws-reqs"), chips.map(([k, v]) => el("li", {}, el("b", { text: `${k}: ` }), v)));
    this.q(".dl-label").textContent = CA.CLIPBOARD_ONLY ? "Copy" : "Download";
  }

  renderNotes(d) {
    const { el, fill } = CA;
    const card = (title, items) => items && items.length
      ? el("section", { class: "note-card" }, el("h3", { text: title }), el("ul", {}, items.map((t) => el("li", { text: t }))))
      : null;
    fill(this.q(".ws-notes"), card("What was assumed", d.assumptions), card("Questions to confirm", d.open_questions));
  }

  renderReview(d) {
    const note = this.q(".ws-review");
    note.hidden = d.reviewed;
    CA.fill(note, CA.el("b", { text: "Unreviewed mappings. " }),
      `${d.provider_name} service choices have not yet been checked by a specialist. Treat them as a draft.`);
  }

  renderProviders() {
    const { el, fill } = CA;
    const providers = (CA.meta && CA.meta.providers) || [];
    fill(this.q(".ws-provider-bar"), providers.map((p) => el("button", {
      type: "button", role: "tab", class: "ws-provider-tab", "data-id": p.id,
      "aria-selected": String(p.id === this.state.provider),
      onclick: () => this.setProvider(p.id),
    }, p.name, p.reviewed ? null : el("span", { class: "unreviewed", title: "Not yet reviewed by a specialist", text: "●" }))));
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

  renderDiagram(d) {
    const canvas = this.q(".ws-canvas");
    canvas.innerHTML = d.svg; // generated server-side; every text node in it is XML-escaped
    this.wireNodes(canvas, (id) => this.select(this.state.selectedId === id ? null : id));
    this.q(".icon-note").textContent = d.official_icons
      ? "Icons come from the official package configured on the server."
      : "Coloured badges mark each service by category.";
  }

  select(id) {
    this.state.selectedId = id;
    this.renderInspector();
  }

  renderInspector() {
    const { el, fill, number, fidelityBadge, FIDELITY_HELP } = CA;
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
    fill(this.q(".inspector-body"),
      el("h3", { text: comp.service || comp.label }),
      el("p", { class: "sub", text: comp.service ? comp.label : "Outside the cloud" }),
      el("div", { class: "row" },
        el("span", { class: "badge muted-badge", text: stageName || TIER_NAMES[comp.tier] }),
        el("code", { text: comp.capability }),
        fidelityBadge(comp.fidelity)),
      el("h4", { text: "Why it is here" }),
      comp.rationale ? el("p", { text: comp.rationale })
        : el("p", { class: "note" }, el("b", { text: "Generic reason: " }), comp.capability_description),
      comp.evidence && comp.evidence.length > 0 && el("h4", { text: "From the requirements" }),
      (comp.evidence || []).map((q) => el("blockquote", { class: "evidence", text: `“${q}”` })),
      comp.fidelity && el("h4", { text: "How close is the match" }),
      comp.fidelity && el("p", { text: FIDELITY_HELP[comp.fidelity] }),
      comp.note && el("p", { class: "note", text: comp.note }),
      comp.alternatives.length > 0 && el("h4", { text: "Alternatives" }),
      comp.alternatives.length > 0 && el("ul", {}, comp.alternatives.map((a) => el("li", { text: a }))),
      comp.connections.length > 0 && el("h4", { text: "Connections" }),
      comp.connections.length > 0 && el("ul", {}, comp.connections.map((c) =>
        el("li", { text: (c.to ? `→ ${name(c.to)}` : `← ${name(c.from)}`) + (c.label ? `: ${c.label}` : "") }))),
      sizing.length > 0 && el("h4", { text: "Sizing assumptions" }),
      sizing.length > 0 && el("table", {}, el("tbody", {}, sizing.map(([k, v]) =>
        el("tr", {}, el("td", { text: k.replaceAll("_", " ") }), el("td", { text: number(v) }))))),
      comp.docs && el("h4", { text: "Documentation" }),
      comp.docs && el("p", {}, el("a", { href: comp.docs, target: "_blank", rel: "noopener noreferrer", text: comp.docs })),
    );
  }

  // ---------- bill of services ----------
  renderBill(d) {
    const { el, fill, fidelityBadge } = CA;
    const stages = Object.entries(CA.meta.stages);
    const sections = stages.map(([key, label]) => {
      const comps = d.components.filter((c) => c.stage === key);
      if (!comps.length) return null;
      return el("section", { class: "bill-stage" },
        el("div", { class: "bill-stage-name" }, label, el("small", { text: STAGE_HELP[key] || "" })),
        el("div", { class: "bill-cards" }, comps.map((c) => el("button", {
          type: "button", class: "bill-card",
          onclick: () => { this.setView("diagram"); this.select(c.id); },
        },
        el("span", { class: "svc", text: c.service || c.label }),
        el("span", { class: "meta" }, c.label, " · ", el("code", { text: c.capability }), fidelityBadge(c.fidelity),
          c.evidence && c.evidence.length ? el("span", { class: "badge muted-badge", title: "Quoted from the requirements", text: "quoted" }) : null),
        el("span", { class: "why", text: c.rationale || c.capability_description }),
        ))));
    });
    fill(this.q(".bill"), sections);
  }

  // ---------- workflows ----------
  renderWorkflows(d) {
    const { el, fill } = CA;
    const wfs = d.workflows || [];
    if (this.state.workflow >= wfs.length) this.state.workflow = 0;
    fill(this.q(".wf-tabs"), wfs.map((w, i) => el("button", {
      type: "button", role: "tab", class: "wf-tab", "aria-selected": String(i === this.state.workflow),
      onclick: () => { this.stopPlaying(); this.state.workflow = i; this.state.step = -1; this.renderWorkflows(this.state.design); },
    }, w.name)));
    const canvas = this.q(".wf-canvas");
    canvas.innerHTML = d.svg;
    this.wireNodes(canvas, (id) => { this.setView("diagram"); this.select(id); });
    const wf = wfs[this.state.workflow];
    const byId = Object.fromEntries(d.components.map((c) => [c.id, c]));
    if (!wf) {
      fill(this.q(".wf-steps"), el("li", { class: "muted", text: "This design has no workflows yet." }));
      this.q(".wf-controls").hidden = true;
      return;
    }
    this.q(".wf-controls").hidden = false;
    fill(this.q(".wf-steps"), wf.steps.map((step, i) => el("li", {
      class: "wf-step", tabindex: "0",
      "aria-current": i === this.state.step ? "step" : null,
      onclick: () => { this.stopPlaying(); this.stepTo(i); },
      onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.stopPlaying(); this.stepTo(i); } },
    },
    el("div", {}, el("span", { text: step.text }),
      el("div", { class: "services" }, step.components.filter((id) => byId[id]).map((id) =>
        el("span", { text: byId[id].service || byId[id].label })))))));
    this.highlight(this.state.step >= 0 ? wf.steps[this.state.step] : null);
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
