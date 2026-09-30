"""
Presentation generation endpoints. Orchestrates the full hierarchical
pipeline: objectives -> outline -> slide content -> examples -> speaker
notes -> quality control -> selective regeneration -> PPTX build.
"""
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database import models
from backend.utils import helpers
from backend.ai import gemini_client, outline_generator, slide_generator, notes_generator, quality_control
from backend.rag import retriever

router = APIRouter(prefix="/api/presentation", tags=["presentation"])


# ----------------------------- schemas -----------------------------

class OutlineRequest(BaseModel):
    topic: str
    description: str = ""
    collection: str = "default"
    num_slides: int = Field(5, ge=3, le=30)
    duration_minutes: int = Field(15, ge=1, le=180)
    audience: str = "General Audience"
    difficulty: str = "Intermediate"
    style: str = "Professional"
    include_examples: bool = True
    generate_notes: bool = False
    use_documents: bool = True


class OutlineSlideEdit(BaseModel):
    slide_number: int
    title: str
    purpose: str = ""
    layout: str = "content"


class OutlineUpdateRequest(BaseModel):
    presentation_title: Optional[str] = None
    slides: List[OutlineSlideEdit]


class GenerateRequest(BaseModel):
    presentation_id: str
    auto_fix_quality_issues: bool = False


class RegenerateSlideRequest(BaseModel):
    presentation_id: str
    slide_number: int


class QualityCheckRequest(BaseModel):
    presentation_id: str


# ----------------------------- helpers -----------------------------

