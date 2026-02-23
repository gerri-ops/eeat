"""Recommendation engine: turns scoring gaps into ranked, paste-ready fixes.

Every recommendation includes what to change, why, where,
a copy-ready block, effort level, and expected impact.
"""

from __future__ import annotations

from app.models import (
    CitationAudit,
    ComplianceFlag,
    ContentPreset,
    DimensionScore,
    EEATScore,
    EffortLevel,
    EvidenceGrade,
    ExtractedContent,
    FixScope,
    ImpactLevel,
    Recommendation,
    YMYLRisk,
)
from app.scoring.presets import get_preset_config


# ── Template library ─────────────────────────────────────────────────────────

def _attorney_review_block(author: str = "[Attorney Name]") -> str:
    return (
        f"Reviewed by {author}, [Title]. Licensed in [State]. "
        f"Last reviewed on [Date]."
    )


def _scope_jurisdiction_block() -> str:
    return (
        "This page covers general legal information in [State]. "
        "Rules can change by county, court, and the specific facts of your case."
    )


def _no_legal_advice_block() -> str:
    return (
        "This information is not legal advice and does not create an "
        "attorney-client relationship. Talk with a lawyer about your specific facts."
    )


def _sources_block() -> str:
    return "Sources: [State statute link], [court rule link], [agency guidance link]"


def _how_we_built_block() -> str:
    return (
        "We built this guide from current statutes and court rules, "
        "plus our case intake patterns. We update it when deadlines or rules change."
    )


def _editorial_note_block(reviewer: str = "[Reviewer Name]") -> str:
    return (
        f"Editorially reviewed by {reviewer}. "
        f"Last reviewed on [Date]. We follow our editorial guidelines for accuracy."
    )


def _author_bio_block() -> str:
    return (
        "[Author Name] is a [Title/Role] with [X years] of experience in "
        "[practice area / specialty]. [He/She/They] [is/are] licensed in [State] "
        "and [has/have] handled [area of work]. Contact: [email / phone]."
    )


def _corrections_policy_block() -> str:
    return (
        "We take accuracy seriously. If you see an error, please contact us at "
        "[email]. We review and correct reported inaccuracies within [X] business days."
    )


def _how_we_tested_block() -> str:
    return (
        "How we tested: We [tested/reviewed/evaluated] [X products/services] over "
        "[time period]. We [describe methodology]. Our evaluation criteria included "
        "[criteria list]."
    )


def _who_this_is_for_block() -> str:
    return (
        "Who this is for: This guide is designed for [target audience]. "
        "If you [specific condition], you should consult a [professional type] instead."
    )


# ── Recommendation generators ───────────────────────────────────────────────

def _recs_from_missing_signals(
    score: EEATScore,
    content: ExtractedContent,
    preset: ContentPreset,
) -> list[Recommendation]:
    """Generate recommendations for signals that were checked but not found."""
    recs: list[Recommendation] = []
    config = get_preset_config(preset)
    is_legal = preset.value.startswith("legal")

    all_dimensions = [
        ("Trust", score.trust),
        ("Experience", score.experience),
        ("Expertise", score.expertise),
        ("Authoritativeness", score.authoritativeness),
    ]

    for dim_name, dim in all_dimensions:
        for sig in dim.signals:
            if sig.found:
                continue

            # Map each missing signal to a concrete recommendation
            rec = _signal_to_recommendation(sig.signal, dim_name, is_legal, content)
            if rec:
                # Boost impact if it's a required signal for the preset
                if sig.signal in config.required_signals:
                    rec.impact = ImpactLevel.HIGH
                    rec.points_potential += 2.0
                recs.append(rec)

    return recs


