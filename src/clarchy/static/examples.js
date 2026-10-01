"use strict";

// The Examples page: a gallery of reviewed reference architectures; each opens in a workspace.

const Examples = (() => {
  const { $, el, fill, api } = CA;
  const TAG_RULES = [
    ["Kubernetes", ["kubernetes", "event-autoscaling"]],
    ["AI", ["llm-inference", "vector-search"]],
    ["Data", ["stream", "batch-etl", "data-warehouse"]],
    ["Event-driven", ["message-queue", "event-bus", "workflow"]],
    ["Serverless", ["serverless-function"]],
    ["Containers", ["container-service"]],
    ["Web", ["cdn"]],
  ];
  let patterns = [];
  let filter = "All";
  let workspace = null;
  const thumbs = {};

  function tagsFor(pattern) {
    const caps = new Set(pattern.capabilities || []);
    return TAG_RULES.filter(([, list]) => list.some((c) => caps.has(c))).map(([tag]) => tag);
  }

  async function thumbnail(pattern, img) {
    if (!thumbs[pattern.id]) {
      thumbs[pattern.id] = (async () => {
        const found = await api.pattern(pattern.id);
        if (!found) return null;
        const result = await api.design(found.spec_yaml, "aws");
        return result.ok ? result.body.svg : null;
      })();
    }
    const svg = await thumbs[pattern.id];
    if (svg) img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(CA.croppedSvgText(svg, { transparent: true }))}`;
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
      const img = el("img", { alt: `${p.name} on AWS`, loading: "lazy" });
      thumbnail(p, img);
      return el("li", {}, el("a", { class: "example-card", href: `#examples/${p.id}` },
        el("div", { class: "example-thumb" }, img),
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

  return { init, show };
})();
