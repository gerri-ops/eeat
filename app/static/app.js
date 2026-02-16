/* ── E-E-A-T Content Grader — Frontend Application ────────────────────────── */

let currentData = null;
let activeInputType = "url";

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
      const err = await resp.json();
      throw new Error(err.detail || "Analysis failed");
    }
    currentData = await resp.json();
    renderResults(currentData);
  } catch (e) {
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
  document.getElementById("results").style.display = "";
  document.getElementById("headerActions").style.display = "";

  renderSummary(data);
  renderScoreDashboard(data.score);
  renderFixes(data.recommendations);
  renderEvidence(data.score);
  renderClaims(data.citation_audit);
  renderCompliance(data.score.compliance_flags);
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

  // Badges
  const badges = document.getElementById("badgesArea");
  const riskClass = { high: "badge-risk-high", medium: "badge-risk-medium", low: "badge-risk-low" };
  badges.innerHTML = `
    <span class="badge ${riskClass[score.ymyl_risk] || 'badge-risk-low'}">${score.ymyl_risk} risk</span>
    <span class="badge" style="background:rgba(99,102,241,0.15);color:var(--accent);">${score.preset_used.replace(/_/g, " ")}</span>
  `;

  // Sub-scores
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

/* ── Priority Fixes ──────────────────────────────────────────────────────── */
function renderFixes(recs) {
  const container = document.getElementById("tab-fixes");
  if (!recs.length) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:2rem;">No recommendations generated.</p>';
    return;
  }
  container.innerHTML = recs.map((r, i) => `
    <div class="fix-card">
      <div class="fix-header">
        <h4><span style="color:var(--text-dim);margin-right:0.5rem;">#${i + 1}</span>${esc(r.title)}</h4>
        <div class="fix-meta">
          <span class="badge badge-impact-${r.impact}">${r.impact} impact</span>
          <span class="badge badge-effort-${r.effort}">${r.effort}</span>
          ${r.dimension ? `<span class="badge" style="background:rgba(99,102,241,0.12);color:var(--accent);">${r.dimension}</span>` : ""}
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
  `).join("");
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

/* ── Export functions ─────────────────────────────────────────────────────── */
function exportJSON() {
  if (!currentData) return;
  const blob = new Blob([JSON.stringify(currentData, null, 2)], { type: "application/json" });
  downloadBlob(blob, "eeat-report.json");
}

function exportChecklist() {
  if (!currentData) return;
  let md = `# E-E-A-T Content Grader — Fix Checklist\n\n`;
  md += `**Overall Score:** ${currentData.score.overall}/100\n`;
  md += `**YMYL Risk:** ${currentData.score.ymyl_risk}\n`;
  md += `**Preset:** ${currentData.score.preset_used}\n\n`;
  md += `---\n\n## Priority Fixes\n\n`;
  currentData.recommendations.forEach((r, i) => {
    md += `### ${i + 1}. ${r.title}\n`;
    md += `- **Impact:** ${r.impact} | **Effort:** ${r.effort} | **Dimension:** ${r.dimension}\n`;
    md += `- **Why:** ${r.why_it_matters}\n`;
    if (r.where) md += `- **Where:** ${r.where}\n`;
    if (r.copy_block) md += `\n\`\`\`\n${r.copy_block}\n\`\`\`\n`;
    md += `\n`;
  });

  if (currentData.score.compliance_flags.length) {
    md += `---\n\n## Compliance Flags\n\n`;
    currentData.score.compliance_flags.forEach((f) => {
      md += `- **${f.rule}** (${f.severity}): ${f.explanation}\n  - Fix: ${f.fix}\n`;
    });
  }

  const blob = new Blob([md], { type: "text/markdown" });
  downloadBlob(blob, "eeat-checklist.md");
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

// Allow Enter key to trigger analysis from URL input
document.getElementById("urlInput").addEventListener("keypress", (e) => {
  if (e.key === "Enter") runAnalysis();
});
