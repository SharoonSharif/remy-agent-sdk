# TypeScript examples

Requires Node.js 22.22+ (native type stripping). Run from `typescript/`:

```bash
# Once you have package-registry access:
npm install
# Or install the SDK tarball supplied by the maintainers:
# npm install --no-save --package-lock=false /path/to/remy-agent-sdk.tgz
```

Set `REMY_CORE`, `DEMO_MODEL`, `DEMO_GATEWAY` and `DEMO_TOKEN` in your shell.
See `.env.example` for placeholders; it is not automatically loaded. `REMY_CORE`
is the absolute path to the compatible frozen executable. The token is a gateway
bearer, not a direct model-provider API key.

```bash
npm run typecheck
npm run hello
npm run streaming
npm run tool
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
