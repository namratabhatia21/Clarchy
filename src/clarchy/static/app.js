"use strict";

// Boot and routing. On a multi-page site every page has its own address: /, /examples/,
// /examples/<id>/, /services/[?filters], /how-to/[#howto-<step>], /blog/, /blog/<id>/,
// /about/, /privacy/ and /terms/. Each address is a complete page; once one has loaded,
// links switch pages here without reloading, fetching a page's section the first time it
// is shown and keeping it (so a plan in progress survives a look at How to). Single-file
// builds hold every section and route on the hash (#howto, #examples/<id>,
// #howto/<step>). Old hash links (/#examples) go to the new addresses.

(async function main() {
  const { $, api } = CA;
  const PATH = CA.ROUTING === "path";
  const MENU = { example: "examples", post: "blog" }; // the menu item a sub-page belongs to
  const SHEETS = {
    plan: "01 · Plan", examples: "02 · Examples", example: "02 · Examples", services: "03 · Services",
    howto: "04 · How to", blog: "05 · Blog", post: "05 · Blog", about: "06 · About",
    privacy: "Privacy", terms: "Terms",
  };
  const FIRST = {
    "": "plan", examples: "examples", services: "services", "how-to": "howto",
    blog: "blog", about: "about", privacy: "privacy", terms: "terms",
  };

  // "#examples/rag-chatbot" -> { page: "example", sub: "rag-chatbot", params }
  function fromHash(hash) {
    const raw = hash.replace(/^#\/?/, "");
    const [path, query = ""] = raw.split("?");
    const [first, sub] = path.split("/");
    const aliases = { catalog: "services", designer: "examples", "how-to": "howto", help: "howto", "": "plan" };
    let page = aliases[first] ?? first;
    if (!["plan", "examples", "services", "howto", "blog", "about", "privacy", "terms"].includes(page)) return null;
    if (page === "examples" && sub) page = "example";
    if (page === "blog" && sub) page = "post";
    return { page, sub: sub || undefined, params: new URLSearchParams(query) };
  }

  // "/examples/rag-chatbot/" -> { page: "example", sub: "rag-chatbot", params }
  function fromPath(url) {
    const parts = url.pathname.split("/").filter(Boolean);
    let page = FIRST[parts[0] || ""];
    if (!page || parts.length > 2) return null;
    if (parts[1]) {
      if (page === "examples") page = "example";
      else if (page === "blog") page = "post";
      else return null;
    }
    const step = page === "howto" && url.hash.startsWith("#howto-") ? url.hash.slice(7) : undefined;
    return { page, sub: parts[1] || step, params: url.searchParams };
  }

  const parse = (url) => (PATH ? fromPath(url) : fromHash(url.hash));

  // ---------- sections: fetched from their own address the first time ----------
  const fetched = new Map(); // path -> promise of that page's HTML
  function pageHtml(url) {
    const key = url.pathname;
    if (!fetched.has(key)) {
      const request = fetch(key, { headers: { Accept: "text/html" } }).then((res) => {
        if (!res.ok) throw new Error(`${key}: ${res.status}`);
        return res.text();
      });
      request.catch(() => fetched.delete(key));
      fetched.set(key, request);
    }
    return fetched.get(key);
  }

  async function sectionFor(page, url) {
    if ($(`page-${page}`)) return $(`page-${page}`);
    const doc = new DOMParser().parseFromString(await pageHtml(url), "text/html");
    const found = doc.getElementById(`page-${page}`);
    if (!found) throw new Error(`no ${page} section at ${url.pathname}`);
    if ($(`page-${page}`)) return $(`page-${page}`); // another navigation got there first
    const section = document.importNode(found, true);
    section.hidden = true;
    $("main").append(section);
    return section;
  }

  // ---------- each page's script starts the first time the page is shown ----------
  let boot = null; // { meta, samples, patterns }
  const started = new Set();
  async function start(page) {
    if (started.has(page)) return;
    started.add(page);
    const { meta, samples, patterns } = boot;
    if (page === "plan") {
      Plan.init(meta, samples);
      Drafting.start();
    } else if (page === "examples" || page === "example") {
      Examples.init(patterns);
    } else if (page === "services") {
      Services.initControls();
    } else if (page === "howto") {
      HowTo.init();
    } else if (page === "blog" || page === "post") {
      await Blog.init();
    }
  }

  // ---------- the head, when a page is shown without reloading ----------
  let index = {};
  try { index = JSON.parse(($("site-pages") || {}).textContent || "{}"); } catch { /* keep the head */ }
  function setHead(url) {
    const entry = index[url.pathname];
    if (!entry) return;
    const [title, description] = entry;
    const absolute = `${location.origin}${url.pathname}`;
    const set = (selector, attr, value) => {
      const node = document.querySelector(selector);
      if (node) node.setAttribute(attr, value);
    };
    document.title = title;
    set('meta[name="description"]', "content", description);
    set('meta[property="og:title"]', "content", title);
    set('meta[property="og:description"]', "content", description);
    set('meta[property="og:url"]', "content", absolute);
    set('link[rel="canonical"]', "href", absolute);
  }

  // ---------- showing a page ----------
  let current = null;
  async function show(route, url, { scroll = false } = {}) {
    const { page, sub, params } = route;
    const samePage = Boolean(current && current.page === page && current.sub === sub);
    current = { page, sub };
    await start(page);
    document.body.dataset.page = page;
    $("sheet-name").textContent = SHEETS[page];
    for (const section of document.querySelectorAll("main > .page")) section.hidden = section.dataset.page !== page;
    const menu = MENU[page] || page;
    for (const link of document.querySelectorAll(".main-link")) {
      if (link.dataset.page === menu) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    if (PATH) setHead(url);
    // "/#brief" (Start a plan, from How to) opens the home page at the brief.
    const spot = page === "plan" && url.hash ? document.getElementById(url.hash.slice(1)) : null;
    if (spot) spot.scrollIntoView();
    else if (scroll && !samePage && !(page === "howto" && sub)) window.scrollTo({ top: 0 });
    if (page === "example") Examples.show(sub);
    if (page === "services") Services.show(params);
    if (page === "howto") HowTo.show(sub);
    if (page === "post") Blog.show(sub);
    window.dispatchEvent(new CustomEvent("clarchy:page", { detail: { page } }));
  }

  // Goes to a page of this site; resolves once it is showing.
  async function go(target, { replace = false } = {}) {
    const url = new URL(target, location.href);
    const route = url.origin === location.origin ? parse(url) : null;
    if (!route) { location.assign(url.href); return; }
    if (PATH) {
      try {
        await sectionFor(route.page, url);
      } catch {
        location.assign(url.href); // let the server answer
        return;
      }
    }
    if (url.href !== location.href) {
      try {
        if (replace) history.replaceState(null, "", url.href);
        else history.pushState(null, "", url.href);
      } catch { /* some frames refuse; the page still changes */ }
    }
    await show(route, url, { scroll: true });
  }
  CA.go = go;

  // Links to pages of this site switch without reloading. A link to a spot on the same
  // page, or one opened in a new tab, is left to the browser.
  function sitePage(a) {
    if (!a || a.target || a.hasAttribute("download")) return null;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return null;
    if (PATH && url.pathname === location.pathname && url.search === location.search && url.hash) return null;
    return parse(url) ? url : null;
  }

  function wireLinks() {
    document.addEventListener("click", (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const url = sitePage(e.target.closest("a[href]"));
      if (!url) return;
      e.preventDefault();
      go(url.href);
    });
    if (PATH) {
      // A page starts loading while the pointer is on its link, so it shows at once.
      const warm = (e) => {
        const url = sitePage(e.target.closest && e.target.closest("a[href]"));
        if (url && !$(`page-${parse(url).page}`)) pageHtml(url).catch(() => {});
      };
      document.addEventListener("pointerover", warm, { passive: true });
      document.addEventListener("focusin", warm);
      window.addEventListener("popstate", () => {
        const url = new URL(location.href);
        const route = parse(url);
        if (!route) return;
        sectionFor(route.page, url).then(() => show(route, url), () => location.reload());
      });
    } else {
      window.addEventListener("hashchange", () => {
        const route = fromHash(location.hash);
        if (route) show(route, new URL(location.href));
      });
    }
  }

  // ---------- start ----------
  const [meta, samples, patterns] = await Promise.all([api.meta(), api.samples(), api.patterns()]);
  CA.store("clarchy.lead", null); // a sign-up kept by browsers before accounts were removed
  CA.meta = meta;
  boot = { meta, samples, patterns };
  $("project-name").title = `Clarchy ${meta.version}`;
  $("copyright").textContent = `© ${new Date().getFullYear()} Clarchy`;

  // A page built for a hosted API learns which planner it has from that API.
  const chip = $("engine-chip");
  if (CA.MODE === "remote" && chip) {
    chip.hidden = false;
    if (meta.engine && meta.engine.mode === "ai") {
      chip.textContent = `AI · ${meta.engine.model}`;
      chip.classList.add("ai");
      chip.title = meta.engine.label || "";
    } else {
      chip.textContent = "Rule-based planner";
      chip.title = (meta.engine && meta.engine.reason) || "";
    }
  }

  wireLinks();
  const here = new URL(location.href);
  // Old links such as clarchy.com/#examples/rag-chatbot.
  const legacy = PATH && here.pathname === "/" && here.hash ? fromHash(here.hash) : null;
  if (legacy && legacy.page !== "plan") {
    await go(CA.href(legacy.page, legacy.sub, legacy.params.toString()), { replace: true });
    return;
  }
  const route = parse(here) || { page: document.body.dataset.page || "plan", sub: undefined, params: here.searchParams };
  await show(route, here);
})();
