# Remy Agent SDK

The public integration hub for Remy Agent SDK: runnable Python and TypeScript
examples, setup instructions, and developer feedback.

This repository contains client examples. The SDK implementation and Core runtime
are distributed separately. Examples use only the public SDK API.

## Availability

**Preview:** SDK and compatible Core distribution access is still being prepared.
This repository being public does not mean the packages are publicly installable
yet. Until registry access is available, obtain the SDK wheel/tarball and a
compatible frozen Core from the maintainers. No access to an implementation
repository is required to run the examples.

The examples currently target Python SDK `0.0.1` and TypeScript SDK `0.1.0`.
These are independent SDK versions, not a Core compatibility guarantee. Supply
`REMY_CORE` explicitly during preview; use a Core advertising `sdk.agent.v1`.

## Choose your language

| Python 3.11+ | Node.js 22.22+ / TypeScript |
| --- | --- |
| [Setup and examples](python/README.md) | [Setup and examples](typescript/README.md) |

Both language directories include the same three scenarios:

1. **Hello** — run a prompt and read the final result.
2. **Streaming** — consume text events and inspect final token usage.
3. **Custom tool** — expose a local addition function and explicitly authorize it.

Every example runs a real Agent through its Core subprocess. A live model run
requires an enabled model, a gateway URL and a gateway bearer token; provider
charges may apply. Tokens are read from the environment and never included in
example output. `.env.example` contains placeholders only; examples do not load
`.env` files automatically.

By default, the SDK starts with no product preset, project settings or built-in
tools. The custom-tool example grants access only to its own addition function.

## Repository layout

```text
python/       Independent Python example application
typescript/   Independent TypeScript example application
.github/      Syntax checks that do not need registry credentials
```

## Local integration smoke test

After installing both example environments and obtaining a compatible frozen
Core, run from the repository root:

```bash
REMY_CORE=/absolute/path/to/core/executable python3 scripts/smoke.py
```

This starts a local HTTP model peer and executes all six examples through their
installed SDK packages and the real Core. It uses a temporary state directory
and a dummy local token, with no provider credentials or external model calls.
Expect six `PASS` lines. TypeScript's `npm run typecheck` is a separate check.

The syntax workflow checks parsing only. It does not claim model integration or
SDK compatibility verification. Local maintainer acceptance runs the examples
against installed SDK artifacts and a compatible Core using a local HTTP model
peer; private credentials and build artifacts are not checked into this repo.

## Feedback

Please use [Issues](https://github.com/corepasshq/remy-agent-sdk/issues) for
integration questions and reproducible failures. Include the example name,
language/runtime version, SDK version and sanitized error message. Never include
tokens, personal conversation content or private project files.

[中文说明](README.zh-CN.md)
