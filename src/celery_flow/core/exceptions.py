"""Domain exceptions for celery-flow.

All celery-flow exceptions inherit from CeleryFlowError, making it easy
to catch all library-specific errors with a single except clause.

Exception hierarchy:
    CeleryFlowError
    ├── ConfigurationError
    │   └── UnsupportedBrokerError
    └── TransportError

Example:
    >>> try:
    ...     init(app, transport_url="kafka://localhost")
    ... except CeleryFlowError as e:
    ...     print(f"celery-flow error: {e}")
"""


class CeleryFlowError(Exception):
    """Base exception for all celery-flow errors.

    Catch this to handle any error raised by the library.
    """


class ConfigurationError(CeleryFlowError):
    """Invalid or missing configuration.

    Raised when celery-flow cannot be initialized due to
    configuration problems (missing broker URL, invalid settings, etc.).
    """


class TransportError(CeleryFlowError):
    """Transport-related error.

    Raised when event publishing or consuming fails due to
    connection issues, timeouts, or broker unavailability.

    Note:
        In the library (Celery side), transport errors are caught and
        logged rather than propagated, to avoid affecting task execution.
    """


class UnsupportedBrokerError(ConfigurationError):
    """Broker URL scheme is not supported.

    Raised when attempting to create a transport from a URL with an
    unsupported scheme (e.g., "kafka://").

    Attributes:
        scheme: The unsupported URL scheme that was provided.
    """

    def __init__(self, scheme: str) -> None:
        """Initialize with the unsupported scheme.

        Args:
            scheme: The URL scheme that is not supported (e.g., "kafka").
        """
        self.scheme = scheme
        super().__init__(
            f"Unsupported broker scheme: '{scheme}'. "
            f"Supported: redis, rediss, amqp, amqps, memory"
        )
