"""Extract structured content signals from HTML or plain text."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
import tldextract

from app.models import (
    AuthorInfo,
    ContentSection,
    DateInfo,
    ExtractedContent,
    LinkInfo,
    SiteSignals,
)


GOV_TLDS = {".gov", ".mil", ".gc.ca", ".gov.uk", ".gov.au"}
EDU_TLDS = {".edu", ".ac.uk", ".edu.au"}


def _is_government(domain: str) -> bool:
    return any(domain.endswith(t) for t in GOV_TLDS)


def _is_educational(domain: str) -> bool:
    return any(domain.endswith(t) for t in EDU_TLDS)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"


def extract_from_html(html: str, source_url: str | None = None) -> ExtractedContent:
    """Parse HTML and pull out every signal the scoring engine needs."""
    soup = BeautifulSoup(html, "lxml")
    base_domain = _extract_domain(source_url) if source_url else ""

    # ── Title ────────────────────────────────────────────────────────────
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"]
    elif soup.title:
        title = soup.title.get_text()
    title = _clean(title)

    # ── Meta description ─────────────────────────────────────────────────
    meta_desc = ""
    md_tag = soup.find("meta", attrs={"name": "description"})
    if md_tag and md_tag.get("content"):
        meta_desc = md_tag["content"]

    # ── Body text and sections ───────────────────────────────────────────
    body = soup.find("article") or soup.find("main") or soup.body
    sections: list[ContentSection] = []
    plain_parts: list[str] = []

    if body:
        headings = body.find_all(re.compile(r"^h[1-6]$"))
        if headings:
            for idx, h in enumerate(headings):
                level = int(h.name[1])
                heading_text = _clean(h.get_text())
                section_text_parts: list[str] = []
                for sib in h.find_next_siblings():
                    if isinstance(sib, Tag) and re.match(r"^h[1-6]$", sib.name):
                        break
                    section_text_parts.append(_clean(sib.get_text()))
                section_text = " ".join(section_text_parts)
                sections.append(
                    ContentSection(
                        heading=heading_text,
                        text=section_text,
                        level=level,
                        index=idx,
                    )
                )
                plain_parts.append(heading_text + " " + section_text)
        else:
            text = _clean(body.get_text())
            sections.append(ContentSection(text=text, index=0))
            plain_parts.append(text)

    plain_text = " ".join(plain_parts)
    word_count = len(plain_text.split())

    # ── Author info ──────────────────────────────────────────────────────
    author = _extract_author(soup)

    # ── Dates ────────────────────────────────────────────────────────────
    dates = _extract_dates(soup)

    # ── Links ────────────────────────────────────────────────────────────
    outbound: list[LinkInfo] = []
    internal: list[LinkInfo] = []
    for a in (body or soup).find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urljoin(source_url or "", href) if source_url else href
        link_domain = _extract_domain(full_url) if full_url.startswith("http") else ""
        is_ext = link_domain != base_domain if base_domain else True
        info = LinkInfo(
            url=full_url,
            anchor_text=_clean(a.get_text()),
            is_external=is_ext,
            domain=link_domain,
            is_government=_is_government(link_domain),
            is_educational=_is_educational(link_domain),
        )
        if is_ext:
            outbound.append(info)
        else:
            internal.append(info)

    # ── Images ───────────────────────────────────────────────────────────
    images = []
    for img in (body or soup).find_all("img"):
        src = img.get("src", "") or img.get("data-src", "")
        if src:
            images.append(urljoin(source_url or "", src))

    # ── Schema / structured data ─────────────────────────────────────────
    schema_types: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        txt = script.get_text()
        for m in re.findall(r'"@type"\s*:\s*"([^"]+)"', txt):
            schema_types.append(m)

    # ── Disclaimers & disclosures ────────────────────────────────────────
    disclaimers = _find_disclaimer_texts(soup)
    disclosures = _find_disclosure_texts(soup)

    # ── Site signals (from on-page footers / nav) ────────────────────────
    site_signals = _detect_site_signals_from_page(soup, source_url)

    return ExtractedContent(
        title=title,
        meta_description=meta_desc,
        url=source_url,
        domain=base_domain,
        raw_html=html,
        plain_text=plain_text,
        word_count=word_count,
        sections=sections,
        author=author,
        dates=dates,
        outbound_links=outbound,
        internal_links=internal,
        images=images,
        site_signals=site_signals,
        has_schema_markup=bool(schema_types),
        schema_types=schema_types,
        disclaimers=disclaimers,
        disclosure_texts=disclosures,
    )


def extract_from_text(text: str) -> ExtractedContent:
    """Minimal extraction for pasted plain text."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sections = [
        ContentSection(text=p, index=i) for i, p in enumerate(paragraphs)
    ]
    return ExtractedContent(
        plain_text=text,
        word_count=len(text.split()),
        sections=sections,
    )


# ── Private helpers ──────────────────────────────────────────────────────────


