let currentThreadId = localStorage.getItem("realestate_thread_id") || null;
let latestAnswerMarkdown = "";
let waitingForApproval = false;

const AGENT_LABELS = {
  property_search_agent: "🏡 Property Search Agent",
  valuation_agent: "📊 Valuation Agent",
  neighborhood_agent: "📍 Neighborhood Agent",
  action_dispatch_agent: "⚡ Action Dispatch Agent",
  property_plan_agent: "📋 Property Plan Agent"
};

/* =====================================================
   THEME TOGGLE
   ===================================================== */

function getPreferredTheme() {
  const stored = localStorage.getItem("estateguard_theme");
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("estateguard_theme", theme);

  const sunIcon = document.getElementById("themeSunIcon");
  const moonIcon = document.getElementById("themeMoonIcon");
  const label = document.getElementById("themeLabel");

  if (theme === "dark") {
    sunIcon.style.display = "block";
    moonIcon.style.display = "none";
    if (label) label.textContent = "Switch to Light";
  } else {
    sunIcon.style.display = "none";
    moonIcon.style.display = "block";
    if (label) label.textContent = "Switch to Dark";
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  applyTheme(next);

  // Animate the theme icon
  const icon = document.getElementById("themeIcon");
  if (icon) {
    icon.style.transition = "transform .5s cubic-bezier(.34, 1.56, .64, 1)";
    icon.style.transform = "rotate(360deg) scale(1.15)";
    setTimeout(() => { icon.style.transform = "rotate(0deg) scale(1)"; }, 500);
  }

  showToast(next === "dark" ? "🌙 Dark mode activated" : "☀️ Light mode activated", "info");
}

// Apply saved theme on load
document.addEventListener("DOMContentLoaded", function () {
  applyTheme(getPreferredTheme());
  initCharCounter();
  initTextareaAutoResize();
  initNavRipples();
  animateStatCounters();
});

/* =====================================================
   TOAST NOTIFICATIONS
   ===================================================== */

function showToast(message, type = "info", duration = 2800) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-dot"></span>${message}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-out");
    toast.addEventListener("animationend", () => toast.remove());
  }, duration);
}

/* =====================================================
   CHARACTER COUNTER
   ===================================================== */

function initCharCounter() {
  const textarea = document.getElementById("userInput");
  const counter = document.getElementById("charCounter");
  if (!textarea || !counter) return;

  function updateCounter() {
    const len = textarea.value.length;
    counter.textContent = `${len} character${len !== 1 ? "s" : ""}`;
    counter.classList.remove("warn", "over");
    if (len > 1500) counter.classList.add("over");
    else if (len > 1000) counter.classList.add("warn");
  }

  textarea.addEventListener("input", updateCounter);
  updateCounter();
}

/* =====================================================
   TEXTAREA AUTO-RESIZE
   ===================================================== */

function initTextareaAutoResize() {
  const textarea = document.getElementById("userInput");
  if (!textarea) return;

  textarea.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 320) + "px";
  });
}

/* =====================================================
   NAV RIPPLE EFFECT
   ===================================================== */

function initNavRipples() {
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("mouseenter", function (e) {
      const rect = this.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      this.style.setProperty("--ripple-x", x + "%");
      this.style.setProperty("--ripple-y", y + "%");
    });
  });
}

/* =====================================================
   STAT COUNTER ANIMATION
   ===================================================== */

function animateStatCounters() {
  const statValues = document.querySelectorAll(".stat-value");
  statValues.forEach((el, i) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(8px)";
    setTimeout(() => {
      el.style.transition = "opacity .4s ease, transform .4s ease";
      el.style.opacity = "1";
      el.style.transform = "translateY(0)";
    }, 100 + i * 80);
  });
}

/* =====================================================
   CORE FUNCTIONS
   ===================================================== */

function setPrompt(text) {
  const textarea = document.getElementById("userInput");
  textarea.value = text;
  textarea.dispatchEvent(new Event("input")); // trigger counter + resize
  textarea.focus();
  showToast("✨ Scenario loaded", "success", 1800);
}

