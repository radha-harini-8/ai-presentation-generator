"""
Stage 3 (slide content) + Stage 4 (examples).

Optimized version:
- Generates ALL slides in one Gemini call.
- Keeps the prompt reasonably structured.
- Uses RAG context separately for each slide.
- Reduces Gemini API calls significantly.
"""

import json
from typing import Any, Dict, List

from backend.ai import gemini_client
from backend.ai.outline_generator import SYSTEM_INSTRUCTION


def _validate_slide_content(
    data: Dict[str, Any],
    slide_number: int,
    fallback_title: str,
) -> Dict[str, Any]:

    if not isinstance(data, dict):
        raise gemini_client.GeminiResponseError(
            f"Slide {slide_number} content was not a JSON object."
        )

    content = data.get("content")

    if not isinstance(content, list) or not content:
        raise gemini_client.GeminiResponseError(
            f"Slide {slide_number} content has no bullets."
        )

    bullets = [
        str(b).strip()
        for b in content
        if str(b).strip()
    ][:6]

    if not bullets:
        raise gemini_client.GeminiResponseError(
            f"Slide {slide_number} content bullets were empty."
        )

    sources = data.get("sources", [])

    if not isinstance(sources, list):
        sources = []

    return {
        "slide_number": slide_number,
        "title": str(data.get("title") or fallback_title),
        "content": bullets,
        "example": str(data.get("example", "") or ""),
        "sources": [str(s) for s in sources],
    }


def _build_batch_prompt(
    outline_slides: List[Dict[str, Any]],
    topic: str,
    audience: str,
    difficulty: str,
    style: str,
    include_examples: bool,
    seconds_per_slide: float,
    contexts: Dict[int, str],
) -> str:

    slides_for_prompt = []

    for slide in outline_slides:
        slide_number = slide["slide_number"]

        slides_for_prompt.append(
            {
                "slide_number": slide_number,
                "title": slide["title"],
                "purpose": slide.get("purpose", ""),
                "layout": slide.get("layout", "content"),
                "context": contexts.get(
                    slide_number,
                    "(No source documents available.)"
                ),
            }
        )

    slides_json = json.dumps(
        slides_for_prompt,
        ensure_ascii=False,
        indent=2,
    )

    return f"""
Create the complete content for a presentation.

IMPORTANT:
Generate ALL slides in this request.
Do NOT generate only one slide.
Return ONLY valid JSON.
Do not use Markdown code fences.

Presentation topic:
{topic}

Audience:
{audience}

Difficulty:
{difficulty}

Style:
{style}

Seconds per slide:
{seconds_per_slide}

Include examples:
{include_examples}

Slides to generate:

{slides_json}

For every slide, generate:

1. A clear and engaging title.
2. 3 to 6 concise presentation bullets.
3. An example when examples are requested.
4. Relevant sources when source context is provided.

Keep the content appropriate for the specified audience,
difficulty, and presentation style.

Do not invent facts when the provided source context contains
relevant information. Use the source context when appropriate.

Return exactly this JSON structure:

[
  {{
    "slide_number": 1,
    "title": "Slide title",
    "content": [
      "Bullet 1",
      "Bullet 2",
      "Bullet 3"
    ],
    "example": "Example text",
    "sources": []
  }},
  {{
    "slide_number": 2,
    "title": "Slide title",
    "content": [
      "Bullet 1",
      "Bullet 2",
      "Bullet 3"
    ],
    "example": "Example text",
    "sources": []
  }}
]

Return one object for EVERY requested slide.
Do not omit any slide.
"""


def generate_slide_content(
    topic: str,
    audience: str,
    difficulty: str,
    style: str,
    include_examples: bool,
    seconds_per_slide: float,
    context: str,
    slide_title: str,
    slide_purpose: str,
    slide_layout: str,
    slide_number: int,
    total_slides: int,
) -> Dict[str, Any]:

    """
    Generate a single slide.

    This function is retained for individual slide regeneration.
    The normal presentation generation uses generate_all_slides()
    which generates the complete deck in one Gemini call.
    """

    prompt = f"""
Create content for ONE presentation slide.

Topic:
{topic}

Audience:
{audience}

Difficulty:
{difficulty}

Style:
{style}

Slide number:
{slide_number} of {total_slides}

Slide title:
{slide_title}

Slide purpose:
{slide_purpose}

Layout:
{slide_layout}

Seconds per slide:
{seconds_per_slide}

Include examples:
{include_examples}

Source context:
{context}

Return ONLY valid JSON:

{{
  "slide_number": {slide_number},
  "title": "{slide_title}",
  "content": [
    "Bullet 1",
    "Bullet 2",
    "Bullet 3"
  ],
  "example": "Example if appropriate",
  "sources": []
}}

Use 3 to 6 concise bullets.
"""

    raw = gemini_client.generate_json(
        prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
    )

    return _validate_slide_content(
        raw,
        slide_number,
        slide_title,
    )


def generate_all_slides(
    outline_slides: List[Dict[str, Any]],
    topic: str,
    audience: str,
    difficulty: str,
    style: str,
    include_examples: bool,
    seconds_per_slide: float,
    context_lookup,
) -> List[Dict[str, Any]]:
    """
    Generate ALL slides using ONE Gemini API request.

    Previously:
        1 Gemini request per slide

    Now:
        1 Gemini request for the complete slide deck.
    """

    contexts: Dict[int, str] = {}

    for slide in outline_slides:
        query = f"{slide['title']} {slide.get('purpose', '')}"

        contexts[slide["slide_number"]] = context_lookup(query)

    prompt = _build_batch_prompt(
        outline_slides=outline_slides,
        topic=topic,
        audience=audience,
        difficulty=difficulty,
        style=style,
        include_examples=include_examples,
        seconds_per_slide=seconds_per_slide,
        contexts=contexts,
    )

    raw = gemini_client.generate_json(
        prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
    )

    if not isinstance(raw, list):
        raise gemini_client.GeminiResponseError(
            "Gemini did not return a list of slides."
        )

    expected_numbers = {
        slide["slide_number"]
        for slide in outline_slides
    }

    generated_numbers = {
        item.get("slide_number")
        for item in raw
        if isinstance(item, dict)
    }

    missing = expected_numbers - generated_numbers

    if missing:
        raise gemini_client.GeminiResponseError(
            f"Gemini did not generate slides: {sorted(missing)}"
        )

    results = []

    for slide in outline_slides:

        slide_number = slide["slide_number"]

        generated_slide = next(
            (
                item
                for item in raw
                if isinstance(item, dict)
                and item.get("slide_number") == slide_number
            ),
            None,
        )

        if generated_slide is None:
            raise gemini_client.GeminiResponseError(
                f"Missing generated content for slide {slide_number}."
            )

        content = _validate_slide_content(
            generated_slide,
            slide_number,
            slide["title"],
        )

        content["layout"] = slide.get("layout", "content")
        content["purpose"] = slide.get("purpose", "")

        results.append(content)

    return results