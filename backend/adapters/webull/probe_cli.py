"""Command-line entry point for the redacted, read-only Webull capability probe."""
from __future__ import annotations

import json
import argparse

from .probe import CapabilityProbe, WebullClient, WebullCredentials


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the redacted Webull read-only capability probe.")
    parser.add_argument("--option-symbol", default="AAPL", help="A valid option contract symbol or ID from Webull (default: AAPL, which only checks endpoint reachability).")
    args = parser.parse_args()
    credentials = WebullCredentials.from_local_env()
    report = CapabilityProbe(WebullClient(credentials)).run(option_symbol=args.option_symbol)
    print(json.dumps(report.redacted_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
