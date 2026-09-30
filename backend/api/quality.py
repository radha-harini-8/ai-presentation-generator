"""
Standalone quality-control endpoint: POST /api/presentation/quality-check

Separated from presentations.py to mirror the project's modular structure
(api/documents.py, api/presentations.py, api/quality.py), even though it
operates on the same Presentation model.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database import models
from backend.utils import helpers
from backend.ai import gemini_client, quality_control

router = APIRouter(prefix="/api/presentation", tags=["quality"])


class QualityCheckRequest(BaseModel):
    presentation_id: str


@router.post("/quality-check")
def quality_check(req: QualityCheckRequest, db: Session = Depends(get_db)):
    """Re-run quality control against the currently stored slide content."""
    pres = db.query(models.Presentation).filter(models.Presentation.id == req.presentation_id).first()
    if not pres:
        raise HTTPException(status_code=404, detail="Presentation not found.")

    if not pres.slides or not any(helpers.from_json(s.content_json, []) for s in pres.slides):
        raise HTTPException(status_code=400, detail="Presentation has no generated content yet.")

    slides = [
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

    try:
        qc_report = quality_control.run_quality_control(
            pres.title, pres.audience, pres.difficulty, pres.style, slides
        )
    except gemini_client.GeminiAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except gemini_client.GeminiQuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except gemini_client.GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    pres.quality_report_json = helpers.to_json(qc_report)
    db.add(models.GenerationHistory(
        presentation_id=pres.id, action="quality_check",
        detail=f"quality_score={qc_report['quality_score']}",
    ))
    db.commit()
    return qc_report
