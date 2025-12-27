"""Integration tests for FastAPI components."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from celery_flow.core.events import TaskEvent, TaskState
from celery_flow.server.fastapi.auth import require_api_key, require_basic_auth
from celery_flow.server.fastapi.extension import CeleryFlowExtension
from celery_flow.server.fastapi.router import create_router
from celery_flow.server.store import GraphStore
from celery_flow.server.websocket import WebSocketManager


class TestCreateRouter:
    """Tests for create_router() factory function."""

    def test_create_router_with_defaults(self) -> None:
        """Router creates its own store and ws_manager if not provided."""
        router = create_router()

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Health endpoint should work
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_create_router_with_store(self) -> None:
        """Router uses provided store."""
        store = GraphStore()
        store.add_event(
            TaskEvent(
                task_id="test-123",
                name="tests.sample",
                state=TaskState.SUCCESS,
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )

        router = create_router(store=store)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/tasks/test-123")
        assert response.status_code == 200
        assert response.json()["task"]["task_id"] == "test-123"

    def test_create_router_with_auth(self) -> None:
        """Router applies auth dependency."""
        router = create_router(auth_dependency=require_api_key("secret"))
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Without auth - should fail
        response = client.get("/api/health")
        assert response.status_code == 401

        # With auth - should work
        response = client.get("/api/health", headers={"X-API-Key": "secret"})
        assert response.status_code == 200


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint integration."""

    def test_websocket_connect_disconnect(self) -> None:
        """WebSocket connects and disconnects cleanly."""
        store = GraphStore()
        ws_manager = WebSocketManager()
        router = create_router(store=store, ws_manager=ws_manager)

        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            with client.websocket_connect("/ws"):
                assert ws_manager.connection_count == 1

            # After disconnect
            assert ws_manager.connection_count == 0


class TestCeleryFlowExtension:
    """Tests for CeleryFlowExtension lifecycle."""

    def test_extension_creates_components(self) -> None:
        """Extension creates store, ws_manager, and optionally consumer."""
        ext = CeleryFlowExtension(
            broker_url="memory://",
            embedded_consumer=True,
        )

        assert ext.store is not None
        assert ext.ws_manager is not None
        assert ext.consumer is not None

    def test_extension_without_consumer(self) -> None:
        """Extension can run without embedded consumer."""
        ext = CeleryFlowExtension(
            broker_url="memory://",
            embedded_consumer=False,
        )

        assert ext.consumer is None

    def test_extension_router_includes_api(self) -> None:
        """Extension router includes API endpoints."""
        ext = CeleryFlowExtension(broker_url="memory://", serve_ui=False)

        app = FastAPI()
        app.include_router(ext.router, prefix="/flow")
        client = TestClient(app)

        response = client.get("/flow/api/health")
        assert response.status_code == 200

    def test_extension_with_auth(self) -> None:
        """Extension applies auth to routes."""
        ext = CeleryFlowExtension(
            broker_url="memory://",
            serve_ui=False,
            auth_dependency=require_basic_auth("admin", "pass"),
        )

        app = FastAPI()
        app.include_router(ext.router, prefix="/flow")
        client = TestClient(app)

        # Without auth
        response = client.get("/flow/api/health")
        assert response.status_code == 401

        # With auth
        response = client.get("/flow/api/health", auth=("admin", "pass"))
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_extension_lifespan(self) -> None:
        """Extension lifespan starts/stops ws_manager broadcast loop."""
        ext = CeleryFlowExtension(
            broker_url="memory://",
            embedded_consumer=False,  # Don't test consumer here (blocks)
            serve_ui=False,
        )

        app = FastAPI()

        # Simulate lifespan
        async with ext.lifespan(app):
            # WS manager should have loop
            assert ext.ws_manager._loop is not None
            assert ext.ws_manager._broadcast_task is not None

        # After lifespan exit
        assert ext.ws_manager._loop is None
        assert ext.ws_manager._broadcast_task is None

    @pytest.mark.asyncio
    async def test_extension_compose_lifespan(self) -> None:
        """Extension can compose with another lifespan."""
        ext = CeleryFlowExtension(broker_url="memory://", embedded_consumer=False)

        other_started = False
        other_stopped = False

        @asynccontextmanager
        async def other_lifespan(app: FastAPI) -> AsyncIterator[None]:
            nonlocal other_started, other_stopped
            other_started = True
            yield
            other_stopped = True

        combined = ext.compose_lifespan(other_lifespan)
        app = FastAPI()

        async with combined(app):
            assert other_started

        assert other_stopped

    def test_extension_store_receives_events(self) -> None:
        """Events added to store are accessible via API."""
        ext = CeleryFlowExtension(
            broker_url="memory://",
            embedded_consumer=False,
            serve_ui=False,
        )

        # Add event directly to store
        ext.store.add_event(
            TaskEvent(
                task_id="direct-event",
                name="tests.direct",
                state=TaskState.STARTED,
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.include_router(ext.router)
        client = TestClient(app)

        response = client.get("/api/tasks/direct-event")
        assert response.status_code == 200
        assert response.json()["task"]["name"] == "tests.direct"