def _signal_to_recommendation(
    signal_name: str,
    dimension: str,
    is_legal: bool,
    content: ExtractedContent,
) -> Recommendation | None:
    """Map a missing signal name to a concrete recommendation with copy block."""

    templates: dict[str, tuple[str, str, str, EffortLevel, ImpactLevel, float, FixScope]] = {
        "Disclaimer / legal notice present": (
            "Add a legal disclaimer",
            "Legal content without disclaimers can mislead readers and create liability risk.",
            _no_legal_advice_block(),
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            4.0,
            FixScope.PAGE_LEVEL,
        ),
        "About page linked": (
            "Add or link an About page",
            "An About page establishes site identity and ownership — a baseline trust signal.",
            "",
            EffortLevel.MODERATE,
            ImpactLevel.HIGH,
            3.0,
            FixScope.NEW_PAGE,
        ),
        "Contact information present": (
            "Add visible contact information",
            "Readers and raters look for real contact paths (phone, email, address) to verify legitimacy.",
            "",
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            3.0,
            FixScope.GLOBAL,
        ),
        "Privacy policy linked": (
            "Add a privacy policy link",
            "A privacy policy is a baseline expectation for any professional website.",
            "",
            EffortLevel.EASY,
            ImpactLevel.MEDIUM,
            1.5,
            FixScope.GLOBAL,
        ),
        "Terms of service linked": (
            "Add terms of service link",
            "Terms of service clarify the site-user relationship.",
            "",
            EffortLevel.EASY,
            ImpactLevel.LOW,
            1.0,
            FixScope.GLOBAL,
        ),
        "Editorial / review policy": (
            "Add an editorial policy page",
            "An editorial policy shows content goes through a review process, boosting Trust.",
            _editorial_note_block(),
            EffortLevel.MODERATE,
            ImpactLevel.HIGH,
            3.5,
            FixScope.NEW_PAGE,
        ),
        "Dates shown (published / updated)": (
            "Add publish and update dates",
            "Visible dates let readers judge freshness. Undated content looks unmaintained.",
            "Published: [Date] | Last updated: [Date]",
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            3.0,
            FixScope.PAGE_LEVEL,
        ),
        "Outbound citation count and quality": (
            "Add authoritative citations to support claims",
            "Unsupported claims weaken trust. Link to statutes, regulations, .gov/.edu sources.",
            _sources_block() if is_legal else "Sources: [primary source link], [authoritative source link]",
            EffortLevel.MODERATE,
            ImpactLevel.HIGH,
            4.0,
            FixScope.PAGE_LEVEL,
        ),
        "Affiliate / advertising disclosure": (
            "Add an affiliate / advertising disclosure",
            "FTC guidelines require disclosure when content is monetized through affiliate links or sponsorship.",
            "Disclosure: This page may contain affiliate links. We may earn a commission at no extra cost to you.",
            EffortLevel.EASY,
            ImpactLevel.MEDIUM,
            2.0,
            FixScope.PAGE_LEVEL,
        ),
        "Structured data (schema.org)": (
            "Add schema.org structured data",
            "Structured data helps search engines understand page purpose and display rich results.",
            "",
            EffortLevel.MODERATE,
            ImpactLevel.MEDIUM,
            2.0,
            FixScope.GLOBAL,
        ),
        "First-hand experience language": (
            "Add first-hand experience details",
            "Content reads as generic advice. Add specific details about what you tested, tried, or observed.",
            _how_we_tested_block(),
            EffortLevel.MODERATE,
            ImpactLevel.HIGH,
            3.5,
            FixScope.PAGE_LEVEL,
        ),
        "Procedural / step-by-step detail": (
            "Add step-by-step procedural detail",
            "Readers trust content that walks them through real steps, not just theory.",
            "",
            EffortLevel.MODERATE,
            ImpactLevel.MEDIUM,
            2.5,
            FixScope.PAGE_LEVEL,
        ),
        "Real-world caveats and limitations": (
            "Add caveats and honest limitations",
            "Content that acknowledges trade-offs and limitations reads as more credible.",
            "",
            EffortLevel.EASY,
            ImpactLevel.MEDIUM,
            2.0,
            FixScope.PAGE_LEVEL,
        ),
        "Original images / media": (
            "Add original images or screenshots",
            "Original visuals support experience claims and increase engagement.",
            "",
            EffortLevel.MODERATE,
            ImpactLevel.MEDIUM,
            2.0,
            FixScope.PAGE_LEVEL,
        ),
        "Domain-specific terminology": (
            "Use more precise domain terminology",
            "Generic language makes content look like it was written by a non-expert.",
            "",
            EffortLevel.EASY,
            ImpactLevel.MEDIUM,
            2.0,
            FixScope.PAGE_LEVEL,
        ),
        "Proper scoping and pro referrals": (
            "Add audience scoping and professional referrals",
            "Tell readers who this is for and when to consult a professional. Critical for YMYL topics.",
            _who_this_is_for_block() if not is_legal else (
                _scope_jurisdiction_block() + "\n\n" + _no_legal_advice_block()
            ),
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            4.0,
            FixScope.PAGE_LEVEL,
        ),
        "Content depth (word count + structure)": (
            "Deepen the content with more sections",
            "The page is thin. Add sections that address edge cases, exceptions, and practical details.",
            "",
            EffortLevel.HEAVY,
            ImpactLevel.MEDIUM,
            2.5,
            FixScope.PAGE_LEVEL,
        ),
        "Author name present": (
            "Add a visible author name",
            "Anonymous content on sensitive topics is a major trust red flag.",
            "",
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            3.0,
            FixScope.PAGE_LEVEL,
        ),
        "Author bio with credentials": (
            "Add an author bio with relevant credentials",
            "A bio with specific, relevant background signals that the author is qualified to write this.",
            _author_bio_block(),
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            4.0,
            FixScope.PAGE_LEVEL,
        ),
        "Dedicated author page": (
            "Create a dedicated author profile page",
            "A standalone author page lets readers (and Google) verify the author's identity and expertise.",
            "",
            EffortLevel.MODERATE,
            ImpactLevel.HIGH,
            3.5,
            FixScope.NEW_PAGE,
        ),
        "Professional credentials listed": (
            "List professional credentials explicitly",
            "Credentials like bar admissions, licenses, and certifications should be stated clearly.",
            "[Author Name], Esq. — Licensed in [State], [Bar Number]. [X] years practicing [area].",
            EffortLevel.EASY,
            ImpactLevel.HIGH,
            4.0,
            FixScope.PAGE_LEVEL,
        ),
        "Internal linking depth": (
            "Add more internal links to related content",
            "Strong internal linking demonstrates topical coverage depth and helps readers navigate related guides.",
            "",
            EffortLevel.EASY,
            ImpactLevel.MEDIUM,
            2.0,
            FixScope.PAGE_LEVEL,
        ),
        "Attorney roster / team page": (
            "Add or link an attorney team page",
            "A team page with attorney profiles establishes firm credibility and lets readers verify qualifications.",
            "",
            EffortLevel.MODERATE,
            ImpactLevel.HIGH,
            3.0,
            FixScope.NEW_PAGE,
        ),
    }

    if signal_name not in templates:
        return None

    title, why, copy_block, effort, impact, pts, scope = templates[signal_name]
    return Recommendation(
        title=title,
        what_to_change=title,
        why_it_matters=why,
        where="Page-level" if "page" in signal_name.lower() or "policy" in signal_name.lower() else "Content body",
        copy_block=copy_block,
        effort=effort,
        impact=impact,
        dimension=dimension,
        points_potential=pts,
        scope=scope,
    )


