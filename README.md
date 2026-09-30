<<<<<<< HEAD
# ai-presentation-generator
An AI-powered web app that turns topics and uploaded documents into polished PowerPoint presentations. Gemini generates the content, while RAG grounds it in sources. Users can edit slides, check quality, add speaker notes, and download decks.
=======
# AI Presentation Generator

Generate a professional, downloadable PowerPoint (`.pptx`) presentation from a topic,
optional source documents (PDF/DOCX/TXT), and a handful of settings — audience,
difficulty, style, slide count, and duration. Content is produced by the Gemini API
using **hierarchical prompting** (objectives → outline → slide content → examples →
speaker notes → quality control → selective regeneration), grounded by **RAG**
(Retrieval-Augmented Generation) over your uploaded documents.

---

## 1. Features

- Topic + description + document upload (PDF, DOCX, TXT)
- Configurable slides, duration, audience, difficulty, style, examples, speaker notes
- RAG pipeline: extraction → cleaning → chunking → embeddings → FAISS vector search
- Hierarchical Gemini prompting (7 stages, never one giant prompt)
- Strict JSON validation with automatic retry/repair on malformed AI output
- AI-driven quality control with **selective** slide regeneration (not full rebuilds)
- Duration-aware speaker notes (targets a words-per-slide budget from your duration)
- Real `.pptx` file generation via `python-pptx`, with 5 reusable slide layouts
- Web UI: upload, configure, watch progress, preview, edit, regenerate, download
- SQLite persistence of documents, presentations, slides, and generation history
- `.env`-based configuration — API key is never hard-coded

---

## 2. Architecture

```
USER → HTML/CSS/JS (frontend/) → FastAPI (backend/)
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                                  ▼
              User Settings                        Documents
                    │                                  │
                    │                     Extract → Clean → Chunk → Embed → FAISS
                    │                                  │
                    └────────────────┬─────────────────┘
                                      ▼
                               RAG Retrieval
                                      ▼
                                 Gemini API
                     (objectives → outline → slide content
                      → examples → speaker notes → QC → fix)
                                      ▼
                                 python-pptx
                                      ▼
                             presentation.pptx → USER
```

### Project structure

```
ai-presentation-generator/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config.py                # env-driven settings
│   ├── api/                     # documents.py, presentations.py, quality.py
│   ├── ai/                      # gemini_client, prompts, outline/slide/notes/quality generators
│   ├── rag/                     # document_loader, text_chunker, embeddings, vector_store, retriever
│   ├── presentation/             # ppt_generator, layouts, templates (python-pptx)
│   ├── database/                 # SQLAlchemy models + session
│   └── utils/                    # helpers (safe filenames, JSON, timing math)
├── frontend/
│   ├── index.html, preview.html
│   ├── css/style.css
│   └── js/app.js, js/preview.js
├── uploads/                      # uploaded source documents (gitignored)
├── generated_presentations/       # output .pptx files (gitignored)
├── vector_store/                  # FAISS indexes + metadata (gitignored)
├── .env / .env.example
├── requirements.txt
└── README.md
```

---

## 3. Installation

### 3.1 Prerequisites
- Python 3.11 or 3.12 (see the note in 3.2 below — newer Pythons can break the build)
- A Gemini API key: https://aistudio.google.com/app/apikey

### 3.1a Extracting the zip on Windows
`unzip` is a Linux/macOS command and won't work in Command Prompt. Instead:
right-click `ai-presentation-generator.zip` in File Explorer → **Extract All...**,
then `cd` into the extracted folder. (PowerShell users can also run
`Expand-Archive ai-presentation-generator.zip .`)

### 3.2 Set up a virtual environment

**Important — use Python 3.11 or 3.12.** Several packages here (`pymupdf`,
`faiss-cpu`, `sentence-transformers`) ship pre-built wheels only for released,
widely-adopted Python versions. On a brand-new Python (e.g. 3.13/3.14), pip may
find no wheel and try to **compile from source**, which fails on Windows without
Visual Studio Build Tools installed (this is exactly the `pymupdf ... Unable to
find Visual Studio` error). Check what you have and install 3.11/3.12 if needed
from https://www.python.org/downloads/ (tick "Add python.exe to PATH" during
install).

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (Command Prompt) — run from inside the project folder
py -3.12 -m venv venv
venv\Scripts\activate.bat

# Windows (PowerShell)
py -3.12 -m venv venv
venv\Scripts\Activate.ps1
```

If `py -3.12` says that version isn't installed, run `py -0` to list what you
have, or install 3.12 first. `python3` (not `py -3.12`) is correct on macOS/Linux.

### 3.3 Install dependencies

```bash
pip install -r requirements.txt
```

> Note: `sentence-transformers` will download its embedding model (~90MB, `all-MiniLM-L6-v2`)
> the first time it runs — this requires an internet connection on first use only.

### 3.4 Configure your API key

```bash
# macOS / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Edit `.env` (in Notepad or any editor) and set:

```
GEMINI_API_KEY=your_actual_key_here
GEMINI_MODEL=gemini-2.0-flash
```

**Never** commit `.env` — it's already listed in `.gitignore`.

---

## 4. Running the application

Run everything from the **project root** (so the `backend` package resolves):

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The backend also serves the frontend as static files, so simply open:

```
http://localhost:8000
```

No separate frontend server is required for local development. Interactive API docs
(Swagger UI) are available at `http://localhost:8000/docs`.

If you prefer to serve the frontend separately (e.g. via VS Code Live Server on
`http://127.0.0.1:5500`), that origin is already whitelisted in `.env.example`'s
`ALLOWED_ORIGINS` — just make sure `API_BASE` in `frontend/js/app.js` and
`preview.js` points at `http://localhost:8000`.

