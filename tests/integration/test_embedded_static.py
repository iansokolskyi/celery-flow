"""Integration tests for embedded static file serving with path rewriting."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from stemtrace import StemtraceExtension


class TestHtmlPathRewriting:
    """Tests for HTML asset path rewriting when embedded at various prefixes."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create a mock dist directory with realistic HTML."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()

        # Simulate Vite-built index.html with absolute asset paths
        html = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>stemtrace</title>
    <script type="module" crossorigin src="/assets/index-abc123.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-def456.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>"""
        (dist_dir / "index.html").write_text(html)
        (assets_dir / "index-abc123.js").write_text("console.log('app');")
        (assets_dir / "index-def456.css").write_text("body { margin: 0; }")
        return dist_dir

    def test_rewrite_assets_at_stemtrace_prefix(self, mock_dist: Path) -> None:
        """Assets rewritten from /assets/ to /stemtrace/assets/ when mounted at /stemtrace."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/stemtrace"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/stemtrace")

            client = TestClient(app)
            response = client.get("/stemtrace/")

            assert response.status_code == 200
            html = response.text

            # Asset paths should be rewritten
            assert '"/stemtrace/assets/index-abc123.js"' in html
            assert '"/stemtrace/assets/index-def456.css"' in html

            # Original absolute paths should NOT be present
            assert '"/assets/index-abc123.js"' not in html
            assert '"/assets/index-def456.css"' not in html

    def test_rewrite_assets_at_nested_prefix(self, mock_dist: Path) -> None:
        """Assets rewritten correctly for nested prefixes like /api/monitoring."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://",
                embedded_consumer=False,
                prefix="/api/monitoring",
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/api/monitoring")

            client = TestClient(app)
            response = client.get("/api/monitoring/")

            assert response.status_code == 200
            html = response.text

            assert '"/api/monitoring/assets/index-abc123.js"' in html
            assert '"/api/monitoring/assets/index-def456.css"' in html

    def test_no_rewrite_at_root_prefix(self, mock_dist: Path) -> None:
        """Assets remain /assets/ when mounted at root /."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/"
            )
            app = FastAPI()
            app.include_router(ext.router)

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            html = response.text

            # At root, assets stay at /assets/
            assert '"/assets/index-abc123.js"' in html


class TestBasePathInjection:
    """Tests for __STEMTRACE_BASE__ injection in HTML."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create mock dist with simple HTML."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()
        (dist_dir / "index.html").write_text("<html><head></head><body></body></html>")
        return dist_dir

    def test_base_path_injected_at_stemtrace(self, mock_dist: Path) -> None:
        """__STEMTRACE_BASE__ is injected with correct prefix."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/stemtrace"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/stemtrace")

            client = TestClient(app)
            response = client.get("/stemtrace/")

            assert response.status_code == 200
            assert 'window.__STEMTRACE_BASE__="/stemtrace"' in response.text

    def test_base_path_injected_at_nested_prefix(self, mock_dist: Path) -> None:
        """__STEMTRACE_BASE__ is correct for nested prefixes."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/admin/tasks"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/admin/tasks")

            client = TestClient(app)
            response = client.get("/admin/tasks/")

            assert response.status_code == 200
            assert 'window.__STEMTRACE_BASE__="/admin/tasks"' in response.text

    def test_base_path_empty_at_root(self, mock_dist: Path) -> None:
        """__STEMTRACE_BASE__ is empty string when mounted at root."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/"
            )
            app = FastAPI()
            app.include_router(ext.router)

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            assert 'window.__STEMTRACE_BASE__=""' in response.text


class TestSpaFallbackPathDetection:
    """Tests for SPA fallback route prefix detection."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create mock dist."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()
        html = '<html><head></head><body><script src="/assets/app.js"></script></body></html>'
        (dist_dir / "index.html").write_text(html)
        return dist_dir

    def test_spa_fallback_extracts_prefix(self, mock_dist: Path) -> None:
        """SPA routes extract prefix from URL and rewrite HTML."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/stemtrace"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/stemtrace")

            client = TestClient(app)

            # Request a SPA route like /stemtrace/tasks/abc-123
            response = client.get("/stemtrace/tasks/abc-123")

            assert response.status_code == 200
            # Should have prefix in asset path
            assert '"/stemtrace/assets/app.js"' in response.text
            # Should have correct base path
            assert 'window.__STEMTRACE_BASE__="/stemtrace"' in response.text

    def test_spa_fallback_nested_route(self, mock_dist: Path) -> None:
        """Deeply nested SPA routes still get correct prefix."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/stemtrace"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/stemtrace")

            client = TestClient(app)

            response = client.get("/stemtrace/graphs/abc/nodes/xyz")

            assert response.status_code == 200
            assert 'window.__STEMTRACE_BASE__="/stemtrace"' in response.text


