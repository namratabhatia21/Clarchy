"use strict";

// The How to page: a guide in numbered sections (/how-to/#howto-<section>, or #howto/<section>
// on a single-file build), and an example brief that can be planned straight from the page.

const HowTo = (() => {
  const { $ } = CA;
  let links = [];
  let steps = [];
  let pinned = null; // the section picked in the contents, until the reader scrolls
  let ticking = false;

  function setCurrent(section) {
    for (const link of links) {
      if (link.dataset.section === section) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    }
  }

  // The current section is the last one whose heading has passed a third of the way down.
  function track() {
    ticking = false;
    const page = $("page-howto");
    if (!page || page.hidden || !steps.length) return;
    if (pinned) { setCurrent(pinned); return; }
    const line = window.innerHeight / 3;
    let current = steps[0];
    for (const step of steps) if (step.getBoundingClientRect().top <= line) current = step;
    setCurrent(current.dataset.section);
  }

  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(track); }
  }

  function show(section) {
    const target = section && document.getElementById(`howto-${section}`);
    pinned = target ? section : null;
    if (target) target.scrollIntoView({ block: "start" });
    else window.scrollTo({ top: 0 });
    track();
  }

  // Puts the example brief in the composer on the Plan page, and plans it if asked.
  async function useBrief(now) {
    const text = $("howto-brief-text").textContent.replace(/\s+/g, " ").trim();
    await CA.go(CA.href("plan"));
    Plan.useBrief(text, { now });
  }

  function init() {
    links = [...document.querySelectorAll(".howto-index a")];
    steps = [...document.querySelectorAll(".howto-step")];
    for (const link of links) {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        CA.replaceUrl(link.getAttribute("href"));
        show(link.dataset.section);
      });
    }
    for (const button of document.querySelectorAll("[data-brief]")) {
      button.hidden = !CA.canPlan();
      button.addEventListener("click", () => useBrief(button.dataset.brief === "plan"));
    }
    const unpin = () => { pinned = null; };
    window.addEventListener("wheel", unpin, { passive: true });
    window.addEventListener("touchstart", unpin, { passive: true });
    window.addEventListener("keydown", unpin);
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  return { init, show };
})();
