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
      page: ["plan", "examples", "services"].includes(page) ? page : "plan",
      sub,
      params: new URLSearchParams(query),
    };
  }

  function route() {
    const { page, sub, params } = parseHash();
    for (const section of document.querySelectorAll(".page")) section.hidden = section.dataset.page !== page;
    for (const link of document.querySelectorAll(".main-link")) {
      if (link.dataset.page === page) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (page === "examples") Examples.show(sub);
    if (page === "services") Services.show(params);
  }

  const [meta, samples, patterns] = await Promise.all([api.meta(), api.samples(), api.patterns()]);
  CA.meta = meta;
  $("version").textContent = `CloudArchie ${meta.version}`;

  const chip = $("engine-chip");
  chip.hidden = false;
  if (CA.MODE === "static") {
    chip.textContent = "Demo · recorded runs";
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
  window.addEventListener("hashchange", route);
  route();
})();
