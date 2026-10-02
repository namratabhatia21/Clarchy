"use strict";

// The Examples page: a gallery of reviewed reference architectures; each opens in a workspace.

const Examples = (() => {
  const { $, el, fill, api } = CA;
  const TAG_RULES = [
    ["Kubernetes", ["kubernetes", "event-autoscaling"]],
    ["AI", ["llm-inference", "vector-search", "agent-orchestration", "llm-gateway"]],
    ["Data", ["stream", "batch-etl", "data-warehouse"]],
    ["Event-driven", ["message-queue", "event-bus", "workflow"]],
    ["Serverless", ["serverless-function"]],
    ["Containers", ["container-service"]],
    ["Web", ["cdn"]],
  ];
  let patterns = [];
  let filter = "All";
  let workspace = null;
  const designs = {}; // pattern id -> promise of its AWS design

  function tagsFor(pattern) {
    const caps = new Set(pattern.capabilities || []);
    return TAG_RULES.filter(([, list]) => list.some((c) => caps.has(c))).map(([tag]) => tag);
  }

  function awsDesign(id) {
    if (!designs[id]) {
      designs[id] = (async () => {
        const found = await api.pattern(id);
        if (!found) return null;
        const result = await api.design(found.spec_yaml, "aws");
        return result.ok ? result.body : null;
      })();
    }
    return designs[id];
  }

  const svgSource = (svg) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(CA.croppedSvgText(svg, { transparent: true }))}`;

  // Diagrams load when they come into view, so pages that don't show them never fetch them.
  function whenVisible(node, load) {
    if (!("IntersectionObserver" in window)) { load(); return; }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { observer.disconnect(); load(); }
    }, { rootMargin: "300px" });
    observer.observe(node);
  }

  function thumbnail(pattern, frame, img) {
    whenVisible(frame, async () => {
      const design = await awsDesign(pattern.id);
      if (design) img.src = svgSource(design.svg);
    });
  }

  // The home page's real result: a reference example drawn on AWS, with its size and cost.
  function preview(figure) {
    whenVisible(figure, async () => {
      const design = await awsDesign(figure.dataset.example);
      if (!design) { figure.hidden = true; return; }
      figure.querySelector("img").src = svgSource(design.svg);
      const monthly = design.cost && design.cost.available ? design.cost.monthly : null;
      figure.querySelector(".proof-title").textContent = `${design.name} on AWS`;
      figure.querySelector(".proof-meta").textContent = [
        CA.plural(design.components.length, "service"),
        monthly !== null && `about ${CA.money(monthly)} a month`,
        design.policies.length > 0 && `${CA.plural(design.policies.length, "policy", "policies")} checked`,
      ].filter(Boolean).join(" · ");
    });
  }

  function renderFilters() {
    const tags = ["All", ...TAG_RULES.map(([t]) => t).filter((t) => patterns.some((p) => tagsFor(p).includes(t)))];
    fill($("example-filters"), tags.map((t) => el("button", {
      type: "button", class: "chip", "aria-pressed": String(t === filter),
      onclick: () => { filter = t; renderFilters(); renderGrid(); },
    }, t)));
  }

  function renderGrid() {
    const shown = patterns.filter((p) => filter === "All" || tagsFor(p).includes(filter));
    fill($("example-grid"), shown.map((p) => {
      const img = el("img", { alt: `${p.name} on AWS` });
      const frame = el("div", { class: "example-thumb" }, img);
      thumbnail(p, frame, img);
      return el("li", {}, el("a", { class: "example-card", href: `#examples/${p.id}` },
        frame,
        el("div", { class: "example-body" },
          el("h2", { text: p.name }),
          el("p", { text: p.summary || "" })),
        el("dl", { class: "card-block" },
          el("div", {}, el("dt", { text: "No." }), el("dd", { text: String(patterns.indexOf(p) + 1).padStart(2, "0") })),
          el("div", {}, el("dt", { text: "Type" }), el("dd", { text: tagsFor(p).slice(0, 2).join(" · ") || "General" })),
          el("div", {}, el("dt", { text: "Services" }), el("dd", { text: String(p.components || 0) })))));
    }));
  }

  async function show(id) {
    const pattern = patterns.find((p) => p.id === id);
    $("examples-index").hidden = Boolean(pattern);
    $("example-detail").hidden = !pattern;
    if (!pattern) return;
    if (!workspace) workspace = new Workspace($("example-workspace"), { editable: true });
    if (workspace.patternId !== id) {
      workspace.patternId = id;
      const found = await api.pattern(id);
      if (found) await workspace.load(found.spec_yaml);
    }
    window.scrollTo({ top: 0 });
  }

  function init(list) {
    patterns = list;
    renderFilters();
    renderGrid();
  }

  return { init, show, preview };
})();
