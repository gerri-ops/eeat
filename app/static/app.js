/* ── E-E-A-T Content Grader — Frontend Application ────────────────────────── */

let currentData = null;
let activeInputType = "url";
let activePriorityFilter = "all";

const SCOPE_META = {
  global_fix: { label: "Global Fix", icon: "🌐", desc: "Site-wide implementation" },
  new_page:   { label: "New Page",   icon: "📄", desc: "New page to create & link" },
  page_level: { label: "Page Level", icon: "✏️", desc: "Author / editor can fix on this page" },
};

const SCOPE_ORDER = ["page_level", "global_fix", "new_page"];

/* ── Input tab switching ─────────────────────────────────────────────────── */
document.querySelectorAll("#inputTabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#inputTabs button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeInputType = btn.dataset.type;
    document.getElementById("inputUrl").style.display = activeInputType === "url" ? "" : "none";
    document.getElementById("inputHtml").style.display = activeInputType === "html" ? "" : "none";
    document.getElementById("inputText").style.display = activeInputType === "text" ? "" : "none";
  });
});

/* ── Result tab switching ────────────────────────────────────────────────── */
document.querySelectorAll("#resultTabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#resultTabs button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

/* ── Priority filter switching ───────────────────────────────────────────── */
document.querySelectorAll("#priorityFilters .filter-pill").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#priorityFilters .filter-pill").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activePriorityFilter = btn.dataset.priority;
    if (currentData) renderFixesContent(currentData.recommendations);
  });
});

/* ── Run analysis ────────────────────────────────────────────────────────── */
async function runAnalysis() {
  const content = getInputContent();
  if (!content) {
    alert("Please enter content to analyze.");
    return;
  }

  const body = {
    input_type: activeInputType,
    content: content,
    author_name: document.getElementById("authorInput").value || null,
    site_name: document.getElementById("siteInput").value || null,
    preset: document.getElementById("presetInput").value || null,
  };

  showLoading(true);
  try {
    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      let detail = "Analysis failed (status " + resp.status + ")";
      try {
        const err = await resp.json();
        detail = err.detail || detail;
      } catch (_) {
        detail += " — " + (await resp.text()).substring(0, 200);
      }
      throw new Error(detail);
    }
    currentData = await resp.json();
    renderResults(currentData);
  } catch (e) {
    console.error("Analysis error:", e);
    document.getElementById("inputPanel").style.display = "";
    alert("Error: " + e.message);
  } finally {
    showLoading(false);
  }
}

function getInputContent() {
  if (activeInputType === "url") return document.getElementById("urlInput").value.trim();
  if (activeInputType === "html") return document.getElementById("htmlInput").value.trim();
  return document.getElementById("textInput").value.trim();
}

function showLoading(show) {
  document.getElementById("loading").classList.toggle("visible", show);
  document.getElementById("analyzeBtn").disabled = show;
  if (show) {
    const msgs = ["Fetching content...", "Extracting signals...", "Running rules engine...", "Scoring E-E-A-T...", "Generating recommendations..."];
    let i = 0;
    window._loadingInterval = setInterval(() => {
      i = (i + 1) % msgs.length;
      document.getElementById("loadingText").textContent = msgs[i];
    }, 1800);
  } else {
    clearInterval(window._loadingInterval);
  }
}

/* ── Render all results ──────────────────────────────────────────────────── */
function renderResults(data) {
  document.getElementById("inputPanel").style.display = "none";
  document.getElementById("results").style.display = "block";
  document.getElementById("headerActions").style.display = "flex";

  renderAnalyzedUrl(data);
  renderSummary(data);
  renderScoreDashboard(data.score);
  renderFixes(data.recommendations);
  renderEvidence(data.score);
  renderClaims(data.citation_audit);
  renderCompliance(data.score.compliance_flags);
}

