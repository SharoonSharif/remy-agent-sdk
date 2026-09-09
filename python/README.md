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
# Set DEMO_TOKEN securely in your shell or secret manager.
```

The examples use the production API at `https://api.corepass.com/edge/v1`.
The bearer is a gateway token, not a direct model-provider API key. `.env.example`
is a reference and is not automatically loaded.

```bash
.venv/bin/python examples/hello.py
.venv/bin/python examples/streaming.py
.venv/bin/python examples/custom_tool.py
```

For an IDE run configuration, select this directory's `.venv/bin/python` as the
Python interpreter (Windows: `.venv/Scripts/python.exe`). Set `REMY_CORE`,
`DEMO_MODEL`, and `DEMO_TOKEN` in that run configuration; an IDE launched outside
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
