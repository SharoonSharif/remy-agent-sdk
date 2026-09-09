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
export DEMO_GATEWAY=https://your-gateway.example/v1
# Set DEMO_TOKEN securely in your shell or secret manager.
```

The bearer is a gateway token, not a direct model-provider API key. `.env.example`
is a reference and is not automatically loaded.

```bash
python examples/hello.py
python examples/streaming.py
python examples/custom_tool.py
```

Expect final text for hello, incremental text plus usage for streaming, and a
`Local add(...)` line followed by the result for the tool example. Model tool
selection is not deterministic: the tool example fails explicitly if the model
does not call the addition tool. A failed or interrupted run exits nonzero.
The Core subprocess is closed even when a run raises an exception.
