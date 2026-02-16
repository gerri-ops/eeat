"""Combined scoring engine.

Merges rules-engine scores with AI model-rater scores,
applies preset weights, and produces the final EEATScore.
"""

from __future__ import annotations

from app.analysis.claims import audit_claims
from app.analysis.compliance import scan_compliance
from app.analysis.ymyl import classify_ymyl, detect_preset
from app.models import (
    AnalysisReport,
    CitationAudit,
    ContentPreset,
    DimensionScore,
    EEATScore,
    ExtractedContent,
    YMYLRisk,
)
from app.recommendations.engine import generate_recommendations
from app.scoring.model_rater import run_model_rater
from app.scoring.presets import get_preset_config
from app.scoring.rules_engine import run_rules_engine


def _merge_dimensions(
    rules: dict[str, DimensionScore],
    model: dict[str, DimensionScore] | None,
    rules_weight: float = 0.6,
) -> dict[str, DimensionScore]:
    """Blend rules-engine and model-rater scores for each dimension."""
    if model is None:
        return rules

    model_weight = 1.0 - rules_weight
    merged: dict[str, DimensionScore] = {}

    for dim in ["experience", "expertise", "authoritativeness", "trust"]:
        r = rules.get(dim, DimensionScore(name=dim.capitalize()))
        m = model.get(dim, DimensionScore(name=dim.capitalize()))
        blended_score = round(r.score * rules_weight + m.score * model_weight, 1)
        merged[dim] = DimensionScore(
            name=dim.capitalize(),
            score=blended_score,
            signals=r.signals + m.signals,
            summary=m.summary or r.summary,
        )

    return merged


def _compute_overall(
    dims: dict[str, DimensionScore],
    preset: ContentPreset,
) -> float:
    """Compute weighted overall score (0-100) using preset weights."""
    config = get_preset_config(preset)
    weighted = (
        dims["experience"].score * (config.experience_weight / 25.0)
        + dims["expertise"].score * (config.expertise_weight / 25.0)
        + dims["authoritativeness"].score * (config.authoritativeness_weight / 25.0)
        + dims["trust"].score * (config.trust_weight / 25.0)
    )
    return round(min(100.0, max(0.0, weighted)), 1)


def _generate_summary(
    score: EEATScore,
    content: ExtractedContent,
    audit: CitationAudit,
    preset: ContentPreset,
) -> str:
    """Generate a plain-English summary of the analysis."""
    parts: list[str] = []
    parts.append(
        f"Overall E-E-A-T score: {score.overall}/100 "
        f"(Experience {score.experience.score}/25, "
        f"Expertise {score.expertise.score}/25, "
        f"Authoritativeness {score.authoritativeness.score}/25, "
        f"Trust {score.trust.score}/25)."
    )
    parts.append(f"YMYL risk: {score.ymyl_risk.value}. Preset: {preset.value}.")

    if audit.unsupported > 0:
        parts.append(
            f"{audit.unsupported} claim(s) lack citations."
        )
    if audit.needs_qualification > 0:
        parts.append(
            f"{audit.needs_qualification} claim(s) use overbroad language."
        )
    if score.compliance_flags:
        parts.append(
            f"{len(score.compliance_flags)} compliance flag(s) detected."
        )

    # Weakest dimension
    dims = {
        "Experience": score.experience.score,
        "Expertise": score.expertise.score,
        "Authoritativeness": score.authoritativeness.score,
        "Trust": score.trust.score,
    }
    weakest = min(dims, key=dims.get)  # type: ignore[arg-type]
    parts.append(f"Weakest dimension: {weakest} ({dims[weakest]}/25).")

    return " ".join(parts)


async def score_content(
    content: ExtractedContent,
    preset_override: ContentPreset | None = None,
) -> AnalysisReport:
    """Run the full scoring pipeline and return a complete report."""

    # 1. Classify YMYL risk
    ymyl_risk = classify_ymyl(content)

    # 2. Detect or use preset
    preset = preset_override or detect_preset(content)

    # 3. Run rules engine (deterministic)
    rules_scores = run_rules_engine(content, ymyl_risk, preset)

    # 4. Run model rater (AI-assisted, may return None)
    model_scores = await run_model_rater(content, ymyl_risk, preset)

    # 5. Merge scores
    merged = _merge_dimensions(rules_scores, model_scores)

    # 6. Compute overall
    overall = _compute_overall(merged, preset)

    # 7. Run claims/citation audit
    audit = audit_claims(content)

    # 8. Run compliance scanner
    compliance_flags = scan_compliance(content)

    # 9. Build score object
    eeat_score = EEATScore(
        overall=overall,
        experience=merged["experience"],
        expertise=merged["expertise"],
        authoritativeness=merged["authoritativeness"],
        trust=merged["trust"],
        ymyl_risk=ymyl_risk,
        preset_used=preset,
        compliance_flags=compliance_flags,
    )

    # 10. Generate recommendations
    recs = generate_recommendations(eeat_score, content, audit, preset, ymyl_risk)

    # 11. Summary
    summary = _generate_summary(eeat_score, content, audit, preset)

    return AnalysisReport(
        score=eeat_score,
        extracted=content,
        citation_audit=audit,
        recommendations=recs,
        summary=summary,
    )