class TestPrefixNormalization:
    """Tests for prefix format normalization."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create mock dist."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()
        (dist_dir / "index.html").write_text("<html><head></head><body></body></html>")
        return dist_dir

    @pytest.mark.parametrize(
        ("input_prefix", "expected_base"),
        [
            ("stemtrace", "/stemtrace"),  # No leading slash
            ("/stemtrace", "/stemtrace"),  # With leading slash
            ("/stemtrace/", "/stemtrace"),  # With trailing slash
            ("stemtrace/", "/stemtrace"),  # Both missing/extra
            ("/api/stemtrace", "/api/stemtrace"),  # Nested path
            ("api/stemtrace/", "/api/stemtrace"),  # Nested without leading
        ],
    )
    def test_prefix_normalization(
        self, mock_dist: Path, input_prefix: str, expected_base: str
    ) -> None:
        """Various prefix formats are normalized correctly."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix=input_prefix
            )
            app = FastAPI()
            app.include_router(ext.router, prefix=f"/{input_prefix.strip('/')}")

            client = TestClient(app)
            response = client.get(f"{expected_base}/")

            assert response.status_code == 200
            assert f'window.__STEMTRACE_BASE__="{expected_base}"' in response.text


class TestAssetServing:
    """Tests that actual asset files are served at the correct paths."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create mock dist with assets."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()
        (dist_dir / "index.html").write_text("<html></html>")
        (assets_dir / "app.js").write_text("console.log('test');")
        (assets_dir / "style.css").write_text("body{}")
        return dist_dir

    def test_assets_served_at_prefixed_path(self, mock_dist: Path) -> None:
        """Assets are served at /stemtrace/assets/..."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/stemtrace"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/stemtrace")

            client = TestClient(app)

            # Assets should be available at the prefixed path
            js_response = client.get("/stemtrace/assets/app.js")
            assert js_response.status_code == 200
            assert "console.log" in js_response.text

            css_response = client.get("/stemtrace/assets/style.css")
            assert css_response.status_code == 200
            assert "body" in css_response.text

    def test_assets_not_served_at_root(self, mock_dist: Path) -> None:
        """Assets at /assets/ should 404 when mounted at /stemtrace."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(
                broker_url="memory://", embedded_consumer=False, prefix="/stemtrace"
            )
            app = FastAPI()
            app.include_router(ext.router, prefix="/stemtrace")

            client = TestClient(app)

            # Root /assets/ should not work
            response = client.get("/assets/app.js")
            assert response.status_code == 404


class TestTrailingSlashRedirect:
    """Tests for trailing slash redirect to prevent fall-through to catch-all mounts."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create mock dist."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()
        (dist_dir / "index.html").write_text("<html><head></head></html>")
        return dist_dir

    def test_no_trailing_slash_redirects(self, mock_dist: Path) -> None:
        """/stemtrace redirects to /stemtrace/ via init_app."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(broker_url="memory://", embedded_consumer=False)
            app = FastAPI()
            ext.init_app(app)

            client = TestClient(app, follow_redirects=False)
            response = client.get("/stemtrace")

            assert response.status_code == 307
            assert response.headers["location"] == "/stemtrace/"

    def test_no_trailing_slash_with_follow_redirects(self, mock_dist: Path) -> None:
        """/stemtrace redirects to /stemtrace/ and serves HTML."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(broker_url="memory://", embedded_consumer=False)
            app = FastAPI()
            ext.init_app(app)

            client = TestClient(app, follow_redirects=True)
            response = client.get("/stemtrace")

            assert response.status_code == 200
            assert "window.__STEMTRACE_BASE__" in response.text

    def test_no_trailing_slash_doesnt_fall_through_to_mount(
        self, mock_dist: Path
    ) -> None:
        """/stemtrace should NOT fall through to a catch-all mount at /."""
        from starlette.responses import PlainTextResponse

        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(broker_url="memory://", embedded_consumer=False)
            app = FastAPI()
            ext.init_app(app)

            # Simulate Django-like catch-all mount
            async def catch_all(scope: dict, receive: object, send: object) -> None:
                response = PlainTextResponse("Django caught this!", status_code=200)
                await response(scope, receive, send)  # type: ignore[arg-type]

            app.mount("/", catch_all)

            client = TestClient(app)
            response = client.get("/stemtrace")

            # Should be redirected to /stemtrace/, NOT caught by Django mount
            assert response.status_code == 200
            assert "Django caught this!" not in response.text
            assert "window.__STEMTRACE_BASE__" in response.text


