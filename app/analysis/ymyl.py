"""YMYL topic-risk classifier.

Labels content as high / medium / low risk and selects
the right content preset so scoring thresholds adjust automatically.
"""

from __future__ import annotations

import re

from app.models import ContentPreset, ExtractedContent, YMYLRisk


# ── Keyword lexicons ─────────────────────────────────────────────────────────

LEGAL_HIGH = {
    "attorney", "lawyer", "law firm", "statute of limitations",
    "negligence", "liability", "personal injury", "medical malpractice",
    "wrongful death", "class action", "plaintiff", "defendant",
    "settlement", "verdict", "litigation", "criminal defense",
    "family law", "divorce", "custody", "immigration law",
    "dui", "dwi", "felony", "misdemeanor", "probation",
    "workers compensation", "workers' compensation", "bankruptcy",
    "foreclosure", "eviction", "tort", "damages", "indictment",
    "arraignment", "bail", "subpoena", "deposition",
}

MEDICAL_HIGH = {
    "diagnosis", "treatment", "medication", "dosage", "side effects",
    "symptoms", "surgery", "prescription", "therapy", "prognosis",
    "clinical trial", "contraindication", "overdose", "emergency",
    "cancer", "diabetes", "heart disease", "stroke",
    "mental health", "depression", "anxiety", "suicid",
}

FINANCE_HIGH = {
    "investment", "mortgage", "tax return", "retirement fund",
    "401k", "ira", "securities", "credit score", "debt",
    "loan", "insurance claim", "financial advisor", "fiduciary",
    "estate planning", "trust fund", "will and testament",
}

SAFETY_HIGH = {
    "child safety", "recall", "poison", "hazard", "emergency",
    "self-harm", "abuse", "trafficking", "weapon",
}

MEDIUM_RISK = {
    "health", "wellness", "nutrition", "fitness", "supplement",
    "tax", "budget", "saving", "credit card", "refinance",
    "parenting", "pregnancy", "elder care",
}

LEGAL_PRESET_SIGNALS = {
    "practice area": ContentPreset.LEGAL_PRACTICE_AREA,
    "case results": ContentPreset.LEGAL_CASE_RESULTS,
    "testimonial": ContentPreset.LEGAL_CASE_RESULTS,
    "faq": ContentPreset.LEGAL_FAQ,
    "frequently asked": ContentPreset.LEGAL_FAQ,
    "guide": ContentPreset.LEGAL_GUIDE,
    "overview": ContentPreset.LEGAL_GUIDE,
    "location": ContentPreset.LEGAL_LOCATION,
    "serving": ContentPreset.LEGAL_LOCATION,
}


def classify_ymyl(content: ExtractedContent) -> YMYLRisk:
    """Return the YMYL risk level for the extracted content."""
    text = (content.plain_text + " " + content.title).lower()
    tokens = set(re.findall(r"[a-z][a-z' ]+", text))

    high_hits = sum(1 for kw in LEGAL_HIGH if kw in text)
    high_hits += sum(1 for kw in MEDICAL_HIGH if kw in text)
    high_hits += sum(1 for kw in FINANCE_HIGH if kw in text)
    high_hits += sum(1 for kw in SAFETY_HIGH if kw in text)

    if high_hits >= 3:
        return YMYLRisk.HIGH

    medium_hits = sum(1 for kw in MEDIUM_RISK if kw in text)
    if medium_hits >= 2 or high_hits >= 1:
        return YMYLRisk.MEDIUM

    return YMYLRisk.LOW


def detect_preset(content: ExtractedContent) -> ContentPreset:
    """Detect the best content preset from page signals."""
    text = (content.plain_text + " " + content.title).lower()

    # Check if legal
    legal_hits = sum(1 for kw in LEGAL_HIGH if kw in text)
    if legal_hits >= 2:
        for signal, preset in LEGAL_PRESET_SIGNALS.items():
            if signal in text:
                return preset
        return ContentPreset.LEGAL_PRACTICE_AREA

    medical_hits = sum(1 for kw in MEDICAL_HIGH if kw in text)
    if medical_hits >= 3:
        return ContentPreset.MEDICAL

    finance_hits = sum(1 for kw in FINANCE_HIGH if kw in text)
    if finance_hits >= 3:
        return ContentPreset.FINANCE

    # Product review signals
    review_words = {"review", "tested", "compared", "best", "top", "vs", "rating"}
    if sum(1 for w in review_words if w in text) >= 2:
        return ContentPreset.PRODUCT_REVIEW

    diy_words = {"how to", "step by step", "tutorial", "diy", "guide", "instructions"}
    if sum(1 for w in diy_words if w in text) >= 2:
        return ContentPreset.DIY_TUTORIAL

    return ContentPreset.GENERAL
