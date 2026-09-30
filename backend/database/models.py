"""
SQLAlchemy ORM models: users, documents, presentations, slides, generation_history.
"""
import datetime
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from backend.database.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String, unique=True, nullable=False, default="guest")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    presentations = relationship("Presentation", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)          # pdf / docx / txt
    file_size_bytes = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    collection_name = Column(String, nullable=False)     # vector store namespace
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="documents")


class Presentation(Base):
    __tablename__ = "presentations"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    title = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    description = Column(Text, default="")

    slide_count = Column(Integer, default=10)
    duration_minutes = Column(Integer, default=15)
    seconds_per_slide = Column(Float, default=90.0)

    audience = Column(String, default="General Audience")
    difficulty = Column(String, default="Intermediate")
    style = Column(String, default="Professional")

    include_examples = Column(Integer, default=1)     # 0/1 boolean
    generate_notes = Column(Integer, default=1)
    use_documents = Column(Integer, default=1)

    objectives_json = Column(Text, default="[]")       # JSON string
    outline_json = Column(Text, default="{}")           # JSON string (full structured outline)
    quality_report_json = Column(Text, default="{}")

    status = Column(String, default="created")  # created -> outline -> content -> notes -> qc -> ppt_ready
    file_path = Column(String, default="")

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="presentations")
    slides = relationship("Slide", back_populates="presentation", cascade="all, delete-orphan",
                           order_by="Slide.slide_number")
    history = relationship("GenerationHistory", back_populates="presentation", cascade="all, delete-orphan")


class Slide(Base):
    __tablename__ = "slides"

    id = Column(String, primary_key=True, default=gen_uuid)
    presentation_id = Column(String, ForeignKey("presentations.id"), nullable=False)

    slide_number = Column(Integer, nullable=False)
    title = Column(String, default="")
    purpose = Column(String, default="")
    content_json = Column(Text, default="[]")      # JSON list of bullet strings
    example = Column(Text, default="")
    speaker_notes = Column(Text, default="")
    sources_json = Column(Text, default="[]")       # JSON list of source filenames
    layout = Column(String, default="content")       # title / content / two_column / example / conclusion

    presentation = relationship("Presentation", back_populates="slides")


class GenerationHistory(Base):
    __tablename__ = "generation_history"

    id = Column(String, primary_key=True, default=gen_uuid)
    presentation_id = Column(String, ForeignKey("presentations.id"), nullable=False)
    action = Column(String, nullable=False)
    detail = Column(Text, default="")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    presentation = relationship("Presentation", back_populates="history")