/* ── Analyzed URL Banner ─────────────────────────────────────────────────── */
function renderAnalyzedUrl(data) {
  const banner = document.getElementById("analyzedUrlBanner");
  const textEl = document.getElementById("analyzedUrlText");
  const url = data.extracted && data.extracted.url;
  if (url) {
    textEl.innerHTML = `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>`;
    banner.style.display = "flex";
  } else {
    const title = data.extracted && data.extracted.title;
    if (title) {
      textEl.textContent = title;
      banner.style.display = "flex";
    } else {
      banner.style.display = "none";
    }
  }
}

/* ── Summary bar ─────────────────────────────────────────────────────────── */
function renderSummary(data) {
  document.getElementById("summaryBar").textContent = data.summary;
}

/* ── Score dashboard ─────────────────────────────────────────────────────── */
function renderScoreDashboard(score) {
  const overall = score.overall;
  const ring = document.getElementById("scoreRing");
  const circumference = 2 * Math.PI * 70;
  const offset = circumference - (overall / 100) * circumference;

  ring.style.strokeDasharray = circumference;
  setTimeout(() => {
    ring.style.strokeDashoffset = offset;
    ring.style.stroke = scoreColor(overall);
  }, 100);

  const numEl = document.getElementById("overallScore");
  animateNumber(numEl, 0, Math.round(overall), 800);

  const badges = document.getElementById("badgesArea");
  const riskClass = { high: "badge-risk-high", medium: "badge-risk-medium", low: "badge-risk-low" };
  badges.innerHTML = `
    <span class="badge ${riskClass[score.ymyl_risk] || 'badge-risk-low'} has-tooltip" data-tooltip="risk-${score.ymyl_risk}">${score.ymyl_risk} risk</span>
    <span class="badge" style="background:rgba(99,102,241,0.15);color:var(--accent);">${score.preset_used.replace(/_/g, " ")}</span>
  `;
  initTooltips();

  const dims = [
    { key: "experience", label: "Experience", data: score.experience },
    { key: "expertise", label: "Expertise", data: score.expertise },
    { key: "authoritativeness", label: "Authoritativeness", data: score.authoritativeness },
    { key: "trust", label: "Trust", data: score.trust },
  ];

  const container = document.getElementById("subScores");
  container.innerHTML = dims.map((d) => {
    const pct = (d.data.score / 25) * 100;
    const color = scoreColor(d.data.score * 4);
    return `
      <div class="sub-score-card" onclick="showDimensionDetail('${d.key}')">
        <div class="sub-score-header">
          <h3>${d.label}</h3>
          <div class="sub-score-num" style="color:${color}">${d.data.score}</div>
        </div>
        <div class="sub-bar"><div class="sub-bar-fill" style="width:${pct}%;background:${color}"></div></div>
        <div class="sub-score-summary">${d.data.summary || `${d.data.signals.filter((s) => s.found).length}/${d.data.signals.length} signals found`}</div>
      </div>
    `;
  }).join("");
}

function showDimensionDetail(key) {
  document.querySelectorAll("#resultTabs button").forEach((b) => b.classList.remove("active"));
  document.querySelector('#resultTabs button[data-tab="evidence"]').classList.add("active");
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  document.getElementById("tab-evidence").classList.add("active");
  const el = document.getElementById("evidence-" + key);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ── Priority Fixes (grouped by scope, filterable by priority) ───────────── */
function renderFixes(recs) {
  const toolbar = document.getElementById("fixesToolbar");
  toolbar.style.display = recs.length ? "flex" : "none";
  renderFixesContent(recs);
}

function renderFixesContent(recs) {
  const container = document.getElementById("fixesContent");
  if (!recs || !recs.length) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:2rem;">No recommendations generated.</p>';
    return;
  }

  const filtered = activePriorityFilter === "all"
    ? recs
    : recs.filter((r) => r.impact === activePriorityFilter);

  if (!filtered.length) {
    container.innerHTML = `<p style="color:var(--text-muted);padding:2rem;">No ${activePriorityFilter}-priority fixes found.</p>`;
    return;
  }

  const grouped = {};
  SCOPE_ORDER.forEach((s) => (grouped[s] = []));
  filtered.forEach((r) => {
    const scope = r.scope || "page_level";
    if (!grouped[scope]) grouped[scope] = [];
    grouped[scope].push(r);
  });

  let globalIdx = 0;
  let html = "";

  SCOPE_ORDER.forEach((scopeKey) => {
    const items = grouped[scopeKey];
    if (!items || !items.length) return;
    const meta = SCOPE_META[scopeKey];

    html += `
      <div class="scope-group">
        <div class="scope-group-header">
          <span class="scope-icon">${meta.icon}</span>
          <h3>${meta.label}</h3>
          <span class="scope-count">${items.length} fix${items.length !== 1 ? "es" : ""}</span>
          <span class="scope-desc">${meta.desc}</span>
        </div>
        <div class="scope-group-body">
    `;

    items.forEach((r) => {
      globalIdx++;
      html += renderFixCard(r, globalIdx);
    });

    html += `</div></div>`;
  });

  container.innerHTML = html;
  initTooltips();
}

