"""
Stage 1 (objectives) + Stage 2 (outline) of the hierarchical pipeline.
"""
from typing import Any, Dict, List

from backend.ai import gemini_client, prompts

SYSTEM_INSTRUCTION = (
    "You are an expert presentation designer and instructional content writer. "
    "You always respond with strictly valid JSON matching the requested schema, "
    "with no markdown fences and no extra commentary."
)


def _validate_objectives(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise gemini_client.GeminiResponseError("Objectives response was not a JSON object.")
    title = data.get("presentation_title")
    objectives = data.get("objectives")
    if not title or not isinstance(objectives, list) or not objectives:
        raise gemini_client.GeminiResponseError("Objectives response is missing required fields.")
    return {"presentation_title": str(title), "objectives": [str(o) for o in objectives]}


def generate_objectives(topic, description, audience, difficulty, style, num_slides,
                         duration_minutes, include_examples, seconds_per_slide, context) -> Dict[str, Any]:
    prompt = prompts.objectives_prompt(
        topic, description, audience, difficulty, style, num_slides,
        duration_minutes, include_examples, seconds_per_slide, context
    )
    raw = gemini_client.generate_json(prompt, system_instruction=SYSTEM_INSTRUCTION, temperature=0.6)
    return _validate_objectives(raw)


def _validate_outline(data: Dict[str, Any], expected_slides: int) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise gemini_client.GeminiResponseError("Outline response was not a JSON object.")
    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise gemini_client.GeminiResponseError("Outline response has no slides.")

    valid_layouts = {"title", "content", "two_column", "example", "conclusion"}
    cleaned: List[Dict[str, Any]] = []
    for i, slide in enumerate(slides[:expected_slides], start=1):
        layout = slide.get("layout", "content")
        if layout not in valid_layouts:
            layout = "content"
        cleaned.append({
            "slide_number": i,
            "title": str(slide.get("title", f"Slide {i}")),
            "purpose": str(slide.get("purpose", "")),
            "layout": layout,
        })

    # Force sane structure: first slide is a title slide, last is conclusion
    if cleaned:
        cleaned[0]["layout"] = "title"
        cleaned[-1]["layout"] = "conclusion"

    # Pad if the model returned fewer slides than requested
    while len(cleaned) < expected_slides:
        n = len(cleaned) + 1
        cleaned.append({
            "slide_number": n,
            "title": f"Additional Point {n}",
            "purpose": "Supplementary content",
            "layout": "content",
        })
        cleaned[-1]["layout"] = "conclusion" if n == expected_slides else "content"

    return {
        "presentation_title": str(data.get("presentation_title", "Untitled Presentation")),
        "objectives": [str(o) for o in data.get("objectives", [])],
        "slides": cleaned,
    }


def generate_outline(topic, description, audience, difficulty, style, num_slides,
                      duration_minutes, include_examples, seconds_per_slide, context,
                      presentation_title, objectives) -> Dict[str, Any]:
    prompt = prompts.outline_prompt(
        topic, description, audience, difficulty, style, num_slides,
        duration_minutes, include_examples, seconds_per_slide, context,
        presentation_title, objectives
    )
    raw = gemini_client.generate_json(prompt, system_instruction=SYSTEM_INSTRUCTION, temperature=0.6)
    return _validate_outline(raw, expected_slides=num_slides)