function setLoading(isLoading, mode = "draft") {
  const sendBtn = document.getElementById("sendBtn");
  const simBtn = document.getElementById("simBtn");
  const btnText = document.getElementById("btnText");
  const btnLoader = document.getElementById("btnLoader");
  const approveBtn = document.getElementById("approveBtn");
  const reviseBtn = document.getElementById("reviseBtn");

  sendBtn.disabled = isLoading;
  simBtn.disabled = isLoading;
  approveBtn.disabled = isLoading;
  reviseBtn.disabled = isLoading;

  if (isLoading && mode === "draft") {
    btnText.classList.add("hidden");
    btnLoader.classList.remove("hidden");
  } else {
    btnText.classList.remove("hidden");
    btnLoader.classList.add("hidden");
  }
}

function showError(message) {
  const errorBox = document.getElementById("errorBox");
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function hideError() {
  const errorBox = document.getElementById("errorBox");
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function renderMarkdown(element, markdown) {
  if (typeof marked !== "undefined") {
    element.innerHTML = marked.parse(markdown || "");
  } else {
    element.innerText = markdown || "";
  }
}

function revealSection(section) {
  section.classList.remove("hidden");
  section.classList.remove("section-reveal");
  // Force reflow to restart animation
  void section.offsetWidth;
  section.classList.add("section-reveal");
}

function showWorkflow(data) {
  const section = document.getElementById("workflowSection");
  const reasoning = document.getElementById("supervisorReasoning");
  const chips = document.getElementById("agentChips");
  const guardrailBadge = document.getElementById("guardrailBadge");

  reasoning.textContent = data.supervisor_reasoning || "Supervisor routing completed.";
  chips.innerHTML = "";

  (data.selected_agents || []).forEach((agent, idx) => {
    const chip = document.createElement("span");
    chip.className = "agent-chip";
    chip.style.animationDelay = `${idx * 0.08}s`;
    chip.textContent = AGENT_LABELS[agent] || agent;
    chips.appendChild(chip);
  });

  if (data.guardrail_allowed === false) {
    guardrailBadge.textContent = "Input Guardrail Blocked";
    guardrailBadge.classList.add("blocked");
  } else {
    guardrailBadge.textContent = "Input Guardrail Passed";
    guardrailBadge.classList.remove("blocked");
  }

  revealSection(section);
}

function renderActionEvaluations(evaluations, auditLogs) {
  const section = document.getElementById("actionGuardrailSection");
  const container = document.getElementById("actionEvaluationsContainer");
  container.innerHTML = "";

  const logsToDisplay = (evaluations && evaluations.length > 0)
    ? evaluations.map(e => e.audit_entry || e)
    : (auditLogs || []).slice(0, 5);

  if (logsToDisplay.length === 0) {
    section.classList.add("hidden");
    return;
  }

  logsToDisplay.forEach((log, idx) => {
    const card = document.createElement("div");
    card.className = `action-eval-card outcome-${(log.outcome || "allow").toLowerCase()}`;
    card.style.opacity = "0";
    card.style.transform = "translateY(12px)";

    const outcomeBadge = (log.outcome || "").toUpperCase();

    card.innerHTML = `
      <div class="card-top">
        <span class="outcome-badge badge-${(log.outcome || "allow").toLowerCase()}">${outcomeBadge}</span>
        <span class="action-name">Tool: <code>${log.action}</code></span>
        <span class="rule-id">Rule: ${log.rule_id || "default"}</span>
      </div>
      <div class="card-details">
        <p><strong>Parameters:</strong> <code>${JSON.stringify(log.params || {})}</code></p>
        <p><strong>Reason:</strong> ${log.reason || ""}</p>
        <p class="meta-info">
          <span>Timestamp: ${log.timestamp || "Just now"}</span>
          <span>Dry Run: ${log.dry_run ? "YES" : "NO"}</span>
          <span>Executed: ${log.executed ? "YES" : "NO"}</span>
        </p>
      </div>
    `;

    container.appendChild(card);

    // Staggered entrance animation
    setTimeout(() => {
      card.style.transition = "opacity .35s ease, transform .35s ease";
      card.style.opacity = "1";
      card.style.transform = "translateY(0)";
    }, 60 + idx * 80);
  });

  revealSection(section);
}

function showResult(answer, threadId, isDraft = false) {
  latestAnswerMarkdown = answer || "";

  const resultSection = document.getElementById("resultSection");
  const resultBox = document.getElementById("resultBox");
  const threadInfo = document.getElementById("threadInfo");
  const resultTitle = document.getElementById("resultTitle");

  renderMarkdown(resultBox, latestAnswerMarkdown);
  threadInfo.textContent = `Thread ID: ${threadId}`;
  resultTitle.textContent = isDraft ? "Draft Real Estate Proposal" : "Final Real Estate Advisory Report";
  revealSection(resultSection);

  resultSection.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

function showApproval(data) {
  waitingForApproval = true;
  const section = document.getElementById("approvalSection");
  const approvalRequest = document.getElementById("approvalRequest");
  approvalRequest.textContent = data.approval_request ||
    "Approve the draft or action before proceeding to final plan generation.";
  revealSection(section);
}

function hideApproval() {
  waitingForApproval = false;
  document.getElementById("approvalSection").classList.add("hidden");
  document.getElementById("approvalFeedback").value = "";
}

async function sendMessage() {
  hideError();

  if (waitingForApproval) {
    showError("Please approve or revise the current proposal draft before starting another.");
    return;
  }

  const input = document.getElementById("userInput");
  const message = input.value.trim();
  const dryRun = document.getElementById("dryRunToggle").checked;

  if (!message) {
    showError("Please enter your real estate request first.");
    return;
  }

  setLoading(true, "draft");
  showToast("🔄 Processing your request...", "info", 4000);

  try {
    const response = await fetch("/api/realestate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: message,
        thread_id: currentThreadId,
        dry_run: dryRun
      })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Something went wrong.");
    }

    currentThreadId = data.thread_id;
    localStorage.setItem("realestate_thread_id", currentThreadId);

    showWorkflow(data);
    renderActionEvaluations(data.action_evaluations, data.audit_logs);

    if (data.requires_approval) {
      showResult(data.proposal || data.answer, data.thread_id, true);
      showApproval(data);
      showToast("👤 Human approval required", "info");
    } else {
      hideApproval();
      showResult(data.answer, data.thread_id, false);
      showToast("✅ Report generated successfully!", "success");
    }
  } catch (error) {
    showError(error.message);
    showToast("❌ Request failed", "info", 3000);
  } finally {
    setLoading(false, "draft");
  }
}

async function submitApproval(approved) {
  hideError();

  if (!currentThreadId || !waitingForApproval) {
    showError("There is no proposal or action waiting for approval.");
    return;
  }

  const feedbackInput = document.getElementById("approvalFeedback");
  const feedback = feedbackInput.value.trim();

  if (!approved && !feedback) {
    showError("Please enter revision feedback before requesting changes.");
    feedbackInput.focus();
    return;
  }

  setLoading(true, "approval");
  showToast(approved ? "✅ Approving..." : "✏️ Sending revisions...", "info", 3000);

  try {
    const response = await fetch("/api/realestate/approve", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        thread_id: currentThreadId,
        approved: approved,
        feedback: feedback
      })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Could not resume the workflow.");
    }

    showWorkflow(data);
    renderActionEvaluations(data.action_evaluations, data.audit_logs);
    hideApproval();
    showResult(data.answer, data.thread_id, false);
    showToast("✅ Final report ready!", "success");
  } catch (error) {
    showError(error.message);
    showToast("❌ Approval failed", "info", 3000);
  } finally {
    setLoading(false, "approval");
  }
}

