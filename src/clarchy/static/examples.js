"use strict";

// The Examples page, a gallery of reviewed reference architectures, and each example in a
// workspace on its own page.

const Examples = (() => {
  const { $, api } = CA;
  let patterns = [];
  let workspace = null;
  const designs = {}; // pattern id -> promise of its AWS design

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

  const svgSource = (svg) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(CA.croppedSvgText(svg, { transparent: true, drawingOnly: true }))}`;

  // Diagrams load when they come into view, so pages that don't show them never fetch them.
  function whenVisible(node, load) {
    if (!("IntersectionObserver" in window)) { load(); return; }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { observer.disconnect(); load(); }
    }, { rootMargin: "300px" });
    observer.observe(node);
  }

  function thumbnail(id, frame, img) {
    whenVisible(frame, async () => {
      const design = await awsDesign(id);
      if (design) img.src = svgSource(design.svg);
    });
  }

  // The cards and filters come with the page (site.py); this adds the drawings and makes
  // the filters work.
  function bindIndex() {
    const grid = $("example-grid");
    if (!grid || grid.dataset.ready) return;
    grid.dataset.ready = "true";
    for (const card of grid.querySelectorAll(".example-card[data-id]")) {
      thumbnail(card.dataset.id, card.querySelector(".example-thumb"), card.querySelector("img"));
    }
    const filters = [...$("example-filters").querySelectorAll("[data-tag]")];
    for (const button of filters) {
      button.addEventListener("click", () => {
        const tag = button.dataset.tag;
        for (const other of filters) other.setAttribute("aria-pressed", String(other === button));
        for (const li of grid.children) li.hidden = tag !== "All" && !(li.dataset.tags || "").split("|").includes(tag);
      });
    }
  }

  async function show(id) {
    const pattern = patterns.find((p) => p.id === id);
    if (!pattern) { CA.go(CA.href("examples"), { replace: true }); return; }
    const crumb = document.querySelector("#page-example [data-crumb]");
    if (crumb) crumb.textContent = pattern.name;
    if (!workspace) workspace = new Workspace($("example-workspace"), { editable: true });
    if (workspace.patternId !== id) {
      workspace.patternId = id;
      const found = await api.pattern(id);
      if (found) await workspace.load(found.spec_yaml);
    }
  }

  function init(list) {
    patterns = list;
    bindIndex();
  }

  return { init, show };
})();
