// ============================================================
// AI Presentation Generator - preview/edit page logic
// ============================================================

const API_BASE = "";

let presentation = JSON.parse(sessionStorage.getItem("apg_presentation") || "null");
let currentSlideIndex = 0;
let editing = false;

const slideNav = document.getElementById("slideNav");
const slidePreview = document.getElementById("slidePreview");
const previewError = document.getElementById("previewError");

if (!presentation) {
  slidePreview.innerHTML = "<p>No presentation loaded. Go back and generate one first.</p>";
} else {
  init();
}

function init() {
  document.getElementById("presTitle").textContent = presentation.title;
  document.getElementById("presMeta").textContent =
    `${presentation.audience} • ${presentation.difficulty} • ${presentation.style} • ${presentation.slide_count} slides • ${presentation.duration_minutes} min`;
  renderNav();
  renderSlide(0);
}

function renderNav() {
  slideNav.innerHTML = "";
  presentation.slides.forEach((s, i) => {
    const btn = document.createElement("button");
    btn.textContent = `${s.slide_number}`;
    btn.title = s.title;
    if (i === currentSlideIndex) btn.classList.add("active");
    btn.addEventListener("click", () => { editing = false; renderSlide(i); });
    slideNav.appendChild(btn);
  });
}

function renderSlide(index) {
  currentSlideIndex = index;
  [...slideNav.children].forEach((btn, i) => btn.classList.toggle("active", i === index));
  const slide = presentation.slides[index];
  previewError.classList.add("hidden");

  const bulletsHtml = (slide.content || []).map((b) => `<li>${escapeHtml(b)}</li>`).join("");
  const exampleHtml = slide.example
    ? `<div class="example-box"><strong>Example:</strong> ${escapeHtml(slide.example)}</div>`
    : "";
  const sourcesHtml = (slide.sources || []).length
    ? `<div style="margin-top:10px;font-size:12px;color:#888;">Sources: ${slide.sources.map(escapeHtml).join(", ")}</div>`
    : "";
  const notesHtml = slide.speaker_notes
    ? `<div class="notes"><strong>Speaker notes:</strong> ${escapeHtml(slide.speaker_notes)}</div>`
    : "";

  slidePreview.innerHTML = `
    <div style="font-size:12px;color:#888;">Slide ${slide.slide_number} of ${presentation.slide_count} — ${slide.layout}</div>
    <h3>${escapeHtml(slide.title)}</h3>
    <ul>${bulletsHtml}</ul>
    ${exampleHtml}
    ${sourcesHtml}
    ${notesHtml}
  `;

  document.getElementById("editBtn").style.display = "inline-block";
  document.getElementById("saveBtn").style.display = "none";
}

document.getElementById("backBtn").addEventListener("click", () => {
  window.location.href = "index.html";
});

document.getElementById("downloadBtn2").addEventListener("click", () => {
  if (presentation && presentation.id) {
    window.location.href = `${API_BASE}/api/presentation/${presentation.id}/download`;
  }
});

document.getElementById("editBtn").addEventListener("click", () => {
  const slide = presentation.slides[currentSlideIndex];
  slidePreview.innerHTML = `
    <div style="font-size:12px;color:#888;">Editing Slide ${slide.slide_number}</div>
    <label style="color:#333;font-size:13px;">Title</label>
    <input type="text" id="editTitle" value="${escapeAttr(slide.title)}" style="width:100%;padding:8px;margin-bottom:10px;">
    <label style="color:#333;font-size:13px;">Bullets (one per line)</label>
    <textarea class="edit-content" id="editContent">${escapeHtml((slide.content || []).join("\n"))}</textarea>
    <label style="color:#333;font-size:13px;">Example</label>
    <input type="text" id="editExample" value="${escapeAttr(slide.example || "")}" style="width:100%;padding:8px;">
  `;
  document.getElementById("editBtn").style.display = "none";
  document.getElementById("saveBtn").style.display = "inline-block";
});

document.getElementById("saveBtn").addEventListener("click", () => {
  const slide = presentation.slides[currentSlideIndex];
  slide.title = document.getElementById("editTitle").value.trim() || slide.title;
  slide.content = document.getElementById("editContent").value
    .split("\n").map((s) => s.trim()).filter(Boolean);
  slide.example = document.getElementById("editExample").value.trim();

  sessionStorage.setItem("apg_presentation", JSON.stringify(presentation));
  renderNav();
  renderSlide(currentSlideIndex);

  // Note: this saves the edit locally for preview purposes. To persist it into
  // the downloadable PPTX, use "Regenerate This Slide" or extend this call to
  // hit a PUT endpoint that writes edited content back into the database.
});

document.getElementById("regenSlideBtn").addEventListener("click", async () => {
  const slide = presentation.slides[currentSlideIndex];
  const btn = document.getElementById("regenSlideBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Regenerating…';
  previewError.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/api/presentation/regenerate-slide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presentation_id: presentation.id, slide_number: slide.slide_number }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to regenerate slide.");

    presentation = data;
    sessionStorage.setItem("apg_presentation", JSON.stringify(presentation));
    renderNav();
    renderSlide(currentSlideIndex);
  } catch (err) {
    previewError.textContent = err.message;
    previewError.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "🔄 Regenerate This Slide";
  }
});

document.getElementById("regenAllBtn").addEventListener("click", async () => {
  const btn = document.getElementById("regenAllBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Checking…';
  previewError.classList.add("hidden");

  try {
    const res = await fetch(`${API_BASE}/api/presentation/quality-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ presentation_id: presentation.id }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Quality check failed.");
    alert(`Quality score: ${data.quality_score} / 10\n\nIssues:\n${(data.issues || []).join("\n") || "None"}`);
  } catch (err) {
    previewError.textContent = err.message;
    previewError.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "🔄 Re-run Quality Check";
  }
});

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function escapeAttr(str) {
  return String(str).replace(/"/g, "&quot;");
}
