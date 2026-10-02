"use strict";

// The Plan page: describe an app (type or attach a document), watch the pipeline run,
// then explore the result in a workspace.

const Plan = (() => {
  const { $, el, fill, api } = CA;
  const DRAFT_KEY = "clarchy.plan-draft";
  const HF_KEY = "clarchy.hf";
  const STAGE_ORDER = ["read", "understand", "design", "toolchain", "workflows", "map"];
  const STAGE_TITLES = {
    read: "Read the requirements",
    understand: "Understand what's needed",
    design: "Design the architecture",
    toolchain: "Add build and deploy",
    workflows: "Describe the workflows",
    map: "Map to every cloud",
  };
  const STAGE_SHORT = {
    read: "Read", understand: "Understand", design: "Design",
    toolchain: "Build & deploy", workflows: "Workflows", map: "Every cloud",
  };
  const STAGE_DOING = {
    read: "Reading the requirements…",
    understand: "Understanding what's needed…",
    design: "Designing the architecture…",
    toolchain: "Adding build and deploy…",
    workflows: "Describing the workflows…",
    map: "Mapping to every cloud…",
  };
  const ACCEPTED = [".docx", ".pdf", ".xlsx", ".md", ".markdown", ".txt", ".csv"];
  const MAX_BYTES = 10 * 1024 * 1024;

  let samples = [];
  let workspace = null;
  const run = { file: null, active: false, replay: false, started: {}, stageEls: {}, stepEls: {} };

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
    $("requirements").disabled = Boolean(run.file) || !CA.canPlan();
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
    run.stepEls = {};
    run.started = {};
    fill($("stages"), STAGE_ORDER.map((stage, i) => {
      const item = el("li", { class: "stage", "data-status": "pending", "data-stage": stage },
        el("span", { class: "stage-icon", "aria-hidden": "true", text: String(i + 1) }),
        el("div", { class: "stage-title" }, el("span", { text: STAGE_TITLES[stage] }), el("span", { class: "stage-time" })),
        el("p", { class: "stage-detail" }));
      run.stageEls[stage] = item;
      return item;
    }));
    fill($("stepper"), STAGE_ORDER.map((stage) => {
      const step = el("li", { "data-status": "pending", text: STAGE_SHORT[stage] });
      run.stepEls[stage] = step;
      return step;
    }));
    const pipeline = $("pipeline");
    pipeline.classList.remove("done", "failed");
    pipeline.open = true;
    setStatus("Planning…");
  }

  function setStatus(text) {
    $("pipeline-status").textContent = text;
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
    run.stepEls[e.stage].dataset.status = e.status;
    item.querySelector(".stage-icon").textContent = e.status === "done" ? "✓" : e.status === "error" ? "!" : String(STAGE_ORDER.indexOf(e.stage) + 1);
    if (e.detail) item.querySelector(".stage-detail").textContent = e.detail;
    if (e.status === "running") {
      run.started[e.stage] = performance.now();
      setStatus(STAGE_DOING[e.stage] || "Planning…");
    }
    if (e.status === "done" && run.started[e.stage] && !run.replay) {
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
      details.querySelector("summary").textContent = "Planner steps";
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
    $("run-notices").append(el("div", { class: kind, text }));
  }

  async function onResult(e) {
    const how = e.mode === "ai" ? `by ${e.model}` : run.replay ? "(recorded rule-based run)" : "with the rule-based planner";
    // Render while hidden so the previous result never flashes up.
    const root = $("plan-workspace");
    if (!workspace) {
      workspace = new Workspace(root, { editable: true, onReplan: CA.canPlan() ? replan : null });
    }
    await workspace.load(e.spec_yaml);
    const pipeline = $("pipeline");
    pipeline.classList.add("done");
    pipeline.open = false;
    setStatus(`Planned ${how}`);
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
      case "progress": setStatus(e.text); break;
      case "error": {
        const running = Object.values(run.stageEls).find((item) => item.dataset.status === "running");
        if (running) {
          running.dataset.status = "error";
          run.stepEls[running.dataset.stage].dataset.status = "error";
          running.querySelector(".stage-icon").textContent = "!";
        }
        $("pipeline").classList.add("failed");
        setStatus("Planning stopped");
        notice(e.message, "banner");
        $("result-placeholder").hidden = true;
        break;
      }
      case "result": onResult(e); break;
      default: break;
    }
  }

  function hfSettings() {
    return {
      token: $("hf-token").value.trim(),
      model: $("hf-model").value.trim() || CA.HF_DEFAULT_MODEL,
      base_url: $("hf-endpoint").value.trim() || null,
    };
  }

  // Plan again with answers to the open questions (and corrections to assumptions),
  // keeping the answers already given so each round builds on the last.
  function replan(answers) {
    const input = run.input;
    if (!input) return;
    const fresh = new Set(answers.map((a) => a.question).filter(Boolean));
    const merged = [...(input.answers || []).filter((a) => !a.question || !fresh.has(a.question)), ...answers];
    const base = input.baseLabel || input.label
      || (input.file ? input.file.name : `“${input.text.trim().replace(/\s+/g, " ").slice(0, 120)}”`);
    start({
      text: input.text, file: input.file, answers: merged, baseLabel: base,
      label: `${base} · ${CA.plural(merged.length, "answer")}`,
    });
  }

  async function start({ text, file, sampleId, label, answers = [], baseLabel = null }) {
    if (run.active) return;
    const mode = $("mode").value;
    const replay = Boolean(sampleId) && CA.hasRecordedRun(sampleId) && mode !== "hf" && !answers.length;
    if (!replay) {
      if (!file && (!text || text.trim().length < 20)) {
        showError("Describe your app in a sentence or two, or attach a requirements document.");
        $("requirements").focus();
        return;
      }
      if (mode === "hf" && !hfSettings().token && !hfSettings().base_url) {
        showError("Paste a Hugging Face access token to use an open-source model, or choose the rule-based planner.");
        $("hf-token").focus();
        return;
      }
    }
    showError("");
    run.active = true;
    // A plan from the visitor's own brief uses a free diagram; samples and re-plans don't.
    if (!sampleId && !answers.length && !(await Access.spend())) {
      run.active = false;
      return;
    }
    run.replay = replay;
    run.input = { text, file, label, answers, baseLabel };
    $("plan-start").hidden = true;
    $("run").hidden = false;
    $("run-notices").replaceChildren();
    $("run-input-name").textContent = label
      || (file ? `${file.name} · ${formatBytes(file.size)}` : `“${text.trim().replace(/\s+/g, " ").slice(0, 160)}”`);
    $("run-mode").textContent = "";
    resetStages();
    $("result-placeholder").hidden = false;
    $("plan-workspace").hidden = true;
    window.scrollTo({ top: 0 });
    try {
      await api.plan({
        text, file, mode, region: $("region").value,
        sampleId: replay ? sampleId : null,
        hf: mode === "hf" ? hfSettings() : null,
        answers,
      }, onEvent);
    } finally {
      run.active = false;
    }
  }

  function backToComposer() {
    $("run").hidden = true;
    $("plan-start").hidden = false;
    $("requirements").focus();
  }

  // From the How to page: puts a brief in the composer and, if asked, plans it.
  function useBrief(text, { now = false } = {}) {
    if (run.active || !CA.canPlan()) return;
    setFile(null);
    $("requirements").value = text;
    CA.store(DRAFT_KEY, text);
    showError("");
    backToComposer();
    window.scrollTo({ top: 0 });
    if (now) start({ text });
  }

  function setupPlanners(engine) {
    const select = $("mode");
    if (CA.MODE !== "static") {
      if (engine.mode !== "ai") {
        const ai = select.querySelector('option[value="ai"]');
        ai.disabled = true;
        ai.textContent = "AI agent (not configured)";
      }
      return;
    }
    // In the browser: the rule-based planner always, or an open-source model through
    // Hugging Face with the visitor's own token.
    fill(select,
      el("option", { value: "rules", text: "Rule-based, in your browser" }),
      el("option", { value: "hf", text: "Open-source model (Hugging Face)" }));
    let token = "";
    try { token = sessionStorage.getItem(HF_KEY) || ""; } catch { /* optional */ }
    const saved = CA.recall(HF_KEY) || {};
    $("hf-token").value = token;
    $("hf-model").value = saved.model || CA.HF_DEFAULT_MODEL;
    const toggle = () => { $("hf-settings").hidden = select.value !== "hf"; };
    select.addEventListener("change", () => { toggle(); CA.store(HF_KEY, { ...saved, mode: select.value }); });
    $("hf-token").addEventListener("change", () => { try { sessionStorage.setItem(HF_KEY, $("hf-token").value.trim()); } catch { /* optional */ } });
    $("hf-model").addEventListener("change", () => { saved.model = $("hf-model").value.trim(); CA.store(HF_KEY, saved); });
    $("hf-endpoint").value = saved.base_url || "";
    $("hf-endpoint").addEventListener("change", () => { saved.base_url = $("hf-endpoint").value.trim(); CA.store(HF_KEY, saved); });
    if (saved.mode === "hf") select.value = "hf";
    toggle();
  }

  // ---------- setup ----------
  function init(meta, sampleList) {
    samples = sampleList;
    const regionSelect = $("region");
    if (regionSelect.options.length <= 1) { // the page usually lists them already (site.py)
      for (const [key, label] of Object.entries(meta.regions)) regionSelect.append(el("option", { value: key, text: label }));
    }
    setupPlanners(meta.engine || { mode: "none" });

    if (!CA.canPlan()) {
      // A replay-only build (no planning engine): the samples still work.
      $("static-note").hidden = false;
      $("requirements").disabled = true;
      $("plan-button").disabled = true;
      $("mode-option").hidden = true;
      $("region-option").hidden = true;
      document.querySelector(".attach-btn").hidden = true;
      $("composer-foot").hidden = true;
    } else {
      const draft = CA.recall(DRAFT_KEY);
      if (typeof draft === "string") $("requirements").value = draft;
    }

    const runSample = (s) => {
      if (CA.canPlan()) $("requirements").value = s.text;
      setFile(null);
      start({ text: s.text, sampleId: s.id, label: `Sample · ${s.title}` });
    };
    // The sample buttons come with the page (site.py); older pages get them drawn here.
    const listed = [...$("sample-list").querySelectorAll("[data-sample]")];
    if (listed.length) {
      for (const button of listed) {
        const s = samples.find((x) => x.id === button.dataset.sample);
        if (s) button.addEventListener("click", () => runSample(s));
      }
    } else {
      fill($("sample-list"), samples.map((s) => el("li", {}, el("button", {
        type: "button", class: "chip sample", title: s.text.split("\n").slice(1).join(" ").trim().slice(0, 220),
        onclick: () => runSample(s),
      }, s.title))));
    }

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

    if (CA.canPlan()) {
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

  return { init, useBrief };
})();
