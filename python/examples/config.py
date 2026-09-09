"""Example application configuration for the development API."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from remy import Auth

GATEWAY = "https://dev-api.corepass.com/edge/v1"

#: Sits next to this directory, so running an example straight from an IDE
#: works without a shell that has sourced anything.
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _load_env_file(path=ENV_FILE):
    """Fill in DEMO_* from ``python/.env``, WITHOUT overriding what is set.

    Not overriding is the load-bearing half. ``scripts/smoke.py`` runs the
    examples against a local fake model peer by injecting ``DEMO_*`` into the
    child environment; if a developer's real ``.env`` won here, the smoke run
    would authenticate with a real token against the real gateway and stop
    being the offline check it advertises. A shell that exported something on
    purpose wins for the same reason.

    Hand-parsed rather than pulling in python-dotenv: these examples are
    published to show what integrating the SDK costs, and one convenience is
    not worth a dependency in that answer.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        # No .env is the normal case for a consumer who exports in the shell.
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.removeprefix("export ").strip()
        if not name or name in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[name] = value


def options():
    _load_env_file()
    names = ("DEMO_MODEL", "DEMO_TOKEN", "DEMO_PRODUCT_ID")
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise SystemExit("Set required environment variables: " + ", ".join(missing))
    return {
        "model": os.environ["DEMO_MODEL"],
        "auth": Auth(token=os.environ["DEMO_TOKEN"], gateway=GATEWAY),
    }


def with_task(config):
    """Open a usage task and put its id where the Core will look for it.

    The bearer is a ``cpst2`` SERVICE credential, not a user's own token, and
    the gateway runs task attribution in enforce mode: a service-authenticated
    call carries no live session to bill, so it must name the task that
    authorized the spend or the request is rejected with 400
    ``metadata.task_id is required``.

    The id travels by ENVIRONMENT rather than an SDK argument, because the Core
    is what talks to the gateway -- it reads ``SANDBOX_TASK_ID`` and copies the
    value into ``metadata.task_id`` on every model call. Nothing in the SDK's
    own surface needs to know about it.

    ``env`` REPLACES the child's environment rather than overlaying it (the
    TypeScript binding's ``process.env`` overlays instead), so the parent's own
    variables have to be passed through explicitly.
    """
    auth = config["auth"]
    return {
        **config,
        "env": {**os.environ, "SANDBOX_TASK_ID": _open_task(auth)},
    }


def _open_task(auth):
    """Mint a task id from the gateway, or raise with the reason it refused.

    ``product_id`` must be one of the audiences the service token was issued
    for -- the gateway checks exact membership, so a token audienced only for
    its own service name cannot open a task for any product. ``system`` books
    the spend to the service itself; naming a user instead takes both
    ``user_id`` and ``tenant_id`` and a token carrying ``attribute_for_others``.
    """
    request = urllib.request.Request(
        f"{auth.gateway}/tasks",
        data=json.dumps(
            {"product_id": os.environ["DEMO_PRODUCT_ID"], "system": True}
        ).encode(),
        headers={
            "Authorization": f"Bearer {auth.token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)["task_id"]
    except urllib.error.HTTPError as exc:
        # The body says which of product_id/user_id/tenant_id the gateway
        # objected to. Swallowing it leaves only "HTTP Error 400: Bad Request".
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"Could not open a usage task ({exc.code}): {detail}") from exc


def require_completed(result):
    result.raise_for_status()
    if result.status != "completed":
        raise RuntimeError(f"Run ended with status {result.status}")
