"""
Turns a presentation's structured slide data into an actual .pptx file
using the reusable layout functions, and attaches speaker notes.
"""
from pathlib import Path
from typing import Any, Dict, List

from pptx import Presentation
from pptx.util import Inches

from backend.presentation import layouts, templates
from backend.config import settings


def _set_notes(slide, notes_text: str):
    if not notes_text:
        return
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = notes_text


def build_presentation(
    presentation_title: str,
    subtitle: str,
    style_name: str,
    slides: List[Dict[str, Any]],
    output_filename: str,
) -> Path:
    """
    slides: list of dicts with keys:
        slide_number, title, content (list[str]), example (str),
        speaker_notes (str), layout (str)
    """
    style = templates.get_style(style_name)

    prs = Presentation()
    prs.slide_width = layouts.SLIDE_WIDTH
    prs.slide_height = layouts.SLIDE_HEIGHT

    total = len(slides)

    for slide_data in slides:
        layout_type = slide_data.get("layout", "content")
        number = slide_data["slide_number"]
        title = slide_data["title"]
        bullets = slide_data.get("content", [])
        example = slide_data.get("example", "")

        if layout_type == "title" or number == 1:
            slide = layouts.create_title_slide(prs, title, subtitle, style, number, total)
        elif layout_type == "conclusion" or number == total:
            slide = layouts.create_conclusion_slide(prs, title, bullets, style, number, total)
        elif layout_type == "two_column" and len(bullets) >= 4:
            mid = len(bullets) // 2
            slide = layouts.create_two_column_slide(
                prs, title, bullets[:mid], bullets[mid:], style, number, total
            )
        elif layout_type == "example" and example:
            slide = layouts.create_example_slide(prs, title, bullets, example, style, number, total)
        else:
            slide = layouts.create_content_slide(prs, title, bullets, style, number, total, example=example)

        _set_notes(slide, slide_data.get("speaker_notes", ""))

    output_path = settings.GENERATED_DIR / output_filename
    prs.save(str(output_path))
    return output_path