async function runSimulation() {
  hideError();
  const dryRun = document.getElementById("dryRunToggle").checked;
  const simSection = document.getElementById("simulationSection");
  const simCards = document.getElementById("simulationCards");
  const simSummaryBadge = document.getElementById("simulationSummaryBadge");

  setLoading(true, "draft");
  showToast("🧪 Running simulation harness...", "info", 4000);

  try {
    const response = await fetch("/api/simulate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ dry_run: dryRun })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Simulation failed.");
    }

    const sim = data.simulation;
    simSummaryBadge.textContent = `${sim.passed}/${sim.total} Scenarios Passed (${sim.dry_run ? "Dry Run" : "Standard"})`;

    simCards.innerHTML = "";
    sim.scenarios.forEach((sc, idx) => {
      const card = document.createElement("div");
      card.className = `sim-card ${sc.passed ? "sim-pass" : "sim-fail"}`;
      card.style.opacity = "0";
      card.style.transform = "translateY(16px)";

      card.innerHTML = `
        <div class="sim-card-header">
          <span class="sim-status-badge ${sc.passed ? "pass" : "fail"}">${sc.passed ? "PASS" : "FAIL"}</span>
          <h4>${sc.scenario_name}</h4>
        </div>
        <p><strong>Action:</strong> <code>${sc.action}</code> | <strong>Rule:</strong> <code>${sc.rule_id}</code></p>
        <p><strong>Expected:</strong> <code>${sc.expected_outcome}</code> | <strong>Actual:</strong> <code>${sc.actual_outcome}</code></p>
        <p class="sim-reason">${sc.reason}</p>
      `;
      simCards.appendChild(card);

      // Staggered entrance
      setTimeout(() => {
        card.style.transition = "opacity .4s ease, transform .4s ease";
        card.style.opacity = "1";
        card.style.transform = "translateY(0)";
      }, 80 + idx * 100);
    });

    revealSection(simSection);
    simSection.scrollIntoView({ behavior: "smooth", block: "start" });

    renderActionEvaluations(null, sim.audit_logs);
    showToast(`🧪 Simulation complete: ${sim.passed}/${sim.total} passed`, "success");
  } catch (error) {
    showError(error.message);
    showToast("❌ Simulation failed", "info", 3000);
  } finally {
    setLoading(false, "draft");
  }
}