def _extract_author(soup: BeautifulSoup) -> AuthorInfo:
    author = AuthorInfo()

    # meta tag
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author.name = meta_author["content"]

    # schema author
    for script in soup.find_all("script", type="application/ld+json"):
        txt = script.get_text()
        m = re.search(r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', txt)
        if m:
            author.name = author.name or m.group(1)

    # byline patterns
    byline_classes = ["author", "byline", "writer", "contributor", "author-name"]
    for cls in byline_classes:
        el = soup.find(class_=re.compile(cls, re.I))
        if el:
            author.name = author.name or _clean(el.get_text())
            link = el.find("a", href=True)
            if link:
                author.profile_url = link["href"]
                author.has_author_page = True
            break

    # bio / about-the-author section
    bio_el = soup.find(class_=re.compile(r"author.?bio|about.?author", re.I))
    if bio_el:
        author.bio = _clean(bio_el.get_text())[:1000]

    # credentials: look for common patterns near author name
    if author.bio:
        cred_patterns = [
            r"(J\.?D\.?|Esq\.?|Attorney|Lawyer|Licensed|Bar\s+\w+)",
            r"(M\.?D\.?|Ph\.?D\.?|CPA|CFP|RN|LPN)",
            r"(\d+\s+years?\s+(?:of\s+)?experience)",
        ]
        creds = []
        for pat in cred_patterns:
            m = re.search(pat, author.bio, re.I)
            if m:
                creds.append(m.group(1))
        if creds:
            author.credentials = "; ".join(creds)

    return author


def _extract_dates(soup: BeautifulSoup) -> DateInfo:
    dates = DateInfo()
    time_els = soup.find_all("time")
    for t in time_els:
        dt = t.get("datetime", "") or _clean(t.get_text())
        parent_text = _clean(t.parent.get_text()) if t.parent else ""
        if "publish" in parent_text.lower() or "posted" in parent_text.lower():
            dates.published = dates.published or dt
        elif "update" in parent_text.lower() or "modif" in parent_text.lower():
            dates.updated = dates.updated or dt
        elif "review" in parent_text.lower():
            dates.reviewed = dates.reviewed or dt
        else:
            dates.published = dates.published or dt

    # meta tags
    for attr in ["article:published_time", "datePublished"]:
        tag = soup.find("meta", property=attr) or soup.find(
            "meta", attrs={"name": attr}
        )
        if tag and tag.get("content"):
            dates.published = dates.published or tag["content"]

    for attr in ["article:modified_time", "dateModified"]:
        tag = soup.find("meta", property=attr) or soup.find(
            "meta", attrs={"name": attr}
        )
        if tag and tag.get("content"):
            dates.updated = dates.updated or tag["content"]

    return dates


DISCLAIMER_KEYWORDS = [
    "not legal advice",
    "not a substitute",
    "does not create",
    "attorney-client",
    "consult a",
    "consult an",
    "seek professional",
    "general information",
    "informational purposes",
    "no guarantee",
    "disclaimer",
]

DISCLOSURE_KEYWORDS = [
    "affiliate",
    "commission",
    "sponsored",
    "paid partnership",
    "advertising",
    "compensation",
    "material connection",
    "ftc",
]


def _find_disclaimer_texts(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for el in soup.find_all(["p", "div", "span", "small", "aside"]):
        txt = _clean(el.get_text()).lower()
        if any(kw in txt for kw in DISCLAIMER_KEYWORDS) and len(txt) < 2000:
            found.append(_clean(el.get_text()))
    return found[:10]


def _find_disclosure_texts(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for el in soup.find_all(["p", "div", "span", "small", "aside"]):
        txt = _clean(el.get_text()).lower()
        if any(kw in txt for kw in DISCLOSURE_KEYWORDS) and len(txt) < 2000:
            found.append(_clean(el.get_text()))
    return found[:10]


def _detect_site_signals_from_page(
    soup: BeautifulSoup, source_url: str | None
) -> SiteSignals:
    """Detect trust-page links from footer / nav without extra HTTP calls."""
    signals = SiteSignals()
    link_texts: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        lt = _clean(a.get_text()).lower()
        link_texts[lt] = a["href"]

    about_keys = ["about", "about us", "our firm", "our story", "who we are"]
    contact_keys = ["contact", "contact us", "get in touch"]
    privacy_keys = ["privacy", "privacy policy"]
    terms_keys = ["terms", "terms of service", "terms of use", "terms & conditions"]
    editorial_keys = ["editorial policy", "editorial guidelines", "editorial standards"]
    attorney_keys = ["attorneys", "our attorneys", "our team", "our lawyers", "team"]

    for lt in link_texts:
        if any(k == lt for k in about_keys):
            signals.has_about_page = True
        if any(k == lt for k in contact_keys):
            signals.has_contact_page = True
            signals.contact_paths.append(link_texts[lt])
        if any(k == lt for k in privacy_keys):
            signals.has_privacy_policy = True
        if any(k == lt for k in terms_keys):
            signals.has_terms = True
        if any(k == lt for k in editorial_keys):
            signals.has_editorial_policy = True
        if any(k == lt for k in attorney_keys):
            signals.has_attorney_roster = True

    # Phone / address on page
    page_text = soup.get_text()
    phone_match = re.search(
        r"(\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4})", page_text
    )
    if phone_match:
        signals.contact_paths.append(f"phone: {phone_match.group(1)}")

    return signals
