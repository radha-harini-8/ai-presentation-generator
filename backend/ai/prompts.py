"""
Prompt templates for every stage of the hierarchical generation pipeline.
Kept separate from the generator logic so prompts can be tuned independently.
"""

AUDIENCE_GUIDANCE = {
    "School Students": "Use very simple vocabulary, short sentences, everyday analogies, and easy practical examples. Avoid jargon entirely.",
    "College Students": "Use moderate technical detail with academic framing. Include definitions and illustrative examples suited to undergraduate study.",
    "Professionals": "Use industry-oriented language focused on practical applications, business impact, and real-world use cases.",
    "Technical Audience": "Use precise technical terminology. Include algorithms, architecture, implementation details, and technical trade-offs.",
    "General Audience": "Use clear, accessible language with minimal jargon, relatable examples, and a friendly explanatory tone.",
}

DIFFICULTY_GUIDANCE = {
    "Beginner": "Explain every concept from first principles in simple terms. Avoid unexplained jargon.",
    "Intermediate": "Include moderate technical depth. Assume basic familiarity with the subject but explain non-obvious concepts.",
    "Advanced": "Include technical details, algorithms, architecture, known limitations, and advanced/edge-case examples. Assume strong background knowledge.",
}

STYLE_GUIDANCE = {
    "Academic": "formal, citation-aware tone, structured like a lecture, definitions before examples",
    "Professional": "polished, business-appropriate tone, concise and outcome-focused",
    "Simple": "plain, friendly, minimal jargon, short sentences",
    "Technical": "precise, detail-dense, engineering-oriented",
    "Minimal": "very concise, sparse text, high-level statements only",
}


def _settings_block(topic, description, audience, difficulty, style, num_slides,
                     duration_minutes, include_examples, seconds_per_slide) -> str:
    return f"""
Topic: {topic}
Description: {description or "(none provided)"}
Audience: {audience} — {AUDIENCE_GUIDANCE.get(audience, "")}
Difficulty: {difficulty} — {DIFFICULTY_GUIDANCE.get(difficulty, "")}
Presentation style: {style} — {STYLE_GUIDANCE.get(style, "")}
Number of slides required: {num_slides}
Total duration: {duration_minutes} minutes ({seconds_per_slide:.0f} seconds of speaking time per slide)
Include worked examples: {"Yes" if include_examples else "No"}
""".strip()


def objectives_prompt(topic, description, audience, difficulty, style, num_slides,
                       duration_minutes, include_examples, seconds_per_slide, context) -> str:
    settings_block = _settings_block(topic, description, audience, difficulty, style,
                                      num_slides, duration_minutes, include_examples, seconds_per_slide)
    return f"""You are stage 1 of a presentation-generation pipeline: OBJECTIVES.

{settings_block}

Relevant source material retrieved from the user's uploaded documents (prioritize this information,
do not contradict it; if it's empty, rely on general knowledge):
{context}

Generate 3 to 6 clear learning/presentation objectives for this presentation, tailored to the
audience and difficulty above.

Respond with ONLY valid JSON in this exact shape, nothing else:
{{
  "presentation_title": "string",
  "objectives": ["string", "string", "..."]
}}"""


def outline_prompt(topic, description, audience, difficulty, style, num_slides,
                    duration_minutes, include_examples, seconds_per_slide, context,
                    presentation_title, objectives) -> str:
    settings_block = _settings_block(topic, description, audience, difficulty, style,
                                      num_slides, duration_minutes, include_examples, seconds_per_slide)
    return f"""You are stage 2 of a presentation-generation pipeline: OUTLINE.

{settings_block}

Presentation title: {presentation_title}
Objectives: {objectives}

Relevant source material (prioritize this; avoid hallucinating facts that contradict it):
{context}

Create a logical, well-sequenced outline with EXACTLY {num_slides} slides. The first slide should be
a title/intro slide and the last slide should be a conclusion/summary slide. Each slide needs a
clear purpose that builds logically on the previous one, avoiding repetition.

Respond with ONLY valid JSON in this exact shape, nothing else:
{{
  "presentation_title": "{presentation_title}",
  "objectives": {objectives},
  "slides": [
    {{"slide_number": 1, "title": "string", "purpose": "string", "layout": "title"}},
    {{"slide_number": 2, "title": "string", "purpose": "string", "layout": "content"}}
  ]
}}

The "layout" field for each slide must be one of: "title", "content", "two_column", "example", "conclusion".
Slide 1 must use "title" and the last slide must use "conclusion"."""