function renderFixCard(r, idx) {
  const scopeMeta = SCOPE_META[r.scope] || SCOPE_META.page_level;
  return `
    <div class="fix-card">
      <div class="fix-header">
        <h4><span style="color:var(--text-dim);margin-right:0.5rem;">#${idx}</span>${esc(r.title)}</h4>
        <div class="fix-meta">
          <span class="badge badge-impact-${r.impact} has-tooltip" data-tooltip="impact-${r.impact}">${r.impact} impact</span>
          <span class="badge badge-effort-${r.effort} has-tooltip" data-tooltip="effort-${r.effort}">${r.effort}</span>
          ${r.dimension ? `<span class="badge" style="background:rgba(99,102,241,0.12);color:var(--accent);">${r.dimension}</span>` : ""}
          <span class="badge badge-scope-${r.scope} has-tooltip" data-tooltip="scope-${r.scope}">${scopeMeta.label}</span>
        </div>
      </div>
      <div class="fix-body">
        <p>${esc(r.why_it_matters)}</p>
        ${r.where ? `<p class="fix-where">Where: ${esc(r.where)}</p>` : ""}
      </div>
      ${r.copy_block ? `
        <div class="copy-block">
          <button class="copy-btn" onclick="copyText(this)">Copy</button>
          ${esc(r.copy_block)}
        </div>
      ` : ""}
    </div>
  `;
}

/* ── Evidence View ───────────────────────────────────────────────────────── */
function renderEvidence(score) {
  const dims = [
    { key: "trust", label: "Trust", data: score.trust },
    { key: "experience", label: "Experience", data: score.experience },
    { key: "expertise", label: "Expertise", data: score.expertise },
    { key: "authoritativeness", label: "Authoritativeness", data: score.authoritativeness },
  ];

  const container = document.getElementById("tab-evidence");
  container.innerHTML = dims.map((d) => `
    <div class="evidence-section" id="evidence-${d.key}">
      <h4>
        <span style="color:${scoreColor(d.data.score * 4)};font-size:1.1rem;font-weight:800;">${d.data.score}</span>
        <span>/25</span>
        ${d.label}
      </h4>
      ${d.data.signals.map((s) => `
        <div class="signal-row">
          <div class="signal-icon ${s.found ? "found" : "missing"}">${s.found ? "&#10003;" : "&#10007;"}</div>
          <div class="signal-info">
            <div class="signal-name">${esc(s.signal)}</div>
            <div class="signal-explain">${esc(s.explanation)}</div>
            ${s.quote ? `<div class="signal-quote">${esc(s.quote)}</div>` : ""}
          </div>
          <div class="signal-pts" style="color:${s.found ? "var(--green)" : "var(--text-dim)"}">${s.found ? "+" + s.points.toFixed(1) : "0"}</div>
        </div>
      `).join("")}
    </div>
  `).join("");
}