def _recs_from_claims(audit: CitationAudit, is_legal: bool) -> list[Recommendation]:
    """Generate recommendations from the citation audit."""
    recs: list[Recommendation] = []

    unsupported = [c for c in audit.claims if c.evidence_grade == EvidenceGrade.UNSUPPORTED]
    if unsupported:
        examples = "\n".join(f'- "{c.text[:120]}"' for c in unsupported[:5])
        recs.append(Recommendation(
            title=f"Add sources for {len(unsupported)} unsupported claim(s)",
            what_to_change="Add credible citations near these claims",
            why_it_matters="Unsupported claims weaken trust, especially on YMYL topics.",
            where="Multiple sections",
            copy_block=f"Claims needing sources:\n{examples}",
            effort=EffortLevel.MODERATE,
            impact=ImpactLevel.HIGH,
            dimension="Trust",
            points_potential=min(5.0, len(unsupported) * 1.0),
            scope=FixScope.PAGE_LEVEL,
        ))

    weak = [c for c in audit.claims if c.evidence_grade == EvidenceGrade.WEAKLY_SUPPORTED]
    if weak:
        recs.append(Recommendation(
            title=f"Upgrade {len(weak)} weak citation(s)",
            what_to_change="Replace blog/forum sources with primary or institutional sources",
            why_it_matters="Low-authority sources don't support sensitive claims.",
            where="Multiple sections",
            copy_block="Replace sources from: " + ", ".join(audit.low_trust_sources[:5]),
            effort=EffortLevel.MODERATE,
            impact=ImpactLevel.MEDIUM,
            dimension="Trust",
            points_potential=min(3.0, len(weak) * 0.5),
            scope=FixScope.PAGE_LEVEL,
        ))

    overbroad = [c for c in audit.claims if c.evidence_grade == EvidenceGrade.NEEDS_QUALIFICATION]
    if overbroad:
        examples = "\n".join(f'- "{c.text[:120]}"' for c in overbroad[:5])
        recs.append(Recommendation(
            title=f"Qualify {len(overbroad)} overbroad claim(s)",
            what_to_change="Replace absolute language with scoped, conditional statements",
            why_it_matters="Overbroad claims reduce credibility and can mislead readers.",
            where="Multiple sections",
            copy_block=f"Claims to qualify:\n{examples}\n\nReplace 'always' / 'never' / 'guaranteed' with conditional language.",
            effort=EffortLevel.EASY,
            impact=ImpactLevel.HIGH,
            dimension="Trust",
            points_potential=min(4.0, len(overbroad) * 1.0),
            scope=FixScope.PAGE_LEVEL,
        ))

    return recs


