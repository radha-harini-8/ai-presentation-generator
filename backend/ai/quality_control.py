"""
Stage 6 (quality control) + Stage 7 (selective regeneration) of the pipeline.
"""
from typing import Any, Dict, List

from backend.ai import gemini_client, prompts, slide_generator, notes_generator
from backend.ai.outline_generator import SYSTEM_INSTRUCTION


def _validate_qc(data: Dict[str, Any], total_slides: int) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise gemini_client.GeminiResponseError("Quality control response was not a JSON object.")

    score = data.get("quality_score", 7.0)
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 7.0
    score = max(0.0, min(10.0, score))

    issues = data.get("issues", [])
    suggestions = data.get("suggestions", [])
    to_regenerate = data.get("slides_to_regenerate", [])

    if not isinstance(issues, list):
        issues = []
    if not isinstance(suggestions, list):
        suggestions = []
    if not isinstance(to_regenerate, list):
        to_regenerate = []

    valid_regen = []
    for n in to_regenerate:
        try:
            n_int = int(n)
        except (TypeError, ValueError):
            continue
        if 1 <= n_int <= total_slides:
            valid_regen.append(n_int)

    return {
        "quality_score": round(score, 1),
        "issues": [str(i) for i in issues],
        "suggestions": [str(s) for s in suggestions],
        "slides_to_regenerate": sorted(set(valid_regen)),
    }


def _summarize_slides(slides: List[Dict[str, Any]]) -> str:
    lines = []
    for s in slides:
        bullets = "; ".join(s.get("content", []))
        notes_len = len(s.get("speaker_notes", "") or "")
        lines.append(
            f"Slide {s['slide_number']} [{s.get('layout', 'content')}] \"{s['title']}\": "
            f"bullets=[{bullets}] example={'yes' if s.get('example') else 'no'} "
            f"notes_chars={notes_len}"
        )
    return "\n".join(lines)


def run_quality_control(presentation_title: str, audience: str, difficulty: str,
                         style: str, slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = _summarize_slides(slides)
    prompt = prompts.quality_control_prompt(presentation_title, audience, difficulty, style, summary)
    raw = gemini_client.generate_json(prompt, system_instruction=SYSTEM_INSTRUCTION, temperature=0.4)
    return _validate_qc(raw, total_slides=len(slides))


def regenerate_flagged_slides(
    slides: List[Dict[str, Any]],
    slide_numbers: List[int],
    topic: str,
    audience: str,
    difficulty: str,
    style: str,
    include_examples: bool,
    seconds_per_slide: float,
    context_lookup,
    generate_notes: bool,
) -> List[Dict[str, Any]]:
    """Regenerate only the flagged slides in place, leaving the rest untouched."""
    total = len(slides)
    by_number = {s["slide_number"]: s for s in slides}

    for n in slide_numbers:
        old = by_number.get(n)
        if not old:
            continue
        query = f"{old['title']} {old.get('purpose', '')}"
        context = context_lookup(query)
        new_content = slide_generator.generate_slide_content(
            topic, audience, difficulty, style, include_examples, seconds_per_slide,
            context, old["title"], old.get("purpose", ""), old.get("layout", "content"),
            n, total,
        )
        new_content["layout"] = old.get("layout", "content")
        new_content["purpose"] = old.get("purpose", "")

        if generate_notes:
            new_content["speaker_notes"] = notes_generator.generate_speaker_notes(
                topic, audience, difficulty, style, seconds_per_slide,
                new_content["title"], new_content["content"], new_content.get("example", ""),
                is_first=(n == 1), is_last=(n == total),
            )
        else:
            new_content["speaker_notes"] = old.get("speaker_notes", "")

        by_number[n] = new_content

    return [by_number[s["slide_number"]] for s in slides]
