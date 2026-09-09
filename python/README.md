# Python examples

Requires Python 3.11+ and a compatible frozen Core. Keep this environment separate
from any Core development environment.

Run commands from `python/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
# Once you have package-index access:
python -m pip install 'remy-agent-sdk==0.0.1'
# Or install the wheel supplied by the maintainers:
# python -m pip install /path/to/remy_agent_sdk-0.0.1-py3-none-any.whl
```

Set configuration in your shell (PowerShell users can use `$env:NAME = "value"`):

```bash
export REMY_CORE=/absolute/path/to/core/executable
export DEMO_MODEL=your-enabled-model
export DEMO_PRODUCT_ID=your-product-id
# Set DEMO_TOKEN securely in your shell or secret manager.
```

The examples use the development API at `https://dev-api.corepass.com/edge/v1`.
Copy `.env.example` to `.env` in the language directory and fill it in;
the examples load that file, but never override a variable already set in the
environment, so an exported value or an IDE run configuration still wins.
`.env.example` contains placeholders only — do not commit real credentials.

The bearer is a `cpst2` SERVICE token, not a user's own bearer and not a
direct model-provider API key. The gateway enforces task attribution: a
service-authenticated call has no live session to bill, so every model call
must carry the id of a usage task. `config.with_task` / `withTask` opens one
against `POST /tasks` and passes the id to the Core as `SANDBOX_TASK_ID`, which
the Core copies into `metadata.task_id`. `DEMO_PRODUCT_ID` names the product
the spend is booked to and must be one of the audiences your token was issued
for.

```bash
.venv/bin/python examples/hello.py
.venv/bin/python examples/streaming.py
.venv/bin/python examples/custom_tool.py
# Needs no REMY_CORE — it starts no Core.
.venv/bin/python examples/models.py
```

For an IDE run configuration, select this directory's `.venv/bin/python` as the
Python interpreter (Windows: `.venv/Scripts/python.exe`). Set `REMY_CORE`,
`DEMO_MODEL`, `DEMO_TOKEN`, and `DEMO_PRODUCT_ID` in that run configuration; an IDE launched outside
your terminal may not inherit its environment variables.

If `from remy import Agent` fails, check the package loaded by the selected
interpreter:

```bash
.venv/bin/python -c 'import sys, remy; print(sys.executable); print(remy.__file__); from remy import Agent; print(Agent)'
```

The package path should be inside this virtual environment's `site-packages`
when using a wheel. A path into a different SDK checkout indicates that a source
path or editable installation is taking precedence. Select the example virtual
environment and remove unrelated SDK source directories from the run
configuration's `PYTHONPATH` or source roots.

Expect final text for hello, incremental text plus usage for streaming, and a
`Local add(...)` line followed by the result for the tool example. Model tool
selection is not deterministic: the tool example fails explicitly if the model
does not call the addition tool. A failed or interrupted run exits nonzero.
The Core subprocess is closed even when a run raises an exception.
