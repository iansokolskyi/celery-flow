"""Tests for public API."""

from celery_flow import __version__, init


def test_version() -> None:
    """Version is set."""
    assert __version__ == "0.1.0"


def test_init_placeholder() -> None:
    """init() exists and is callable (placeholder for now)."""
    # Just verify it doesn't raise
    # Once implemented, this test should use a real Celery app
    init(None)  # type: ignore[arg-type]