/* ── Claims Audit ────────────────────────────────────────────────────────── */
function renderClaims(audit) {
  const container = document.getElementById("tab-claims");
  if (!audit || !audit.total_claims) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:2rem;">No verifiable claims detected.</p>';
    return;
  }

  const gradeColors = {
    supported: "var(--green)",
    weakly_supported: "var(--yellow)",
    unsupported: "var(--red)",
    needs_qualification: "var(--orange)",
  };
  const gradeLabels = {
    supported: "Supported",
    weakly_supported: "Weak",
    unsupported: "Unsupported",
    needs_qualification: "Needs Qualification",
  };

  let html = `
    <div class="claims-summary">
      <div class="claim-stat"><div class="num">${audit.total_claims}</div><div class="label">Total Claims</div></div>
      <div class="claim-stat"><div class="num" style="color:var(--green)">${audit.supported}</div><div class="label">Supported</div></div>
      <div class="claim-stat"><div class="num" style="color:var(--yellow)">${audit.weakly_supported}</div><div class="label">Weak Sources</div></div>
      <div class="claim-stat"><div class="num" style="color:var(--red)">${audit.unsupported}</div><div class="label">Unsupported</div></div>
      <div class="claim-stat"><div class="num" style="color:var(--orange)">${audit.needs_qualification}</div><div class="label">Overbroad</div></div>
    </div>
  `;

  audit.claims.forEach((c) => {
    const color = gradeColors[c.evidence_grade] || "var(--text-dim)";
    const label = gradeLabels[c.evidence_grade] || c.evidence_grade;
    html += `
      <div class="claim-card">
        <div class="claim-text">"${esc(c.text)}"</div>
        <div class="claim-meta">
          <span class="badge" style="background:${color}22;color:${color};">${label}</span>
          <span class="badge" style="background:var(--bg);color:var(--text-dim);">${c.claim_type.replace(/_/g, " ")}</span>
          ${c.nearest_citation ? `<span style="color:var(--text-dim);font-size:0.75rem;">Source: ${esc(c.nearest_citation.substring(0, 60))}</span>` : ""}
        </div>
        ${c.explanation ? `<p style="font-size:0.8rem;color:var(--text-muted);margin-top:0.4rem;">${esc(c.explanation)}</p>` : ""}
      </div>
    `;
  });

  container.innerHTML = html;
}

/* ── Compliance ──────────────────────────────────────────────────────────── */
function renderCompliance(flags) {
  const container = document.getElementById("tab-compliance");
  if (!flags || !flags.length) {
    container.innerHTML = '<p style="color:var(--green);padding:2rem;">No compliance issues detected.</p>';
    return;
  }

  container.innerHTML = flags.map((f) => `
    <div class="compliance-flag ${f.severity}">
      <h5>${esc(f.rule)} <span style="color:var(--text-dim);font-weight:400;">&mdash; ${f.severity}</span></h5>
      <div class="flag-text">${esc(f.text)}</div>
      <div class="flag-explain">${esc(f.explanation)}</div>
      <div class="flag-fix">Fix: ${esc(f.fix)}</div>
    </div>
  `).join("");
}

/* ── Tooltip system ──────────────────────────────────────────────────────── */
function initTooltips() {
  document.querySelectorAll(".has-tooltip").forEach((el) => {
    if (el._tooltipBound) return;
    el._tooltipBound = true;

    el.addEventListener("mouseenter", showTooltip);
    el.addEventListener("mouseleave", hideTooltip);
    el.addEventListener("focus", showTooltip);
    el.addEventListener("blur", hideTooltip);
  });
}

function showTooltip(e) {
  const el = e.currentTarget;
  const key = el.dataset.tooltip;
  if (!key) return;

  const defEl = document.querySelector(`[data-tooltip-id="${key}"]`);
  if (!defEl) return;

  let tip = document.getElementById("tooltip-popup");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "tooltip-popup";
    tip.className = "tooltip-popup";
    document.body.appendChild(tip);
  }

  tip.textContent = defEl.textContent;
  tip.style.display = "block";

  const rect = el.getBoundingClientRect();
  const tipRect = tip.getBoundingClientRect();
  let left = rect.left + rect.width / 2 - tipRect.width / 2;
  let top = rect.bottom + 8;

  if (left < 8) left = 8;
  if (left + tipRect.width > window.innerWidth - 8) left = window.innerWidth - tipRect.width - 8;
  if (top + tipRect.height > window.innerHeight - 8) top = rect.top - tipRect.height - 8;

  tip.style.left = left + "px";
  tip.style.top = top + "px";
  tip.classList.add("visible");
}

