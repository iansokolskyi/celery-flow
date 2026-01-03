"""Static file serving for bundled React UI assets."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

_FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"


def _rewrite_html_for_prefix(
    html: str, prefix: str, *, rewrite_assets: bool = True
) -> str:
    """Rewrite asset paths and inject base path config for the given mount prefix.

    Args:
        html: The HTML content to rewrite.
        prefix: The base path prefix (e.g., "/stemtrace").
        rewrite_assets: If True, rewrite asset paths. If False, only inject API base.
    """
    if prefix and rewrite_assets:
        html = html.replace('"/assets/', f'"{prefix}/assets/')
        html = html.replace("'/assets/", f"'{prefix}/assets/")
    return html.replace(
        "<head>", f'<head><script>window.__STEMTRACE_BASE__="{prefix}";</script>'
    )


def get_static_router() -> APIRouter | None:
    """Create router for UI static files. Returns None if dist/ missing."""
    return get_static_router_with_base(None)


def get_static_router_with_base(api_base: str | None) -> APIRouter | None:
    """Create router for UI with explicit API base path.

    Args:
        api_base: Fixed base path for API/WebSocket connections.
                  If None, derives from request URL path.

    Returns:
        APIRouter for UI, or None if dist/ missing.
    """
    if not _FRONTEND_DIR.exists():
        logger.warning("Frontend dist not found at %s", _FRONTEND_DIR)
        return None

    router = APIRouter(tags=["stemtrace-ui"])
    router.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIR / "assets"),
        name="stemtrace-assets",
    )

    @router.get("/", response_class=HTMLResponse)
    async def serve_index(request: Request) -> HTMLResponse:
        """Serve the main index.html page."""
        index_path = _FRONTEND_DIR / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>UI not built</h1>", status_code=503)

        if api_base is not None:
            # Explicit API base: don't rewrite assets (they're served at current mount)
            prefix = api_base
            rewrite_assets = False
        else:
            # Derive from URL: rewrite assets to match mount point
            prefix = request.url.path.rstrip("/") or ""
            rewrite_assets = True
        return HTMLResponse(
            _rewrite_html_for_prefix(
                index_path.read_text(), prefix, rewrite_assets=rewrite_assets
            )
        )

    @router.get("/{path:path}", response_model=None)
    async def serve_spa(path: str, request: Request) -> FileResponse | HTMLResponse:
        """Serve static files or fall back to index.html for SPA routing."""
        file_path = _FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        index_path = _FRONTEND_DIR / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>Not found</h1>", status_code=404)

        if api_base is not None:
            # Explicit API base: don't rewrite assets (they're served at current mount)
            prefix = api_base
            rewrite_assets = False
        else:
            # Extract prefix: /stemtrace/tasks/123 -> /stemtrace
            url_path = request.url.path
            prefix = (
                url_path[: -len(path)].rstrip("/")
                if path and url_path.endswith(path)
                else url_path.rstrip("/")
            )
            rewrite_assets = True
        return HTMLResponse(
            _rewrite_html_for_prefix(
                index_path.read_text(), prefix, rewrite_assets=rewrite_assets
            )
        )

    return router


def is_ui_available() -> bool:
    """Check if built UI assets exist."""
    return (_FRONTEND_DIR / "index.html").exists()
