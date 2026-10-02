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

// A placeholder that shows what kind of answer helps, from the question's wording.
function answerHint(text, kind) {
  const t = text.toLowerCase();
  if (/where are most users|region/.test(t)) return "e.g. Germany, and data must stay in the EU";
  if (/how many people|user numbers/.test(t)) return "e.g. 10,000 employees, about 50 requests a second at peak";
  if (/budget/.test(t)) return "e.g. $3,000 a month";
  if (/availability/.test(t)) return "e.g. 99.95%";
  if (kind === "assumption") return "Leave empty to keep it, or correct it";
  if (/^(does|do|is|are|will|can|should)\b/.test(t)) return "Yes or no, or a short answer";
  return "Your answer";
}

class Workspace {
  constructor(root, { editable = false, onReplan = null } = {}) {
    this.root = root;
    // An example's page arrives with its title drawn (site.py). It stays where it is (it is
    // the page's h1, and moving it would paint it again); the rest is built around it.
    const parts = document.getElementById("workspace-template").content.cloneNode(true);
    const drawn = root.querySelector(":scope > .ws-head");
    if (drawn) {
      const head = parts.querySelector(".ws-head");
      drawn.append(...[...head.children].filter((child) => !child.matches(".ws-title")));
      head.remove();
      root.append(parts);
    } else {
      root.replaceChildren(parts);
    }
    this.q = (sel) => root.querySelector(sel);
    this.qa = (sel) => root.querySelectorAll(sel);
    this.editable = editable && CA.canEdit();
    this.onReplan = onReplan;
    this.answering = false;
    this.cache = new Map();
    this.state = {
      specYaml: "", originalYaml: "", provider: "aws", view: "diagram", design: null,
      selectedId: null, workflow: 0, step: -1, playing: null, seq: 0, zoomed: false, term: 12,
      credits: CA.recall("clarchy.credits") || { cloud: 0, ai: 0 },
    };
    root.dataset.provider = this.state.provider;

    for (const tab of this.qa(".ws-view-tab")) {
      tab.addEventListener("click", () => this.setView(tab.dataset.view));
    }
    this.q(".inspector-close").addEventListener("click", () => this.select(null));
    this.q(".answer-btn").addEventListener("click", (e) => {
      e.preventDefault(); // a button inside <summary> would also toggle the panel
      this.setAnswering(true);
    });
    this.q(".answer-form").addEventListener("submit", (e) => {
      e.preventDefault();
      this.submitAnswers();
    });
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
    this.answering = false;
    if (provider) this.setProvider(provider, { refresh: false });
    this.setView(view);
    this.q(".spec-editor").value = specYaml;
    this.drawNext = true;
    await this.refresh();
  }

  setProvider(id, { refresh = true } = {}) {
    this.drawNext = true; // a new sheet draws itself in; live spec edits just redraw
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
    if (view === "cost") this.countCosts();
  }

  // The cost totals are worked out in front of the reader when the Cost view opens.
  countCosts() {
    for (const node of this.qa(".cost .stat-value[data-value]")) {
      if (node.dataset.counted) continue;
      node.dataset.counted = "true";
      CA.countUp(node, Number(node.dataset.value), (v) => CA.money(v));
    }
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
    this.renderPolicies(d);
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

    const canAnswer = Boolean(this.onReplan) && (assumptions.length > 0 || questions.length > 0);
    this.q(".answer-btn").hidden = !canAnswer || this.answering;
    this.q(".ws-notes").hidden = this.answering;
    const form = this.q(".answer-form");
    form.hidden = !this.answering;
    if (this.answering) this.renderAnswerForm(form, assumptions, questions);
  }

  setAnswering(on) {
    this.answering = on && Boolean(this.onReplan);
    const box = this.q(".ws-review-notes");
    if (this.answering) box.open = true;
    this.renderNotes(this.state.design);
    if (this.answering) {
      const first = box.querySelector(".answer-input");
      if (first) first.focus();
    }
  }

  // Questions first: they are what the planner could not work out on its own.
  renderAnswerForm(form, assumptions, questions) {
    const { el, fill } = CA;
    const item = (text, kind) => el("label", { class: "answer-item" },
      el("span", { class: "answer-q", text }),
      el("input", {
        type: "text", class: "answer-input", "data-question": text, autocomplete: "off",
        maxlength: "500", placeholder: answerHint(text, kind),
      }));
    const group = (title, items, kind) => items.length
      ? el("fieldset", { class: "answer-group" }, el("legend", { text: title }), items.map((t) => item(t, kind)))
      : null;
    fill(form,
      el("p", { class: "hint", text: "Answer what you know and leave the rest. Your answers are added to the end of the brief and the design is planned again." }),
      group("Questions to confirm", questions, "question"),
      group("What was assumed", assumptions, "assumption"),
      el("label", { class: "answer-item" },
        el("span", { class: "answer-q", text: "Anything else to add or change?" }),
        el("textarea", {
          class: "answer-extra", rows: "2", maxlength: "500",
          placeholder: "e.g. Developers use GitHub Copilot, or keep chat logs for 2 years",
        })),
      el("p", { class: "answer-error", role: "alert", hidden: true }),
      el("div", { class: "answer-actions" },
        el("button", { type: "submit", class: "btn btn-primary", text: "Re-plan with my answers" }),
        el("button", { type: "button", class: "btn btn-ghost", text: "Cancel", onclick: () => this.setAnswering(false) })));
  }