def _recs_from_compliance(flags: list[ComplianceFlag]) -> list[Recommendation]:
    """Turn compliance flags into recommendations."""
    recs: list[Recommendation] = []
    for flag in flags:
        recs.append(Recommendation(
            title=f"Fix {flag.rule} issue: {flag.explanation[:60]}",
            what_to_change=flag.explanation,
            why_it_matters=f"Violates {flag.rule}. This can create misleading impressions and pose ethical/legal risk.",
            where=flag.location,
            copy_block=flag.fix,
            effort=EffortLevel.EASY,
            impact=ImpactLevel.HIGH if flag.severity == "high" else ImpactLevel.MEDIUM,
            dimension="Trust",
            points_potential=3.0 if flag.severity == "high" else 1.5,
            scope=FixScope.PAGE_LEVEL,
        ))
    return recs


def _recs_for_legal_extras(
    content: ExtractedContent,
    score: EEATScore,
) -> list[Recommendation]:
    """Legal-specific recommendations beyond standard signals."""
    recs: list[Recommendation] = []

    if not content.dates.reviewed:
        recs.append(Recommendation(
            title="Add attorney review line",
            what_to_change="Add a 'Reviewed by [Attorney]' line with date",
            why_it_matters="Attorney review signals editorial oversight — a top trust signal for legal content.",
            where="Below the title or at the end of the article",
            copy_block=_attorney_review_block(),
            effort=EffortLevel.EASY,
            impact=ImpactLevel.HIGH,
            dimension="Trust",
            points_potential=4.0,
            scope=FixScope.PAGE_LEVEL,
        ))

    has_how_built = any("how we" in s.text.lower() for s in content.sections)
    if not has_how_built:
        recs.append(Recommendation(
            title='Add "How we built this guide" section',
            what_to_change="Explain the research methodology",
            why_it_matters="Transparency about research process builds trust with readers and raters.",
            where="End of article, before sources",
            copy_block=_how_we_built_block(),
            effort=EffortLevel.EASY,
            impact=ImpactLevel.MEDIUM,
            dimension="Experience",
            points_potential=2.5,
            scope=FixScope.PAGE_LEVEL,
        ))

    return recs


# ── Main entry point ─────────────────────────────────────────────────────────

def generate_recommendations(
    score: EEATScore,
    content: ExtractedContent,
    audit: CitationAudit,
    preset: ContentPreset,
    ymyl_risk: YMYLRisk,
) -> list[Recommendation]:
    """Generate the full ranked recommendation list."""
    recs: list[Recommendation] = []

    # From missing signals
    recs.extend(_recs_from_missing_signals(score, content, preset))

    # From claims audit
    is_legal = preset.value.startswith("legal")
    recs.extend(_recs_from_claims(audit, is_legal))

    # From compliance flags
    recs.extend(_recs_from_compliance(score.compliance_flags))

    # Legal extras
    if is_legal:
        recs.extend(_recs_for_legal_extras(content, score))

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[Recommendation] = []
    for r in recs:
        if r.title not in seen:
            seen.add(r.title)
            unique.append(r)

    # Sort: HIGH impact first, then by points_potential descending
    impact_order = {ImpactLevel.HIGH: 0, ImpactLevel.MEDIUM: 1, ImpactLevel.LOW: 2}
    unique.sort(key=lambda r: (impact_order.get(r.impact, 2), -r.points_potential))

    return unique
