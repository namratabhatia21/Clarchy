"use strict";

// Drafting instruments and motion for the home page (ADR 0009): a large protractor that
// turns as you scroll, an architect's scale that marks how far down the page you are, a
// detail drawing that assembles itself stage by stage, and diagrams that draw themselves
// in. Purely decorative: nothing here changes what the page does, and it all stands
// still for people who prefer reduced motion.

const Drafting = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  const DEG_PER_PX = 0.09;
  const NEEDLE = 200; // degrees, measured clockwise from the right-hand side

  function svg(tag, attrs = {}, text) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const polar = (r, deg) => {
    const a = (deg * Math.PI) / 180;
    return [(r * Math.cos(a)).toFixed(2), (r * Math.sin(a)).toFixed(2)];
  };

  // ---------- the protractor ----------
  function buildDial(root) {
    const R = 300;
    const ticks = { minor: "", mid: "", major: "" };
    for (let a = 0; a < 360; a++) {
      const kind = a % 10 === 0 ? "major" : a % 5 === 0 ? "mid" : "minor";
      const len = { major: 24, mid: 15, minor: 8 }[kind];
      const [x1, y1] = polar(R - len, a);
      const [x2, y2] = polar(R, a);
      ticks[kind] += `M${x1} ${y1}L${x2} ${y2}`;
      // an inner scale, as on a full-circle protractor
      if (a % 5 === 0) {
        const [u1, v1] = polar(196, a);
        const [u2, v2] = polar(196 + (a % 10 === 0 ? 12 : 6), a);
        ticks.minor += `M${u1} ${v1}L${u2} ${v2}`;
      }
    }
    const dial = svg("g", { class: "dial" });
    dial.append(
      svg("circle", { r: R, class: "rim" }),
      svg("circle", { r: 236, class: "hair" }),
      svg("circle", { r: 196, class: "hair" }),
      svg("circle", { r: 120, class: "construction" }),
      svg("path", { d: `M${-R} 0H${R}M0 ${-R}V${R}`, class: "construction" }),
      svg("path", { d: ticks.minor, class: "tick" }),
      svg("path", { d: ticks.mid, class: "tick" }),
      svg("path", { d: ticks.major, class: "tick major" }),
      svg("circle", { r: 7, class: "hair" }),
      svg("path", { d: "M-14 0H14M0 -14V14", class: "hair" }),
    );
    for (let a = 0; a < 360; a += 10) {
      dial.append(svg("text", {
        class: "num",
        transform: `rotate(${a}) translate(254 0) rotate(90)`,
        "text-anchor": "middle",
      }, String(a)));
    }
    for (let a = 0; a < 360; a += 30) {
      dial.append(svg("text", {
        class: "num inner",
        transform: `rotate(${a}) translate(176 0) rotate(90)`,
        "text-anchor": "middle",
      }, String((360 - a) % 360)));
    }
    root.querySelector(".dial-svg").append(dial);

    // The needle stays put; the dial turns under it, so the reading changes as you scroll.
    const [nx, ny] = polar(318, NEEDLE);
    const [lx, ly] = polar(96, NEEDLE + 14); // inside the dial, clear of the page text
    const needle = root.querySelector(".needle-svg");
    needle.append(
      svg("path", { d: `M0 0L${nx} ${ny}`, class: "needle" }),
      svg("circle", { r: 5, class: "needle-pivot" }),
      svg("text", { x: lx, y: ly, class: "reading", "text-anchor": "middle" }, "000°"),
    );
    return { dial: root.querySelector(".dial-svg"), reading: needle.querySelector(".reading") };
  }

  // ---------- the architect's scale ----------
  function buildScale(root) {
    const length = 600;
    let minor = "";
    let major = "";
    const out = root.querySelector(".scale-svg");
    for (let y = 0; y <= length; y += 10) {
      if (y % 50 === 0) {
        major += `M0 ${y}H16`;
        out.append(svg("text", { x: 20, y: y + 3.5, class: "num" }, String(y / 50)));
      } else {
        minor += `M0 ${y}H${y % 25 === 0 ? 11 : 7}`;
      }
    }
    out.prepend(svg("path", { d: minor, class: "tick" }), svg("path", { d: major, class: "tick major" }));
    return { marker: root.querySelector(".scale-marker"), length };
  }

  // ---------- diagrams draw themselves in ----------
  function drawIn(canvas) {
    const drawing = canvas && canvas.querySelector("svg");
    if (!drawing || reduced.matches) return;
    for (const edge of drawing.querySelectorAll(".ca-edge")) edge.setAttribute("pathLength", "1");
    drawing.querySelectorAll("g.node").forEach((node, i) => node.style.setProperty("--i", i));
    canvas.classList.remove("drawing");
    void canvas.offsetWidth; // restart the animation
    canvas.classList.add("drawing");
    clearTimeout(canvas.drawTimer);
    canvas.drawTimer = setTimeout(() => canvas.classList.remove("drawing"), 2400);
  }

  // ---------- drawings plotted as they come into view ----------
  // Things already on screen stay as they are; the rest are plotted top to bottom the
  // first time they scroll in (app.css: [data-draw]).
  const PLOTTED = ".proof, .plan-card, .howto-step, .about-contact";
  let watcher = null;
  function reveal() {
    if (reduced.matches || !("IntersectionObserver" in window)) return;
    watcher ||= new IntersectionObserver((entries) => {
      for (const { target, isIntersecting } of entries) {
        if (!target.dataset.draw) {
          target.dataset.draw = isIntersecting ? "seen" : "waiting";
          if (isIntersecting) watcher.unobserve(target);
        } else if (isIntersecting) {
          target.dataset.draw = "drawn";
          watcher.unobserve(target);
        }
      }
    }, { rootMargin: "0px 0px -6% 0px" });
    for (const node of document.querySelectorAll(PLOTTED)) {
      if (!node.dataset.draw && !node.closest(".page[hidden]")) watcher.observe(node);
    }
  }
  window.addEventListener("clarchy:page", () => requestAnimationFrame(reveal));

  // ---------- scroll ----------
  // Runs once the home page is on screen: at load, or when it is first opened from another
  // page (app.js).
  function init() {
    const start = document.getElementById("plan-start");
    const instruments = document.querySelector(".instruments");
    if (!start || !instruments || start.dataset.drafting) return;
    start.dataset.drafting = "true";
    const protractor = buildDial(instruments.querySelector(".protractor"));
    const scale = buildScale(instruments.querySelector(".scale-rule"));
    const figure = document.querySelector(".story-fig");
    const steps = [...document.querySelectorAll(".story-step")];
    const how = [...document.querySelectorAll(".story .how-line li")];
    const poster = document.getElementById("poster");
    const posterDial = poster && poster.querySelector(".pd-dial");
    const posterReading = poster && poster.querySelector(".pd-reading");
    const topbar = document.querySelector(".topbar");
    let stage = -1;
    let queued = false;

    function setStage(n) {
      if (n === stage) return;
      stage = n;
      for (let k = 1; k <= steps.length; k++) figure.classList.toggle(`s${k}`, k <= n);
      steps.forEach((step, i) => step.classList.toggle("active", i + 1 === n));
      how.forEach((li, i) => {
        li.classList.toggle("done", i + 1 < n);
        li.classList.toggle("active", i + 1 === n);
      });
    }

    function update() {
      queued = false;
      if (start.offsetParent === null) { // the run view or another page is showing
        topbar?.classList.remove("on-poster");
        return;
      }
      const y = window.scrollY;
      const angle = y * DEG_PER_PX;
      if (poster) {
        // The header sits on the poster, and the instruments wait, until it scrolls away.
        const over = poster.getBoundingClientRect().bottom > (topbar ? topbar.offsetHeight : 0) + 4;
        topbar?.classList.toggle("on-poster", over);
        instruments.classList.toggle("on-poster", over);
        if (posterDial) posterDial.setAttribute("transform", `rotate(${(angle * 2).toFixed(2)})`);
        if (posterReading) {
          posterReading.textContent = `${((((212 - angle * 2) % 360) + 360) % 360).toFixed(0).padStart(3, "0")}°`;
        }
      }
      protractor.dial.style.transform = `rotate(${angle.toFixed(2)}deg)`;
      const reading = ((((NEEDLE - angle) % 360) + 360) % 360).toFixed(0).padStart(3, "0");
      protractor.reading.textContent = `${reading}°`;
      const room = document.documentElement.scrollHeight - window.innerHeight;
      const progress = room > 0 ? Math.min(1, y / room) : 0;
      scale.marker.style.transform = `translateY(${(progress * scale.length).toFixed(1)}px)`;
      let n = 0;
      for (const [i, step] of steps.entries()) {
        if (step.getBoundingClientRect().top < window.innerHeight * 0.6) n = i + 1;
      }
      setStage(n);
    }

    const schedule = () => {
      if (!queued) { queued = true; requestAnimationFrame(update); }
    };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("clarchy:page", () => setTimeout(schedule, 0));
    new MutationObserver(schedule).observe(start, { attributes: true, attributeFilter: ["hidden"] });

    // The poster's buttons take you to the brief and put the cursor in it.
    for (const button of document.querySelectorAll("[data-to-brief]")) {
      button.addEventListener("click", () => {
        document.getElementById("brief").scrollIntoView({ behavior: reduced.matches ? "auto" : "smooth" });
        document.getElementById("requirements")?.focus({ preventScroll: true });
      });
    }
    if (reduced.matches) for (const el of document.querySelectorAll(".story-fig, .drafting-loader")) el.pauseAnimations?.();

    // The massing model in the hero holds the right of the page: the protractor waits until
    // it has scrolled away.
    const model = document.getElementById("hero-model");
    if (model && "IntersectionObserver" in window) {
      new IntersectionObserver(([entry]) => {
        instruments.classList.toggle("yield", entry.isIntersecting);
      }, { threshold: 0.15 }).observe(model);
    }

    // The dial swings into place once, then follows the scroll closely.
    instruments.classList.add("intro");
    update();
    requestAnimationFrame(() => instruments.classList.add("ready"));
    setTimeout(() => instruments.classList.remove("intro"), 1800);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  return { drawIn, start: init };
})();
