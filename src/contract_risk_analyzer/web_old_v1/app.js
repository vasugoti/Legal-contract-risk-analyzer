/* =====================================================================
   Contract Risk Analyzer — front-end
   Plain JavaScript, no libraries. Talks to the FastAPI backend:
     GET  /health, /model/info, /metrics
     POST /extract-text (FormData "file"), /analyze/document,
          /analyze/clause, /search/similar
   Works with both the old report fields and the new optional ones
   (risk_level, risk_color, risk_action, category_breakdown,
    flag.title, flag.recommendation).
   ===================================================================== */
(() => {
  "use strict";

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (v) =>
    String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
  const SEVERITIES = ["critical", "high", "medium", "low"];
  const sevRank = (s) => { const i = SEVERITIES.indexOf(String(s || "").toLowerCase()); return i < 0 ? 9 : i; };
  const sevOf = (s) => { const v = String(s?.value ?? s ?? "").toLowerCase(); return SEVERITIES.includes(v) ? v : "medium"; };
  const humanize = (t) =>
    String(t || "Risk")
      .replace(/_RISK$/i, "")
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase());
  const pct = (v) => { const n = num(v); return n <= 1 ? n * 100 : n; };

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  };

  function toast(msg, kind = "") {
    const el = document.createElement("div");
    el.className = `toast ${kind ? "is-" + kind : ""}`;
    el.textContent = msg;
    $("toasts").appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; }, 3800);
    setTimeout(() => el.remove(), 4200);
  }

  function setLoading(btn, on) {
    if (!btn) return;
    btn.classList.toggle("is-loading", on);
    btn.disabled = on;
    btn.setAttribute("aria-busy", on ? "true" : "false");
  }

  async function api(path, options = {}) {
    let res;
    try {
      res = await fetch(path, options);
    } catch {
      throw new Error("Cannot reach the API. Is the server running?");
    }
    const type = res.headers.get("content-type") || "";
    const body = type.includes("application/json") ? await res.json().catch(() => null) : await res.text().catch(() => "");
    if (!res.ok) {
      let detail = body && typeof body === "object" ? body.detail : body;
      if (Array.isArray(detail)) detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      throw new Error(detail || `Request failed (${res.status})`);
    }
    return body;
  }
  const postJSON = (path, data) =>
    api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

  // ------------------------------------------------------------------
  // Theme
  // ------------------------------------------------------------------
  function applyTheme(t) { document.documentElement.dataset.theme = t; }
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(store.get("cra-theme", prefersDark ? "dark" : "light"));
  $("theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    store.set("cra-theme", next);
  });

  // ------------------------------------------------------------------
  // Tabs (click, arrow keys, #hash)
  // ------------------------------------------------------------------
  const tabs = $$(".tab");
  function openTab(id, focus = false) {
    tabs.forEach((t) => {
      const on = t.dataset.tab === id;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      if (on && focus) t.focus();
    });
    $$(".panel").forEach((p) => { const on = p.id === id; p.hidden = !on; p.classList.toggle("is-active", on); });
    history.replaceState(null, "", "#" + id.replace("tab-", ""));
    if (id === "tab-metrics") fetchMetrics();
  }
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => openTab(t.dataset.tab));
    t.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
        openTab(n.dataset.tab, true);
      }
    });
  });

  // ------------------------------------------------------------------
  // System status
  // ------------------------------------------------------------------
  async function initSystem() {
    const dot = $("status-dot"), txt = $("status-text"), badge = $("model-badge");
    const [health, info] = await Promise.allSettled([api("/health"), api("/model/info")]);
    if (health.status === "fulfilled") { dot.className = "dot is-ok"; txt.textContent = "API online"; }
    else { dot.className = "dot is-bad"; txt.textContent = "API offline"; }

    if (info.status === "fulfilled" && info.value) {
      const m = info.value;
      if (m.mock_mode) {
        badge.textContent = "Mock model";
        badge.classList.add("is-warn");
        $("demo-mode-badge").hidden = false;
      } else if (m.fallback_active) {
        badge.textContent = "Fallback: TF-IDF";
        badge.title = m.fallback_reason || "Primary model failed to load";
        badge.classList.add("is-warn");
      } else {
        badge.textContent = m.model_name || "Model ready";
        badge.title = [m.model_name, m.model_id, m.num_labels ? m.num_labels + " labels" : ""].filter(Boolean).join(" · ");
      }
      $("clause-model-tag").textContent = m.model_name || m.active_backend || "model";
      if (m.disclaimer) $("disclaimer-text").textContent = m.disclaimer;
    } else {
      badge.textContent = "Model: unknown";
    }
  }

  // ------------------------------------------------------------------
  // Samples
  // ------------------------------------------------------------------
  const SAMPLES = {
    low: {
      id: "SVC-LOW-001",
      text: `SERVICE AGREEMENT

1. Services. The Service Provider shall provide website maintenance services as described in Schedule A, using reasonable skill and care.

2. Fees. The Client shall pay the monthly fee within thirty (30) days of receiving a valid invoice.

3. Term and Termination. This Agreement starts on the Effective Date and continues for twelve (12) months. Either party may terminate this Agreement by giving sixty (60) days' prior written notice to the other party, or immediately if the other party commits a material breach that is not remedied within thirty (30) days.

4. Confidentiality. Each party shall keep the other party's confidential information secret during the term and for three (3) years after it ends.

5. Limitation of Liability. Neither party shall be liable for indirect or consequential losses, and each party's total liability shall not exceed the fees paid in the previous twelve (12) months.

6. Amendments. Any change to this Agreement must be in writing signed by both parties.

7. Governing Law. This Agreement is governed by the laws of India, and the courts at Surat shall have exclusive jurisdiction.`,
    },
    medium: {
      id: "SAAS-MED-002",
      text: `SOFTWARE SUBSCRIPTION AGREEMENT

1. Subscription. The Provider grants the Customer a non-exclusive licence to use the platform during the Subscription Term.

2. Renewal. The Subscription Term shall automatically renew for successive renewal terms of twelve (12) months unless either party gives notice ninety (90) days before the end of the current term.

3. Fees. All fees are payable in advance and are non-refundable. Late payment shall attract interest @ 18% per annum.

4. Price Changes. The Provider may increase the fees at each renewal, and prices are subject to change with thirty (30) days' notice.

5. Warranties. The platform is provided "as is" and the Provider does not warrant that it will be error-free.

6. Suspension. The Provider may suspend access if any invoice remains unpaid for more than fifteen (15) days.

7. Support. Support requests will be prioritised at the Provider's sole discretion.

8. Governing Law. This Agreement is governed by the laws of India and the courts at Bengaluru have exclusive jurisdiction.`,
    },
    high: {
      id: "VND-HIGH-003",
      text: `VENDOR SERVICES AGREEMENT

1. Exclusivity. The Vendor shall supply the Products to the Company on an exclusive basis and shall not engage any other customer in the territory.

2. Termination. The Company may terminate this Agreement at any time, without cause and without prior notice, with immediate effect.

3. Liability. The Vendor shall be solely liable for any and all losses suffered by the Company, and the Vendor's liability shall be unlimited.

4. Indemnity. The Vendor shall indemnify, defend and hold harmless the Company from any and all claims, including reasonable attorneys' fees, whether or not caused by the Vendor.

5. Changes. The Company reserves the right to modify these terms at any time without notice to the Vendor.

6. Penalties. For any delay the Vendor shall pay liquidated damages of 5% of the order value per day.

7. Intellectual Property. The Vendor hereby assigns all right, title and interest in all work product to the Company and waives all moral rights.

8. Non-Compete. The Vendor shall not compete with the Company or engage in any competing business for a period of three (3) years after termination.

9. Disputes. Disputes shall be resolved by a sole arbitrator appointed by the Company.`,
    },
  };

  // ------------------------------------------------------------------
  // Document input
  // ------------------------------------------------------------------
  const docText = $("doc-text-input");
  const updateCount = () => { $("doc-char-count").textContent = `${docText.value.length.toLocaleString()} characters`; };
  docText.addEventListener("input", updateCount);

  const sampleBtn = $("btn-load-sample-doc"), sampleMenu = $("sample-menu");
  sampleBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    sampleMenu.hidden = !sampleMenu.hidden;
    sampleBtn.setAttribute("aria-expanded", String(!sampleMenu.hidden));
  });
  document.addEventListener("click", () => { sampleMenu.hidden = true; sampleBtn.setAttribute("aria-expanded", "false"); });
  $$("[data-sample]", sampleMenu).forEach((b) =>
    b.addEventListener("click", () => {
      const s = SAMPLES[b.dataset.sample];
      docText.value = s.text;
      $("doc-id-input").value = s.id;
      updateCount();
      setUpload("", "");
      toast("Sample loaded. Press Analyze contract.");
    })
  );

  $("btn-clear-doc").addEventListener("click", () => {
    docText.value = "";
    $("contract-file-input").value = "";
    updateCount();
    setUpload("", "");
    showDocState("empty");
    docText.focus();
  });

  // ---- upload ----
  function setUpload(msg, kind) {
    const el = $("upload-status");
    el.textContent = msg;
    el.className = "upload-status" + (kind ? " is-" + kind : "");
  }
  async function uploadFile(file) {
    if (!file) return;
    const ok = /\.(pdf|docx|txt)$/i.test(file.name);
    if (!ok) { setUpload("Only PDF, DOCX or TXT files are supported.", "bad"); return; }
    if (file.size > 20 * 1024 * 1024) { setUpload("File is larger than 20 MB.", "bad"); return; }
    setUpload(`Extracting text from ${file.name}…`, "");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const data = await api("/extract-text", { method: "POST", body: fd });
      const text = (data && data.text) || "";
      if (!text.trim()) throw new Error("No text found. Scanned PDFs need OCR first.");
      docText.value = text;
      updateCount();
      const base = file.name.replace(/\.[^.]+$/, "").replace(/[^\w-]+/g, "-").slice(0, 40);
      if (base) $("doc-id-input").value = base;
      setUpload(`✓ ${file.name} — ${num(data.characters, text.length).toLocaleString()} characters extracted`, "ok");
    } catch (err) {
      setUpload(err.message, "bad");
    }
  }
  $("contract-file-input").addEventListener("change", (e) => uploadFile(e.target.files[0]));
  const dz = $("dropzone");
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("is-drag"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("is-drag"); }));
  dz.addEventListener("drop", (e) => uploadFile(e.dataTransfer.files[0]));

  // ------------------------------------------------------------------
  // Document analysis
  // ------------------------------------------------------------------
  let lastReport = null;
  let flagFilter = { sev: "all", q: "", limit: 25 };

  function showDocState(state) {
    $("doc-empty-state").hidden = state !== "empty";
    $("doc-loading").hidden = state !== "loading";
    $("doc-results-content").hidden = state !== "results";
  }

  async function analyzeDocument() {
    const text = docText.value.trim();
    if (!text) { toast("Paste a contract or upload a file first.", "bad"); docText.focus(); return; }
    const btn = $("btn-analyze-doc");
    setLoading(btn, true);
    showDocState("loading");
    try {
      const report = await postJSON("/analyze/document", {
        document_id: $("doc-id-input").value.trim() || "document-001",
        text,
      });
      lastReport = report;
      renderReport(report);
      showDocState("results");
      if (window.innerWidth < 1080) $("doc-results-content").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showDocState(lastReport ? "results" : "empty");
      toast(err.message, "bad");
    } finally {
      setLoading(btn, false);
    }
  }
  $("btn-analyze-doc").addEventListener("click", analyzeDocument);
  docText.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") analyzeDocument(); });

  const BANDS = [
    { name: "Low", max: 30, action: "Low risk — a standard review should be enough." },
    { name: "Medium", max: 60, action: "Medium risk — negotiate the flagged clauses before signing." },
    { name: "High", max: 80, action: "High risk — get a legal review before signing." },
    { name: "Critical", max: 101, action: "Critical risk — do not sign without a lawyer's review and changes." },
  ];
  const bandFor = (score) => BANDS.find((b) => score < b.max) || BANDS[3];
  const sevColorVar = (lvl) => ({ low: "--low", medium: "--med", high: "--high", critical: "--crit" }[lvl] || "--med");

  function renderReport(r) {
    const flags = Array.isArray(r.risk_flags) ? r.risk_flags.slice() : [];
    const score = Math.max(0, Math.min(100, num(r.overall_risk_score)));
    const band = bandFor(score);
    const level = String(r.risk_level || band.name);
    const lvlKey = level.toLowerCase();

    // gauge
    const meter = $("doc-risk-meter");
    const len = meter.getTotalLength ? meter.getTotalLength() : 251;
    meter.style.strokeDasharray = `${len}`;
    meter.style.strokeDashoffset = `${len}`;
    meter.style.stroke = r.risk_color || `var(${sevColorVar(lvlKey)})`;
    requestAnimationFrame(() => requestAnimationFrame(() => { meter.style.strokeDashoffset = `${len * (1 - score / 100)}`; }));
    animateNumber($("doc-risk-score"), score);

    const pill = $("doc-risk-level");
    pill.textContent = `${level} risk`;
    pill.className = `level-pill level-${lvlKey}`;

    $("doc-report-id").textContent = `Report · ${r.document_id || "document"}`;
    $("doc-risk-action").textContent = r.risk_action || band.action;
    $("doc-summary-text").textContent = r.summary || "";

    // counts
    const sb = r.severity_breakdown || {};
    const counts = {};
    SEVERITIES.forEach((s) => { counts[s] = sb[s] ?? flags.filter((f) => sevOf(f.severity) === s).length; });
    SEVERITIES.forEach((s) => { $(`sev-${s}-count`).textContent = counts[s]; });
    $("doc-clause-count").textContent = num(r.total_clauses).toLocaleString();
    $("doc-flags-count").textContent = flags.length.toLocaleString();

    // categories
    const cats = buildCategories(r, flags);
    $("doc-category-count").textContent = cats.length;
    renderTopRisks(cats);

    // flags
    flagFilter = { sev: "all", q: "", limit: 25 };
    $("flag-search").value = "";
    $$("#severity-filter .chip").forEach((c) => c.classList.toggle("is-on", c.dataset.sev === "all"));
    renderFlags();

    // recommendations
    const recs = Array.isArray(r.recommendations) ? r.recommendations : [];
    $("doc-recommendations").innerHTML = recs.length
      ? recs.map((t, i) => `<li><input type="checkbox" id="rec-${i}"><label for="rec-${i}"><span>${esc(t)}</span></label></li>`).join("")
      : `<li class="muted">No recommendations returned.</li>`;
    $$("#doc-recommendations input").forEach((c) => c.addEventListener("change", () => c.closest("li").classList.toggle("done", c.checked)));

    // taxonomy
    const tax = Object.entries(r.predicted_clause_types || {}).filter(([, v]) => num(v) > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
    const maxTax = Math.max(1, ...tax.map((t) => t[1]));
    renderBars($("taxonomy-table-body"), tax.map(([k, v]) => ({ label: k, value: v, ratio: v / maxTax, text: String(v) })), "No clause types returned.");
  }

  function buildCategories(r, flags) {
    if (Array.isArray(r.category_breakdown) && r.category_breakdown.length) {
      return r.category_breakdown.map((c) => ({
        type: c.flag_type, title: c.title || humanize(c.flag_type), severity: sevOf(c.severity),
        clauses: num(c.clauses, 1), points: num(c.points),
      })).sort((a, b) => sevRank(a.severity) - sevRank(b.severity) || b.points - a.points);
    }
    const map = new Map();
    flags.forEach((f) => {
      const k = f.flag_type || "RISK";
      const cur = map.get(k) || { type: k, title: f.title || humanize(k), severity: sevOf(f.severity), clauses: 0, points: 0 };
      cur.clauses += 1;
      if (sevRank(f.severity) < sevRank(cur.severity)) cur.severity = sevOf(f.severity);
      map.set(k, cur);
    });
    return Array.from(map.values()).sort((a, b) => sevRank(a.severity) - sevRank(b.severity) || b.clauses - a.clauses);
  }

  function renderTopRisks(cats) {
    const el = $("top-risks");
    $("top-risks-card").hidden = cats.length === 0;
    el.innerHTML = cats.slice(0, 6).map((c) => `
      <button class="risk-tile" type="button" data-type="${esc(c.type)}" style="--sev: var(${sevColorVar(c.severity)})">
        <span class="sevtxt">${esc(c.severity)}</span>
        <strong>${esc(c.title)}</strong>
        <span class="meta"><span>${c.clauses} clause${c.clauses === 1 ? "" : "s"}</span>${c.points ? `<span>${c.points.toFixed(1)} pts</span>` : ""}</span>
      </button>`).join("");
    $$(".risk-tile", el).forEach((b) => b.addEventListener("click", () => {
      $("flag-search").value = b.dataset.type;
      flagFilter.q = b.dataset.type.toLowerCase();
      flagFilter.sev = "all";
      $$("#severity-filter .chip").forEach((c) => c.classList.toggle("is-on", c.dataset.sev === "all"));
      renderFlags();
      $("flags-table-body").scrollIntoView({ behavior: "smooth", block: "center" });
    }));
  }

  function flagHTML(f, open = false) {
    const sev = sevOf(f.severity);
    const md = f.metadata || {};
    const title = f.title || md.title || humanize(f.flag_type);
    const rec = f.recommendation || md.recommendation || "";
    const evidence = f.evidence_text || f.text || "";
    const match = f.matched_pattern || md.matched_pattern || md.evidence || f.evidence || "";
    let evHTML = esc(evidence);
    if (match && typeof match === "string" && match.length > 2) {
      const re = new RegExp(esc(match).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      evHTML = evHTML.replace(re, (m) => `<mark>${m}</mark>`);
    }
    const conf = f.confidence != null ? ` · ${Math.round(pct(f.confidence))}% confidence` : "";
    return `
      <details class="flag f-${sev}" ${open ? "open" : ""}>
        <summary>
          <span class="sev-badge b-${sev}">${esc(sev)}</span>
          <span class="f-title">${esc(title)}<span class="f-sub">${esc(f.reason || "")}</span></span>
          <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
        </summary>
        <div class="flag-body">
          ${evidence ? `<div class="evidence">${evHTML}</div>` : ""}
          ${rec ? `<div class="rec"><b>Suggested fix</b><span>${esc(rec)}</span></div>` : ""}
          <div class="flag-meta">${esc(f.flag_type || "")}${f.clause_id != null ? " · clause " + esc(f.clause_id) : ""}${conf}</div>
        </div>
      </details>`;
  }

  function renderFlags() {
    const all = (lastReport?.risk_flags || []).slice().sort((a, b) => sevRank(a.severity) - sevRank(b.severity));
    const q = flagFilter.q;
    const list = all.filter((f) => {
      if (flagFilter.sev !== "all" && sevOf(f.severity) !== flagFilter.sev) return false;
      if (!q) return true;
      return [f.flag_type, f.title, f.reason, f.evidence_text, f.recommendation].join(" ").toLowerCase().includes(q);
    });
    $("flags-visible-count").textContent = list.length === all.length ? all.length : `${list.length} of ${all.length}`;
    const el = $("flags-table-body");
    if (!list.length) {
      el.innerHTML = `<div class="no-items">${all.length ? "No flags match this filter." : "No risk flags were raised for this contract."}</div>`;
      return;
    }
    const shown = list.slice(0, flagFilter.limit);
    el.innerHTML = shown.map((f, i) => flagHTML(f, i === 0 && !q && flagFilter.sev === "all")).join("") +
      (list.length > shown.length ? `<button class="btn btn-ghost btn-sm show-more" id="flags-more" type="button">Show ${Math.min(25, list.length - shown.length)} more (${list.length - shown.length} hidden)</button>` : "");
    const more = $("flags-more");
    if (more) more.addEventListener("click", () => { flagFilter.limit += 25; renderFlags(); });
  }

  $$("#severity-filter .chip").forEach((c) => c.addEventListener("click", () => {
    flagFilter.sev = c.dataset.sev;
    flagFilter.limit = 25;
    $$("#severity-filter .chip").forEach((x) => x.classList.toggle("is-on", x === c));
    renderFlags();
  }));
  let searchTimer;
  $("flag-search").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { flagFilter.q = e.target.value.trim().toLowerCase(); flagFilter.limit = 25; renderFlags(); }, 150);
  });

  function renderBars(el, rows, emptyText) {
    if (!rows.length) { el.innerHTML = `<div class="no-items">${esc(emptyText)}</div>`; return; }
    el.innerHTML = rows.map((r) => `
      <div class="bar-row" title="${esc(r.label)}">
        <span class="lbl">${esc(r.label)}</span>
        <span class="bar"><span data-w="${Math.max(2, Math.round(r.ratio * 100))}"></span></span>
        <span class="val">${esc(r.text)}</span>
      </div>`).join("");
    requestAnimationFrame(() => requestAnimationFrame(() => $$(".bar span[data-w]", el).forEach((s) => { s.style.width = s.dataset.w + "%"; })));
  }

  function animateNumber(el, target) {
    const start = performance.now(), dur = 800, decimals = Number.isInteger(target) ? 0 : 1;
    const step = (t) => {
      const p = Math.min(1, (t - start) / dur);
      el.textContent = (target * (1 - Math.pow(1 - p, 3))).toFixed(decimals);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // ---- report actions ----
  $("btn-download-json").addEventListener("click", () => {
    if (!lastReport) return;
    const blob = new Blob([JSON.stringify(lastReport, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${(lastReport.document_id || "report").replace(/[^\w-]+/g, "-")}-risk-report.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  $("btn-copy-summary").addEventListener("click", async () => {
    if (!lastReport) return;
    const r = lastReport;
    const cats = buildCategories(r, r.risk_flags || []);
    const lines = [
      `Contract risk report — ${r.document_id || ""}`,
      `Score: ${num(r.overall_risk_score).toFixed(1)}/100 (${r.risk_level || bandFor(num(r.overall_risk_score)).name})`,
      `Clauses: ${num(r.total_clauses)} · Flags: ${(r.risk_flags || []).length}`,
      "",
      "Main risks:",
      ...cats.slice(0, 8).map((c) => `- [${c.severity.toUpperCase()}] ${c.title} (${c.clauses} clause${c.clauses === 1 ? "" : "s"})`),
      "",
      "Recommendations:",
      ...(r.recommendations || []).map((x) => `- ${x}`),
      "",
      "Automated triage only — not legal advice.",
    ];
    try { await navigator.clipboard.writeText(lines.join("\n")); toast("Summary copied.", "ok"); }
    catch { toast("Copy failed — your browser blocked clipboard access.", "bad"); }
  });
  $("btn-print").addEventListener("click", () => {
    const opened = $$("#flags-table-body details:not([open])");
    opened.forEach((d) => d.setAttribute("open", ""));
    window.print();
    opened.forEach((d) => d.removeAttribute("open"));
  });

  // ------------------------------------------------------------------
  // Single clause
  // ------------------------------------------------------------------
  const PRESETS = {
    "preset-term": "Either party may terminate this Agreement at any time, without cause, by giving the other party written notice with immediate effect.",
    "preset-indem": "The Supplier shall indemnify, defend and hold harmless the Customer from any and all claims, losses and expenses, including reasonable attorneys' fees, arising out of the Services.",
    "preset-liab": "The Contractor shall be solely liable for any and all losses suffered by the Client, and its liability under this Agreement shall be unlimited.",
    "preset-law": "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, and the courts of Delaware shall have exclusive jurisdiction.",
    "preset-assign": "The Company may freely assign this Agreement to any affiliate or successor without the consent of the other party.",
  };
  const clauseText = $("clause-text-input");
  const updateClauseCount = () => { $("clause-char-count").textContent = `${clauseText.value.length} characters`; };
  clauseText.addEventListener("input", updateClauseCount);
  Object.entries(PRESETS).forEach(([id, text]) => $(id).addEventListener("click", () => {
    clauseText.value = text; updateClauseCount(); analyzeClause();
  }));
  $("btn-clear-clause").addEventListener("click", () => {
    clauseText.value = ""; updateClauseCount();
    $("clause-result-card").hidden = true; $("clause-empty").hidden = false; clauseText.focus();
  });

  async function analyzeClause() {
    const text = clauseText.value.trim();
    if (!text) { toast("Type or pick a clause first.", "bad"); clauseText.focus(); return; }
    const btn = $("btn-analyze-clause");
    setLoading(btn, true);
    try {
      const r = await postJSON("/analyze/clause", { text });
      $("clause-predicted-label").textContent = r.predicted_label || "—";
      const conf = Math.round(pct(r.confidence));
      $("clause-confidence-val").textContent = `${conf}%`;
      const bar = $("clause-confidence-bar");
      bar.style.width = "0";
      requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = conf + "%"; }));

      const topk = (r.top_k_labels || []).map((x) => Array.isArray(x)
        ? { label: x[0], score: x[1] }
        : { label: x.label, score: x.score ?? x.confidence ?? x.probability });
      renderBars($("clause-topk-body"), topk.map((t) => ({ label: t.label, ratio: pct(t.score) / 100, text: `${pct(t.score).toFixed(1)}%` })), "No candidates returned.");

      const flags = (r.risk_flags || []).slice().sort((a, b) => sevRank(a.severity) - sevRank(b.severity));
      $("clause-risk-flags-container").innerHTML = flags.length
        ? flags.map((f, i) => flagHTML(f, i === 0)).join("")
        : `<div class="no-items">No risk rule fired for this clause.</div>`;

      $("clause-empty").hidden = true;
      $("clause-result-card").hidden = false;
    } catch (err) {
      toast(err.message, "bad");
    } finally {
      setLoading(btn, false);
    }
  }
  $("btn-analyze-clause").addEventListener("click", analyzeClause);
  clauseText.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") analyzeClause(); });

  // ------------------------------------------------------------------
  // Precedent search
  // ------------------------------------------------------------------
  const SEARCH_PRESETS = {
    "search-preset-1": "The supplier shall indemnify and hold harmless the customer against third-party claims",
    "search-preset-2": "Either party may terminate this agreement by giving thirty days written notice",
    "search-preset-3": "This agreement shall be governed by the laws of the State of New York",
  };
  Object.entries(SEARCH_PRESETS).forEach(([id, q]) => $(id).addEventListener("click", () => { $("search-query-input").value = q; runSearch(); }));
  $("search-query-input").addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
  $("btn-run-search").addEventListener("click", runSearch);

  async function runSearch() {
    const query = $("search-query-input").value.trim();
    if (!query) { toast("Type something to search for.", "bad"); return; }
    const btn = $("btn-run-search");
    setLoading(btn, true);
    try {
      const r = await postJSON("/search/similar", { query, top_k: num($("search-topk-input").value, 5) });
      const results = r.results || [];
      $("search-results-count").textContent = results.length;
      $("search-results-list").innerHTML = results.length ? results.map((x) => {
        const s = pct(x.score);
        return `<article class="result">
          <div class="result-head">
            <strong>${esc(x.label || "Clause")}</strong>
            <span class="sim"><span class="bar"><span style="width:${Math.max(2, Math.min(100, s))}%"></span></span>${s.toFixed(1)}% similar</span>
          </div>
          <p>${esc(x.text)}</p>
          ${x.clause_id != null ? `<div class="flag-meta" style="margin-top:6px">${esc(x.clause_id)}</div>` : ""}
        </article>`;
      }).join("") : `<div class="no-items">No similar clauses found. Is the retrieval index built?</div>`;
      $("search-results-card").hidden = false;
    } catch (err) {
      toast(err.message, "bad");
    } finally {
      setLoading(btn, false);
    }
  }

  // ------------------------------------------------------------------
  // Metrics
  // ------------------------------------------------------------------
  async function fetchMetrics() {
    const btn = $("btn-refresh-metrics");
    setLoading(btn, true);
    try {
      const m = await api("/metrics");
      $("rt-analyzed-clauses").textContent = num(m.analyzed_clauses).toLocaleString();
      $("rt-analyzed-docs").textContent = num(m.analyzed_documents).toLocaleString();
      $("rt-avg-latency").textContent = `${num(m.average_latency_ms).toFixed(0)} ms`;
      $("rt-risk-flags").textContent = num(m.total_risk_flags).toLocaleString();
      renderBenchmark(m.benchmark || {}, m);
    } catch (err) {
      $("bm-desc").textContent = "Could not load metrics: " + err.message;
    } finally {
      setLoading(btn, false);
    }
  }
  $("btn-refresh-metrics").addEventListener("click", fetchMetrics);

  function renderBenchmark(b, m) {
    if (b.title) $("bm-title").textContent = b.title;
    if (b.badge) $("bm-badge").textContent = b.badge;
    $("bm-desc").textContent = b.description || "Benchmark details are not available for this backend.";
    const fb = $("bm-fallback-banner");
    fb.hidden = !b.fallback_active;
    fb.textContent = b.fallback_active ? `Fallback active: ${b.fallback_reason || "primary model unavailable"}` : "";
    $("bm-col-legalpro").textContent = b.active_model_name || m.active_model_name || "Transformer";

    $("bm-cards").innerHTML = (b.cards || []).map((c) =>
      `<div class="bm-card"><small>${esc(c.label)}</small><strong>${esc(c.value)}</strong>${c.sub ? `<em>${esc(c.sub)}</em>` : ""}</div>`).join("");

    const rows = b.comparison_table || [];
    $("bm-comparison-tbody").innerHTML = rows.length ? rows.map((r) => {
      const ch = String(r.change ?? "");
      const cls = /^\+/.test(ch) ? "up" : /^-/.test(ch) ? "down" : "";
      return `<tr class="${r.is_reference ? "is-ref" : ""}"><td>${esc(r.metric)}</td><td>${esc(r.tfidf)}</td><td><b>${esc(r.legalpro)}</b></td><td class="${cls}">${esc(ch)}</td></tr>`;
    }).join("") : `<tr><td colspan="4" class="muted">No comparison data.</td></tr>`;

    const specs = b.specs || [];
    $("bm-specs-tbody").innerHTML = specs.length
      ? specs.map((s) => `<tr><td class="muted">${esc(s.label)}</td><td>${esc(s.value)}</td></tr>`).join("")
      : `<tr><td class="muted">No specifications.</td></tr>`;
  }

  // ------------------------------------------------------------------
  // Start
  // ------------------------------------------------------------------
  const startTab = "tab-" + (location.hash.replace("#", "") || "document");
  openTab($(startTab) ? startTab : "tab-document");
  initSystem();
  updateCount();
  updateClauseCount();
})();
