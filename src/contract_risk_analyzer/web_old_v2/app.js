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
  let modelLabel = "";
  async function initSystem() {
    const dot = $("status-dot"), txt = $("status-text"), badge = $("model-badge");
    const [health, info] = await Promise.allSettled([api("/health"), api("/model/info")]);
    if (health.status === "fulfilled") { dot.className = "dot is-ok"; txt.textContent = "API online"; }
    else { dot.className = "dot is-bad"; txt.textContent = "API offline"; }

    if (info.status === "fulfilled" && info.value) {
      const m = info.value;
      modelLabel = m.mock_mode ? "Mock model (demo)" : m.fallback_active ? "TF-IDF fallback" : (m.model_name || m.active_backend || "");
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
  let analyzedText = "";
  let analyzedAt = null;
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
      analyzedText = text;
      analyzedAt = new Date();
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
  // ------------------------------------------------------------------
  // Full report download (PDF / Word / HTML / JSON)
  // ------------------------------------------------------------------
  const dlBtn = $("btn-download-report"), dlMenu = $("download-menu");
  dlBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    dlMenu.hidden = !dlMenu.hidden;
    dlBtn.setAttribute("aria-expanded", String(!dlMenu.hidden));
  });
  dlMenu.addEventListener("click", (e) => e.stopPropagation());
  document.addEventListener("click", () => { dlMenu.hidden = true; dlBtn.setAttribute("aria-expanded", "false"); });
  $$("[data-format]", dlMenu).forEach((b) => b.addEventListener("click", () => {
    dlMenu.hidden = true;
    downloadReport(b.dataset.format);
  }));

  const safeName = (s) => String(s || "contract").replace(/[^\w-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "contract";

  function saveBlob(content, type, filename) {
    const blob = new Blob([content], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  function downloadReport(format) {
    if (!lastReport) { toast("Analyze a contract first.", "bad"); return; }
    const base = `${safeName(lastReport.document_id)}-risk-report`;
    const withText = $("include-contract-text").checked;
    try {
      if (format === "json") {
        const data = { ...lastReport, generated_at: (analyzedAt || new Date()).toISOString(), model: modelLabel || undefined };
        if (withText) data.contract_text = analyzedText;
        saveBlob(JSON.stringify(data, null, 2), "application/json", `${base}.json`);
      } else if (format === "html") {
        saveBlob(buildReportHTML(lastReport, { withText, forWord: false }), "text/html;charset=utf-8", `${base}.html`);
      } else if (format === "doc") {
        saveBlob("﻿" + buildReportHTML(lastReport, { withText, forWord: true }), "application/msword", `${base}.doc`);
      } else if (format === "pdf") {
        printReportPDF(buildReportHTML(lastReport, { withText, forWord: false }), base);
        return;
      }
      toast("Report downloaded.", "ok");
    } catch (err) {
      toast("Could not create the report: " + err.message, "bad");
    }
  }

  function printReportPDF(html, title) {
    const old = $("report-print-frame");
    if (old) old.remove();
    const frame = document.createElement("iframe");
    frame.id = "report-print-frame";
    frame.setAttribute("aria-hidden", "true");
    frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden;";
    document.body.appendChild(frame);
    const pageTitle = document.title;
    frame.onload = () => {
      setTimeout(() => {
        document.title = title; // default PDF file name in most browsers
        try { frame.contentWindow.focus(); frame.contentWindow.print(); }
        finally { setTimeout(() => { document.title = pageTitle; }, 1000); }
      }, 250);
    };
    frame.srcdoc = html;
    toast('Choose "Save as PDF" in the print dialog.', "ok");
  }

  function highlight(text, match) {
    let out = esc(text);
    if (match && typeof match === "string" && match.length > 2) {
      const re = new RegExp(esc(match).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      out = out.replace(re, (m) => `<mark>${m}</mark>`);
    }
    return out;
  }

  function buildReportHTML(r, { withText = true, forWord = false } = {}) {
    const flags = (r.risk_flags || []).slice().sort((a, b) => sevRank(a.severity) - sevRank(b.severity));
    const score = Math.max(0, Math.min(100, num(r.overall_risk_score)));
    const band = bandFor(score);
    const level = String(r.risk_level || band.name);
    const lvl = level.toLowerCase();
    const action = r.risk_action || band.action;
    const cats = buildCategories(r, flags);
    const sb = r.severity_breakdown || {};
    const sevCount = (s) => sb[s] ?? flags.filter((f) => sevOf(f.severity) === s).length;
    const when = (analyzedAt || new Date()).toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" });
    const tax = Object.entries(r.predicted_clause_types || {}).filter(([, v]) => num(v) > 0).sort((a, b) => b[1] - a[1]);
    const recs = r.recommendations || [];
    const C = { critical: "#b42318", high: "#c2410c", medium: "#a16207", low: "#2f6f4f" };
    const BG = { critical: "#fbe9e7", high: "#fdeee3", medium: "#fbf3dc", low: "#e6f2ea" };
    const lvlColor = C[lvl] || "#1f2a44";
    const badge = (s) => `<span class="badge" style="background:${BG[s]};color:${C[s]}">${esc(s.toUpperCase())}</span>`;

    const findings = flags.map((f, i) => {
      const s = sevOf(f.severity);
      const md = f.metadata || {};
      const title = f.title || md.title || humanize(f.flag_type);
      const rec = f.recommendation || md.recommendation || "";
      const match = f.matched_pattern || md.matched_pattern || md.evidence || f.evidence || "";
      const conf = f.confidence != null ? `${Math.round(pct(f.confidence))}%` : "—";
      return `
      <div class="finding" style="border-left-color:${C[s]}">
        <table class="plain"><tr>
          <td><h3>Finding ${i + 1}. ${esc(title)}</h3></td>
          <td class="right">${badge(s)}</td>
        </tr></table>
        <p class="meta">Risk type: ${esc(f.flag_type || "—")} &nbsp;·&nbsp; Clause: ${esc(f.clause_id ?? "—")} &nbsp;·&nbsp; Confidence: ${conf}</p>
        ${f.reason ? `<p><b>Why it matters:</b> ${esc(f.reason)}</p>` : ""}
        ${f.evidence_text ? `<div class="quote">${highlight(f.evidence_text, match)}</div>` : ""}
        ${rec ? `<p class="fix"><b>Recommended action:</b> ${esc(rec)}</p>` : ""}
      </div>`;
    }).join("");

    const css = `
      @page { size: A4; margin: 16mm 15mm 18mm; }
      @page { @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 9pt Arial, sans-serif; color: #777; } }
      body { font-family: "Segoe UI", Arial, Helvetica, sans-serif; color: #1d2640; font-size: 10.5pt; line-height: 1.5; margin: 0; ${forWord ? "" : "max-width: 820px; margin: 0 auto; padding: 28px;"} }
      h1 { font-family: Georgia, "Times New Roman", serif; font-size: 22pt; margin: 0 0 2px; color: #1d2640; }
      h2 { font-family: Georgia, "Times New Roman", serif; font-size: 14pt; margin: 22px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #1d2640; color: #1d2640; page-break-after: avoid; }
      h3 { font-size: 11pt; margin: 0; }
      p { margin: 4px 0; }
      .sub { color: #666; margin: 0 0 14px; }
      table { border-collapse: collapse; width: 100%; }
      .grid td, .grid th { border: 1px solid #ddd5c8; padding: 6px 9px; text-align: left; vertical-align: top; font-size: 10pt; }
      .grid th { background: #f5f1ea; font-size: 9pt; text-transform: uppercase; letter-spacing: .04em; color: #3a4360; }
      .plain td { padding: 0; border: 0; vertical-align: middle; }
      .right { text-align: right; }
      .meta-table td { padding: 3px 12px 3px 0; font-size: 9.5pt; color: #444; border: 0; }
      .scorebox { border: 1px solid #ddd5c8; background: #fbf8f3; padding: 14px 16px; margin: 8px 0 4px; }
      .score { font-family: Georgia, serif; font-size: 30pt; font-weight: bold; color: ${lvlColor}; }
      .score small { font-size: 11pt; color: #777; font-weight: normal; }
      .level { font-size: 13pt; font-weight: bold; color: ${lvlColor}; }
      .bar { height: 10px; background: #ece6db; margin: 8px 0 4px; }
      .bar div { height: 10px; background: ${lvlColor}; width: ${score}%; }
      .scale { font-size: 8pt; color: #888; }
      .badge { display: inline-block; padding: 2px 8px; font-size: 8pt; font-weight: bold; letter-spacing: .05em; border-radius: 4px; }
      .finding { border: 1px solid #e5ddd0; border-left: 4px solid #999; padding: 10px 12px; margin: 0 0 10px; page-break-inside: avoid; }
      .finding .meta { font-size: 8.5pt; color: #777; font-family: Consolas, "Courier New", monospace; }
      .quote { font-family: Georgia, serif; background: #f7f3ec; border-left: 3px solid #d8cebd; padding: 7px 10px; margin: 6px 0; color: #3a4360; }
      mark { background: #f3d9a8; color: inherit; }
      .fix { background: #e6f2ea; padding: 6px 9px; margin-top: 6px; }
      ol li, ul li { margin-bottom: 4px; }
      .contract { white-space: pre-wrap; font-family: Georgia, serif; font-size: 9.5pt; line-height: 1.55; border: 1px solid #e5ddd0; padding: 12px; background: #fcfaf6; }
      .disclaimer { margin-top: 22px; padding: 10px 12px; border: 1px solid #e5ddd0; font-size: 9pt; color: #555; background: #fbf8f3; }
      .page-break { page-break-before: always; }
      .muted { color: #777; }
      @media print { body { padding: 0; max-width: none; } a { color: inherit; text-decoration: none; } }`;

    const head = forWord
      ? `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><title>${esc(r.document_id || "Contract")} — Risk Report</title><!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]--><style>${css}</style></head>`
      : `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(r.document_id || "Contract")} — Risk Report</title><style>${css}</style></head>`;

    return `${head}<body>
      <h1>Contract Risk Analysis Report</h1>
      <p class="sub">Automated clause classification and risk triage</p>
      <table class="meta-table">
        <tr><td><b>Document</b></td><td>${esc(r.document_id || "—")}</td><td><b>Generated</b></td><td>${esc(when)}</td></tr>
        <tr><td><b>Model</b></td><td>${esc(modelLabel || "—")}</td><td><b>Clauses analysed</b></td><td>${num(r.total_clauses)}</td></tr>
      </table>

      <h2>1. Executive summary</h2>
      <div class="scorebox">
        <table class="plain"><tr>
          <td style="width:42%"><span class="score">${score.toFixed(1)}</span> <small>/ 100</small><br><span class="level">${esc(level)} risk</span></td>
          <td><p><b>${esc(action)}</b></p><p>${esc(r.summary || "")}</p></td>
        </tr></table>
        <div class="bar"><div></div></div>
        <div class="scale">0 — Low — 30 — Medium — 60 — High — 80 — Critical — 100</div>
      </div>
      <table class="grid" style="margin-top:10px">
        <tr><th>Clauses</th><th>Risk flags</th><th>Risk types</th><th>Critical</th><th>High</th><th>Medium</th><th>Low</th></tr>
        <tr><td>${num(r.total_clauses)}</td><td>${flags.length}</td><td>${cats.length}</td>
          <td style="color:${C.critical}"><b>${sevCount("critical")}</b></td><td style="color:${C.high}"><b>${sevCount("high")}</b></td>
          <td style="color:${C.medium}"><b>${sevCount("medium")}</b></td><td style="color:${C.low}"><b>${sevCount("low")}</b></td></tr>
      </table>

      <h2>2. Risks by type</h2>
      ${cats.length ? `<table class="grid"><tr><th>#</th><th>Risk</th><th>Severity</th><th>Clauses</th>${cats.some((c) => c.points) ? "<th>Points</th>" : ""}</tr>
        ${cats.map((c, i) => `<tr><td>${i + 1}</td><td>${esc(c.title)}</td><td>${badge(c.severity)}</td><td>${c.clauses}</td>${cats.some((x) => x.points) ? `<td>${c.points ? c.points.toFixed(1) : "—"}</td>` : ""}</tr>`).join("")}
      </table>` : `<p class="muted">No configured risk indicators were detected.</p>`}

      <h2>3. Detailed findings</h2>
      ${findings || `<p class="muted">No risk flags were raised for this contract.</p>`}

      <h2>4. Recommendations</h2>
      ${recs.length ? `<ol>${recs.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>` : `<p class="muted">No recommendations returned.</p>`}

      <h2>5. Clause types identified by the model</h2>
      ${tax.length ? `<table class="grid"><tr><th>LEDGAR category</th><th>Clauses</th></tr>${tax.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${num(v)}</td></tr>`).join("")}</table>` : `<p class="muted">No clause types returned.</p>`}

      <h2>6. Method</h2>
      <p>The contract was split into clauses. Each clause was classified into one of 100 LexGLUE LEDGAR categories by the NLP model${modelLabel ? ` (${esc(modelLabel)})` : ""}. Configurable risk rules then matched risky wording and clause types and assigned a severity (low, medium, high, critical).</p>
      <p>The overall score counts each risk type once, adds a small capped bonus for repeated clauses, and uses a saturating curve, so a longer contract is not scored higher just because it is longer. The score is limited by the most severe risk found.</p>

      ${withText && analyzedText ? `<h2 class="page-break">Appendix A. Contract text analysed</h2><div class="contract">${esc(analyzedText)}</div>` : ""}

      <div class="disclaimer"><b>Disclaimer.</b> ${esc($("disclaimer-text").textContent || "This report is an automated risk triage and is not legal advice.")}</div>
    </body></html>`;
  }

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
