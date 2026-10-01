"use strict";

// The Plan page: describe an app (type or attach a document), watch the pipeline run,
// then explore the result in a workspace.

const Plan = (() => {
  const { $, el, fill, api } = CA;
  const DRAFT_KEY = "cloudarchie.plan-draft";
  const STAGE_ORDER = ["read", "understand", "design", "toolchain", "workflows", "map"];
  const STAGE_TITLES = {
    read: "Read the requirements",
    understand: "Understand what's needed",
    design: "Design the architecture",
    toolchain: "Add build and deploy",
    workflows: "Describe the workflows",
    map: "Map to every cloud",
  };
  const ACCEPTED = [".docx", ".pdf", ".xlsx", ".md", ".markdown", ".txt", ".csv"];
  const MAX_BYTES = 10 * 1024 * 1024;

  let samples = [];
  let workspace = null;
  const run = { file: null, active: false, started: {}, stageEls: {} };

  function formatBytes(n) {
    return n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`;
  }

  function showError(message) {
    const box = $("composer-error");
    box.hidden = !message;
    box.textContent = message || "";
  }

  function setFile(file) {
    if (file) {
      const ext = (file.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
      if (!ACCEPTED.includes(ext)) {
        showError(`${ext || "That file type"} isn't supported. Use Word, PDF, Excel, Markdown or text.`);
        return;
      }
      if (file.size > MAX_BYTES) {
        showError("That file is larger than 10 MB. Attach a smaller document.");
        return;
      }
    }
    showError("");
    run.file = file || null;
    $("attachment").hidden = !run.file;
    $("requirements").disabled = Boolean(run.file) || CA.MODE === "static";
    if (run.file) {
      $("file-badge").textContent = (run.file.name.split(".").pop() || "doc").slice(0, 4);
      $("file-name").textContent = run.file.name;
      $("file-size").textContent = formatBytes(run.file.size);
    } else {
      $("file-input").value = "";
    }
  }

  // ---------- pipeline view ----------
  function resetStages() {
    run.stageEls = {};
    run.started = {};
    fill($("stages"), STAGE_ORDER.map((stage) => {
      const item = el("li", { class: "stage", "data-status": "pending", "data-stage": stage },
        el("span", { class: "stage-icon", "aria-hidden": "true" }),
        el("div", { class: "stage-title" }, el("span", { text: STAGE_TITLES[stage] }), el("span", { class: "stage-time" })),
        el("p", { class: "stage-detail" }));
      run.stageEls[stage] = item;
      return item;
    }));
  }

  function stageDetails(stage) {
    const item = run.stageEls[stage];
    let details = item.querySelector("details");
    if (!details) {
      details = el("details", {}, el("summary", { text: "Details" }));
      item.append(details);
    }
    return details;
  }

  function onStage(e) {
    const item = run.stageEls[e.stage];
    if (!item) return;
    item.dataset.status = e.status;
    const icon = item.querySelector(".stage-icon");
    icon.textContent = e.status === "done" ? "✓" : e.status === "error" ? "!" : "";
    if (e.detail) item.querySelector(".stage-detail").textContent = e.detail;
    if (e.status === "running") run.started[e.stage] = performance.now();
    if (e.status === "done" && run.started[e.stage] && CA.MODE !== "static") {
      const seconds = (performance.now() - run.started[e.stage]) / 1000;
      item.querySelector(".stage-time").textContent = seconds < 0.1 ? "" : `${seconds.toFixed(1)}s`;
    }
    if (e.items && e.items.length) {
      const details = stageDetails(e.stage);
      const old = details.querySelector(".stage-items");
      if (old) old.remove();
      details.append(el("ul", { class: "stage-items" }, e.items.map((t) => el("li", { text: t }))));
    }
  }

  function traceList(stage) {
    const details = stageDetails(stage);
    let list = details.querySelector(".trace");
    if (!list) {
      details.open = true;
      details.querySelector("summary").textContent = "Agent trace";
      list = el("ol", { class: "trace" });
      details.append(list);
    }
    return list;
  }

  function onTrace(e) {
    const list = traceList(e.stage);
    if (e.type === "tool_call") list.append(el("li", { class: "call", text: `→ ${e.name}${e.summary ? ` (${e.summary})` : ""}` }));
    if (e.type === "tool_result") list.append(el("li", { class: e.ok ? "ok" : "fail", text: `${e.ok ? "✓" : "✗"} ${e.summary || e.name}` }));
    if (e.type === "note") list.append(el("li", { class: "note", text: e.text }));
    list.scrollTop = list.scrollHeight;
  }

  function notice(text, kind = "notice") {
    $("stages").before(el("div", { class: `${kind} run-notice`, text }));
  }

  function setModeChip(text) {
    $("run-mode").textContent = text;
  }

  async function onResult(e) {
    setModeChip(e.mode === "ai" ? `AI agent · ${e.model}` : CA.MODE === "static" ? "Recorded rule-based run" : "Rule-based planner");
    // Render while hidden so the previous result never flashes up.
    const root = $("plan-workspace");
    if (!workspace) workspace = new Workspace(root, { editable: true });
    await workspace.load(e.spec_yaml);
    $("result-placeholder").hidden = true;
    root.hidden = false;
    // On narrow screens the pipeline sits above the result, so bring the result into view.
    if (window.matchMedia("(max-width: 960px)").matches) root.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function onEvent(e) {
    switch (e.type) {
      case "stage": onStage(e); break;
      case "tool_call": case "tool_result": case "note": onTrace(e); break;
      case "notice": notice(e.text); break;
      case "error": {
        const running = Object.values(run.stageEls).find((item) => item.dataset.status === "running");
        if (running) { running.dataset.status = "error"; running.querySelector(".stage-icon").textContent = "!"; }
        notice(e.message, "banner");
        $("result-placeholder").hidden = true;
        break;
      }
      case "result": onResult(e); break;
      default: break;
    }
  }

  async function start({ text, file, sampleId, label }) {
    if (run.active) return;
    if (!file && !sampleId && (!text || text.trim().length < 20)) {
      showError("Describe your app in a sentence or two, or attach a requirements document.");
      $("requirements").focus();
      return;
    }
    showError("");
    run.active = true;
    $("plan-start").hidden = true;
    $("run").hidden = false;
    for (const old of document.querySelectorAll(".run-notice")) old.remove();
    $("run-input-name").textContent = label
      || (file ? `${file.name} · ${formatBytes(file.size)}` : text.trim().replace(/\s+/g, " ").slice(0, 300));
    const engine = CA.meta.engine || {};
    setModeChip(CA.MODE === "static" ? "Recorded run" : engine.mode === "ai" && $("mode").value !== "rules" ? `AI agent · ${engine.model}` : "Rule-based planner");
    resetStages();
    $("result-placeholder").hidden = false;
    $("plan-workspace").hidden = true;
    window.scrollTo({ top: 0 });
    try {
      await api.plan({ text, file, sampleId, mode: $("mode").value, region: $("region").value }, onEvent);
    } finally {
      run.active = false;
    }
  }

  function backToComposer() {
    $("run").hidden = true;
    $("plan-start").hidden = false;
    $("requirements").focus();
  }

  // ---------- setup ----------
  function init(meta, sampleList) {
    samples = sampleList;
    const regionSelect = $("region");
    for (const [key, label] of Object.entries(meta.regions)) regionSelect.append(el("option", { value: key, text: label }));

    const engine = meta.engine || { mode: "none" };
    const aiOption = $("mode").querySelector('option[value="ai"]');
    if (engine.mode !== "ai") {
      aiOption.disabled = true;
      aiOption.textContent = "AI agent (needs an API key on the server)";
    }
    if (CA.MODE === "static") {
      $("static-note").hidden = false;
      $("requirements").disabled = true;
      $("plan-button").disabled = true;
      $("mode-option").hidden = true;
      regionSelect.closest(".option").hidden = true;
      document.querySelector(".attach-btn").hidden = true;
      document.querySelector(".composer-tools .muted").hidden = true;
    } else {
      const draft = CA.recall(DRAFT_KEY);
      if (typeof draft === "string") $("requirements").value = draft;
    }

    fill($("sample-list"), samples.map((s) => el("li", {}, el("button", {
      type: "button", class: "sample",
      onclick: () => {
        if (CA.MODE !== "static") $("requirements").value = s.text;
        setFile(null);
        start({ text: s.text, sampleId: s.id, label: `Sample: ${s.title}` });
      },
    }, el("b", { text: s.title }), el("span", { text: s.text.split("\n").slice(1).join(" ").trim() })))));

    $("composer").addEventListener("submit", (e) => {
      e.preventDefault();
      start({ text: $("requirements").value, file: run.file });
    });
    $("requirements").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $("composer").requestSubmit(); }
    });
    $("requirements").addEventListener("input", () => {
      showError("");
      CA.store(DRAFT_KEY, $("requirements").value);
    });
    $("file-input").addEventListener("change", (e) => setFile(e.target.files[0]));
    $("file-remove").addEventListener("click", () => setFile(null));
    $("new-plan").addEventListener("click", backToComposer);

    if (CA.MODE !== "static") {
      const composer = $("composer");
      let depth = 0;
      composer.addEventListener("dragenter", (e) => { e.preventDefault(); depth += 1; composer.classList.add("dragging"); });
      composer.addEventListener("dragover", (e) => e.preventDefault());
      composer.addEventListener("dragleave", () => { depth -= 1; if (depth <= 0) { depth = 0; composer.classList.remove("dragging"); } });
      composer.addEventListener("drop", (e) => {
        e.preventDefault();
        depth = 0;
        composer.classList.remove("dragging");
        if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
      });
    }
  }

  return { init };
})();
