"""
Stage 5 of the hierarchical pipeline: speaker notes generation.
"""
from typing import Any, Dict, List

from backend.ai import gemini_client, prompts
from backend.ai.outline_generator import SYSTEM_INSTRUCTION


def _validate_notes(data: Dict[str, Any]) -> str:
    if not isinstance(data, dict):
        raise gemini_client.GeminiResponseError("Speaker notes response was not a JSON object.")
    notes = data.get("speaker_notes")
    if not notes or not str(notes).strip():
        raise gemini_client.GeminiResponseError("Speaker notes response was empty.")
    return str(notes).strip()


def generate_speaker_notes(
    topic: str,
    audience: str,
    difficulty: str,
    style: str,
    seconds_per_slide: float,
    slide_title: str,
    slide_content: List[str],
    slide_example: str,
    is_first: bool,
    is_last: bool,
) -> str:
    prompt = prompts.speaker_notes_prompt(
        topic, audience, difficulty, style, seconds_per_slide,
        slide_title, slide_content, slide_example, is_first, is_last,
    )
    raw = gemini_client.generate_json(prompt, system_instruction=SYSTEM_INSTRUCTION, temperature=0.7)
    return _validate_notes(raw)


def generate_all_notes(slides: List[Dict[str, Any]], topic, audience, difficulty, style,
                        seconds_per_slide: float) -> List[Dict[str, Any]]:
    total = len(slides)
    for i, slide in enumerate(slides):
        slide["speaker_notes"] = generate_speaker_notes(
            topic, audience, difficulty, style, seconds_per_slide,
            slide["title"], slide["content"], slide.get("example", ""),
            is_first=(i == 0), is_last=(i == total - 1),
        )
    return slides
