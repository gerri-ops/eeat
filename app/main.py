"""FastAPI application: E-E-A-T Content Grader API + UI."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.models import AnalysisRequest, ContentPreset, InputType
from app.parser.extractor import extract_from_html, extract_from_text
from app.parser.fetcher import fetch_url
from app.scoring.scorer import score_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="E-E-A-T Content Grader",
    description="Score content for Experience, Expertise, Authoritativeness, and Trust",
    version="1.0.0",
)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Prevent browsers from caching stale static files."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheStaticMiddleware)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the single-page frontend."""
    index = STATIC_DIR / "index.html"
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.post("/api/analyze")
async def analyze(req: AnalysisRequest):
    """Main analysis endpoint.

    Accepts a URL, raw HTML, or plain text.
    Returns the full E-E-A-T score, evidence, claims audit,
    compliance flags, and ranked recommendations.
    """
    try:
        # 1. Ingest content
        if req.input_type == InputType.URL:
            html = await fetch_url(req.content)
            content = extract_from_html(html, source_url=req.content)
        elif req.input_type == InputType.HTML:
            content = extract_from_html(req.content)
        else:
            content = extract_from_text(req.content)

        # Override author info if provided
        if req.author_name:
            content.author.name = content.author.name or req.author_name
        if req.site_name:
            content.domain = content.domain or req.site_name

        # 2. Score
        preset_override = req.preset if req.preset else None
        report = await score_content(content, preset_override=preset_override)

        # 3. Strip raw_html from response to keep payload lean
        report.extracted.raw_html = ""

        return report.model_dump()

    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/presets")
async def list_presets():
    """Return available content presets."""
    return [{"value": p.value, "label": p.value.replace("_", " ").title()} for p in ContentPreset]


@app.get("/api/health")
async def health():
    return {"status": "ok"}