function hideTooltip() {
  const tip = document.getElementById("tooltip-popup");
  if (tip) {
    tip.classList.remove("visible");
    tip.style.display = "none";
  }
}

/* ── Download menu toggle ────────────────────────────────────────────────── */
function toggleDownloadMenu() {
  const menu = document.getElementById("downloadMenu");
  menu.classList.toggle("open");
}

document.addEventListener("click", (e) => {
  const menu = document.getElementById("downloadMenu");
  const trigger = document.querySelector(".download-trigger");
  if (menu && trigger && !trigger.contains(e.target) && !menu.contains(e.target)) {
    menu.classList.remove("open");
  }
});

/* ── Spreadsheet helpers (HTML table → .xls for color coding) ────────────── */
function generateColoredXLS(title, headers, rows, colorFn) {
  let html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:spreadsheet" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8">
<style>
  td, th { font-family: Calibri, sans-serif; font-size: 11pt; padding: 4px 8px; border: 1px solid #ccc; }
  th { background: #1a1d27; color: #fff; font-weight: bold; text-align: left; }
</style></head><body>
<h2>${esc(title)}</h2>`;

  if (currentData && currentData.extracted && currentData.extracted.url) {
    html += `<p>URL: ${esc(currentData.extracted.url)}</p>`;
  }

  html += `<table><thead><tr>`;
  headers.forEach((h) => { html += `<th>${esc(h)}</th>`; });
  html += `</tr></thead><tbody>`;

  rows.forEach((row, i) => {
    const bgColor = colorFn ? colorFn(row, i) : "";
    html += `<tr>`;
    row.forEach((cell, ci) => {
      const style = bgColor ? ` style="background:${bgColor}"` : "";
      html += `<td${style}>${esc(String(cell))}</td>`;
    });
    html += `</tr>`;
  });

  html += `</tbody></table></body></html>`;
  return html;
}

function downloadXLS(html, filename) {
  const blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
  downloadBlob(blob, filename);
}

/* ── Download: Priority Fixes Checklist ──────────────────────────────────── */
function downloadPriorityChecklist() {
  if (!currentData) return;
  closeDownloadMenu();

  const headers = ["#", "Done", "Title", "Scope", "Impact", "Effort", "Dimension", "Why It Matters", "Where", "Suggested Copy"];
  const rows = currentData.recommendations.map((r, i) => {
    const scopeLabel = SCOPE_META[r.scope] ? SCOPE_META[r.scope].label : "Page Level";
    return [i + 1, "☐", r.title, scopeLabel, r.impact, r.effort, r.dimension, r.why_it_matters, r.where || "", r.copy_block || ""];
  });

  const impactColors = { high: "#fde8e8", medium: "#fef9e7", low: "#e8f8e8" };
  const html = generateColoredXLS(
    "E-E-A-T Priority Fixes Checklist — Score: " + currentData.score.overall + "/100",
    headers,
    rows,
    (row) => impactColors[row[4]] || ""
  );
  downloadXLS(html, "eeat-priority-fixes.xls");
}

/* ── Download: Evidence View ─────────────────────────────────────────────── */
function downloadEvidenceSpreadsheet() {
  if (!currentData) return;
  closeDownloadMenu();

  const headers = ["Dimension", "Signal", "Found", "Points", "Explanation", "Quote"];
  const rows = [];
  const dims = [
    { label: "Trust", data: currentData.score.trust },
    { label: "Experience", data: currentData.score.experience },
    { label: "Expertise", data: currentData.score.expertise },
    { label: "Authoritativeness", data: currentData.score.authoritativeness },
  ];

  dims.forEach((d) => {
    d.data.signals.forEach((s) => {
      rows.push([d.label, s.signal, s.found ? "✓ Yes" : "✗ No", s.points.toFixed(1), s.explanation, s.quote || ""]);
    });
  });

  const html = generateColoredXLS(
    "E-E-A-T Evidence View — Score: " + currentData.score.overall + "/100",
    headers,
    rows,
    (row) => row[2].startsWith("✓") ? "#d4edda" : "#f8d7da"
  );
  downloadXLS(html, "eeat-evidence-view.xls");
}

/* ── Download: Claims Audit ──────────────────────────────────────────────── */
function downloadClaimsSpreadsheet() {
  if (!currentData) return;
  closeDownloadMenu();

  const audit = currentData.citation_audit;
  if (!audit || !audit.claims || !audit.claims.length) {
    alert("No claims data to export.");
    return;
  }

  const headers = ["#", "Claim Text", "Type", "Evidence Grade", "Source", "Explanation"];
  const rows = audit.claims.map((c, i) => [
    i + 1, c.text, c.claim_type.replace(/_/g, " "), c.evidence_grade.replace(/_/g, " "),
    c.nearest_citation || "None", c.explanation || ""
  ]);

  const gradeColors = {
    supported: "#d4edda", "weakly supported": "#fff3cd",
    unsupported: "#f8d7da", "needs qualification": "#fde8d0"
  };
  const html = generateColoredXLS(
    "E-E-A-T Claims Audit — " + audit.total_claims + " claims analyzed",
    headers,
    rows,
    (row) => gradeColors[row[3]] || ""
  );
  downloadXLS(html, "eeat-claims-audit.xls");
}

/* ── Download: Compliance ────────────────────────────────────────────────── */
function downloadComplianceSpreadsheet() {
  if (!currentData) return;
  closeDownloadMenu();

  const flags = currentData.score.compliance_flags;
  if (!flags || !flags.length) {
    alert("No compliance issues to export.");
    return;
  }

  const headers = ["Rule", "Severity", "Flagged Text", "Explanation", "Suggested Fix"];
  const rows = flags.map((f) => [f.rule, f.severity, f.text, f.explanation, f.fix]);

  const sevColors = { high: "#f8d7da", warning: "#fff3cd", medium: "#fff3cd", low: "#d4edda" };
  const html = generateColoredXLS(
    "E-E-A-T Compliance Report",
    headers,
    rows,
    (row) => sevColors[row[1]] || ""
  );
  downloadXLS(html, "eeat-compliance.xls");
}

/* ── Download: Full PDF Report ───────────────────────────────────────────── */
function downloadFullPDF() {
  if (!currentData) return;
  closeDownloadMenu();

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 14;
  let y = 20;

  function checkPage(needed) {
    if (y + needed > doc.internal.pageSize.getHeight() - 15) {
      doc.addPage();
      y = 20;
    }
  }

  function sectionTitle(text) {
    checkPage(14);
    doc.setFontSize(14);
    doc.setFont(undefined, "bold");
    doc.setTextColor(99, 102, 241);
    doc.text(text, margin, y);
    y += 8;
    doc.setTextColor(30, 30, 30);
  }

  // Title
  doc.setFontSize(20);
  doc.setFont(undefined, "bold");
  doc.setTextColor(99, 102, 241);
  doc.text("E-E-A-T Content Grader Report", margin, y);
  y += 10;

  // URL
  doc.setFontSize(9);
  doc.setFont(undefined, "normal");
  doc.setTextColor(100, 100, 100);
  const url = currentData.extracted && currentData.extracted.url;
  if (url) {
    doc.text("URL: " + url, margin, y);
    y += 5;
  }
  doc.text("Generated: " + new Date().toLocaleDateString(), margin, y);
  y += 10;

  // Overall Score
  doc.setFontSize(28);
  doc.setFont(undefined, "bold");
  const overall = Math.round(currentData.score.overall);
  doc.setTextColor(...pdfScoreRGB(overall));
  doc.text(overall + "/100", margin, y);
  doc.setFontSize(10);
  doc.setTextColor(100, 100, 100);
  doc.text("Overall E-E-A-T Score", margin + 36, y - 1);
  y += 5;
  doc.setFontSize(9);
  doc.text("YMYL Risk: " + currentData.score.ymyl_risk + "  |  Preset: " + currentData.score.preset_used.replace(/_/g, " "), margin, y);
  y += 10;

  // Summary
  if (currentData.summary) {
    doc.setFontSize(9);
    doc.setFont(undefined, "normal");
    doc.setTextColor(60, 60, 60);
    const summaryLines = doc.splitTextToSize(currentData.summary, pageWidth - margin * 2);
    checkPage(summaryLines.length * 4 + 4);
    doc.text(summaryLines, margin, y);
    y += summaryLines.length * 4 + 6;
  }

  // Sub-scores table
  sectionTitle("Dimension Scores");
  doc.autoTable({
    startY: y,
    margin: { left: margin, right: margin },
    head: [["Dimension", "Score", "Max", "Signals Found"]],
    body: [
      ["Experience", currentData.score.experience.score, 25, currentData.score.experience.signals.filter((s) => s.found).length + "/" + currentData.score.experience.signals.length],
      ["Expertise", currentData.score.expertise.score, 25, currentData.score.expertise.signals.filter((s) => s.found).length + "/" + currentData.score.expertise.signals.length],
      ["Authoritativeness", currentData.score.authoritativeness.score, 25, currentData.score.authoritativeness.signals.filter((s) => s.found).length + "/" + currentData.score.authoritativeness.signals.length],
      ["Trust", currentData.score.trust.score, 25, currentData.score.trust.signals.filter((s) => s.found).length + "/" + currentData.score.trust.signals.length],
    ],
    styles: { fontSize: 8, cellPadding: 2 },
    headStyles: { fillColor: [99, 102, 241], textColor: 255 },
  });
  y = doc.lastAutoTable.finalY + 10;

  // Priority Fixes
  if (currentData.recommendations.length) {
    sectionTitle("Priority Fixes (" + currentData.recommendations.length + ")");
    const fixRows = currentData.recommendations.map((r, i) => {
      const scopeLabel = SCOPE_META[r.scope] ? SCOPE_META[r.scope].label : "Page Level";
      return [i + 1, r.title, scopeLabel, r.impact, r.effort, r.dimension, r.why_it_matters.substring(0, 80)];
    });
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      head: [["#", "Fix", "Scope", "Impact", "Effort", "Dimension", "Why"]],
      body: fixRows,
      styles: { fontSize: 7, cellPadding: 1.5 },
      headStyles: { fillColor: [99, 102, 241], textColor: 255 },
      columnStyles: {
        0: { cellWidth: 8 },
        1: { cellWidth: 35 },
        2: { cellWidth: 20 },
        3: { cellWidth: 15 },
        4: { cellWidth: 18 },
        5: { cellWidth: 22 },
        6: { cellWidth: "auto" },
      },
      didParseCell: function(data) {
        if (data.section === "body" && data.column.index === 3) {
          const val = data.cell.raw;
          if (val === "high") data.cell.styles.textColor = [220, 38, 38];
          else if (val === "medium") data.cell.styles.textColor = [180, 130, 0];
          else data.cell.styles.textColor = [22, 163, 74];
        }
      }
    });
    y = doc.lastAutoTable.finalY + 10;
  }

  // Evidence
  sectionTitle("Evidence View");
  const evidenceRows = [];
  ["trust", "experience", "expertise", "authoritativeness"].forEach((dim) => {
    currentData.score[dim].signals.forEach((s) => {
      evidenceRows.push([dim.charAt(0).toUpperCase() + dim.slice(1), s.signal, s.found ? "✓" : "✗", s.points.toFixed(1), (s.explanation || "").substring(0, 60)]);
    });
  });
  doc.autoTable({
    startY: y,
    margin: { left: margin, right: margin },
    head: [["Dimension", "Signal", "Found", "Pts", "Explanation"]],
    body: evidenceRows,
    styles: { fontSize: 7, cellPadding: 1.5 },
    headStyles: { fillColor: [99, 102, 241], textColor: 255 },
    didParseCell: function(data) {
      if (data.section === "body" && data.column.index === 2) {
        data.cell.styles.textColor = data.cell.raw === "✓" ? [22, 163, 74] : [220, 38, 38];
      }
    }
  });
  y = doc.lastAutoTable.finalY + 10;

  // Claims
  const audit = currentData.citation_audit;
  if (audit && audit.total_claims > 0) {
    sectionTitle("Claims Audit (" + audit.total_claims + " claims)");
    const claimRows = audit.claims.map((c, i) => [
      i + 1, c.text.substring(0, 60), c.claim_type.replace(/_/g, " "),
      c.evidence_grade.replace(/_/g, " "), c.nearest_citation ? c.nearest_citation.substring(0, 40) : "None"
    ]);
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      head: [["#", "Claim", "Type", "Grade", "Source"]],
      body: claimRows,
      styles: { fontSize: 7, cellPadding: 1.5 },
      headStyles: { fillColor: [99, 102, 241], textColor: 255 },
      didParseCell: function(data) {
        if (data.section === "body" && data.column.index === 3) {
          const grade = data.cell.raw;
          if (grade === "supported") data.cell.styles.textColor = [22, 163, 74];
          else if (grade === "unsupported") data.cell.styles.textColor = [220, 38, 38];
          else if (grade.includes("weak")) data.cell.styles.textColor = [180, 130, 0];
          else data.cell.styles.textColor = [234, 120, 0];
        }
      }
    });
    y = doc.lastAutoTable.finalY + 10;
  }

  // Compliance
  if (currentData.score.compliance_flags.length) {
    sectionTitle("Compliance Flags (" + currentData.score.compliance_flags.length + ")");
    const compRows = currentData.score.compliance_flags.map((f) => [
      f.rule, f.severity, f.text.substring(0, 50), f.explanation.substring(0, 50), f.fix.substring(0, 50)
    ]);
    doc.autoTable({
      startY: y,
      margin: { left: margin, right: margin },
      head: [["Rule", "Severity", "Text", "Explanation", "Fix"]],
      body: compRows,
      styles: { fontSize: 7, cellPadding: 1.5 },
      headStyles: { fillColor: [99, 102, 241], textColor: 255 },
    });
  }

  doc.save("eeat-full-report.pdf");
}

function pdfScoreRGB(score) {
  if (score >= 75) return [22, 163, 74];
  if (score >= 50) return [180, 130, 0];
  if (score >= 25) return [234, 120, 0];
  return [220, 38, 38];
}

/* ── Legacy export (JSON) ────────────────────────────────────────────────── */
function exportJSON() {
  if (!currentData) return;
  closeDownloadMenu();
  const blob = new Blob([JSON.stringify(currentData, null, 2)], { type: "application/json" });
  downloadBlob(blob, "eeat-report.json");
}

function closeDownloadMenu() {
  const menu = document.getElementById("downloadMenu");
  if (menu) menu.classList.remove("open");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/* ── Utility ─────────────────────────────────────────────────────────────── */
function resetUI() {
  document.getElementById("inputPanel").style.display = "";
  document.getElementById("results").style.display = "none";
  document.getElementById("headerActions").style.display = "none";
  document.getElementById("analyzedUrlBanner").style.display = "none";
  activePriorityFilter = "all";
  document.querySelectorAll("#priorityFilters .filter-pill").forEach((b) => b.classList.remove("active"));
  document.querySelector('#priorityFilters .filter-pill[data-priority="all"]').classList.add("active");
  currentData = null;
}

function copyText(btn) {
  const block = btn.parentElement;
  const text = block.textContent.replace("Copy", "").trim();
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "Copied!";
    setTimeout(() => (btn.textContent = "Copy"), 1500);
  });
}

function scoreColor(score) {
  if (score >= 75) return "var(--green)";
  if (score >= 50) return "var(--yellow)";
  if (score >= 25) return "var(--orange)";
  return "var(--red)";
}

function animateNumber(el, from, to, duration) {
  const start = performance.now();
  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

function esc(str) {
  if (!str) return "";
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

document.getElementById("urlInput").addEventListener("keypress", (e) => {
  if (e.key === "Enter") runAnalysis();
});