class TestLifespanComposition:
    """Tests for lifespan composition via init_app."""

    @pytest.fixture
    def mock_dist(self, tmp_path: Path) -> Path:
        """Create mock dist."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        assets_dir = dist_dir / "assets"
        assets_dir.mkdir()
        (dist_dir / "index.html").write_text("<html></html>")
        return dist_dir

    def test_lifespan_order_with_init_app(self, mock_dist: Path) -> None:
        """init_app wraps lifespan: stemtrace starts first, stops last."""
        events: list[str] = []

        @asynccontextmanager
        async def user_lifespan(app: FastAPI) -> AsyncIterator[None]:
            events.append("user_startup")
            yield
            events.append("user_shutdown")

        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            ext = StemtraceExtension(broker_url="memory://", embedded_consumer=False)

            # Patch before init_app so the wrapped lifespan captures patched methods
            original_start = ext._ws_manager.start_broadcast_loop
            original_stop = ext._ws_manager.stop_broadcast_loop

            async def tracked_start() -> None:
                events.append("stemtrace_startup")
                await original_start()

            async def tracked_stop() -> None:
                events.append("stemtrace_shutdown")
                await original_stop()

            ext._ws_manager.start_broadcast_loop = tracked_start  # type: ignore[method-assign]
            ext._ws_manager.stop_broadcast_loop = tracked_stop  # type: ignore[method-assign]

            app = FastAPI(lifespan=user_lifespan)
            ext.init_app(app)

            # TestClient triggers lifespan on enter/exit
            with TestClient(app):
                pass  # Lifespan runs on context enter

        # Verify order: stemtrace starts before user, stops after user
        assert events == [
            "stemtrace_startup",
            "user_startup",
            "user_shutdown",
            "stemtrace_shutdown",
        ]

    def test_user_lifespan_still_works(self, mock_dist: Path) -> None:
        """User's lifespan startup/shutdown are actually called."""
        user_started = False
        user_stopped = False

        @asynccontextmanager
        async def user_lifespan(app: FastAPI) -> AsyncIterator[None]:
            nonlocal user_started, user_stopped
            user_started = True
            yield
            user_stopped = True

        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            app = FastAPI(lifespan=user_lifespan)

            ext = StemtraceExtension(broker_url="memory://", embedded_consumer=False)
            ext.init_app(app)

            with TestClient(app):
                assert user_started is True

        assert user_stopped is True

    def test_init_app_without_user_lifespan(self, mock_dist: Path) -> None:
        """init_app works when app has no explicit lifespan."""
        with patch("stemtrace.server.ui.static._FRONTEND_DIR", mock_dist):
            app = FastAPI()  # No lifespan

            ext = StemtraceExtension(broker_url="memory://", embedded_consumer=False)
            ext.init_app(app)

            with TestClient(app) as client:
                response = client.get("/stemtrace/")
                assert response.status_code == 200
