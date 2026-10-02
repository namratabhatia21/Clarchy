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
  const PLOTTED = ".plan-card, .howto-step, .about-contact";
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

  // ---------- the pantograph (site.py draws it finished; this runs it) ----------
  // A fixed pivot O and two bars of the same length meeting at the elbow J keep the pencil
  // P twice as far from O as the tracer T; C and D, halfway along the bars, hold T.
  function makePantograph(svg) {
    if (!svg) return null;
    const pairs = (text) => text.trim().split(/\s+/).map((p) => p.split(",").map(Number));
    const [[ox, oy]] = pairs(svg.dataset.pivot);
    const bar = Number(svg.dataset.bar);
    const sketch = pairs(svg.dataset.sketch);
    const lengths = [0];
    for (let i = 1; i < sketch.length; i++) {
      lengths.push(lengths[i - 1] + Math.hypot(sketch[i][0] - sketch[i - 1][0], sketch[i][1] - sketch[i - 1][1]));
    }
    const total = lengths[lengths.length - 1];
    const copy = svg.querySelector(".cg-copy");
    const bars = (name) => [...svg.querySelectorAll(`.${name}`)];
    const lines = { oj: bars("oj"), jp: bars("jp"), ct: bars("ct"), dt: bars("dt") };
    const parts = { J: svg.querySelector(".cg-j"), C: svg.querySelector(".cg-c"), D: svg.querySelector(".cg-d"), T: svg.querySelector(".cg-tracer"), P: svg.querySelector(".cg-pencil") };
    const f = (n) => n.toFixed(1);
    return function (progress) {
      const at = progress * total;
      let i = 1;
      while (i < sketch.length - 1 && lengths[i] < at) i++;
      const [x0, y0] = sketch[i - 1];
      const [x1, y1] = sketch[i];
      const k = lengths[i] > lengths[i - 1] ? (at - lengths[i - 1]) / (lengths[i] - lengths[i - 1]) : 1;
      const T = [x0 + (x1 - x0) * k, y0 + (y1 - y0) * k];
      const P = [ox + 2 * (T[0] - ox), oy + 2 * (T[1] - oy)];
      const dx = P[0] - ox, dy = P[1] - oy, d = Math.hypot(dx, dy);
      const h = Math.sqrt(Math.max(bar * bar - (d * d) / 4, 0));
      let nx = -dy / d, ny = dx / d;
      if (ny > 0) { nx = -nx; ny = -ny; }
      const J = [(ox + P[0]) / 2 + h * nx, (oy + P[1]) / 2 + h * ny];
      const C = [(ox + J[0]) / 2, (oy + J[1]) / 2];
      const D = [(J[0] + P[0]) / 2, (J[1] + P[1]) / 2];
      const set = (els, a, b) => els.forEach((el) => {
        el.setAttribute("x1", f(a[0])); el.setAttribute("y1", f(a[1]));
        el.setAttribute("x2", f(b[0])); el.setAttribute("y2", f(b[1]));
      });
      set(lines.oj, [ox, oy], J); set(lines.jp, J, P); set(lines.ct, C, T); set(lines.dt, D, T);
      for (const [name, point] of Object.entries({ J, C, D, T, P })) {
        parts[name].setAttribute("transform", `translate(${f(point[0])} ${f(point[1])})`);
      }
      copy.style.strokeDasharray = "1";
      copy.style.strokeDashoffset = String(1 - progress);
    };
  }

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
    const heroCta = document.getElementById("hero-cta");
    const topbar = document.querySelector(".topbar");
    const coda = document.getElementById("coda");
    const pantograph = coda && makePantograph(coda.querySelector(".coda-pantograph"));
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

    // The closing frame's pantograph copies its sketch as the frame scrolls into view, and
    // takes the copy back on the way up.
    function openCoda() {
      const box = coda.getBoundingClientRect();
      const shown = box.top < window.innerHeight && box.bottom > 0;
      if (pantograph) {
        const p = reduced.matches ? 1 : Math.min(1, Math.max(0, (window.innerHeight - box.top) / box.height));
        pantograph(1 - (1 - p) ** 2);
      }
      return shown;
    }

    function update() {
      queued = false;
      if (start.offsetParent === null) { // the run view or another page is showing
        topbar?.classList.remove("on-poster", "cta-out");
        return;
      }
      const y = window.scrollY;
      const angle = y * DEG_PER_PX;
      const codaShown = coda ? openCoda() : false;
      if (poster) {
        // The header sits on the poster, and the instruments wait, until it scrolls away
        // (and again while the closing frame is on screen).
        const below = topbar ? topbar.offsetHeight : 0;
        const over = poster.getBoundingClientRect().bottom > below + 4;
        topbar?.classList.toggle("on-poster", over);
        instruments.classList.toggle("on-poster", over || codaShown);
        if (posterDial && !reduced.matches) posterDial.setAttribute("transform", `rotate(${(angle * 2).toFixed(2)})`);
        // Once the hero's button has gone under the header, the header offers the brief.
        if (heroCta) topbar?.classList.toggle("cta-out", heroCta.getBoundingClientRect().bottom < below);
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

    // The hero's button, and the header's once it shows, take you to the brief and put the
    // cursor in it. Elsewhere the header's link opens the home page at the brief (app.js).
    // It listens first (capture), so the page router doesn't also act on the header's link.
    document.addEventListener("click", (e) => {
      const trigger = e.target.closest && e.target.closest("[data-to-brief]");
      if (!trigger || start.offsetParent === null) return;
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      e.stopPropagation();
      document.getElementById("brief").scrollIntoView({ behavior: reduced.matches ? "auto" : "smooth" });
      document.getElementById("requirements")?.focus({ preventScroll: true });
    }, true);
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