---

## 5. Using the app

1. Enter a **topic** (required) and optional description.
2. Optionally upload PDF/DOCX/TXT source documents — they're chunked, embedded, and
   stored in a local FAISS index.
3. Set number of slides, duration, audience, difficulty, style, and toggles.
4. Click **Generate Presentation**. The app will:
   - Retrieve relevant chunks from your documents (if enabled)
   - Generate objectives → outline (stages 1–2)
   - Generate per-slide content + examples (stages 3–4)
   - Generate speaker notes (stage 5)
   - Run AI quality control and regenerate only the flagged slides (stages 6–7)
   - Build the actual `.pptx` file
5. Review the quality score and any AI-flagged issues.
6. Click **Preview Presentation** to browse slides, edit content, or regenerate an
   individual slide.
7. Click **Download PPTX** to get the final file.

---

## 6. API reference

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/documents/upload` | Upload + process a PDF/DOCX/TXT source document |
| GET | `/api/documents` | List uploaded documents in a collection |
| DELETE | `/api/documents/{id}` | Remove a document and its vectors |
| POST | `/api/presentation/outline` | Stage 1–2: generate objectives + outline |
| PUT | `/api/presentation/{id}/outline` | Edit the outline before content generation |
| POST | `/api/presentation/generate` | Stage 3–7 + PPTX build, for a given presentation |
| POST | `/api/presentation/regenerate-slide` | Regenerate one slide and rebuild the PPTX |
| POST | `/api/presentation/quality-check` | Re-run QC against current slide content |
| GET | `/api/presentation/{id}` | Fetch full presentation + slides |
| GET | `/api/presentation/{id}/download` | Download the generated `.pptx` |
| GET | `/api/health` | Health check / config sanity check |

Full interactive docs: `http://localhost:8000/docs`.

---

## 7. RAG architecture

1. **Extraction** — PyMuPDF (PDF), python-docx (DOCX), plain file read (TXT)
2. **Cleaning** — whitespace normalization
3. **Chunking** — word-based sliding window (~800 chars, ~120 char overlap)
4. **Embeddings** — `sentence-transformers` (`all-MiniLM-L6-v2` by default, configurable)
5. **Vector store** — FAISS `IndexFlatIP` (cosine similarity via normalized vectors),
   persisted to disk per "collection" (namespaced per browser session) under
   `vector_store/`, with a JSON metadata sidecar per collection
6. **Retrieval** — each generation stage embeds its own query (topic, or per-slide
   title+purpose) and retrieves the top-K most similar chunks, which are inserted
   into the Gemini prompt as prioritized source material

---

## 8. PowerPoint generation

`backend/presentation/layouts.py` exposes reusable, style-aware slide builders:

- `create_title_slide()`
- `create_content_slide()`
- `create_two_column_slide()`
- `create_example_slide()`
- `create_conclusion_slide()`

`backend/presentation/templates.py` defines color/font presets per presentation
style (Academic, Professional, Simple, Technical, Minimal). `ppt_generator.py`
picks the right layout per slide (based on the AI-assigned layout type) and
attaches the generated speaker notes to each slide's notes pane.

---

## 9. Database

SQLite (via SQLAlchemy) with these tables: `users`, `documents`, `presentations`,
`slides`, `generation_history`. The DB file (`app.db`) is created automatically on
first run (see `init_db()` in `backend/database/database.py`) — no manual migration
step is needed for this project's scope.

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `AI service is not configured` | Set `GEMINI_API_KEY` in `.env` |
| `AI service rejected the API key` | Double-check the key is valid and has Gemini API access enabled |
| `AI service quota exceeded` | Wait and retry, or check your Gemini API usage/billing |
| Upload fails with "Unsupported file type" | Only `.pdf`, `.docx`, `.txt` are accepted |
| First document upload is slow | `sentence-transformers` is downloading its model the first time — subsequent uploads are fast |
| `ModuleNotFoundError: backend` | Run `uvicorn` from the **project root**, not from inside `backend/` |
| `pymupdf ... Unable to find Visual Studio` / long source build then failure | Your Python version is too new for that package's prebuilt wheels (common on 3.13/3.14 right after they're released). Install Python 3.11 or 3.12, recreate the venv with it (`py -3.12 -m venv venv`), and reinstall |
| `'unzip'`, `'source'`, or `'cp'` is not recognized | Those are Linux/macOS commands. On Windows use File Explorer's Extract All (or `Expand-Archive`), `venv\Scripts\activate.bat`, and `copy` instead — see section 3 |
| CORS errors in the browser console | Add your frontend's origin to `ALLOWED_ORIGINS` in `.env` |
| Generated PPTX text looks slightly off in PowerPoint | Layouts use a 16:9 (13.33in × 7.5in) canvas — this is expected and works in all modern PowerPoint/Google Slides/LibreOffice Impress versions |

---

## 11. Future enhancements

- Real user accounts/auth (currently a single implicit "guest" user + a
  browser-generated document collection id)
- Chunk-level citation highlighting in the preview UI
- Support for image-heavy slide layouts and chart embedding
- Async/background job queue for generation (currently synchronous per-request)
- Support for additional export formats (Google Slides, PDF export of the deck)
- ChromaDB as an alternative vector store backend (FAISS is used by default)

---

## 12. Security notes

- The Gemini API key is read only from environment variables (`.env`), never
  hard-coded, and `.env` is gitignored (`.env.example` ships without a real key)
- Uploaded files are validated by extension and size, saved under randomized
  filenames, and never executed
- All unhandled exceptions are caught and returned as a generic friendly message —
  internal errors, stack traces, and API keys are never exposed to the client
>>>>>>> aefd28d (Prepare AI Presentation Generator for deployment)
