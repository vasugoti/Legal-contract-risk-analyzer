document.addEventListener("DOMContentLoaded", () => {
  // Preset Data
  const SAMPLE_CONTRACT = `MASTER SERVICES AGREEMENT

1. Termination. Either party may terminate this Agreement without cause upon thirty days prior written notice. The Company may terminate immediately for material breach that remains uncured.

2. Confidentiality. The recipient shall keep all confidential information secret and use it only for the purposes of this Agreement.

3. Payment. Customer shall pay all undisputed invoices within thirty days of receipt and late payments may accrue interest.

4. Indemnification. Supplier shall indemnify and hold harmless Customer from third-party claims arising from Supplier's breach.

5. Governing Law. This Agreement shall be governed by the laws of the State of New York without regard to conflict of law rules.`;

  const CLAUSE_PRESETS = {
    term: "Either party may terminate this Agreement without cause upon thirty (30) days prior written notice.",
    indem: "Supplier shall indemnify and hold harmless Customer from third-party claims arising from Supplier's breach of warranty.",
    liab: "In no event shall either party be liable for any indirect, incidental, consequential, special, or punitive damages.",
    law: "This Agreement shall be governed by and construed under the laws of the State of Delaware, without regard to its conflict of laws principles.",
    assign: "Neither party may assign or delegate any of its rights or obligations without the prior written consent of the other party."
  };

  // State
  let systemInfo = {
    model_name: "unknown",
    mock_mode: false,
    model_loaded: false,
    disclaimer: ""
  };

  // DOM Elements - Navigation & Header
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const modelBadge = document.getElementById("model-badge");
  const demoBadge = document.getElementById("demo-mode-badge");
  const disclaimerText = document.getElementById("disclaimer-text");

  // DOM Elements - Tab 1: Document
  const docIdInput = document.getElementById("doc-id-input");
  const docTextInput = document.getElementById("doc-text-input");
  const docCharCount = document.getElementById("doc-char-count");
  const contractFileInput = document.getElementById("contract-file-input");
  const uploadStatus = document.getElementById("upload-status");
  const btnAnalyzeDoc = document.getElementById("btn-analyze-doc");
  const btnLoadSampleDoc = document.getElementById("btn-load-sample-doc");
  const btnClearDoc = document.getElementById("btn-clear-doc");
  const docEmptyState = document.getElementById("doc-empty-state");
  const docResultsContent = document.getElementById("doc-results-content");
  const docReportId = document.getElementById("doc-report-id");
  const docSummaryText = document.getElementById("doc-summary-text");
  const docRiskScore = document.getElementById("doc-risk-score");
  const docRiskMeter = document.getElementById("doc-risk-meter");
  const docClauseCount = document.getElementById("doc-clause-count");
  const docFlagsCount = document.getElementById("doc-flags-count");
  const sevCriticalCount = document.getElementById("sev-critical-count");
  const sevHighCount = document.getElementById("sev-high-count");
  const sevMediumCount = document.getElementById("sev-medium-count");
  const sevLowCount = document.getElementById("sev-low-count");
  const docRecommendations = document.getElementById("doc-recommendations");
  const flagsTableBody = document.getElementById("flags-table-body");
  const taxonomyTableBody = document.getElementById("taxonomy-table-body");

  // DOM Elements - Tab 2: Single Clause
  const clauseTextInput = document.getElementById("clause-text-input");
  const btnAnalyzeClause = document.getElementById("btn-analyze-clause");
  const btnClearClause = document.getElementById("btn-clear-clause");
  const clauseResultCard = document.getElementById("clause-result-card");
  const clausePredictedLabel = document.getElementById("clause-predicted-label");
  const clauseConfidenceVal = document.getElementById("clause-confidence-val");
  const clauseConfidenceBar = document.getElementById("clause-confidence-bar");
  const clauseTopkBody = document.getElementById("clause-topk-body");
  const clauseRiskFlagsContainer = document.getElementById("clause-risk-flags-container");
  const clauseModelTag = document.getElementById("clause-model-tag");

  // DOM Elements - Tab 3: Precedent Search
  const searchQueryInput = document.getElementById("search-query-input");
  const searchTopkInput = document.getElementById("search-topk-input");
  const btnRunSearch = document.getElementById("btn-run-search");
  const searchResultsCard = document.getElementById("search-results-card");
  const searchResultsCount = document.getElementById("search-results-count");
  const searchResultsList = document.getElementById("search-results-list");

  // DOM Elements - Tab 4: Metrics
  const btnRefreshMetrics = document.getElementById("btn-refresh-metrics");
  const rtAnalyzedClauses = document.getElementById("rt-analyzed-clauses");
  const rtAnalyzedDocs = document.getElementById("rt-analyzed-docs");
  const rtAvgLatency = document.getElementById("rt-avg-latency");
  const rtRiskFlags = document.getElementById("rt-risk-flags");

  // Tab Navigation
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabButtons.forEach(b => b.classList.remove("active"));
      tabPanels.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");

      if (targetId === "tab-metrics") {
        fetchMetrics();
      }
    });
  });

  // Init Status & Model Info
  async function initSystem() {
    try {
      const [healthRes, infoRes] = await Promise.all([
        fetch("/health"),
        fetch("/model/info")
      ]);

      if (healthRes.ok && infoRes.ok) {
        statusDot.className = "status-dot operational";
        statusText.textContent = "API Operational";
        
        systemInfo = await infoRes.json();
        let modelLabel = systemInfo.mock_mode ? "Mock Mode" : (systemInfo.model_name || "Trained Model");
        if (systemInfo.fallback_active) {
          modelLabel = `${systemInfo.model_name} [Fallback: ${systemInfo.fallback_reason}]`;
          modelBadge.title = `Fallback active: ${systemInfo.fallback_reason}`;
        }
        modelBadge.textContent = "Model: " + modelLabel;
        clauseModelTag.textContent = "Model: " + (systemInfo.model_name || "Trained Model");

        if (systemInfo.disclaimer) {
          disclaimerText.textContent = systemInfo.disclaimer;
        }

        if (systemInfo.mock_mode) {
          demoBadge.classList.remove("hidden");
          demoBadge.textContent = "Demo mode — mock model";
        } else {
          demoBadge.classList.add("hidden");
        }
        fetchMetrics();
      } else {
        throw new Error("Service returned error");
      }
    } catch (err) {
      statusDot.className = "status-dot error";
      statusText.textContent = "Offline / Connection Error";
      modelBadge.textContent = "Model: Unavailable";
    }
  }

  // Fetch Live Metrics & Benchmark Data
  async function fetchMetrics() {
    try {
      const res = await fetch("/metrics");
      if (res.ok) {
        const data = await res.json();
        rtAnalyzedClauses.textContent = Number(data.analyzed_clauses || 0).toLocaleString();
        rtAnalyzedDocs.textContent = Number(data.analyzed_documents || 0).toLocaleString();
        rtAvgLatency.textContent = Number(data.average_latency_ms || 0).toFixed(2);
        rtRiskFlags.textContent = Number(data.total_risk_flags || 0).toLocaleString();

        const bm = data.benchmark;
        if (!bm) return;

        const bmTitle = document.getElementById("bm-title");
        const bmBadge = document.getElementById("bm-badge");
        const bmDesc = document.getElementById("bm-desc");
        const bmFallbackBanner = document.getElementById("bm-fallback-banner");
        const bmCards = document.getElementById("bm-cards");
        const bmColTfidf = document.getElementById("bm-col-tfidf");
        const bmColLegalPro = document.getElementById("bm-col-legalpro");
        const bmCompTbody = document.getElementById("bm-comparison-tbody");
        const bmSpecsTbody = document.getElementById("bm-specs-tbody");

        if (bmTitle) bmTitle.textContent = bm.title;
        if (bmBadge) bmBadge.textContent = bm.badge;
        if (bmDesc) bmDesc.textContent = bm.description;

        if (bmFallbackBanner) {
          if (bm.fallback_active) {
            bmFallbackBanner.className = "amber-badge";
            bmFallbackBanner.textContent = `Fallback active: ${bm.fallback_reason || "Model check failed"}`;
          } else {
            bmFallbackBanner.className = "hidden";
          }
        }

        // Render Cards
        if (bmCards && Array.isArray(bm.cards)) {
          bmCards.innerHTML = bm.cards.map(c => `
            <div class="metric-card">
              <div class="metric-label">${c.label}</div>
              <div class="metric-value">${c.value}</div>
              <div class="metric-sub">${c.sub}</div>
            </div>
          `).join("");
        }

        // Highlight active column in comparison table
        const isLegalProActive = bm.effective_backend === "legalpro";
        const colLabel = (bm.active_model_name && bm.active_model_name.includes("RoBERTa")) ? "LEDGAR-SRA" : "LegalPro-BERT";
        if (bmColLegalPro) {
          bmColLegalPro.className = isLegalProActive ? "table-col-active" : "";
          bmColLegalPro.innerHTML = `${colLabel} ${isLegalProActive ? '<span class="meta-tag" style="font-size:10px;padding:1px 4px;margin-left:4px;color:var(--primary);border-color:var(--primary);">ACTIVE</span>' : ''}`;
        }
        if (bmColTfidf) {
          bmColTfidf.className = !isLegalProActive ? "table-col-active" : "";
          bmColTfidf.innerHTML = `TF-IDF + LogReg ${!isLegalProActive ? '<span class="meta-tag" style="font-size:10px;padding:1px 4px;margin-left:4px;color:var(--primary);border-color:var(--primary);">ACTIVE</span>' : ''}`;
        }

        // Render Comparison Table
        if (bmCompTbody && Array.isArray(bm.comparison_table)) {
          bmCompTbody.innerHTML = bm.comparison_table.map(row => {
            if (row.is_reference) {
              return `
                <tr class="row-reference">
                  <td class="font-medium">${row.metric}</td>
                  <td>${row.tfidf}</td>
                  <td>${row.legalpro}</td>
                  <td>${row.change}</td>
                </tr>
              `;
            }
            return `
              <tr>
                <td class="font-medium">${row.metric}</td>
                <td class="${!isLegalProActive ? 'table-col-active' : ''}">${row.tfidf}</td>
                <td class="${isLegalProActive ? 'table-col-active' : ''}">${row.legalpro}</td>
                <td class="font-semibold ${row.change.startsWith('+') ? 'text-success' : ''}">${row.change}</td>
              </tr>
            `;
          }).join("");
        }

        // Render Model Specifications
        if (bmSpecsTbody && Array.isArray(bm.specs)) {
          bmSpecsTbody.innerHTML = bm.specs.map(spec => {
            let valHtml = spec.value;
            if (spec.label === "Fallback" && bm.fallback_active) {
              valHtml = `<span>${spec.value}</span> <span class="amber-badge" style="margin-left:6px;">Fallback active: ${bm.fallback_reason}</span>`;
            } else if (spec.label === "Model Checkpoint" || spec.label === "Artifact Path") {
              valHtml = `<code class="code-ref">${spec.value}</code>`;
            }
            return `
              <tr>
                <td class="font-medium" style="width: 25%;">${spec.label}</td>
                <td>${valHtml}</td>
              </tr>
            `;
          }).join("");
        }
      }
    } catch (err) {
      console.error("Failed to fetch metrics:", err);
    }
  }

  // Document Analysis Handlers
  if (contractFileInput) {
    contractFileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      uploadStatus.className = "upload-status loading";
      uploadStatus.textContent = "Reading file...";
      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch("/extract-text", { method: "POST", body: form });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Upload failed");
        docTextInput.value = data.text;
        docTextInput.dispatchEvent(new Event("input"));
        uploadStatus.className = "upload-status success";
        uploadStatus.textContent = `Loaded ${file.name} (${data.characters.toLocaleString()} characters)`;
      } catch (err) {
        uploadStatus.className = "upload-status error";
        uploadStatus.textContent = "Error: " + err.message;
      }
    });
  }

  docTextInput.addEventListener("input", () => {
    docCharCount.textContent = `${docTextInput.value.length} characters`;
  });

  btnLoadSampleDoc.addEventListener("click", () => {
    docTextInput.value = SAMPLE_CONTRACT;
    docCharCount.textContent = `${docTextInput.value.length} characters`;
  });

  btnClearDoc.addEventListener("click", () => {
    docTextInput.value = "";
    docCharCount.textContent = "0 characters";
    if (contractFileInput) contractFileInput.value = "";
    if (uploadStatus) {
      uploadStatus.textContent = "";
      uploadStatus.className = "upload-status";
    }
    docResultsContent.classList.add("hidden");
    docEmptyState.classList.remove("hidden");
    docReportId.textContent = "No document analyzed";
  });

  btnAnalyzeDoc.addEventListener("click", async () => {
    const text = docTextInput.value.trim();
    if (!text) {
      alert("Please enter contract text or click 'Load Sample MSA'.");
      return;
    }

    const docId = docIdInput.value.trim() || "document-001";
    setLoading(btnAnalyzeDoc, true, "Analyzing Document...");

    try {
      const res = await fetch("/analyze/document", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: docId,
          text: text
        })
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`API Error (${res.status}): ${errText}`);
      }

      const report = await res.json();
      renderDocumentReport(report);
    } catch (err) {
      alert("Failed to analyze document: " + err.message);
    } finally {
      setLoading(btnAnalyzeDoc, false, "Analyze Document");
    }
  });

  function renderDocumentReport(report) {
    docEmptyState.classList.add("hidden");
    docResultsContent.classList.remove("hidden");

    docReportId.textContent = report.document_id || "Document Report";
    docSummaryText.textContent = report.summary || "Analysis complete.";
    
    // Overall Risk Score
    const score = Number(report.overall_risk_score || 0);
    docRiskScore.textContent = score.toFixed(1);
    docRiskMeter.style.width = `${Math.min(100, Math.max(0, score))}%`;

    const docRiskLevel = document.getElementById("doc-risk-level");
    if (docRiskLevel) {
      if (report.risk_level) {
        docRiskLevel.style.display = "inline-block";
        docRiskLevel.textContent = report.risk_level.toUpperCase();
        if (report.risk_color) {
          docRiskLevel.style.color = report.risk_color;
          docRiskLevel.style.borderColor = report.risk_color;
          docRiskMeter.style.backgroundColor = report.risk_color;
        }
      } else {
        docRiskLevel.style.display = "none";
      }
    }

    if (!report.risk_color) {
      if (score >= 60) {
        docRiskMeter.style.backgroundColor = "#CF222E";
      } else if (score >= 30) {
        docRiskMeter.style.backgroundColor = "#D97706";
      } else {
        docRiskMeter.style.backgroundColor = "#1A7F37";
      }
    }

    docClauseCount.textContent = Number(report.total_clauses || 0).toLocaleString();
    docFlagsCount.textContent = Number((report.risk_flags || []).length).toLocaleString();

    // Severity breakdown
    const sev = report.severity_breakdown || {};
    sevCriticalCount.textContent = Number(sev.critical || 0);
    sevHighCount.textContent = Number(sev.high || 0);
    sevMediumCount.textContent = Number(sev.medium || 0);
    sevLowCount.textContent = Number(sev.low || 0);

    // Recommendations
    docRecommendations.innerHTML = "";
    const recs = report.recommendations || [];
    if (recs.length === 0) {
      docRecommendations.innerHTML = "<li>No specific recommendations generated.</li>";
    } else {
      recs.forEach(r => {
        const li = document.createElement("li");
        li.textContent = r;
        docRecommendations.appendChild(li);
      });
    }

    // Risk Flags Table
    flagsTableBody.innerHTML = "";
    const flags = report.risk_flags || [];
    if (flags.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="6" style="text-align: center; color: var(--text-muted); padding: 16px;">No risk flags detected in this document.</td>`;
      flagsTableBody.appendChild(row);
    } else {
      flags.forEach(f => {
        const row = document.createElement("tr");
        const sevClass = (f.severity || "low").toLowerCase();
        const displayType = f.title ? `<strong>${escapeHtml(f.title)}</strong><div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(f.flag_type)}</div>` : `<strong>${escapeHtml(f.flag_type)}</strong>`;
        const actionHtml = f.recommendation ? `<div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;"><em>Action: ${escapeHtml(f.recommendation)}</em></div>` : "";
        row.innerHTML = `
          <td><code class="code-ref">${escapeHtml(f.flag_id)}</code></td>
          <td><span style="font-family: var(--font-mono); font-size: 12px;">${escapeHtml(f.clause_id)}</span></td>
          <td><span class="severity-pill ${sevClass}">${escapeHtml(f.severity)}</span></td>
          <td>${displayType}</td>
          <td>${escapeHtml(f.reason)}${actionHtml}</td>
          <td><span class="evidence-text">${escapeHtml(f.evidence_text || "—")}</span></td>
        `;
        flagsTableBody.appendChild(row);
      });
    }

    // Top Risk Categories Table
    const blockCats = document.getElementById("block-risk-categories");
    const catsBody = document.getElementById("categories-table-body");
    const categories = report.category_breakdown || [];
    if (blockCats && catsBody) {
      if (categories.length > 0) {
        blockCats.style.display = "block";
        catsBody.innerHTML = "";
        categories.slice(0, 5).forEach(c => {
          const row = document.createElement("tr");
          const sevClass = (c.severity || "low").toLowerCase();
          row.innerHTML = `
            <td class="font-medium"><strong>${escapeHtml(c.flag_type)}</strong></td>
            <td><span class="severity-pill ${sevClass}">${escapeHtml(c.severity)}</span></td>
            <td style="font-family: var(--font-mono);">${Number(c.clauses || 1).toLocaleString()}</td>
            <td style="font-family: var(--font-mono);">${Number(c.points || 0).toFixed(1)} pts</td>
          `;
          catsBody.appendChild(row);
        });
      } else {
        blockCats.style.display = "none";
      }
    }

    // Taxonomy Breakdown Table
    taxonomyTableBody.innerHTML = "";
    const types = report.predicted_clause_types || {};
    const entries = Object.entries(types).sort((a, b) => b[1] - a[1]);
    if (entries.length === 0) {
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="2" style="text-align: center; color: var(--text-muted); padding: 16px;">No clauses segmented.</td>`;
      taxonomyTableBody.appendChild(row);
    } else {
      entries.forEach(([typeName, count]) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td class="font-medium">${escapeHtml(typeName)}</td>
          <td style="font-family: var(--font-mono); font-variant-numeric: tabular-nums;">${Number(count).toLocaleString()}</td>
        `;
        taxonomyTableBody.appendChild(row);
      });
    }
  }

  // Single Clause Handlers
  document.getElementById("preset-term").addEventListener("click", () => {
    clauseTextInput.value = CLAUSE_PRESETS.term;
  });
  document.getElementById("preset-indem").addEventListener("click", () => {
    clauseTextInput.value = CLAUSE_PRESETS.indem;
  });
  document.getElementById("preset-liab").addEventListener("click", () => {
    clauseTextInput.value = CLAUSE_PRESETS.liab;
  });
  document.getElementById("preset-law").addEventListener("click", () => {
    clauseTextInput.value = CLAUSE_PRESETS.law;
  });
  document.getElementById("preset-assign").addEventListener("click", () => {
    clauseTextInput.value = CLAUSE_PRESETS.assign;
  });

  btnClearClause.addEventListener("click", () => {
    clauseTextInput.value = "";
    clauseResultCard.classList.add("hidden");
  });

  btnAnalyzeClause.addEventListener("click", async () => {
    const text = clauseTextInput.value.trim();
    if (!text) {
      alert("Please enter clause text or select a preset.");
      return;
    }

    setLoading(btnAnalyzeClause, true, "Analyzing Clause...");
    try {
      const res = await fetch("/analyze/clause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`API Error (${res.status}): ${errText}`);
      }

      const data = await res.json();
      renderClauseResult(data);
    } catch (err) {
      alert("Failed to analyze clause: " + err.message);
    } finally {
      setLoading(btnAnalyzeClause, false, "Analyze Clause");
    }
  });

  function renderClauseResult(data) {
    clauseResultCard.classList.remove("hidden");
    clausePredictedLabel.textContent = data.predicted_label || "Unclassified";
    
    const conf = Number(data.confidence || 0);
    const pct = (conf * 100).toFixed(1);
    clauseConfidenceVal.textContent = `${pct}%`;
    clauseConfidenceBar.style.width = `${Math.min(100, Math.max(0, conf * 100))}%`;

    // Top K table
    clauseTopkBody.innerHTML = "";
    const topk = data.top_k_labels || [];
    if (topk.length === 0) {
      clauseTopkBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No top-k distribution returned.</td></tr>`;
    } else {
      topk.forEach((item, idx) => {
        const label = Array.isArray(item) ? item[0] : item.label;
        const prob = Array.isArray(item) ? item[1] : item.score;
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-family: var(--font-mono);">${idx + 1}</td>
          <td class="font-medium">${escapeHtml(label)}</td>
          <td style="font-family: var(--font-mono); font-variant-numeric: tabular-nums;">${(Number(prob) * 100).toFixed(2)}%</td>
        `;
        clauseTopkBody.appendChild(row);
      });
    }

    // Triggered risk flags
    clauseRiskFlagsContainer.innerHTML = "";
    const flags = data.risk_flags || [];
    if (flags.length === 0) {
      clauseRiskFlagsContainer.innerHTML = `<div style="padding: 12px; font-size: 13px; color: var(--text-muted); background: var(--surface-alt); border: 1px solid var(--border); border-radius: var(--radius-sm);">No risk indicators identified for this clause.</div>`;
    } else {
      flags.forEach(f => {
        const card = document.createElement("div");
        const sevClass = (f.severity || "low").toLowerCase();
        card.className = `flag-card ${sevClass}`;
        card.innerHTML = `
          <div class="flag-header">
            <div class="flag-title-wrap">
              <span class="severity-pill ${sevClass}">${escapeHtml(f.severity)}</span>
              <span class="flag-type-name">${escapeHtml(f.flag_type)}</span>
            </div>
            <code class="code-ref">${escapeHtml(f.flag_id)}</code>
          </div>
          <p class="flag-reason">${escapeHtml(f.reason)}</p>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
            Evidence: <span class="evidence-text" style="display: inline-block; margin-top: 2px;">${escapeHtml(f.evidence_text || "—")}</span>
          </div>
        `;
        clauseRiskFlagsContainer.appendChild(card);
      });
    }
  }

  // Precedent Search Handlers
  document.getElementById("search-preset-1").addEventListener("click", () => {
    searchQueryInput.value = "indemnification and hold harmless obligations";
    btnRunSearch.click();
  });
  document.getElementById("search-preset-2").addEventListener("click", () => {
    searchQueryInput.value = "termination upon thirty days written notice";
    btnRunSearch.click();
  });
  document.getElementById("search-preset-3").addEventListener("click", () => {
    searchQueryInput.value = "governed by the laws of the State of New York";
    btnRunSearch.click();
  });

  btnRunSearch.addEventListener("click", async () => {
    const query = searchQueryInput.value.trim();
    if (!query) {
      alert("Please enter a query to search precedent clauses.");
      return;
    }

    const topK = parseInt(searchTopkInput.value, 10) || 5;
    setLoading(btnRunSearch, true, "Searching...");

    try {
      const res = await fetch("/search/similar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, top_k: topK })
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`API Error (${res.status}): ${errText}`);
      }

      const data = await res.json();
      renderSearchResults(data.results || []);
    } catch (err) {
      alert("Search failed: " + err.message);
    } finally {
      setLoading(btnRunSearch, false, "Search Precedents");
    }
  });

  function renderSearchResults(results) {
    searchResultsCard.classList.remove("hidden");
    searchResultsCount.textContent = `${results.length} results returned`;
    searchResultsList.innerHTML = "";

    if (results.length === 0) {
      searchResultsList.innerHTML = `<div class="empty-desc" style="padding: 24px; text-align: center;">No precedent clauses matched your query.</div>`;
      return;
    }

    results.forEach(item => {
      const el = document.createElement("div");
      el.className = "search-result-item";
      el.innerHTML = `
        <div class="result-item-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="result-id">${escapeHtml(item.clause_id)}</span>
            ${item.label ? `<span class="meta-tag">${escapeHtml(item.label)}</span>` : ""}
          </div>
          <span class="result-score">Similarity: ${Number(item.score).toFixed(4)}</span>
        </div>
        <p class="result-item-text">${escapeHtml(item.text)}</p>
      `;
      searchResultsList.appendChild(el);
    });
  }

  // Metrics Handler
  btnRefreshMetrics.addEventListener("click", () => {
    fetchMetrics();
  });

  // Helpers
  function setLoading(btn, isLoading, text) {
    if (isLoading) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span>${text}`;
    } else {
      btn.disabled = false;
      btn.textContent = text;
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initial Run
  initSystem();
});