  submitAnswers() {
    const form = this.q(".answer-form");
    const answers = [...form.querySelectorAll(".answer-input")]
      .map((input) => ({ question: input.dataset.question, answer: input.value.trim() }))
      .filter((a) => a.answer);
    const extra = form.querySelector(".answer-extra").value.trim();
    if (extra) answers.push({ question: "", answer: extra });
    const error = form.querySelector(".answer-error");
    if (!answers.length) {
      error.textContent = "Answer at least one question, or press Cancel.";
      error.hidden = false;
      return;
    }
    this.onReplan(answers);
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
      // The name is the words drawn in the box, so what is read out matches what is seen.
      const words = [...node.querySelectorAll("text")].map((t) => t.textContent.trim()).filter(Boolean).join(" ");
      node.setAttribute("aria-label", words || (comp.service ? `${comp.service}: ${comp.label}` : comp.label));
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
    if (this.drawNext && typeof Drafting !== "undefined") Drafting.drawIn(canvas);
    this.drawNext = false;
    this.wireNodes(canvas, (id) => this.select(this.state.selectedId === id ? null : id));
    const icons = d.provider === "oss" ? "Icons are each project's own logo." : `Icons are ${d.provider_name}'s official architecture icons.`;
    this.q(".icon-note").textContent = d.official_icons ? icons : "";
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
        el("b", { class: "stat-value", "data-value": term.on_demand, text: money(term.on_demand) }),
        el("span", { class: "stat-sub", text: `${money(cost.monthly)} in the first month` })),
      el("div", { class: "stat" },
        el("span", { class: "stat-label", text: term.commitment ? `With ${term.commitment} commitments` : "With commitments" }),
        term.committed != null
          ? [el("b", { class: "stat-value", "data-value": term.committed, text: money(term.committed) }),
            el("span", { class: "stat-sub good", text: `Save ${money(save)} (${Math.round((save / term.on_demand) * 100)}%)` })]
          : [el("b", { class: "stat-value muted", text: "–" }),
            el("span", { class: "stat-sub", text: cost.break_even_months
              ? `A 1-year commitment pays off after about ${plural(cost.break_even_months, "month")}`
              : "Commitments start at 1 year" })]));

    // Prepaid credits: cloud credits count against the whole bill, model credits (OpenAI,
    // Hugging Face, Anthropic) only against spend on language models.
    const credits = this.state.credits;
    const aiMonthly = cost.lines.filter((l) => l.capability === "llm-inference").reduce((s, l) => s + l.monthly, 0);
    const hasCredits = credits.cloud > 0 || credits.ai > 0;
    const afterCredits = (amount, months) => Math.max(0, amount - credits.cloud - Math.min(credits.ai, aiMonthly * months));
    const covered = credits.cloud + Math.min(credits.ai, aiMonthly * 36);
    const coverMonths = cost.monthly > 0 ? covered / cost.monthly : 0;

    const table = el("table", { class: "cost-table" },
      el("thead", {}, el("tr", {}, ["Period", "On demand", "With commitments", "You save", hasCredits && "After credits"]
        .filter(Boolean).map((h) => el("th", { text: h })))),
      el("tbody", {}, terms.map((t) => el("tr", { class: t.months === this.state.term ? "current" : null },
        el("td", { text: t.label }),
        el("td", { text: money(t.on_demand) }),
        el("td", { text: t.committed != null ? money(t.committed) : "–" }),
        el("td", { class: "good", text: t.committed != null ? money(t.on_demand - t.committed) : "–" }),
        hasCredits && el("td", { class: "credit-cell", text: money(afterCredits(t.committed ?? t.on_demand, t.months)) })))));

    const creditInput = (key, label, hint) => el("label", { class: "credit-field" },
      el("span", { class: "credit-label", text: label }),
      el("span", { class: "credit-input" }, "$", el("input", {
        type: "number", min: "0", step: "100", inputmode: "numeric", value: credits[key] || "", placeholder: "0",
        "aria-label": label, title: hint,
        onchange: (e) => {
          const value = Math.max(0, Number(e.target.value) || 0);
          if (value === (this.state.credits[key] || 0)) return;
          this.state.credits = { ...this.state.credits, [key]: value };
          CA.store("clarchy.credits", this.state.credits);
          // Re-render after the event: the input being changed is replaced by the render.
          setTimeout(() => this.renderCost(this.state.design), 0);
        },
      })));
    const creditPanel = el("div", { class: "credits" },
      el("h3", { class: "cost-subhead", text: "Prepaid credits" }),
      el("div", { class: "credit-row" },
        creditInput("cloud", `${d.provider_name} credits`, "Startup or promotional credits that apply to the whole cloud bill"),
        creditInput("ai", "Model credits", "OpenAI, Hugging Face or Anthropic credits; they count against language-model spend only"),
        el("p", { class: "credit-result", text: hasCredits
          ? `Credits cover about ${coverMonths >= 36 ? "the whole 3 years" : CA.plural(Math.round(coverMonths * 10) / 10, "month")} of this bill${credits.ai > 0 ? `; model credits apply to ${money(aiMonthly)} a month of model spend` : ""}.`
          : "Add credits from your cloud provider, OpenAI, Hugging Face or Anthropic to see what you actually pay." })));

    const lines = [...cost.lines].sort((a, b) => b.monthly - a.monthly);
    const breakdown = el("div", { class: "cost-lines" }, lines.map((line) => el("details", { class: "cost-line" },
      el("summary", {},
        el("span", { class: "svc" }, el("b", { text: line.service }), el("span", { text: line.label })),
        el("span", { class: "line-tags" },
          line.approximate && el("span", { class: "tag close", title: "Priced from the vendor's pricing page, not the cloud provider's price list", text: "Approx." }),
          line.commitment && el("span", { class: "tag neutral", title: line.commitment, text: "Commitment eligible" })),
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
      creditPanel,
      el("h3", { class: "cost-subhead", text: "Monthly breakdown" }),
      breakdown,
      el("div", { class: "cost-notes" },
        el("p", { text: `${cost.price_region} list prices in ${cost.currency}, as of ${cost.as_of} (${cost.source}).` }),
        cost.commitment_notes.length > 0 && el("ul", {}, cost.commitment_notes.map((n) => el("li", { text: n }))),
        el("ul", {}, cost.assumptions.map((n) => el("li", { text: n }))),
        cost.calculator && el("p", {}, "Check with the ", el("a", { href: cost.calculator, target: "_blank", rel: "noopener noreferrer", text: "official calculator ↗" }))));    if (this.state.view === "cost") this.countCosts();
  }

  // ---------- policies ----------
  renderPolicies(d) {
    const { el, fill, plural } = CA;
    const box = this.q(".policies");
    const list = d.policies || [];
    if (!list.length) {
      fill(box, el("div", { class: "cost-empty" },
        el("h3", { text: "No AI or data regulations matched this design" }),
        el("p", { text: "Policies appear when the design uses language models, runs in a regulated region, or states a compliance regime such as GDPR, HIPAA, PCI DSS, SOX or ISO 27001." })));
      return;
    }
    const total = (s) => list.reduce((n, p) => n + p.counts[s], 0);
    const STATUS = {
      covered: { tag: "exact", label: "In the design" },
      gap: { tag: "partial", label: "Gap" },
      action: { tag: "neutral", label: "For your team" },
    };
    const obligation = (o) => el("li", { class: `obligation ${o.status}` },
      el("span", { class: `tag ${STATUS[o.status].tag}`, text: STATUS[o.status].label }),
      el("div", {},
        el("p", { text: o.text }),
        o.status === "covered" && el("p", { class: "ob-detail", text: `Covered by ${o.by.join(", ")}.` }),
        o.status === "gap" && o.suggest.length > 0 && el("p", { class: "ob-detail", text: `Consider adding ${o.suggest[0].capability.replace(/-/g, " ")}: ${o.suggest[0].description}` })));
    fill(box,
      el("div", { class: "policy-summary" },
        el("p", {}, el("b", { text: plural(list.length, "policy", "policies") }), " apply to this design: ",
          `${total("covered")} obligations are covered by the design, `,
          el("span", { class: total("gap") ? "gap-count" : null, text: `${plural(total("gap"), "gap")}` }),
          `, and ${plural(total("action"), "action")} for your team.`)),
      el("div", { class: "policy-list" }, list.map((p, i) => el("details", { class: "policy", open: i === 0 ? true : null },
        el("summary", {},
          el("span", { class: "policy-name" }, el("b", { text: p.name }), p.kind && el("span", { text: p.kind })),
          el("span", { class: "policy-counts" },
            p.counts.covered > 0 && el("span", { class: "tag exact", text: `${p.counts.covered} covered` }),
            p.counts.gap > 0 && el("span", { class: "tag partial", text: `${p.counts.gap} gap${p.counts.gap === 1 ? "" : "s"}` }),
            p.counts.action > 0 && el("span", { class: "tag neutral", text: `${p.counts.action} to do` }))),
        el("div", { class: "policy-body" },
          p.summary && el("p", { class: "policy-text", text: p.summary }),
          p.note && el("p", { class: "hint", text: p.note }),
          el("ul", { class: "obligations" }, p.obligations.map(obligation)),
          p.url && el("a", { class: "price-link", href: p.url, target: "_blank", rel: "noopener noreferrer", text: "Read the source ↗" }))))),
      el("p", { class: "hint", text: "A design checklist, not legal advice. Check the current text with each source and involve your privacy and legal teams early." }));
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