def _friendly_ai_error(exc: gemini_client.GeminiError) -> HTTPException:
    if isinstance(exc, gemini_client.GeminiAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, gemini_client.GeminiQuotaError):
        return HTTPException(status_code=429, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


def _get_presentation_or_404(db: Session, presentation_id: str) -> models.Presentation:
    pres = db.query(models.Presentation).filter(models.Presentation.id == presentation_id).first()
    if not pres:
        raise HTTPException(status_code=404, detail="Presentation not found.")
    return pres


def _log(db: Session, presentation_id: str, action: str, detail: str = ""):
    db.add(models.GenerationHistory(presentation_id=presentation_id, action=action, detail=detail))
    db.commit()


def _context_lookup_factory(collection: str, use_documents: bool):
    def _lookup(query: str) -> str:
        if not use_documents:
            return "(Source documents were not requested for this generation.)"
        chunks = retriever.retrieve_context(collection, query)
        return retriever.format_context_for_prompt(chunks)
    return _lookup


def _presentation_to_dict(pres: models.Presentation) -> dict:
    return {
        "id": pres.id,
        "title": pres.title,
        "topic": pres.topic,
        "description": pres.description,
        "slide_count": pres.slide_count,
        "duration_minutes": pres.duration_minutes,
        "seconds_per_slide": pres.seconds_per_slide,
        "audience": pres.audience,
        "difficulty": pres.difficulty,
        "style": pres.style,
        "include_examples": bool(pres.include_examples),
        "generate_notes": bool(pres.generate_notes),
        "use_documents": bool(pres.use_documents),
        "objectives": helpers.from_json(pres.objectives_json, []),
        "status": pres.status,
        "quality_report": helpers.from_json(pres.quality_report_json, {}),
        "file_ready": bool(pres.file_path),
        "created_at": pres.created_at.isoformat(),
        "updated_at": pres.updated_at.isoformat(),
        "slides": [
            {
                "slide_number": s.slide_number,
                "title": s.title,
                "purpose": s.purpose,
                "content": helpers.from_json(s.content_json, []),
                "example": s.example,
                "speaker_notes": s.speaker_notes,
                "sources": helpers.from_json(s.sources_json, []),
                "layout": s.layout,
            }
            for s in pres.slides
        ],
    }


# ----------------------------- endpoints -----------------------------

@router.post("/outline")
def create_outline(req: OutlineRequest, db: Session = Depends(get_db)):
    """Stage 1 (objectives) + Stage 2 (outline)."""
    seconds_per_slide = helpers.seconds_per_slide(req.duration_minutes, req.num_slides)
    lookup = _context_lookup_factory(req.collection, req.use_documents)
    topic_context = lookup(req.topic)

    try:
        objectives_data = outline_generator.generate_objectives(
            req.topic, req.description, req.audience, req.difficulty, req.style,
            req.num_slides, req.duration_minutes, req.include_examples, seconds_per_slide,
            topic_context,
        )
        outline_data = outline_generator.generate_outline(
            req.topic, req.description, req.audience, req.difficulty, req.style,
            req.num_slides, req.duration_minutes, req.include_examples, seconds_per_slide,
            topic_context, objectives_data["presentation_title"], objectives_data["objectives"],
        )
    except gemini_client.GeminiError as exc:
        raise _friendly_ai_error(exc)

    pres = models.Presentation(
        title=outline_data["presentation_title"],
        topic=req.topic,
        description=req.description,
        slide_count=req.num_slides,
        duration_minutes=req.duration_minutes,
        seconds_per_slide=seconds_per_slide,
        audience=req.audience,
        difficulty=req.difficulty,
        style=req.style,
        include_examples=int(req.include_examples),
        generate_notes=int(req.generate_notes),
        use_documents=int(req.use_documents),
        objectives_json=helpers.to_json(outline_data["objectives"]),
        outline_json=helpers.to_json(outline_data),
        status="outline",
    )
    db.add(pres)
    db.commit()
    db.refresh(pres)

    # remember which document collection this outline was generated against,
    # so later stages (content generation, regeneration) reuse the same RAG context
    outline_data_with_meta = dict(outline_data)
    outline_data_with_meta["collection"] = req.collection
    pres.outline_json = helpers.to_json(outline_data_with_meta)
    db.commit()

    for slide in outline_data["slides"]:
        db.add(models.Slide(
            presentation_id=pres.id,
            slide_number=slide["slide_number"],
            title=slide["title"],
            purpose=slide["purpose"],
            layout=slide["layout"],
            content_json="[]",
            sources_json="[]",
        ))
    db.commit()
    db.refresh(pres)

    _log(db, pres.id, "outline_generated", f"{len(outline_data['slides'])} slides")

    return _presentation_to_dict(pres)


@router.put("/{presentation_id}/outline")
def update_outline(presentation_id: str, req: OutlineUpdateRequest, db: Session = Depends(get_db)):
    """Allow the user to edit the outline (slide titles/purposes/order) before content generation."""
    pres = _get_presentation_or_404(db, presentation_id)

    if req.presentation_title:
        pres.title = req.presentation_title

    existing = {s.slide_number: s for s in pres.slides}
    for edit in req.slides:
        slide = existing.get(edit.slide_number)
        if slide:
            slide.title = edit.title
            slide.purpose = edit.purpose
            slide.layout = edit.layout

    pres.status = "outline"
    db.commit()
    db.refresh(pres)
    _log(db, pres.id, "outline_edited")
    return _presentation_to_dict(pres)


@router.post("/generate")
def generate_presentation(req: GenerateRequest, db: Session = Depends(get_db)):
    """
    Stage 3 (slide content) -> Stage 4 (examples) -> Stage 5 (speaker notes)
    -> Stage 6 (quality control) -> Stage 7 (selective regeneration)
    -> PPTX build. Everything in one call, driven by the stored outline.
    """
    pres = _get_presentation_or_404(db, req.presentation_id)
    if not pres.slides:
        raise HTTPException(status_code=400, detail="Presentation has no outline yet. Call /outline first.")

    use_documents = bool(pres.use_documents)
    include_examples = bool(pres.include_examples)
    generate_notes = bool(pres.generate_notes)

    # figure out which collection this presentation's documents live in
    # (stored implicitly - we re-derive from the outline request via the first document
    # collection if present, else "default")
    collection = "default"
    outline_meta = helpers.from_json(pres.outline_json, {})
    collection = outline_meta.get("collection", collection)

    lookup = _context_lookup_factory(collection, use_documents)

    outline_slides = [
        {"slide_number": s.slide_number, "title": s.title, "purpose": s.purpose, "layout": s.layout}
        for s in pres.slides
    ]

    try:
        # Stage 3 + 4
        generated = slide_generator.generate_all_slides(
            outline_slides, pres.topic, pres.audience, pres.difficulty, pres.style,
            include_examples, pres.seconds_per_slide, lookup,
        )
        # Stage 5
        if generate_notes:
            generated = notes_generator.generate_all_notes(
                generated, pres.topic, pres.audience, pres.difficulty, pres.style,
                pres.seconds_per_slide,
            )
        else:
            for s in generated:
                s["speaker_notes"] = ""

        # Stage 6
        qc_report = quality_control.run_quality_control(
            pres.title, pres.audience, pres.difficulty, pres.style, generated
        )

        # Stage 7 - selective regeneration
        if req.auto_fix_quality_issues and qc_report["slides_to_regenerate"]:
            generated = quality_control.regenerate_flagged_slides(
                generated, qc_report["slides_to_regenerate"],
                pres.topic, pres.audience, pres.difficulty, pres.style,
                include_examples, pres.seconds_per_slide, lookup, generate_notes,
            )
            # re-run QC once after fixes, informational only
            qc_report = quality_control.run_quality_control(
                pres.title, pres.audience, pres.difficulty, pres.style, generated
            )

    except gemini_client.GeminiError as exc:
        raise _friendly_ai_error(exc)

    # persist slide content
    slides_by_number = {s.slide_number: s for s in pres.slides}
    for g in generated:
        slide = slides_by_number.get(g["slide_number"])
        if not slide:
            continue
        slide.title = g["title"]
        slide.content_json = helpers.to_json(g["content"])
        slide.example = g.get("example", "")
        slide.speaker_notes = g.get("speaker_notes", "")
        slide.sources_json = helpers.to_json(g.get("sources", []))
        slide.layout = g.get("layout", slide.layout)

    pres.quality_report_json = helpers.to_json(qc_report)
    pres.status = "qc"
    db.commit()

    # Build the actual PPTX
    try:
        from backend.presentation.ppt_generator import build_presentation
        filename = f"{helpers.safe_filename(pres.title or 'presentation')}.pptx"
        output_path = build_presentation(
            pres.title,
            f"{pres.audience} • {pres.difficulty} • {pres.style}",
            pres.style,
            generated,
            filename,
        )
        pres.file_path = str(output_path)
        pres.status = "ppt_ready"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to build PowerPoint file: {exc}")

    db.refresh(pres)
    _log(db, pres.id, "presentation_generated", f"quality_score={qc_report['quality_score']}")

    return _presentation_to_dict(pres)


@router.post("/regenerate-slide")
def regenerate_slide(req: RegenerateSlideRequest, db: Session = Depends(get_db)):
    """Regenerate a single slide's content (and notes), then rebuild the PPTX."""
    pres = _get_presentation_or_404(db, req.presentation_id)
    slide = next((s for s in pres.slides if s.slide_number == req.slide_number), None)
    if not slide:
        raise HTTPException(status_code=404, detail=f"Slide {req.slide_number} not found.")

    collection = helpers.from_json(pres.outline_json, {}).get("collection", "default")
    lookup = _context_lookup_factory(collection, bool(pres.use_documents))

    try:
        content = slide_generator.generate_slide_content(
            pres.topic, pres.audience, pres.difficulty, pres.style,
            bool(pres.include_examples), pres.seconds_per_slide,
            lookup(f"{slide.title} {slide.purpose}"),
            slide.title, slide.purpose, slide.layout, slide.slide_number, pres.slide_count,
        )
        if pres.generate_notes:
            notes = notes_generator.generate_speaker_notes(
                pres.topic, pres.audience, pres.difficulty, pres.style, pres.seconds_per_slide,
                content["title"], content["content"], content.get("example", ""),
                is_first=(slide.slide_number == 1), is_last=(slide.slide_number == pres.slide_count),
            )
        else:
            notes = ""
    except gemini_client.GeminiError as exc:
        raise _friendly_ai_error(exc)

    slide.title = content["title"]
    slide.content_json = helpers.to_json(content["content"])
    slide.example = content.get("example", "")
    slide.sources_json = helpers.to_json(content.get("sources", []))
    slide.speaker_notes = notes
    db.commit()

    # Rebuild the PPTX so the download stays in sync
    if pres.file_path:
        all_slides = [
            {
                "slide_number": s.slide_number,
                "title": s.title,
                "content": helpers.from_json(s.content_json, []),
                "example": s.example,
                "speaker_notes": s.speaker_notes,
                "layout": s.layout,
            }
            for s in pres.slides
        ]
        from backend.presentation.ppt_generator import build_presentation
        filename = f"{helpers.safe_filename(pres.title or 'presentation')}.pptx"
        output_path = build_presentation(
            pres.title, f"{pres.audience} • {pres.difficulty} • {pres.style}",
            pres.style, all_slides, filename,
        )
        pres.file_path = str(output_path)
        db.commit()

    db.refresh(pres)
    _log(db, pres.id, "slide_regenerated", f"slide_number={req.slide_number}")
    return _presentation_to_dict(pres)


@router.get("/{presentation_id}")
def get_presentation(presentation_id: str, db: Session = Depends(get_db)):
    pres = _get_presentation_or_404(db, presentation_id)
    return _presentation_to_dict(pres)


@router.get("/{presentation_id}/download")
def download_presentation(presentation_id: str, db: Session = Depends(get_db)):
    pres = _get_presentation_or_404(db, presentation_id)
    if not pres.file_path:
        raise HTTPException(status_code=400, detail="Presentation has not been built into a PPTX yet.")

    file_path = pres.file_path
    import os
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Generated file is missing on disk.")

    filename = f"{pres.title or 'presentation'}.pptx".replace("/", "-")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )
