# E-E-A-T Content Grader

A search-focused content QA tool that grades Experience, Expertise, Authoritativeness, and Trust (E-E-A-T) signals, then produces a ranked list of fixes a writer or editor can apply immediately.

Built for **legal content** as the primary use case, with full support for any YMYL or general content type.

## What It Does

**Input:** A URL, raw HTML, or pasted text (plus optional author and site details).

**Output:**

- **E-E-A-T score** (0-100 overall + 4 dimension subscores, each 0-25)
- **Evidence view** with every score point tied to exact passages
- **Claims audit** that identifies unsupported, weakly sourced, and overbroad claims
- **Rule 7.1 compliance scanner** for legal content (ABA Model Rules)
- **Priority fix list** ranked by impact, with paste-ready copy blocks
- **Export** to JSON or Markdown checklist

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure (optional)

Copy `.env.example` to `.env` and add your OpenAI API key for AI-assisted scoring:

```bash
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
```

The tool works without an API key — it runs the full deterministic rules engine. The AI model rater adds nuanced soft checks (experience cues, overconfidence detection, claim-citation mismatch) when an API key is provided.

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## Architecture

```
app/
├── main.py                   # FastAPI app + API endpoints
├── config.py                 # Environment configuration
├── models.py                 # Pydantic data models
├── parser/
│   ├── fetcher.py            # URL fetching
│   └── extractor.py          # HTML/text content extraction
├── analysis/
│   ├── ymyl.py               # YMYL risk classifier
│   ├── claims.py             # Claim detection + citation auditing
│   └── compliance.py         # ABA Rule 7.1 scanner
├── scoring/
│   ├── rules_engine.py       # Deterministic signal checks
│   ├── model_rater.py        # AI-assisted soft checks (OpenAI)
│   ├── presets.py             # Topic-specific weight presets
│   └── scorer.py             # Combined scoring pipeline
├── recommendations/
│   └── engine.py             # Recommendation generator + copy blocks
└── static/
    ├── index.html            # Single-page frontend
    ├── style.css             # Dark-theme design system
    └── app.js                # Frontend application logic
```

## Scoring Model

### Two-Layer Approach

1. **Rules Engine (deterministic):** Checks for presence/absence of trust signals, citation counts, author info, dates, schema markup, disclaimers, and more. Every check produces evidence with a quote and location.

2. **Model Rater (AI-assisted):** Evaluates nuanced signals — does this read like lived experience? Are claims appropriately scoped? Is the tone overconfident? Each judgment includes a supporting quote.

### Dimension Weights (vary by preset)

| Preset | Experience | Expertise | Authoritativeness | Trust |
|--------|-----------|-----------|-------------------|-------|
| General | 20 | 25 | 25 | 30 |
| Legal Practice Area | 15 | 25 | 20 | **40** |
| Medical | 15 | 30 | 15 | **40** |
| Product Review | **35** | 20 | 15 | 30 |
| DIY Tutorial | **35** | 25 | 10 | 30 |

### Content Presets

- General
- Legal: Practice Area, Location, FAQ, Long Guide, Case Results
- Medical
- Finance
- Product Review
- DIY Tutorial

## Key Features

### Claims & Citation Auditing

Detects statistics, legal directives, medical directives, outcome claims, comparative claims, and procedural assertions. Each claim is graded:

- **Supported** — credible citation nearby
- **Weakly supported** — citation present but low authority
- **Unsupported** — no citation found
- **Needs qualification** — overbroad language (always/never/guaranteed)

### Rule 7.1 Compliance (Legal)

Scans for patterns that violate ABA Model Rule 7.1:

- Guarantee language about outcomes
- Unsubstantiated superlative claims
- Cherry-picked results without disclaimers
- "No fee" without conditions
- Testimonials without disclaimers

### Recommendation Engine

Every recommendation includes:

- What to change
- Why it matters
- Exactly where
- A paste-ready copy block
- Effort level (easy/moderate/heavy)
- Expected impact (high/medium/low)

## API

### `POST /api/analyze`

```json
{
  "input_type": "url",
  "content": "https://example.com/page",
  "author_name": "Jane Doe",
  "site_name": "Example Law Firm",
  "preset": "legal_practice_area"
}
```

Returns the full `AnalysisReport` with scores, evidence, claims audit, compliance flags, and recommendations.

### `GET /api/presets`

Returns available content presets.

### `GET /api/health`

Health check endpoint.

## Roadmap

- **Phase A (current):** Single-page grader, rules engine, AI rater, recommendations, export
- **Phase B:** Source quality scoring, re-score tracking, enhanced claim mapping
- **Phase C:** Multi-page crawl, site-level patterns, editor queue
