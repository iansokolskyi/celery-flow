"""Tests for exception classes."""

from celery_flow.core.exceptions import (
    CeleryFlowError,
    ConfigurationError,
    TransportError,
    UnsupportedBrokerError,
)


def test_celery_flow_error_base() -> None:
    """CeleryFlowError is the base exception."""
    err = CeleryFlowError("test error")
    assert str(err) == "test error"
    assert isinstance(err, Exception)


def test_configuration_error_inherits() -> None:
    """ConfigurationError inherits from CeleryFlowError."""
    err = ConfigurationError("bad config")
    assert isinstance(err, CeleryFlowError)


def test_transport_error_inherits() -> None:
    """TransportError inherits from CeleryFlowError."""
    err = TransportError("connection failed")
    assert isinstance(err, CeleryFlowError)


def test_unsupported_broker_error() -> None:
    """UnsupportedBrokerError has scheme info."""
    err = UnsupportedBrokerError("kafka")

    assert err.scheme == "kafka"
    assert "kafka" in str(err)
    assert "Unsupported broker scheme" in str(err)
    assert isinstance(err, ConfigurationError)
