"""ABA Model Rule 7.1 compliance scanner for legal content.

Flags language patterns that create misleading impressions about
legal services, outcomes, or qualifications.
"""

from __future__ import annotations

import re

from app.models import ComplianceFlag, ExtractedContent


# ── Rule 7.1 risk patterns ──────────────────────────────────────────────────
# Each tuple: (pattern, severity, rule_ref, explanation, suggested_fix)

RULE_71_PATTERNS: list[tuple[str, str, str, str, str]] = [
    # Guarantee language
    (
        r"\b(we\s+)?guarantee[ds]?\b",
        "high",
        "Rule 7.1(a)",
        "Guarantee language about legal outcomes is misleading. "
        "No attorney can guarantee results.",
        'Remove "guarantee" or replace with "we work to achieve the best possible outcome."',
    ),
    # Unqualified "best" / superlative claims
    (
        r"\b(best|top|#\s*1|number\s*one|premier|leading)\s+(lawyer|attorney|firm|law\s*firm)\b",
        "high",
        "Rule 7.1(a)",
        "Superlative claims about legal services require substantiation "
        "and can mislead potential clients.",
        'Add substantiation (e.g., award name, ranking source) or soften to "experienced" / "dedicated."',
    ),
    # "Expert" without substantiation
    (
        r"\b(expert|specialist)\s+(in|at|on)\b",
        "medium",
        "Rule 7.1(a)",
        '"Expert" or "specialist" claims may be misleading unless '
        "supported by board certification or recognized specialization.",
        "Replace with specific credentials or use "
        '"experienced in" / "focused on" instead.',
    ),
    # Cherry-picked results without disclaimer
    (
        r"(\$[\d,]+(?:\.\d+)?\s*(million|thousand|settlement|verdict))",
        "high",
        "Rule 7.1(b)",
        "Specific dollar amounts for case results can mislead if presented "
        "without a disclaimer that results vary.",
        'Add: "Past results do not guarantee future outcomes. '
        'Every case is different."',
    ),
    # "No fee" / "free" without conditions
    (
        r"\b(no\s+fee|free\s+consult|free\s+case\s+review|no\s+cost|pay\s+nothing)\b",
        "medium",
        "Rule 7.1(b)",
        '"No fee" claims need conditions stated: '
        "contingency basis, costs vs. fees, what's actually free.",
        'Add conditions: "No attorney fee unless we recover compensation. '
        'Client may be responsible for case costs."',
    ),
    # "You will win / recover / get"
    (
        r"\byou\s+(will|are\s+going\s+to)\s+(win|recover|get|receive|obtain)\b",
        "high",
        "Rule 7.1(a)",
        "Promising specific outcomes is misleading. "
        "Outcomes depend on facts and law.",
        'Replace with "you may be entitled to" or '
        '"we will pursue the maximum recovery available."',
    ),
    # "Always" / "never" about legal outcomes
    (
        r"\b(always|never)\s+(win|lose|recover|get|result|succeed)\b",
        "high",
        "Rule 7.1(a)",
        "Absolute outcome language is inherently misleading in legal contexts.",
        "Replace with conditional language that acknowledges case-specific factors.",
    ),
    # Testimonial without disclaimer
    (
        r"\b(client\s+review|testimonial|what\s+our\s+clients\s+say)\b",
        "medium",
        "Rule 7.1(b)",
        "Client testimonials may create unjustified expectations about results. "
        "Many jurisdictions require disclaimers.",
        'Add: "Client testimonials reflect individual experiences and do not '
        'guarantee similar outcomes."',
    ),
    # Implying special relationship with courts/judges
    (
        r"\b(connections?\s+(?:to|with)\s+(?:the\s+)?(?:court|judge)|inside\s+knowledge)\b",
        "high",
        "Rule 7.1(a) / Rule 8.4",
        "Implying special influence with courts or judges is misleading "
        "and may violate ethics rules.",
        "Remove any language implying special access or influence.",
    ),
]


def scan_compliance(content: ExtractedContent) -> list[ComplianceFlag]:
    """Scan all content sections for Rule 7.1 violations."""
    flags: list[ComplianceFlag] = []

    for section in content.sections:
        text = section.text
        heading = section.heading or f"Section {section.index + 1}"

        for pattern, severity, rule, explanation, fix in RULE_71_PATTERNS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                context_start = max(0, match.start() - 50)
                context_end = min(len(text), match.end() + 50)
                context = "..." + text[context_start:context_end] + "..."

                flags.append(
                    ComplianceFlag(
                        rule=rule,
                        severity=severity,
                        text=context.strip(),
                        location=heading,
                        explanation=explanation,
                        fix=fix,
                    )
                )

    # Deduplicate by matched text
    seen: set[str] = set()
    unique: list[ComplianceFlag] = []
    for f in flags:
        key = f.text[:80]
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique
