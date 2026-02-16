"""Claim detection and citation auditing.

Identifies factual claims, statistics, directives, and comparative assertions,
then grades each claim against nearby citations.
"""

from __future__ import annotations

import re

from app.models import (
    CitationAudit,
    Claim,
    ClaimType,
    EvidenceGrade,
    ExtractedContent,
    LinkInfo,
)


# ── Claim detection patterns ────────────────────────────────────────────────

STAT_PATTERNS = [
    r"\d+\s*%",
    r"\$[\d,]+",
    r"studies?\s+show",
    r"research\s+(shows?|indicates?|suggests?|found)",
    r"according\s+to",
    r"data\s+(shows?|indicates?|suggests?)",
    r"survey",
    r"on\s+average",
    r"approximately\s+\d",
    r"estimated\s+\d",
]

LEGAL_DIRECTIVE_PATTERNS = [
    r"statute\s+of\s+limitations?\s+is\s+\d",
    r"you\s+(must|have\s+to|are\s+required\s+to)\s+file",
    r"deadline\s+(is|of)\s+\d",
    r"within\s+\d+\s+(days?|months?|years?)",
    r"notice\s+requirement",
    r"you\s+(can|may)\s+sue",
    r"liable\s+for",
    r"entitled\s+to",
    r"burden\s+of\s+proof",
    r"comparative\s+fault",
    r"contributory\s+negligence",
]

MEDICAL_DIRECTIVE_PATTERNS = [
    r"you\s+should\s+(take|stop|avoid|consult)",
    r"recommended\s+dosage",
    r"side\s+effects?\s+include",
    r"(safe|unsafe)\s+to",
]

OUTCOME_PATTERNS = [
    r"you\s+will\s+(get|receive|win|recover|obtain)",
    r"guaranteed?\s+",
    r"always\s+results?\s+in",
    r"average\s+settlement",
    r"typical\s+(recovery|verdict|settlement)",
    r"you\s+can\s+expect\s+to\s+(receive|recover)",
]

COMPARATIVE_PATTERNS = [
    r"\b(best|top|most|leading|#\s*1|number\s*one|premier)\b",
    r"better\s+than",
    r"more\s+effective\s+than",
    r"outperforms?",
    r"superior\s+to",
]

PROCEDURAL_PATTERNS = [
    r"(first|then|next),?\s+you\s+(must|should|need\s+to|will)",
    r"step\s+\d",
    r"file\s+(a|the|your)\s+",
    r"serve\s+(the|a)\s+",
    r"appeal\s+(the|a|within)",
]


def _match_claim_type(sentence: str) -> list[tuple[ClaimType, str]]:
    """Return all claim types that match a sentence, with the matched text."""
    s = sentence.lower()
    hits: list[tuple[ClaimType, str]] = []

    for pat in STAT_PATTERNS:
        m = re.search(pat, s)
        if m:
            hits.append((ClaimType.STATISTIC, m.group()))
            break

    for pat in LEGAL_DIRECTIVE_PATTERNS:
        m = re.search(pat, s)
        if m:
            hits.append((ClaimType.LEGAL_DIRECTIVE, m.group()))
            break

    for pat in MEDICAL_DIRECTIVE_PATTERNS:
        m = re.search(pat, s)
        if m:
            hits.append((ClaimType.MEDICAL_DIRECTIVE, m.group()))
            break

    for pat in OUTCOME_PATTERNS:
        m = re.search(pat, s)
        if m:
            hits.append((ClaimType.OUTCOME, m.group()))
            break

    for pat in COMPARATIVE_PATTERNS:
        m = re.search(pat, s)
        if m:
            hits.append((ClaimType.COMPARATIVE, m.group()))
            break

    for pat in PROCEDURAL_PATTERNS:
        m = re.search(pat, s)
        if m:
            hits.append((ClaimType.PROCEDURAL, m.group()))
            break

    return hits


