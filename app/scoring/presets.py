"""Topic presets: weight adjustments and required checks per content type.

Each preset changes how the four E-E-A-T dimensions are weighted
in the overall score and defines which signals are *required* for
the content to score well.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import ContentPreset


@dataclass
class PresetConfig:
    """Weights (must sum to 100) and required signal names."""
    experience_weight: float = 15.0
    expertise_weight: float = 25.0
    authoritativeness_weight: float = 20.0
    trust_weight: float = 40.0
    required_signals: list[str] = field(default_factory=list)
    label: str = "General"


PRESET_CONFIGS: dict[ContentPreset, PresetConfig] = {
    ContentPreset.GENERAL: PresetConfig(
        experience_weight=20.0,
        expertise_weight=25.0,
        authoritativeness_weight=25.0,
        trust_weight=30.0,
        label="General content",
    ),
    ContentPreset.LEGAL_PRACTICE_AREA: PresetConfig(
        experience_weight=15.0,
        expertise_weight=25.0,
        authoritativeness_weight=20.0,
        trust_weight=40.0,
        required_signals=[
            "Disclaimer / legal notice present",
            "Author bio with credentials",
            "Professional credentials listed",
            "Dates shown (published / updated)",
            "Outbound citation count and quality",
            "Proper scoping and pro referrals",
        ],
        label="Legal — Practice Area Page",
    ),
    ContentPreset.LEGAL_LOCATION: PresetConfig(
        experience_weight=10.0,
        expertise_weight=25.0,
        authoritativeness_weight=25.0,
        trust_weight=40.0,
        required_signals=[
            "Disclaimer / legal notice present",
            "Contact information present",
            "Author bio with credentials",
        ],
        label="Legal — Location Page",
    ),
    ContentPreset.LEGAL_FAQ: PresetConfig(
        experience_weight=10.0,
        expertise_weight=30.0,
        authoritativeness_weight=20.0,
        trust_weight=40.0,
        required_signals=[
            "Disclaimer / legal notice present",
            "Proper scoping and pro referrals",
            "Dates shown (published / updated)",
        ],
        label="Legal — FAQ",
    ),
    ContentPreset.LEGAL_GUIDE: PresetConfig(
        experience_weight=15.0,
        expertise_weight=25.0,
        authoritativeness_weight=20.0,
        trust_weight=40.0,
        required_signals=[
            "Disclaimer / legal notice present",
            "Outbound citation count and quality",
            "Author bio with credentials",
            "Dates shown (published / updated)",
            "Proper scoping and pro referrals",
        ],
        label="Legal — Long Guide",
    ),
    ContentPreset.LEGAL_CASE_RESULTS: PresetConfig(
        experience_weight=10.0,
        expertise_weight=20.0,
        authoritativeness_weight=25.0,
        trust_weight=45.0,
        required_signals=[
            "Disclaimer / legal notice present",
            "Author bio with credentials",
        ],
        label="Legal — Case Results / Testimonials",
    ),
    ContentPreset.MEDICAL: PresetConfig(
        experience_weight=15.0,
        expertise_weight=30.0,
        authoritativeness_weight=15.0,
        trust_weight=40.0,
        required_signals=[
            "Author bio with credentials",
            "Outbound citation count and quality",
            "Dates shown (published / updated)",
            "Proper scoping and pro referrals",
        ],
        label="Medical content",
    ),
    ContentPreset.FINANCE: PresetConfig(
        experience_weight=15.0,
        expertise_weight=30.0,
        authoritativeness_weight=20.0,
        trust_weight=35.0,
        required_signals=[
            "Author bio with credentials",
            "Outbound citation count and quality",
            "Dates shown (published / updated)",
        ],
        label="Financial content",
    ),
    ContentPreset.PRODUCT_REVIEW: PresetConfig(
        experience_weight=35.0,
        expertise_weight=20.0,
        authoritativeness_weight=15.0,
        trust_weight=30.0,
        required_signals=[
            "First-hand experience language",
            "Original images / media",
            "Affiliate / advertising disclosure",
        ],
        label="Product Review",
    ),
    ContentPreset.DIY_TUTORIAL: PresetConfig(
        experience_weight=35.0,
        expertise_weight=25.0,
        authoritativeness_weight=10.0,
        trust_weight=30.0,
        required_signals=[
            "First-hand experience language",
            "Procedural / step-by-step detail",
            "Original images / media",
        ],
        label="DIY Tutorial",
    ),
}


def get_preset_config(preset: ContentPreset) -> PresetConfig:
    return PRESET_CONFIGS.get(preset, PRESET_CONFIGS[ContentPreset.GENERAL])
