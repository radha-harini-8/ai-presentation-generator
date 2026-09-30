"""
Document upload / management endpoints.

POST   /api/documents/upload
GET    /api/documents
DELETE /api/documents/{id}
"""
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.database import get_db
from backend.database import models
from backend.rag import document_loader, text_chunker, vector_store
from backend.utils import helpers

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Form("default"),
    db: Session = Depends(get_db),
):
    # --- validate extension ---
    suffix = Path(file.filename).suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: PDF, DOCX, TXT."
        )

    # --- validate size ---
    raw_bytes = await file.read()
    size_mb = len(raw_bytes) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Max allowed is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # --- save to disk with a safe filename ---
    stored_name = helpers.safe_filename(file.filename)
    stored_path = settings.UPLOAD_DIR / stored_name
    stored_path.write_bytes(raw_bytes)

    file_type = suffix.lstrip(".")

    # --- extract + clean + chunk ---
    try:
        raw_text = document_loader.extract_text(stored_path, file_type)
        cleaned = document_loader.clean_text(raw_text)
        chunks = text_chunker.chunk_text(cleaned)
        if not chunks:
            raise document_loader.DocumentExtractionError("No usable content after chunking.")
    except document_loader.DocumentExtractionError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {exc}")

    # --- DB row ---
    doc = models.Document(
        filename=file.filename,
        stored_path=str(stored_path),
        file_type=file_type,
        file_size_bytes=len(raw_bytes),
        chunk_count=len(chunks),
        collection_name=collection,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # --- embeddings + vector store ---
    try:
        vector_store.add_chunks(collection, chunks, document_id=doc.id, filename=file.filename)
    except Exception as exc:  # noqa: BLE001
        db.delete(doc)
        db.commit()
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to build embeddings: {exc}")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "size_bytes": doc.file_size_bytes,
        "chunk_count": doc.chunk_count,
        "collection": collection,
        "upload_date": doc.upload_date.isoformat(),
    }


@router.get("")
def list_documents(collection: str = "default", db: Session = Depends(get_db)):
    docs = db.query(models.Document).filter(models.Document.collection_name == collection).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "size_bytes": d.file_size_bytes,
            "chunk_count": d.chunk_count,
            "upload_date": d.upload_date.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        vector_store.delete_document(doc.collection_name, document_id)
    except Exception:
        pass  # best-effort; don't block deletion of the DB/file record

    Path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"deleted": True, "id": document_id}