def slide_content_prompt(topic, audience, difficulty, style, include_examples,
                          seconds_per_slide, context, slide_title, slide_purpose, slide_layout,
                          slide_number, total_slides) -> str:
    return f"""You are stage 3 of a presentation-generation pipeline: SLIDE CONTENT for one slide.

Overall topic: {topic}
Audience: {audience} — {AUDIENCE_GUIDANCE.get(audience, "")}
Difficulty: {difficulty} — {DIFFICULTY_GUIDANCE.get(difficulty, "")}
Style: {style} — {STYLE_GUIDANCE.get(style, "")}
This is slide {slide_number} of {total_slides}. Layout type: {slide_layout}.
Slide title: {slide_title}
Slide purpose: {slide_purpose}
Include a worked example on this slide if appropriate: {"Yes" if include_examples else "No"}

Relevant source material for this slide (prioritize this; do not contradict it):
{context}

Generate concise slide content. Bullets must be short phrases suitable for a slide — NEVER full
paragraphs. Provide 3 to 6 bullets.

Respond with ONLY valid JSON in this exact shape, nothing else:
{{
  "slide_number": {slide_number},
  "title": "{slide_title}",
  "content": ["short bullet", "short bullet", "short bullet"],
  "example": "one concise example, or empty string if not applicable",
  "sources": ["filename.pdf"]
}}
The "sources" array should list filenames from the source material above that this content draws on,
or an empty array if none were used."""


def speaker_notes_prompt(topic, audience, difficulty, style, seconds_per_slide,
                          slide_title, slide_content, slide_example, is_first, is_last) -> str:
    transition_note = (
        "This is the opening slide — start with a hook that introduces the topic."
        if is_first else
        "This is the closing slide — wrap up with a clear summary and closing statement."
        if is_last else
        "Include a brief natural transition from the previous slide's idea into this one."
    )
    word_target = max(40, int(seconds_per_slide * 2.3))  # ~140 wpm speaking pace estimate

    return f"""You are stage 5 of a presentation-generation pipeline: SPEAKER NOTES.

Topic: {topic}
Audience: {audience} — {AUDIENCE_GUIDANCE.get(audience, "")}
Difficulty: {difficulty}
Style: {style}
Target speaking time for this slide: approximately {seconds_per_slide:.0f} seconds
(roughly {word_target} words of natural spoken narration).

Slide title: {slide_title}
Slide bullets: {slide_content}
Slide example: {slide_example or "(none)"}
{transition_note}

Write natural, spoken-style speaker notes that:
- Explain the slide in full sentences (do NOT just repeat the bullets verbatim)
- Expand on each bullet point with context
- Weave in the example naturally if one is provided
- Sound like something a presenter would actually say out loud
- Match the target speaking duration above

Respond with ONLY valid JSON in this exact shape, nothing else:
{{
  "speaker_notes": "string containing the full spoken narration"
}}"""


def quality_control_prompt(presentation_title, audience, difficulty, style, slides_summary) -> str:
    return f"""You are stage 6 of a presentation-generation pipeline: QUALITY CONTROL.

Presentation: {presentation_title}
Audience: {audience}
Difficulty: {difficulty}
Style: {style}

Full slide-by-slide summary (title + bullets + notes length) to review:
{slides_summary}

Evaluate the presentation as a whole for:
1. Logical flow between slides
2. Correct slide count / structure (title slide first, conclusion last)
3. Repeated or overlapping information between slides
4. Missing important concepts for this topic
5. Excessive text on any slide (slides should be concise, not paragraphs)
6. Audience suitability
7. Difficulty-level suitability
8. Speaker-note quality and completeness
9. Overall coherence

Respond with ONLY valid JSON in this exact shape, nothing else:
{{
  "quality_score": 8.5,
  "issues": ["issue description", "..."],
  "suggestions": ["suggestion", "..."],
  "slides_to_regenerate": [5, 7]
}}
"slides_to_regenerate" should list slide_number values that have serious enough issues to warrant
regenerating that slide's content (empty array if none do). Only flag slides with real problems —
do not flag slides just to have something to flag."""
