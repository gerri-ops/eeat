"""Data models for the E-E-A-T grading system."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class InputType(str, Enum):
    URL = "url"
    HTML = "html"
    TEXT = "text"


class YMYLRisk(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentPreset(str, Enum):
    GENERAL = "general"
    LEGAL_PRACTICE_AREA = "legal_practice_area"
    LEGAL_LOCATION = "legal_location"
    LEGAL_FAQ = "legal_faq"
    LEGAL_GUIDE = "legal_guide"
    LEGAL_CASE_RESULTS = "legal_case_results"
    MEDICAL = "medical"
    FINANCE = "finance"
    PRODUCT_REVIEW = "product_review"
    DIY_TUTORIAL = "diy_tutorial"


class EvidenceGrade(str, Enum):
    SUPPORTED = "supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    UNSUPPORTED = "unsupported"
    NEEDS_QUALIFICATION = "needs_qualification"


class FixScope(str, Enum):
    GLOBAL = "global_fix"
    NEW_PAGE = "new_page"
    PAGE_LEVEL = "page_level"


class EffortLevel(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    HEAVY = "heavy"


class ImpactLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClaimType(str, Enum):
    STATISTIC = "statistic"
    SAFETY = "safety"
    LEGAL_DIRECTIVE = "legal_directive"
    MEDICAL_DIRECTIVE = "medical_directive"
    FINANCIAL = "financial"
    PERFORMANCE = "performance"
    COMPARATIVE = "comparative"
    DEADLINE = "deadline"
    PROCEDURAL = "procedural"
    OUTCOME = "outcome"


# ── Input models ─────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    input_type: InputType
    content: str = Field(..., description="URL, raw HTML, or plain text")
    author_name: Optional[str] = None
    site_name: Optional[str] = None
    preset: Optional[ContentPreset] = None


# ── Extracted content ────────────────────────────────────────────────────────

class AuthorInfo(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    credentials: Optional[str] = None
    profile_url: Optional[str] = None
    has_author_page: bool = False


class DateInfo(BaseModel):
    published: Optional[str] = None
    updated: Optional[str] = None
    reviewed: Optional[str] = None


class LinkInfo(BaseModel):
    url: str
    anchor_text: str
    is_external: bool = True
    domain: str = ""
    is_government: bool = False
    is_educational: bool = False
    is_broken: bool = False


class SiteSignals(BaseModel):
    has_about_page: bool = False
    has_contact_page: bool = False
    has_privacy_policy: bool = False
    has_terms: bool = False
    has_editorial_policy: bool = False
    has_corrections_policy: bool = False
    has_attorney_roster: bool = False
    contact_paths: list[str] = Field(default_factory=list)


class ContentSection(BaseModel):
    heading: str = ""
    text: str = ""
    level: int = 0
    index: int = 0


class ExtractedContent(BaseModel):
    title: str = ""
    meta_description: str = ""
    url: Optional[str] = None
    domain: Optional[str] = None
    raw_html: str = ""
    plain_text: str = ""
    word_count: int = 0
    sections: list[ContentSection] = Field(default_factory=list)
    author: AuthorInfo = Field(default_factory=AuthorInfo)
    dates: DateInfo = Field(default_factory=DateInfo)
    outbound_links: list[LinkInfo] = Field(default_factory=list)
    internal_links: list[LinkInfo] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    site_signals: SiteSignals = Field(default_factory=SiteSignals)
    has_schema_markup: bool = False
    schema_types: list[str] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    disclosure_texts: list[str] = Field(default_factory=list)


# ── Claims and citations ────────────────────────────────────────────────────

class Claim(BaseModel):
    text: str
    claim_type: ClaimType
    section_index: int = 0
    evidence_grade: EvidenceGrade = EvidenceGrade.UNSUPPORTED
    nearest_citation: Optional[str] = None
    explanation: str = ""


class CitationAudit(BaseModel):
    total_claims: int = 0
    supported: int = 0
    weakly_supported: int = 0
    unsupported: int = 0
    needs_qualification: int = 0
    claims: list[Claim] = Field(default_factory=list)
    low_trust_sources: list[str] = Field(default_factory=list)


# ── Scoring ──────────────────────────────────────────────────────────────────

class SignalEvidence(BaseModel):
    signal: str
    found: bool
    quote: str = ""
    location: str = ""
    points: float = 0.0
    explanation: str = ""


class DimensionScore(BaseModel):
    name: str
    score: float = 0.0
    max_score: float = 25.0
    signals: list[SignalEvidence] = Field(default_factory=list)
    summary: str = ""


class ComplianceFlag(BaseModel):
    rule: str
    severity: str = "warning"
    text: str = ""
    location: str = ""
    explanation: str = ""
    fix: str = ""


class EEATScore(BaseModel):
    overall: float = 0.0
    experience: DimensionScore = Field(
        default_factory=lambda: DimensionScore(name="Experience")
    )
    expertise: DimensionScore = Field(
        default_factory=lambda: DimensionScore(name="Expertise")
    )
    authoritativeness: DimensionScore = Field(
        default_factory=lambda: DimensionScore(name="Authoritativeness")
    )
    trust: DimensionScore = Field(
        default_factory=lambda: DimensionScore(name="Trust")
    )
    ymyl_risk: YMYLRisk = YMYLRisk.LOW
    preset_used: ContentPreset = ContentPreset.GENERAL
    compliance_flags: list[ComplianceFlag] = Field(default_factory=list)


# ── Recommendations ─────────────────────────────────────────────────────────

class Recommendation(BaseModel):
    title: str
    what_to_change: str
    why_it_matters: str
    where: str = ""
    section_index: Optional[int] = None
    copy_block: str = ""
    effort: EffortLevel = EffortLevel.EASY
    impact: ImpactLevel = ImpactLevel.HIGH
    dimension: str = ""
    points_potential: float = 0.0
    scope: FixScope = FixScope.PAGE_LEVEL


# ── Full report ──────────────────────────────────────────────────────────────

class AnalysisReport(BaseModel):
    score: EEATScore
    extracted: ExtractedContent
    citation_audit: CitationAudit = Field(default_factory=CitationAudit)
    recommendations: list[Recommendation] = Field(default_factory=list)
    summary: str = ""
