"""
Thin, defensive wrapper around the Gemini API.

Responsibilities:
- Read the API key/model from environment config (never hard-coded).
- Send a prompt and get back text.
- Extract + validate JSON from the model's response.
- Retry once on invalid JSON before giving up.
- Translate low-level SDK errors into friendly, app-specific exceptions.
"""
import time 
import json
import re
from typing import Any, Optional

from backend.config import settings


class GeminiError(Exception):
    """Base class for friendly, user-facing Gemini errors."""


class GeminiAuthError(GeminiError):
    pass


class GeminiQuotaError(GeminiError):
    pass


class GeminiResponseError(GeminiError):
    pass


def _client():
    if not settings.GEMINI_API_KEY:
        raise GeminiAuthError(
            "AI service is not configured. Please set GEMINI_API_KEY in your .env file."
        )
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiError(
            "The google-genai package is not installed. Run: pip install google-genai"
        ) from exc

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _call_gemini(prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.7) -> str:
    """Low level call. Returns raw text. Raises GeminiError subclasses on failure."""
    time.sleep(2)
    try:
        client = _client()
        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction
        config["temperature"] = temperature

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        text = getattr(response, "text", None)
        if not text:
            raise GeminiResponseError("AI service returned an empty response. Please try again.")
        return text

    except GeminiError:
        raise
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "api key" in message or "unauthorized" in message or "permission" in message:
            raise GeminiAuthError(
                "AI service rejected the API key. Please check GEMINI_API_KEY in your .env file."
            ) from exc
        if "quota" in message or "rate limit" in message or "429" in message:
            raise GeminiQuotaError(
                "AI service quota exceeded. Please wait a moment and try again."
            ) from exc
        if "timeout" in message or "deadline" in message:
            raise GeminiError(
                "AI service timed out. Please try again."
            ) from exc
        raise GeminiError(
            "AI service is temporarily unavailable. Please try again."
        ) from exc


def _extract_json(raw_text: str) -> Any:
    """
    Try progressively looser strategies to pull valid JSON out of a model response
    that may include markdown fences, preamble text, etc.
    """
    text = raw_text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: grab the largest {...} or [...] span
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise GeminiResponseError("AI service returned a response that could not be parsed as JSON.")


def generate_json(
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 0.6,
    max_retries: int = 2,
) -> Any:
    """
    Call Gemini and parse the response as JSON, retrying on invalid JSON.
    Never raises a raw SDK exception - only GeminiError subclasses.
    """
    last_error: Optional[Exception] = None
    strict_prompt = prompt

    for attempt in range(max_retries + 1):
        try:
            raw = _call_gemini(strict_prompt, system_instruction=system_instruction, temperature=temperature)
            return _extract_json(raw)
        except GeminiResponseError as exc:
            last_error = exc
            # Tighten the instruction and retry
            strict_prompt = (
                prompt
                + "\n\nIMPORTANT: Your previous response could not be parsed as JSON. "
                  "Respond with ONLY valid JSON. No markdown fences, no commentary, no preamble."
            )
            continue
        except (GeminiAuthError, GeminiQuotaError):
            raise  # no point retrying these

    raise last_error or GeminiResponseError("AI service failed to return valid JSON.")


def generate_text(prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.7) -> str:
    """Call Gemini and return plain text (used for non-JSON generations if needed)."""
    return _call_gemini(prompt, system_instruction=system_instruction, temperature=temperature)