async function loadAuditLogs() {
  const btn = document.getElementById("refreshAuditBtn");
  if (btn) btn.classList.add("spinning");

  try {
    const response = await fetch("/api/audit-logs");
    const data = await response.json();
    if (data.success) {
      renderActionEvaluations(null, data.logs);
      showToast("🔄 Audit trail refreshed", "success", 2000);
    }
  } catch (error) {
    console.error("Could not load audit logs", error);
    showToast("❌ Could not load audit logs", "info", 2500);
  } finally {
    setTimeout(() => {
      if (btn) btn.classList.remove("spinning");
    }, 600);
  }
}

function copyResult() {
  const resultBox = document.getElementById("resultBox");
  const text = resultBox.innerText;

  if (!text) return;

  navigator.clipboard.writeText(text)
    .then(() => {
      const copyBtn = document.getElementById("copyBtn");
      const originalHTML = copyBtn.innerHTML;
      copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied!`;
      showToast("📋 Copied to clipboard!", "success", 2000);
      setTimeout(() => { copyBtn.innerHTML = originalHTML; }, 1800);
    })
    .catch(() => {
      showError("Could not copy result.");
    });
}

function downloadPDF() {
  const pdfContent = document.getElementById("pdfContent");

  if (!latestAnswerMarkdown || !pdfContent) {
    showError("No real estate report available to download.");
    return;
  }

  const downloadBtn = document.querySelector(".download-btn");
  const oldHTML = downloadBtn.innerHTML;
  downloadBtn.innerHTML = `<span class="loader" style="width:14px;height:14px;border-width:2px;"></span> Preparing PDF...`;
  downloadBtn.disabled = true;

  showToast("📥 Generating PDF...", "info", 3000);

  const options = {
    margin: 0.5,
    filename: "real-estate-advisory-report.pdf",
    image: { type: "jpeg", quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
    jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
    pagebreak: { mode: ["avoid-all", "css", "legacy"] }
  };

  html2pdf()
    .set(options)
    .from(pdfContent)
    .save()
    .then(() => {
      downloadBtn.innerHTML = oldHTML;
      downloadBtn.disabled = false;
      showToast("✅ PDF downloaded!", "success");
    })
    .catch(() => {
      downloadBtn.innerHTML = oldHTML;
      downloadBtn.disabled = false;
      showError("Could not download PDF.");
    });
}

/* =====================================================
   KEYBOARD SHORTCUTS
   ===================================================== */

document.addEventListener("keydown", function(event) {
  // Ctrl+Enter to submit
  if (event.ctrlKey && event.key === "Enter") {
    sendMessage();
  }
  // Ctrl+D to toggle theme
  if (event.ctrlKey && event.key === "d") {
    event.preventDefault();
    toggleTheme();
  }
});
