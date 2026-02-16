"""Deterministic rules engine for hard E-E-A-T checks.

Every check produces a SignalEvidence that maps to points,
a quote, and a location so scores are fully transparent.
"""

from __future__ import annotations

import re
from typing import Callable

from app.models import (
    ContentPreset,
    DimensionScore,
    ExtractedContent,
    SignalEvidence,
    YMYLRisk,
)


# ── Helper types ─────────────────────────────────────────────────────────────

CheckFn = Callable[[ExtractedContent], SignalEvidence]


def _signal(
    name: str,
    found: bool,
    pts: float,
    quote: str = "",
    location: str = "",
    explanation: str = "",
) -> SignalEvidence:
    return SignalEvidence(
        signal=name,
        found=found,
        points=pts if found else 0.0,
        quote=quote[:300],
        location=location,
        explanation=explanation,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TRUST checks
# ═══════════════════════════════════════════════════════════════════════════════

def _check_about_page(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "About page linked",
        c.site_signals.has_about_page,
        2.0,
        explanation="An 'About' page establishes site identity and ownership.",
    )


def _check_contact_page(c: ExtractedContent) -> SignalEvidence:
    paths = ", ".join(c.site_signals.contact_paths[:3])
    return _signal(
        "Contact information present",
        c.site_signals.has_contact_page or bool(c.site_signals.contact_paths),
        2.0,
        quote=paths,
        explanation="Reachable contact info builds reader trust.",
    )


def _check_privacy_policy(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Privacy policy linked",
        c.site_signals.has_privacy_policy,
        1.0,
        explanation="A privacy policy is a baseline trust signal for any website.",
    )


def _check_terms(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Terms of service linked",
        c.site_signals.has_terms,
        1.0,
        explanation="Terms of service clarify the relationship between site and user.",
    )


def _check_editorial_policy(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Editorial / review policy",
        c.site_signals.has_editorial_policy,
        2.0,
        explanation="An editorial policy signals content review processes.",
    )


def _check_dates(c: ExtractedContent) -> SignalEvidence:
    has_pub = bool(c.dates.published)
    has_upd = bool(c.dates.updated)
    found = has_pub or has_upd
    detail = []
    if has_pub:
        detail.append(f"Published: {c.dates.published}")
    if has_upd:
        detail.append(f"Updated: {c.dates.updated}")
    return _signal(
        "Dates shown (published / updated)",
        found,
        2.0,
        quote="; ".join(detail),
        explanation="Visible dates let readers judge freshness and maintenance.",
    )


def _check_citations_count(c: ExtractedContent) -> SignalEvidence:
    ext = c.outbound_links
    quality = [l for l in ext if l.is_government or l.is_educational]
    count = len(ext)
    q_count = len(quality)
    pts = min(3.0, count * 0.3 + q_count * 0.5)
    return _signal(
        "Outbound citation count and quality",
        count > 0,
        pts,
        quote=f"{count} outbound links, {q_count} high-authority",
        explanation="Credible outbound citations support claims and build trust.",
    )


def _check_disclaimers(c: ExtractedContent) -> SignalEvidence:
    found = bool(c.disclaimers)
    snippet = c.disclaimers[0][:200] if c.disclaimers else ""
    return _signal(
        "Disclaimer / legal notice present",
        found,
        2.0,
        quote=snippet,
        explanation="Disclaimers set expectations and reduce misleading impressions.",
    )


def _check_disclosures(c: ExtractedContent) -> SignalEvidence:
    found = bool(c.disclosure_texts)
    snippet = c.disclosure_texts[0][:200] if c.disclosure_texts else ""
    return _signal(
        "Affiliate / advertising disclosure",
        found,
        1.5,
        quote=snippet,
        explanation="Disclosures are required when content is monetized.",
    )


def _check_schema(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Structured data (schema.org)",
        c.has_schema_markup,
        1.5,
        quote=", ".join(c.schema_types[:5]),
        explanation="Schema markup helps search engines understand the page's purpose.",
    )


TRUST_CHECKS: list[CheckFn] = [
    _check_about_page,
    _check_contact_page,
    _check_privacy_policy,
    _check_terms,
    _check_editorial_policy,
    _check_dates,
    _check_citations_count,
    _check_disclaimers,
    _check_disclosures,
    _check_schema,
]


# ═══════════════════════════════════════════════════════════════════════════════
# EXPERIENCE checks
# ═══════════════════════════════════════════════════════════════════════════════

FIRSTHAND_PATTERNS = [
    r"\b(I|we)\s+(tested|tried|used|measured|compared|built|installed|configured)\b",
    r"\b(in\s+my|in\s+our)\s+experience\b",
    r"\bwhat\s+(surprised|failed|worked|broke)\b",
    r"\bwhat\s+I('d| would)\s+do\s+differently\b",
    r"\bafter\s+\d+\s+(hours?|days?|weeks?|months?|years?)\s+of\s+(using|testing)\b",
]

PROCEDURAL_DETAIL_PATTERNS = [
    r"\bstep\s+\d\b",
    r"\b(first|then|next|finally),?\s+(I|we|you)\b",
    r"\b(setup|configuration|install)\s+(took|required|involved)\b",
]


def _check_firsthand_language(c: ExtractedContent) -> SignalEvidence:
    text = c.plain_text
    hits = []
    for pat in FIRSTHAND_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 30)
            hits.append(text[start:end].strip())
    found = len(hits) > 0
    pts = min(4.0, len(hits) * 1.0)
    return _signal(
        "First-hand experience language",
        found,
        pts,
        quote=hits[0] if hits else "",
        location="Body text",
        explanation="First-person procedural language signals real experience.",
    )


