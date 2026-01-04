"""Wait for an HTTP endpoint to respond with a 2xx status."""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    """Wait for an HTTP endpoint to become healthy (2xx) or exit non-zero."""
    args = _parse_args()
    deadline = time.monotonic() + args.timeout
    last_error: str | None = None

    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(args.url, method="GET")
            with urllib.request.urlopen(request, timeout=2.0) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)

        time.sleep(args.interval)

    raise SystemExit(f"Service not healthy within {args.timeout}s: {last_error}")


if __name__ == "__main__":
    main()
