"""E2E tests for worker lifecycle visibility.

These tests validate Phase 8 end-to-end behavior in Docker:
- a real Celery worker starts
- stemtrace captures worker_ready
- server consumes the event and exposes it via /api/workers
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import pytest
from redis import Redis

from tests.e2e.conftest import API_URL

if TYPE_CHECKING:
    import httpx


def _wait_for_workers(
    api_client: httpx.Client, timeout: float = 30.0
) -> dict[str, Any]:
    """Poll /workers until at least one worker is present."""
    start = time.time()
    last: dict[str, Any] | None = None
    while time.time() - start < timeout:
        resp = api_client.get("/workers")
        if resp.status_code == 200:
            data = resp.json()
            last = data
            if data.get("total", 0) > 0 and data.get("workers"):
                return data
        time.sleep(0.5)
    raise TimeoutError(
        f"No workers visible via {API_URL}/workers within {timeout}s. Last: {last}"
    )


def _wait_for_worker_ready_in_redis(
    redis_client: Redis[bytes],
    stream_key: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Poll Redis stream until a worker_ready event is found."""
    start = time.time()
    last_len = 0
    while time.time() - start < timeout:
        # Read a recent window; worker_ready should be near the start but is retained by stream.
        entries = redis_client.xrevrange(stream_key, count=200)
        last_len = len(entries)
        for _msg_id, fields in entries:
            raw = fields.get(b"data")
            if not raw:
                continue
            try:
                parsed = json.loads(raw.decode())
            except json.JSONDecodeError:
                continue
            if parsed.get("event_type") == "worker_ready":
                return parsed
        time.sleep(0.5)
    raise TimeoutError(
        f"No worker_ready event found in Redis stream {stream_key!r} within {timeout}s "
        f"(scanned up to {last_len} entries)."
    )


@pytest.mark.e2e
class TestWorkersLifecycleE2E:
    """Phase 8 E2E worker lifecycle tests."""

    def test_workers_endpoint_shows_live_worker(self, api_client: httpx.Client) -> None:
        """Verify /api/workers eventually shows at least one worker."""
        data = _wait_for_workers(api_client, timeout=45.0)
        worker = data["workers"][0]
        assert isinstance(worker.get("hostname"), str)
        assert isinstance(worker.get("pid"), int)
        assert worker.get("status") in {"online", "offline"}
        assert isinstance(worker.get("registered_tasks"), list)

    def test_workers_by_hostname_endpoint_filters(
        self, api_client: httpx.Client
    ) -> None:
        """Verify /api/workers/{hostname} returns only matching hostnames."""
        data = _wait_for_workers(api_client, timeout=45.0)
        hostname = data["workers"][0]["hostname"]

        resp = api_client.get(f"/workers/{hostname}")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["total"] >= 1
        assert all(w["hostname"] == hostname for w in payload["workers"])

    def test_worker_ready_event_is_published_to_redis_stream(self) -> None:
        """Verify worker_ready exists in Redis streams (signal handler + transport)."""
        # Docker compose exposes redis on 16379 to avoid local conflicts.
        redis_client: Redis[bytes] = Redis.from_url(
            "redis://localhost:16379/0", decode_responses=False
        )
        stream_key = "stemtrace:events"
        try:
            event = _wait_for_worker_ready_in_redis(
                redis_client, stream_key, timeout=45.0
            )
            assert event["event_type"] == "worker_ready"
            assert isinstance(event.get("hostname"), str)
            assert isinstance(event.get("pid"), int)
            # Should include at least one E2E task
            tasks = event.get("registered_tasks") or []
            assert isinstance(tasks, list)
            assert any(t == "e2e.add" for t in tasks)
        finally:
            redis_client.close()
