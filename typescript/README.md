# TypeScript examples

Requires Node.js 22.22+ (native type stripping). Run from `typescript/`:

```bash
# Once you have package-registry access:
npm install
# Or install the SDK tarball supplied by the maintainers:
# npm install --no-save --package-lock=false /path/to/remy-agent-sdk.tgz
```

The examples use the development API at `https://dev-api.corepass.com/edge/v1`.
Set `REMY_CORE`, `DEMO_MODEL`, `DEMO_TOKEN` and `DEMO_PRODUCT_ID` in your shell.
Copy `.env.example` to `.env` in the language directory and fill it in;
the examples load that file, but never override a variable already set in the
environment, so an exported value or an IDE run configuration still wins.
`.env.example` contains placeholders only — do not commit real credentials.

`REMY_CORE` is the absolute path to the compatible frozen executable.

The bearer is a `cpst2` SERVICE token, not a user's own bearer and not a
direct model-provider API key. The gateway enforces task attribution: a
service-authenticated call has no live session to bill, so every model call
must carry the id of a usage task. `config.with_task` / `withTask` opens one
against `POST /tasks` and passes the id to the Core as `SANDBOX_TASK_ID`, which
the Core copies into `metadata.task_id`. `DEMO_PRODUCT_ID` names the product
the spend is booked to and must be one of the audiences your token was issued
for.

```bash
npm run typecheck
npm run hello
npm run streaming
npm run tool
# Needs no REMY_CORE — it starts no Core.
npm run models
```

Hello prints final text. Streaming prints incremental text and final usage. The
tool example registers a local addition function, grants only that function
permission, and requires it to be called. Model tool selection is not deterministic;
use a tool-capable model. Any non-completed result exits nonzero. `finally` closes
the Core child on errors as well as success.

This application uses the Node-only `/agent` entry. The package root is a different
surface; browser applications must not import this subprocess-based Node entry.
A registry lockfile will be added once the SDK distribution is publicly accessible;
local tarball paths are deliberately not committed as a shared lockfile.