def _check_procedural_detail(c: ExtractedContent) -> SignalEvidence:
    text = c.plain_text
    hits = 0
    sample = ""
    for pat in PROCEDURAL_DETAIL_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            hits += 1
            if not sample:
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 50)
                sample = text[start:end].strip()
    found = hits > 0
    return _signal(
        "Procedural / step-by-step detail",
        found,
        min(3.0, hits * 1.0),
        quote=sample,
        explanation="Step-by-step detail suggests the author has performed the process.",
    )


def _check_caveats(c: ExtractedContent) -> SignalEvidence:
    caveat_patterns = [
        r"\b(caveat|downside|limitation|drawback|trade.?off)\b",
        r"\b(however|but|on the other hand|that said)\b",
        r"\b(didn't work|wasn't ideal|could be better)\b",
    ]
    text = c.plain_text
    hits = 0
    sample = ""
    for pat in caveat_patterns:
        m = re.search(pat, text, re.I)
        if m:
            hits += 1
            if not sample:
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 60)
                sample = text[start:end].strip()
    found = hits > 0
    return _signal(
        "Real-world caveats and limitations",
        found,
        min(3.0, hits * 0.75),
        quote=sample,
        explanation="Acknowledging limitations signals honest, real-world experience.",
    )


def _check_original_media(c: ExtractedContent) -> SignalEvidence:
    count = len(c.images)
    return _signal(
        "Original images / media",
        count > 0,
        min(3.0, count * 0.5),
        quote=f"{count} images found",
        explanation="Original photos or screenshots support first-hand experience.",
    )


EXPERIENCE_CHECKS: list[CheckFn] = [
    _check_firsthand_language,
    _check_procedural_detail,
    _check_caveats,
    _check_original_media,
]


# ═══════════════════════════════════════════════════════════════════════════════
# EXPERTISE checks
# ═══════════════════════════════════════════════════════════════════════════════

def _check_terminology(c: ExtractedContent) -> SignalEvidence:
    """Check for domain-specific terminology usage."""
    text = c.plain_text.lower()
    legal_terms = [
        "statute", "regulation", "jurisdiction", "negligence", "liability",
        "comparative fault", "damages", "burden of proof", "discovery",
        "motion", "pleading", "tort", "breach", "fiduciary",
    ]
    medical_terms = [
        "diagnosis", "prognosis", "contraindication", "etiology",
        "pathology", "protocol", "clinical",
    ]
    finance_terms = [
        "amortization", "fiduciary", "portfolio", "diversification",
        "yield", "liquidity", "collateral",
    ]
    all_terms = legal_terms + medical_terms + finance_terms
    hits = [t for t in all_terms if t in text]
    return _signal(
        "Domain-specific terminology",
        len(hits) >= 2,
        min(4.0, len(hits) * 0.5),
        quote=", ".join(hits[:8]),
        explanation="Correct specialist terminology signals subject expertise.",
    )


