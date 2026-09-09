"""Example application configuration for the production API."""
import os
from remy import Auth


def options():
    names = ("DEMO_MODEL", "DEMO_TOKEN")
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise SystemExit("Set required environment variables: " + ", ".join(missing))
    return {
        "model": os.environ["DEMO_MODEL"],
        "auth": Auth(token=os.environ["DEMO_TOKEN"], gateway="https://api.corepass.com/edge/v1"),
    }


def require_completed(result):
    result.raise_for_status()
    if result.status != "completed":
        raise RuntimeError(f"Run ended with status {result.status}")
