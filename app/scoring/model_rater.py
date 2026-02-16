"""AI-assisted model rater for soft E-E-A-T checks.

Uses OpenAI to evaluate nuanced quality signals that can't be
captured by regex or heuristics: lived experience, overconfidence,
claim-citation mismatch, and helpful framing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models import (
    ContentPreset,
    DimensionScore,
    ExtractedContent,
    SignalEvidence,
    YMYLRisk,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an expert content quality rater trained on Google's Search Quality Rater Guidelines.
Your job is to evaluate web content for E-E-A-T signals (Experience, Expertise, Authoritativeness, Trust).

You MUST return valid JSON only. No markdown, no commentary outside the JSON.
"""

RATING_PROMPT_TEMPLATE = """\
Evaluate the following content for E-E-A-T quality signals.

CONTENT TITLE: {title}
AUTHOR: {author}
TOPIC RISK: {ymyl_risk} (YMYL level)
CONTENT TYPE: {preset}
WORD COUNT: {word_count}

--- CONTENT (first 6000 chars) ---
{content_text}
--- END CONTENT ---

For each of the 4 E-E-A-T dimensions, provide 2-3 soft-check signals.
Each signal should have:
- "signal": a short name for what you checked
- "found": true/false
- "points": 0.0 to 4.0 (how strong the signal is)
- "quote": exact quote from the content that supports your judgment (or "" if not found)
- "explanation": 1-2 sentences explaining your rating

Return this exact JSON structure:
{{
  "experience": {{
    "signals": [...],
    "summary": "1-2 sentence overall experience assessment"
  }},
  "expertise": {{
    "signals": [...],
    "summary": "1-2 sentence overall expertise assessment"
  }},
  "authoritativeness": {{
    "signals": [...],
    "summary": "1-2 sentence overall authoritativeness assessment"
  }},
  "trust": {{
    "signals": [...],
    "summary": "1-2 sentence overall trust assessment"
  }}
}}

Focus on:
- Experience: Does this read like someone who actually did this? Look for lived detail, real caveats, workflow descriptions.
- Expertise: Is the information accurate, well-scoped, and appropriately nuanced? Does it handle edge cases?
- Authoritativeness: Does the author/site appear to be a recognized source on this topic?
- Trust: Is the content honest, well-sourced, and careful with sensitive claims? Does it avoid harmful overconfidence?

For {ymyl_risk}-risk content, apply stricter standards for Trust and Expertise.
"""


async def run_model_rater(
    content: ExtractedContent,
    ymyl_risk: YMYLRisk,
    preset: ContentPreset,
) -> dict[str, DimensionScore] | None:
    """Call the AI model to evaluate soft E-E-A-T signals.

    Returns None if the API key is not configured or the call fails.
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not set — skipping model rater.")
        return None

    text_sample = content.plain_text[:6000]
    prompt = RATING_PROMPT_TEMPLATE.format(
        title=content.title or "(untitled)",
        author=content.author.name or "(no author found)",
        ymyl_risk=ymyl_risk.value,
        preset=preset.value,
        word_count=content.word_count,
        content_text=text_sample,
    )

    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return _parse_model_response(data)
    except Exception:
        logger.exception("Model rater failed")
        return None


def _parse_model_response(data: dict[str, Any]) -> dict[str, DimensionScore]:
    result: dict[str, DimensionScore] = {}
    for dim in ["experience", "expertise", "authoritativeness", "trust"]:
        block = data.get(dim, {})
        signals = []
        for s in block.get("signals", []):
            signals.append(
                SignalEvidence(
                    signal=s.get("signal", ""),
                    found=s.get("found", False),
                    points=min(4.0, float(s.get("points", 0))),
                    quote=str(s.get("quote", ""))[:300],
                    explanation=str(s.get("explanation", "")),
                )
            )
        raw_pts = sum(s.points for s in signals)
        max_possible = len(signals) * 4.0 if signals else 1.0
        score = min(25.0, (raw_pts / max_possible) * 25.0) if max_possible > 0 else 0.0
        result[dim] = DimensionScore(
            name=dim.capitalize(),
            score=round(score, 1),
            signals=signals,
            summary=block.get("summary", ""),
        )
    return result