def _sentences(text: str) -> list[str]:
    """Naive sentence splitter."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def _grade_claim(
    sentence: str,
    section_links: list[LinkInfo],
) -> tuple[EvidenceGrade, str | None, str]:
    """Grade a claim against links in the same section."""
    if not section_links:
        return EvidenceGrade.UNSUPPORTED, None, "No citation found near this claim."

    # Check quality of nearest link
    best_link = section_links[0]
    if best_link.is_government or best_link.is_educational:
        return (
            EvidenceGrade.SUPPORTED,
            best_link.url,
            f"Supported by authoritative source ({best_link.domain}).",
        )

    trusted_domains = {"nih.gov", "cdc.gov", "who.int", "law.cornell.edu", "uscourts.gov"}
    if best_link.domain in trusted_domains:
        return (
            EvidenceGrade.SUPPORTED,
            best_link.url,
            f"Supported by trusted source ({best_link.domain}).",
        )

    low_trust_indicators = ["blog", "forum", "reddit", "quora", "medium.com", "wikipedia"]
    if any(lt in best_link.domain or lt in best_link.url for lt in low_trust_indicators):
        return (
            EvidenceGrade.WEAKLY_SUPPORTED,
            best_link.url,
            f"Citation present but source may lack authority ({best_link.domain}).",
        )

    return (
        EvidenceGrade.SUPPORTED,
        best_link.url,
        f"Citation present ({best_link.domain}).",
    )


def _is_overbroad(sentence: str) -> bool:
    """Check if a claim uses overbroad language that needs qualification."""
    overbroad = [
        r"\balways\b", r"\bnever\b", r"\beveryone\b", r"\bno one\b",
        r"\bguaranteed?\b", r"\b100\s*%\b", r"\ball\s+cases?\b",
        r"\bwithout\s+exception\b",
    ]
    s = sentence.lower()
    return any(re.search(p, s) for p in overbroad)


def audit_claims(content: ExtractedContent) -> CitationAudit:
    """Run the full claim detection and evidence grading pipeline."""
    all_claims: list[Claim] = []
    low_trust: set[str] = set()

    # Build a per-section link index
    section_links: dict[int, list[LinkInfo]] = {}
    for link in content.outbound_links:
        # Assign links to the closest section heuristically
        for sec in content.sections:
            if link.anchor_text and link.anchor_text.lower() in sec.text.lower():
                section_links.setdefault(sec.index, []).append(link)

    for section in content.sections:
        sents = _sentences(section.text)
        links_nearby = section_links.get(section.index, [])

        for sentence in sents:
            matches = _match_claim_type(sentence)
            if not matches:
                continue

            for claim_type, _matched in matches:
                grade, citation, explanation = _grade_claim(sentence, links_nearby)

                if _is_overbroad(sentence):
                    grade = EvidenceGrade.NEEDS_QUALIFICATION
                    explanation = (
                        "This claim uses absolute language and should be "
                        "scoped with conditions or jurisdiction."
                    )

                if grade == EvidenceGrade.WEAKLY_SUPPORTED and citation:
                    low_trust.add(citation)

                all_claims.append(
                    Claim(
                        text=sentence,
                        claim_type=claim_type,
                        section_index=section.index,
                        evidence_grade=grade,
                        nearest_citation=citation,
                        explanation=explanation,
                    )
                )

    counters = {g: 0 for g in EvidenceGrade}
    for c in all_claims:
        counters[c.evidence_grade] += 1

    return CitationAudit(
        total_claims=len(all_claims),
        supported=counters[EvidenceGrade.SUPPORTED],
        weakly_supported=counters[EvidenceGrade.WEAKLY_SUPPORTED],
        unsupported=counters[EvidenceGrade.UNSUPPORTED],
        needs_qualification=counters[EvidenceGrade.NEEDS_QUALIFICATION],
        claims=all_claims,
        low_trust_sources=sorted(low_trust),
    )
