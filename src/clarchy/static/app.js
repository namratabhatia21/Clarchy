"use strict";

// Boot and routing: #plan (default), #examples, #examples/<id>, #services[?filters].

(async function main() {
  const { $, api } = CA;

  function parseHash() {
    const raw = location.hash.replace(/^#\/?/, "");
    const [path, query = ""] = raw.split("?");
    const [first, sub] = path.split("/");
    const aliases = { catalog: "services", designer: "examples", "": "plan" };
    const page = aliases[first] ?? first;
    return {
      page: ["plan", "examples", "services", "blog", "about"].includes(page) ? page : "plan",
      sub,
      params: new URLSearchParams(query),
    };
  }

  const SHEETS = {
    plan: "01 · Plan", examples: "02 · Examples", services: "03 · Services", blog: "04 · Blog", about: "05 · About",
  };

  function route() {
    const { page, sub, params } = parseHash();
    $("sheet-name").textContent = SHEETS[page];
    for (const section of document.querySelectorAll(".page")) section.hidden = section.dataset.page !== page;
    for (const link of document.querySelectorAll(".main-link")) {
      if (link.dataset.page === page) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (page === "examples") Examples.show(sub);
    if (page === "services") Services.show(params);
    if (page === "blog") Blog.show(sub);
    if (page === "about") window.scrollTo({ top: 0 });
  }

  const [meta, samples, patterns] = await Promise.all([api.meta(), api.samples(), api.patterns()]);
  CA.meta = meta;
  $("version").textContent = `v${meta.version}`;

  const chip = $("engine-chip");
  chip.hidden = false;
  if (CA.MODE === "static") {
    chip.textContent = CA.DATA.engine ? "Runs in your browser" : "Demo · recorded runs";
    chip.title = CA.DATA.engine ? "Plans run on this device with Clarchy's Python engine (Pyodide)" : "";
    chip.classList.add("demo");
  } else if (meta.engine && meta.engine.mode === "ai") {
    chip.textContent = `AI · ${meta.engine.model}`;
    chip.classList.add("ai");
    chip.title = meta.engine.label || "";
  } else {
    chip.textContent = "Rule-based planner";
    chip.title = (meta.engine && meta.engine.reason) || "";
  }

  Plan.init(meta, samples);
  Examples.init(patterns);
  Services.initControls();
  await Blog.init();
  window.addEventListener("hashchange", route);
  route();
})();
