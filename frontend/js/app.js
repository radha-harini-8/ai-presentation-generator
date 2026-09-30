// ============================================================
// AI Presentation Generator - main form logic
// ============================================================

const API_BASE = ""; // same-origin; change if backend is hosted elsewhere, e.g. "http://localhost:8000"

// A lightweight per-browser "collection" id so uploaded documents are
// namespaced per user without requiring full authentication.
function getCollectionId() {
  let id = localStorage.getItem("apg_collection");
  if (!id) {
    id = "col_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("apg_collection", id);
  }
  return id;
}
const COLLECTION = getCollectionId();

const uploadZone = document.getElementById("uploadZone");
const fileInput = document.getElementById("fileInput");
const docList = document.getElementById("docList");
const formError = document.getElementById("formError");
const generateBtn = document.getElementById("generateBtn");

let uploadedDocs = []; // {id, filename}

// ---------------- Upload handling ----------------

uploadZone.addEventListener("click", () => fileInput.click());
uploadZone.addEventListener("dragover", (e) => { e.preventDefault(); uploadZone.classList.add("dragover"); });
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("dragover");
  handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", (e) => handleFiles(e.target.files));

async function handleFiles(fileListObj) {
  const files = Array.from(fileListObj);
  for (const file of files) {
    await uploadOneFile(file);
  }
  fileInput.value = "";
}

async function uploadOneFile(file) {
  const item = document.createElement("div");
  item.className = "doc-item";
  item.innerHTML = `<span>⏳ Uploading ${escapeHtml(file.name)}...</span>`;
  docList.appendChild(item);

  const form = new FormData();
  form.append("file", file);
  form.append("collection", COLLECTION);

  try {
    const res = await fetch(`${API_BASE}/api/documents/upload`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");

    uploadedDocs.push({ id: data.id, filename: data.filename });
    item.innerHTML = `
      <span>📄 ${escapeHtml(data.filename)} — ${data.chunk_count} chunks indexed</span>
      <button class="remove-doc" data-id="${data.id}">Remove</button>
    `;
    item.querySelector(".remove-doc").addEventListener("click", () => removeDoc(data.id, item));
  } catch (err) {
    item.innerHTML = `<span style="color:var(--danger);">✗ ${escapeHtml(file.name)}: ${escapeHtml(err.message)}</span>`;
  }
}

async function removeDoc(id, itemEl) {
  try {
    await fetch(`${API_BASE}/api/documents/${id}`, { method: "DELETE" });
  } catch (e) { /* best-effort */ }
  uploadedDocs = uploadedDocs.filter((d) => d.id !== id);
  itemEl.remove();
}

// ---------------- Generation flow ----------------

const progressCard = document.getElementById("progressCard");
const formCard = document.getElementById("formCard");
const resultCard = document.getElementById("resultCard");
const progressList = document.getElementById("progressList");
const progressError = document.getElementById("progressError");

const STEP_ORDER = ["upload", "outline", "content", "notes", "quality", "ppt"];

function setStep(step, state) {
  const li = progressList.querySelector(`li[data-step="${step}"]`);
  if (!li) return;

  li.classList.remove("active", "done", "error");

  // Only add a class when state is not empty
  if (state) {
    li.classList.add(state);
  }

  if (state === "done") {
    li.querySelector(".dot").textContent = "✓";
  }

  if (state === "error") {
    li.querySelector(".dot").textContent = "!";
  }
}

function markUpTo(step, state) {
  const idx = STEP_ORDER.indexOf(step);
  STEP_ORDER.forEach((s, i) => {
    if (i < idx) setStep(s, "done");
  });
  setStep(step, state);
}

generateBtn.addEventListener("click", startGeneration);

async function startGeneration() {
  const topic = document.getElementById("topic").value.trim();
  formError.classList.add("hidden");

  if (!topic) {
    formError.textContent = "Please enter a presentation topic.";
    formError.classList.remove("hidden");
    return;
  }

  const payload = {
    topic,
    description: document.getElementById("description").value.trim(),
    collection: COLLECTION,
    num_slides: parseInt(document.getElementById("numSlides").value, 10) || 10,
    duration_minutes: parseInt(document.getElementById("duration").value, 10) || 15,
    audience: document.getElementById("audience").value,
    difficulty: document.getElementById("difficulty").value,
    style: document.getElementById("style").value,
    include_examples: document.getElementById("includeExamples").checked,
    generate_notes: document.getElementById("generateNotes").checked,
    use_documents: document.getElementById("useDocuments").checked,
  };

  formCard.classList.add("hidden");
  progressCard.classList.remove("hidden");
  progressError.classList.add("hidden");
  STEP_ORDER.forEach((s) => setStep(s, s === "upload" ? "active" : ""));

  try {
    // Step: documents already uploaded during selection
    await sleep(300);
    markUpTo("outline", "active");

    const outlineRes = await fetch(`${API_BASE}/api/presentation/outline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const outlineData = await outlineRes.json();
    if (!outlineRes.ok) throw new Error(outlineData.detail || "Failed to generate outline.");

    const presentationId = outlineData.id;
    markUpTo("content", "active");

    // Animate through content/notes/quality steps while the (blocking) generate call runs
    const animTimer = animateSteps(["content", "notes", "quality"]);

    const genRes = await fetch(`${API_BASE}/api/presentation/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presentation_id: presentationId, auto_fix_quality_issues: true }),
    });
    clearInterval(animTimer);
    const genData = await genRes.json();
    if (!genRes.ok) throw new Error(genData.detail || "Failed to generate presentation content.");

    markUpTo("ppt", "done");
    setStep("ppt", "done");

    sessionStorage.setItem("apg_presentation", JSON.stringify(genData));
    showResult(genData);

  } catch (err) {
    const currentActive = progressList.querySelector("li.active");
    if (currentActive) currentActive.classList.replace("active", "error"), currentActive.querySelector(".dot").textContent = "!";
    progressError.textContent = err.message || "Something went wrong. Please try again.";
    progressError.classList.remove("hidden");

    const retryBtn = document.createElement("button");
    retryBtn.className = "btn secondary small";
    retryBtn.style.marginTop = "14px";
    retryBtn.textContent = "← Back to form";
    retryBtn.onclick = () => {
      progressCard.classList.add("hidden");
      formCard.classList.remove("hidden");
    };
    progressError.after(retryBtn);
  }
}