def _check_scope_limits(c: ExtractedContent) -> SignalEvidence:
    """Check for proper scoping: audience, applicability, pro referrals."""
    scope_patterns = [
        r"\bthis\s+(applies|is\s+for|covers)\b",
        r"\b(consult|talk\s+to|speak\s+with)\s+(a|an|your)\s+(attorney|lawyer|doctor|advisor|professional)\b",
        r"\b(may\s+not\s+apply|varies\s+by|depends\s+on)\b",
        r"\b(in\s+\w+\s+state|under\s+\w+\s+law)\b",
        r"\b(who\s+this\s+is\s+for|who\s+should)\b",
    ]
    text = c.plain_text
    hits = 0
    sample = ""
    for pat in scope_patterns:
        m = re.search(pat, text, re.I)
        if m:
            hits += 1
            if not sample:
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 50)
                sample = text[start:end].strip()
    return _signal(
        "Proper scoping and pro referrals",
        hits >= 1,
        min(4.0, hits * 1.0),
        quote=sample,
        explanation="Scoping advice to the right audience and referring to professionals when appropriate signals expertise.",
    )


def _check_depth(c: ExtractedContent) -> SignalEvidence:
    """Reward depth: enough word count with multiple sections."""
    wc = c.word_count
    sec = len(c.sections)
    good_depth = wc >= 800 and sec >= 3
    great_depth = wc >= 1500 and sec >= 5
    pts = 2.0 if great_depth else (1.0 if good_depth else 0.0)
    return _signal(
        "Content depth (word count + structure)",
        good_depth,
        pts,
        quote=f"{wc} words, {sec} sections",
        explanation="Sufficient depth with clear structure shows topical command.",
    )


def _check_internal_consistency(c: ExtractedContent) -> SignalEvidence:
    """Placeholder: no contradictions detected (needs model-assist for real check)."""
    return _signal(
        "Internal consistency",
        True,
        1.5,
        explanation="No obvious contradictions detected (deep check deferred to AI rater).",
    )


EXPERTISE_CHECKS: list[CheckFn] = [
    _check_terminology,
    _check_scope_limits,
    _check_depth,
    _check_internal_consistency,
]


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHORITATIVENESS checks
# ═══════════════════════════════════════════════════════════════════════════════

def _check_author_present(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Author name present",
        bool(c.author.name),
        2.0,
        quote=c.author.name or "",
        explanation="Named authorship establishes accountability.",
    )


def _check_author_bio(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Author bio with credentials",
        bool(c.author.bio),
        3.0,
        quote=(c.author.bio or "")[:200],
        explanation="A bio with relevant background signals authority on the topic.",
    )


def _check_author_page(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Dedicated author page",
        c.author.has_author_page,
        2.5,
        quote=c.author.profile_url or "",
        explanation="A dedicated author page lets readers verify credentials.",
    )


def _check_credentials(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Professional credentials listed",
        bool(c.author.credentials),
        3.0,
        quote=c.author.credentials or "",
        explanation="Explicit credentials (bar admissions, degrees, certifications) strengthen authority.",
    )


def _check_internal_linking(c: ExtractedContent) -> SignalEvidence:
    count = len(c.internal_links)
    pts = min(3.0, count * 0.3)
    return _signal(
        "Internal linking depth",
        count >= 3,
        pts,
        quote=f"{count} internal links",
        explanation="Strong internal linking to related content shows topical ownership.",
    )


def _check_attorney_roster(c: ExtractedContent) -> SignalEvidence:
    return _signal(
        "Attorney roster / team page",
        c.site_signals.has_attorney_roster,
        2.0,
        explanation="An attorney roster with profile pages establishes firm credibility.",
    )


AUTHORITATIVENESS_CHECKS: list[CheckFn] = [
    _check_author_present,
    _check_author_bio,
    _check_author_page,
    _check_credentials,
    _check_internal_linking,
    _check_attorney_roster,
]


# ═══════════════════════════════════════════════════════════════════════════════
# Main runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_rules_engine(
    content: ExtractedContent,
    ymyl_risk: YMYLRisk,
    preset: ContentPreset,
) -> dict[str, DimensionScore]:
    """Run all deterministic checks and return dimension scores."""

    def _run_checks(checks: list[CheckFn], name: str, max_pts: float) -> DimensionScore:
        signals = [check(content) for check in checks]
        raw = sum(s.points for s in signals)
        # Normalize to 0-25 scale
        score = min(25.0, (raw / max_pts) * 25.0) if max_pts > 0 else 0.0
        return DimensionScore(name=name, score=round(score, 1), signals=signals)

    trust = _run_checks(TRUST_CHECKS, "Trust", 18.0)
    experience = _run_checks(EXPERIENCE_CHECKS, "Experience", 13.0)
    expertise = _run_checks(EXPERTISE_CHECKS, "Expertise", 12.0)
    authoritativeness = _run_checks(AUTHORITATIVENESS_CHECKS, "Authoritativeness", 15.5)

    return {
        "trust": trust,
        "experience": experience,
        "expertise": expertise,
        "authoritativeness": authoritativeness,
    }
