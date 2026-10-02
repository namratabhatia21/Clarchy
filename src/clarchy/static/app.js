"use strict";

// Boot and routing: #plan (default), #examples, #examples/<id>, #services[?filters],
// #howto, #howto/<section>, #blog, #blog/<id>, #about, #privacy and #terms.

(async function main() {
  const { $, api } = CA;

  function parseHash() {
    const raw = location.hash.replace(/^#\/?/, "");
    const [path, query = ""] = raw.split("?");
    const [first, sub] = path.split("/");
    const aliases = { catalog: "services", designer: "examples", "how-to": "howto", help: "howto", "": "plan" };
    const page = aliases[first] ?? first;
    return {
      page: ["plan", "examples", "services", "howto", "blog", "about", "privacy", "terms"].includes(page) ? page : "plan",
      sub,
      params: new URLSearchParams(query),
    };
  }

  const SHEETS = {
    plan: "01 · Plan", examples: "02 · Examples", services: "03 · Services",
    howto: "04 · How to", blog: "05 · Blog", about: "06 · About", privacy: "Privacy", terms: "Terms",
  };

  function route() {
    const { page, sub, params } = parseHash();
    document.body.dataset.page = page;
    $("sheet-name").textContent = SHEETS[page];
    for (const section of document.querySelectorAll(".page")) section.hidden = section.dataset.page !== page;
    for (const link of document.querySelectorAll(".main-link")) {
      if (link.dataset.page === page) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (page === "examples") Examples.show(sub);
    if (page === "services") Services.show(params);
    if (page === "howto") HowTo.show(sub);
    if (page === "blog") Blog.show(sub);
    if (["about", "privacy", "terms"].includes(page)) window.scrollTo({ top: 0 });
  }

  const [meta, samples, patterns] = await Promise.all([api.meta(), api.samples(), api.patterns()]);
  CA.meta = meta;
  $("project-name").title = `Clarchy ${meta.version}`;
  $("copyright").textContent = `© ${new Date().getFullYear()} Clarchy`;
  if (meta.prices_as_of) {
    const asOf = new Date(`${meta.prices_as_of}T00:00:00`);
    $("prices-as-of").textContent = Number.isNaN(asOf.getTime()) ? meta.prices_as_of
      : `AWS, ${asOf.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`;
  }

  const chip = $("engine-chip");
  chip.hidden = false;
  if (CA.MODE === "static") {
    chip.textContent = CA.DATA.engine ? "Runs in your browser" : "Demo";
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
  Examples.preview($("proof"));
  Services.initControls();
  HowTo.init();
  await Blog.init();
  window.addEventListener("hashchange", route);
  route();
})();
