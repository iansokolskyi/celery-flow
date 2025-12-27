"""CLI entry point for celery-flow server."""

from typing import Annotated

import typer

app = typer.Typer(
    name="celery-flow",
    help="Celery task flow visualizer",
    no_args_is_help=True,
)


@app.command()
def server(
    broker_url: Annotated[
        str,
        typer.Option(
            "--broker-url",
            "-b",
            envvar="CELERY_FLOW_BROKER_URL",
            help="Broker URL for consuming events",
        ),
    ],
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload (development)"),
    ] = False,
) -> None:
    """Start the celery-flow web server."""
    typer.echo(f"Starting celery-flow server on {host}:{port}")
    typer.echo(f"Broker: {broker_url}")
    # TODO: Implement actual server startup with uvicorn
    _ = reload


@app.command()
def consume(
    broker_url: Annotated[
        str,
        typer.Option(
            "--broker-url",
            "-b",
            envvar="CELERY_FLOW_BROKER_URL",
            help="Broker URL for consuming events",
        ),
    ],
) -> None:
    """Run the event consumer (standalone mode)."""
    typer.echo("Starting celery-flow consumer")
    typer.echo(f"Broker: {broker_url}")
    # TODO: Implement actual consumer


@app.command()
def version() -> None:
    """Show version information."""
    from celery_flow import __version__

    typer.echo(f"celery-flow {__version__}")


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