function animateSteps(steps) {
  let i = 0;
  setStep(steps[0], "active");
  return setInterval(() => {
    setStep(steps[i], "done");
    i++;
    if (i < steps.length) {
      setStep(steps[i], "active");
    }
  }, 1800);
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

function showResult(data) {
  progressCard.classList.add("hidden");
  resultCard.classList.remove("hidden");

  const qc = data.quality_report || {};
  document.getElementById("qualityScore").textContent =
    qc.quality_score !== undefined ? `${qc.quality_score} / 10` : "–";

  const issuesBox = document.getElementById("qcIssuesBox");
  const issuesList = document.getElementById("qcIssuesList");
  issuesList.innerHTML = "";
  const issues = qc.issues || [];
  const suggestions = qc.suggestions || [];
  if (issues.length || suggestions.length) {
    issues.forEach((i) => {
      const li = document.createElement("li");
      li.textContent = i;
      issuesList.appendChild(li);
    });
    suggestions.forEach((s) => {
      const li = document.createElement("li");
      li.textContent = "Suggestion: " + s;
      issuesList.appendChild(li);
    });
    issuesBox.classList.remove("hidden");
  } else {
    issuesBox.classList.add("hidden");
  }
}

document.getElementById("previewBtn").addEventListener("click", () => {
  window.location.href = "preview.html";
});

document.getElementById("downloadBtn").addEventListener("click", () => {
  const data = JSON.parse(sessionStorage.getItem("apg_presentation") || "{}");
  if (data.id) window.location.href = `${API_BASE}/api/presentation/${data.id}/download`;
});

document.getElementById("newBtn").addEventListener("click", () => {
  sessionStorage.removeItem("apg_presentation");
  window.location.reload();
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
