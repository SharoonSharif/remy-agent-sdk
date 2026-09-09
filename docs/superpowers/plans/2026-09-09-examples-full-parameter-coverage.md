# Full Parameter Coverage for the Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the example set from 4 scenarios to 11 so that every one of `Agent`'s 20 parameters and all 27 public exports appear in at least one runnable, smoke-verified example.

**Architecture:** Each scenario is one file per binding (`python/examples/<name>.py`, `typescript/examples/<name>.ts`) exporting `main(config)` so `scripts/smoke.py` can drive it against a local fake model peer. The peer gains five capabilities first, because nothing new can be verified before it can produce the responses the new scenarios read. The smoke run's hard-coded three-name example list becomes a data table of eleven entries with per-example expected output.

**Tech Stack:** Python 3.11+ (stdlib only), TypeScript on Node 22.22+ (stdlib only), `remy-agent-sdk` 0.0.1 / `@corepass/remy-agent-sdk` 0.1.0, `scripts/smoke.py` (stdlib `http.server`).

**Spec:** `docs/superpowers/specs/2026-09-09-examples-full-parameter-coverage-design.md`

## Global Constraints

- **No new runtime dependency in either binding.** This repository exists to show what integrating the SDK costs; a dependency added here is a wrong answer to that question.
- **Every new example joins the offline smoke run.** No example is verified only by hand against the real gateway.
- **`core_spec` must be derived from the environment**, never a hard-coded path: it overrides `REMY_CORE`, which is exactly how the smoke run injects a Core.
- **`handshake_timeout` / `command_timeout` are demonstrated at or above their defaults** (10.0 / 30.0). Low values make the smoke run intermittent on a loaded machine.
- **Both bindings stay in step.** A scenario exists in Python and TypeScript or it is not done.
- **Every example exports `main(config)`** and reads gateway/token only from the passed config, never from ambient process configuration.
- **Examples print to stdout only**; no example writes a file outside a temp directory.
- Python examples are `python/examples/<snake_case>.py`; TypeScript examples are `typescript/examples/<kebab-case>.ts`. `smoke.py` already converts between the two.

**`$CORE` in every command below** means a Core executable advertising
`sdk.agent.v1`. No published `remy-core-bin` provides it yet, so export one
before starting and every command in this plan works as written:

```bash
export CORE=/absolute/path/to/a/core-host/advertising/sdk.agent.v1
```

The Core Host must be started with `--sdk`; a wrapper script that adds that
flag is the usual arrangement, because the SDK appends a fixed
`run-module src.bridge.core_host` with no `--sdk` of its own. Verify the export
before Task 1:

```bash
"$CORE" run-module src.bridge.core_host --sdk < /dev/null | head -c 400 | grep -q sdk.agent.v1 \
  && echo "core ok" || echo "this Core does not advertise sdk.agent.v1"
```

---

## File Structure

**Fake peer and harness (Tasks 1-3):**
- Modify `scripts/smoke.py` — `ModelPeer` gains path routing on GET, a real `/models` body, delayed streaming, a reasoning field, and an on-demand failure; `main()`'s example list becomes a data table.

**Scenarios (Tasks 4-10), each one file per binding:**

| File | Responsibility |
|---|---|
| `python/examples/one_shot.py` / `typescript/examples/one-shot.ts` | `run()` / `arun()` and the version constants |
| `python/examples/events.py` / `typescript/examples/events.ts` | every event type and the envelope |
| `python/examples/configuration.py` / `typescript/examples/configuration.ts` | the nine set-once constructor parameters |
| `python/examples/sessions.py` / `typescript/examples/sessions.ts` | `Session` lifecycle and `SessionStore` |
| `python/examples/extending.py` / `typescript/examples/extending.ts` | `skills`, `agents`, `hooks`, `hook_callbacks`, `mcp_servers` |
| `python/examples/errors.py` / `typescript/examples/errors.ts` | `RemyError` and its retry metadata |
| `python/examples/permissions.py` / `typescript/examples/permissions.ts` | `permission_mode`, `RunState`, cancel |

**Fixture (Task 6):**
- Create `python/examples/fixtures/settings.json` and `typescript/examples/fixtures/settings.json` — the one file that must exist on disk, for `setting_sources`.

**Docs (Task 11):**
- Modify `README.md`, `README.zh-CN.md`, `python/README.md`, `typescript/README.md`.

---

## Task 1: Peer path routing, a real model catalog, and the `preset` question

The peer answers `GET` from any path with `{"data": []}`. Two scenarios read the catalog, and one open question from the spec is settled here before any example depends on it.

**Files:**
- Modify: `scripts/smoke.py` (`ModelPeer.do_GET`, around line 60)

**Interfaces:**
- Consumes: nothing.
- Produces: `ModelPeer.CATALOG` — a `list[dict]` of `{"id": str, "owned_by": str}` served by `GET <path>/models`. Later tasks assert against the ids `"demo-model-a"` and `"demo-model-b"`.

- [ ] **Step 1: Settle the `preset` question the spec defers to this task**

Run the existing `hello` example with `preset="remy_code"` forced in, against the real dev gateway, and see whether the Core attempts a filesystem tool call:

```bash
cd /Users/youland/project/remy-agent-sdk/python && set -a && . ./.env && set +a && \
REMY_CORE="$CORE" .venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, 'examples')
from remy import Agent
from config import options, with_task
async def main():
    config = with_task(options())
    async with Agent(**config, preset='remy_code') as agent:
        handle = await agent.run('Say hello in one short sentence.')
        result = await handle.result(raise_on_error=True)
        print('status:', result.status)
        print('text:', result.text[:200])
asyncio.run(main())
"
```

Record the outcome in the Task 6 notes below. If the run completes, `configuration` sets `preset` and executes. If it hangs or errors on a tool call, `configuration` constructs the Agent with `preset` and asserts on `ConfigurationError`-free construction without running a turn, and a comment says why.

- [ ] **Step 2: Write the failing assertion into the peer's own behaviour**

Add to `scripts/smoke.py`, immediately after the `_json` helper added earlier:

```python
    #: Served by GET <path>/models. Two entries, because a one-entry list
    #: cannot catch a parser that returns only its first result.
    CATALOG = [
        {"id": "demo-model-a", "owned_by": "demo-provider"},
        {"id": "demo-model-b", "owned_by": "other-provider"},
    ]
```

- [ ] **Step 3: Run the smoke suite to confirm it still passes unchanged**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 6 PASS. The constant is not yet read by anything.

- [ ] **Step 4: Route GET by path**

Replace `ModelPeer.do_GET` entirely:

```python
    def do_GET(self):
        # Routing by path, which do_POST already does for /tasks. Serving one
        # body from every path let a wrong URL pass as a right one.
        if self.path.rstrip("/").endswith("/models"):
            self._json({"object": "list", "data": type(self).CATALOG})
            return
        self._json({"data": []})
```

- [ ] **Step 5: Verify the catalog is served, and only at /models**

```bash
python3 - <<'EOF'
import json, threading, urllib.request
from http.server import ThreadingHTTPServer
import sys; sys.path.insert(0, 'scripts')
from smoke import ModelPeer
s = ThreadingHTTPServer(("127.0.0.1", 0), ModelPeer)
threading.Thread(target=s.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{s.server_port}"
for path in ("/v1/models", "/v1/other"):
    with urllib.request.urlopen(base + path) as r:
        print(path, "->", json.load(r))
s.shutdown()
EOF
```

Expected: `/v1/models` returns the two-entry catalog; `/v1/other` returns `{"data": []}`.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke.py
git commit -m "test(smoke): route GET by path and serve a real model catalog"
```

---

## Task 2: Peer delayed streaming, a reasoning field, and an on-demand failure

Three capabilities the remaining scenarios cannot be verified without. All three are opt-in per request so the existing six cases keep their current behaviour.

**Files:**
- Modify: `scripts/smoke.py` (`ModelPeer.do_POST`)

**Interfaces:**
- Consumes: `ModelPeer.CATALOG` from Task 1.
- Produces: three request-driven behaviours, selected by the *prompt text* the example sends, because the prompt is the only channel an example controls end to end:
  - a prompt containing `"[[slow]]"` → streamed chunks with a 0.4s gap before the final chunk
  - a prompt containing `"[[thinking]]"` → a `reasoning_content` delta before the text delta
  - a prompt containing `"[[fail]]"` → HTTP 429 with `Retry-After: 2` and a JSON error body carrying `request_id`

- [ ] **Step 1: Write the failing probe**

Create `/tmp/peer_probe.py`:

```python
import json, threading, urllib.request, urllib.error, sys
from http.server import ThreadingHTTPServer
sys.path.insert(0, 'scripts')
from smoke import ModelPeer

s = ThreadingHTTPServer(("127.0.0.1", 0), ModelPeer)
threading.Thread(target=s.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{s.server_port}/v1/chat/completions"

def post(prompt, stream=False):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "stream": stream}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": "Bearer local-demo-token", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode()

try:
    post("[[fail]] anything")
    print("FAIL: expected 429")
except urllib.error.HTTPError as exc:
    print("429 ok, retry-after:", exc.headers.get("Retry-After"),
          "body:", exc.read().decode()[:120])
print("thinking:", "reasoning_content" in post("[[thinking]] hi", stream=True))
s.shutdown()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 /tmp/peer_probe.py`
Expected: prints `FAIL: expected 429`, then `thinking: False`.

- [ ] **Step 3: Implement the three behaviours**

In `scripts/smoke.py`, add `import time` to the imports. Then in `do_POST`, immediately after the `/tasks` branch, insert:

```python
        prompt = " ".join(
            str(m.get("content") or "") for m in body.get("messages", [])
        )
        # Selected by prompt text: the prompt is the only channel an example
        # controls all the way through the Core to here.
        if "[[fail]]" in prompt:
            payload = json.dumps({"error": {
                "code": 42901, "type": "rate_limited",
                "message": "demo rate limit", "request_id": "req-demo-1",
            }}).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "2")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
```

Then in the streaming branch, replace the chunk-writing loop with:

```python
            for index, chunk in enumerate(chunks):
                if index and "[[slow]]" in prompt:
                    # A reply that finishes instantly cannot be cancelled, and a
                    # test that cancels a finished run proves nothing.
                    time.sleep(0.4)
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.flush()
```

And immediately before that loop, add the reasoning delta:

```python
            if "[[thinking]]" in prompt:
                thinking = {**base, "object": "chat.completion.chunk", "choices": [
                    {"index": 0, "delta": {"reasoning_content": "Considering."},
                     "finish_reason": None}]}
                self.wfile.write(("data: " + json.dumps(thinking) + "\n\n").encode())
                self.wfile.flush()
```

- [ ] **Step 4: Run the probe to verify it passes**

Run: `python3 /tmp/peer_probe.py`
Expected: `429 ok, retry-after: 2 body: {"error": {"code": 42901, ...` and `thinking: True`.

- [ ] **Step 5: Run the existing suite to confirm nothing regressed**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: the same 6 PASS as before. None of the existing prompts contain a marker.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke.py
git commit -m "test(smoke): let the peer stall, reason, and fail on request"
```

---

## Task 3: Make the smoke example list a data table

The list is three hard-coded names and a two-branch `expected` expression. Eleven scenarios need per-example expected output, and `models` is not in the list at all.

**Files:**
- Modify: `scripts/smoke.py` (`main()`, the `for example in (...)` loop)

**Interfaces:**
- Consumes: nothing.
- Produces: `EXAMPLES` — a module-level `tuple[tuple[str, str], ...]` of `(example_name, expected_substring)`. Later tasks append one entry each.

- [ ] **Step 1: Add the table with only today's three, plus models**

Above `def main():` in `scripts/smoke.py`:

```python
#: (example name, a substring its stdout must contain). One row per scenario;
#: the run is this table times the two languages. An expected substring rather
#: than exact output, because an example may legitimately print more.
EXAMPLES = (
    ("hello", "Demo reply: ready."),
    ("streaming", "Demo reply: ready."),
    ("custom_tool", "Local add(2, 3) = 5"),
    ("models", "demo-model-a"),
)
```

- [ ] **Step 2: Read the table instead of the hard-coded names**

Replace the loop header and the `expected` lines:

```python
                for example, expected in EXAMPLES:
                    filename = example.replace("_", "-") if language == "typescript" else example
                    path = ROOT / language / "examples" / f"{filename}.{extension}"
                    result = subprocess.run([*executable, str(path), gateway],
                                            cwd=ROOT / language, env=env, text=True,
                                            capture_output=True, timeout=90)
                    if result.returncode:
                        raise RuntimeError(f"{language}/{filename} failed:\n{result.stderr}")
                    if expected not in result.stdout:
                        raise AssertionError(f"{language}/{filename} missing expected output:\n{result.stdout}")
                    print(f"PASS {language}/{filename}", flush=True)
```

- [ ] **Step 3: Run the suite**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 8 PASS — the original six plus `python/models` and `typescript/models`, which now assert against Task 1's catalog.

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke.py
git commit -m "test(smoke): drive the run from an example table, and include models"
```

---

## Task 4: `one_shot` — `run()`, `arun()` and the version constants

`run()` and `arun()` are a different entry point, not a different configuration. A consumer who needs one prompt should not have to read the Agent lifecycle to find them.

**Files:**
- Create: `python/examples/one_shot.py`, `typescript/examples/one-shot.ts`
- Modify: `scripts/smoke.py` (`EXAMPLES`), `typescript/package.json` (scripts)

**Interfaces:**
- Consumes: `EXAMPLES` from Task 3; `options()` / `with_task()` from `config.py` / `config.ts`.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Add the failing smoke rows**

In `scripts/smoke.py`, append to `EXAMPLES`:

```python
    ("one_shot", "Demo reply: ready."),
```

- [ ] **Step 2: Run the suite to verify it fails**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/one_shot` — the runner cannot load a file that does not exist.

- [ ] **Step 3: Write the Python example**

Create `python/examples/one_shot.py`:

```python
import asyncio
from remy import PROTOCOL_NAME, PROTOCOL_VERSION, SDK_API_VERSION, arun
from config import options, require_completed, with_task


async def main(config=None):
    # These three say which contract this binding speaks. Log them when
    # reporting a bug: "it does not work" and "it speaks protocol 1 against an
    # SDK expecting 2" are different reports.
    print(f"SDK API v{SDK_API_VERSION}, {PROTOCOL_NAME} v{PROTOCOL_VERSION}")

    # arun() is one prompt with no Agent to manage: it constructs one, runs,
    # and closes it. Use it when there is no second turn. The synchronous
    # sibling run() is the same call for a script with no event loop, and
    # cannot be used here because this function is already inside one.
    config = with_task(options() if config is None else config)
    result = await arun("Say hello in one short sentence.", **config)
    require_completed(result)
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Write the TypeScript example**

Create `typescript/examples/one-shot.ts`:

```ts
import { run, SDK_API_VERSION, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  // Says which contract this binding speaks. Log it when reporting a bug:
  // "it does not work" and "it speaks a different SDK API version than the
  // one you are reading about" are different reports.
  console.log(`SDK API v${SDK_API_VERSION}`);

  // run() is one prompt with no Agent to manage: it constructs one, runs, and
  // closes it. Use it when there is no second turn.
  const result = await run('Say hello in one short sentence.', await withTask(config));
  requireCompleted(result);
  console.log(result.text);
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 5: Add the npm script**

In `typescript/package.json`, after the `models` line:

```json
    "one-shot": "node --experimental-strip-types examples/one-shot.ts",
```

- [ ] **Step 6: Run the suite to verify it passes**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 10 PASS, including `python/one_shot` and `typescript/one-shot`.

If `run()`'s TypeScript signature does not accept `(prompt, options)`, read it from `node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/agent.d.ts` and adjust the call; the Python side is `arun(prompt, **options)` and was read from the installed package.

- [ ] **Step 7: Commit**

```bash
git add python/examples/one_shot.py typescript/examples/one-shot.ts scripts/smoke.py typescript/package.json
git commit -m "feat(examples): show the one-shot entry point and the version constants"
```

---

## Task 5: `events` — every event type and the envelope

`streaming` shows `TextDeltaEvent` only. Four event types and the envelope have nothing that reads them.

**Files:**
- Create: `python/examples/events.py`, `typescript/examples/events.ts`
- Modify: `scripts/smoke.py` (`EXAMPLES`), `typescript/package.json`

**Interfaces:**
- Consumes: the `[[thinking]]` peer marker from Task 2.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Add the failing smoke rows**

Append to `EXAMPLES`:

```python
    ("events", "thinking delta"),
```

- [ ] **Step 2: Run the suite to verify it fails**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/events`, file not found.

- [ ] **Step 3: Write the Python example**

Create `python/examples/events.py`:

```python
import asyncio
from remy import (
    Agent,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolEvent,
    UsageEvent,
    tool,
)
from config import options, require_completed, with_task


async def main(config=None):
    @tool
    def add(a: int, b: int) -> int:
        """Add two integers and return their sum."""
        return a + b

    config = with_task(options() if config is None else config)
    async with Agent(**config, tools=[add]) as agent:
        # "[[thinking]]" asks the local smoke peer for a reasoning delta. It is
        # an artefact of this repository's offline harness, not SDK syntax --
        # a real model emits reasoning when it reasons.
        handle = await agent.run("[[thinking]] Use add to calculate 2 + 3.")
        async for event in handle:
            # Two halves per event. The PAYLOAD is what happened; the ENVELOPE
            # is where it happened -- run_id, attempt_id, seq, origin. seq
            # orders events within a run, which matters once you buffer them.
            envelope = event.envelope
            if isinstance(event, ThinkingDeltaEvent):
                print(f"thinking delta seq={envelope.seq}: {event.text}")
            elif isinstance(event, TextDeltaEvent):
                print(f"text delta seq={envelope.seq}: {event.text}")
            elif isinstance(event, ToolEvent):
                print(f"tool event seq={envelope.seq}: {event.name}")
            elif isinstance(event, UsageEvent):
                print(f"usage event seq={envelope.seq}: {event.usage}")
            else:
                # Every other event still arrives as a typed RunEvent with the
                # same envelope, so an unknown kind is readable rather than lost.
                print(f"{type(event).__name__} seq={envelope.seq}")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print(f"run {result.run_id} finished as {result.status}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run only this example to check the event and envelope attribute names**

```bash
cd python && set -a && . ./.env && set +a && REMY_CORE="$CORE" .venv/bin/python examples/events.py
```

Expected: a `thinking delta` line, then text deltas, a tool event, a usage event, and a final run line. If an attribute name is wrong the traceback names it; the authoritative list is `EventEnvelope`'s fields:

```bash
cd python && .venv/bin/python -c "
import dataclasses
from remy import EventEnvelope
print([f.name for f in dataclasses.fields(EventEnvelope)])"
```

Fix the example to match the real field names before continuing.

- [ ] **Step 5: Write the TypeScript example**

Create `typescript/examples/events.ts`:

```ts
import { Agent, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  const agent = await Agent.connect({
    ...(await withTask(config)),
    tools: [{
      name: 'add', description: 'Add two integers and return their sum.',
      inputSchema: {
        type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
        required: ['a', 'b'], additionalProperties: false,
      },
      execute(input) { return Number(input.a) + Number(input.b); },
    }],
    onPermission(name, input) {
      return name === 'add' ? { behavior: 'allow', updatedInput: input } : { behavior: 'deny' };
    },
  });
  try {
    // "[[thinking]]" asks the local smoke peer for a reasoning delta. It is an
    // artefact of this repository's offline harness, not SDK syntax.
    const handle = await agent.run('[[thinking]] Use add to calculate 2 + 3.');
    for await (const event of handle) {
      // Two halves per event. The payload is what happened; the envelope is
      // where it happened — runId, attemptId, seq, origin.
      const seq = event.envelope?.seq;
      switch (event.type) {
        case 'assistant.thinking_delta': console.log(`thinking delta seq=${seq}: ${event.text}`); break;
        case 'assistant.text_delta': console.log(`text delta seq=${seq}: ${event.text}`); break;
        case 'tool.started': console.log(`tool event seq=${seq}: ${event.name}`); break;
        case 'run.usage': console.log(`usage event seq=${seq}:`, event.usage); break;
        default: console.log(`${event.type} seq=${seq}`);
      }
    }
    const result = await handle.result;
    requireCompleted(result);
    console.log(`run ${result.runId} finished as ${result.status}`);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 6: Check the TypeScript event type strings**

The `case` labels above are the expected wire names. Confirm them against the installed types before trusting them:

```bash
cd typescript && grep -rn "thinking_delta\|tool.started\|run.usage" node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/types.d.ts
```

Adjust any label the types spell differently. A `default` branch means a wrong label prints instead of crashing, so `npm run events` passing is not by itself proof — the expected `thinking delta` line must appear.

- [ ] **Step 7: Add the npm script and run the suite**

In `typescript/package.json`:

```json
    "events": "node --experimental-strip-types examples/events.ts",
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 12 PASS. The `events` row asserts `thinking delta`, so a wrong event label fails the run.

- [ ] **Step 8: Commit**

```bash
git add python/examples/events.py typescript/examples/events.ts scripts/smoke.py typescript/package.json
git commit -m "feat(examples): read every event type and its envelope"
```

---

## Task 6: `configuration` — the nine set-once parameters

Nine parameters are set once at construction and then invisible. Nine files would say nothing one Agent with every knob set does not, and would hide the fact worth seeing: they are all just constructor arguments.

**Files:**
- Create: `python/examples/configuration.py`, `typescript/examples/configuration.ts`
- Create: `python/examples/fixtures/settings.json`, `typescript/examples/fixtures/settings.json`
- Modify: `scripts/smoke.py` (`EXAMPLES`), `typescript/package.json`

**Interfaces:**
- Consumes: `options()` / `with_task()`.
- Produces: nothing later tasks depend on.

**Note from Task 1 Step 1:** record the `preset` outcome here before writing the example. If the forced-`preset` run completed, keep the `agent.run(...)` call below. If it hung or failed on a tool call, delete the `handle`/`result` lines, keep the constructor, and replace them with `print("configured; not run — see comment")` plus a comment naming what `preset` turned on.

- [ ] **Step 1: Add the failing smoke rows**

Append to `EXAMPLES`:

```python
    ("configuration", "configured cwd"),
```

- [ ] **Step 2: Run the suite to verify it fails**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/configuration`, file not found.

- [ ] **Step 3: Create both fixture files**

`python/examples/fixtures/settings.json` and `typescript/examples/fixtures/settings.json`, identical content:

```json
{
  "$comment": "A settings source for the configuration example. setting_sources takes file paths; this is the file, so the example has something real to point at.",
  "permissions": {}
}
```

- [ ] **Step 4: Write the Python example**

Create `python/examples/configuration.py`:

```python
import asyncio
import os
from pathlib import Path
from remy import Agent, ConfigurationError, CoreSpec
from config import options, require_completed, with_task

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def core_spec_from_env():
    """A CoreSpec built from REMY_CORE, never a hard-coded path.

    core_spec OVERRIDES the executable REMY_CORE names, so a literal path
    would point at someone else's machine -- and would break this repository's
    own smoke run, which works by injecting REMY_CORE. Returning None lets the
    SDK resolve the Core the ordinary way.
    """
    core = (os.environ.get("REMY_CORE") or "").strip()
    if not core:
        return None
    return CoreSpec(core, ("run-module", "src.bridge.core_host"))


async def main(config=None):
    config = with_task(options() if config is None else config)

    # Rejected before anything is spawned, and this is the one parameter whose
    # failure mode is worth showing: a bad permission_mode is a typo, and
    # finding out at construction beats finding out mid-run.
    try:
        Agent(**config, permission_mode="not-a-mode")
    except ConfigurationError as error:
        print(f"rejected at construction: {error}")

    async with Agent(
        **config,
        # Where the Core resolves relative paths. Defaults to the process's cwd.
        cwd=Path.cwd(),
        # Empty by default -- a blank slate. A string replaces it; a mapping
        # with a preset appends to that preset instead.
        system_prompt="You are terse.",
        # Product behaviour is opt-in. Without this the SDK ships no tools,
        # no project settings and no built-in prompt.
        preset="remy_code",
        # A ceiling on model round trips for one run, not a token budget.
        max_steps=8,
        # FILE paths, resolved to absolute. This is the file channel for
        # settings; inline skills/agents/hooks are the other, and inline
        # REPLACES rather than merges.
        setting_sources=[FIXTURES / "settings.json"],
        # Explicit at their defaults. Lowering handshake_timeout makes a cold
        # Core start look like a failure; lowering command_timeout makes a slow
        # model look like one.
        handshake_timeout=10.0,
        command_timeout=30.0,
        # None here means "resolve the Core normally" -- see the helper above.
        core_spec=core_spec_from_env(),
        # REPLACES the child's environment rather than overlaying it, which is
        # why config.with_task() splats os.environ when it adds SANDBOX_TASK_ID.
        env=dict(os.environ),
    ) as agent:
        print(f"configured cwd: {agent.cwd}")
        handle = await agent.run("Say hello in one short sentence.")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run it directly and confirm both prints appear**

```bash
cd python && set -a && . ./.env && set +a && REMY_CORE="$CORE" .venv/bin/python examples/configuration.py
```

Expected: a `rejected at construction:` line, a `configured cwd:` line, then the model's reply. If `preset="remy_code"` misbehaves, apply the Task 1 note above now.

- [ ] **Step 6: Write the TypeScript example**

Create `typescript/examples/configuration.ts`:

```ts
import { Agent, SDKError, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

const FIXTURES = new URL('./fixtures/', import.meta.url);

/**
 * Spawn options built from REMY_CORE, never a hard-coded path.
 *
 * `process.command` overrides the executable REMY_CORE names, so a literal
 * path would point at someone else's machine — and would break this
 * repository's own smoke run, which works by injecting REMY_CORE. Undefined
 * lets the SDK resolve the Core the ordinary way.
 */
function processFromEnv(): AgentOptions['process'] {
  const core = process.env.REMY_CORE?.trim();
  return core ? { command: core } : undefined;
}

export async function main(config: AgentOptions = options()): Promise<void> {
  const ready = await withTask(config);

  // Rejected before anything is spawned: a bad permissionMode is a typo, and
  // finding out at construction beats finding out mid-run.
  try {
    await Agent.connect({ ...ready, permissionMode: 'not-a-mode' as never });
  } catch (error) {
    console.log(`rejected at construction: ${(error as SDKError).message}`);
  }

  const agent = await Agent.connect({
    ...ready,
    cwd: process.cwd(),
    systemPrompt: 'You are terse.',
    preset: 'remy_code',
    maxSteps: 8,
    settingSources: [new URL('settings.json', FIXTURES).pathname],
    callbackTimeoutMs: 30_000,
    // `process.env` OVERLAYS the parent's environment here, where the Python
    // binding's `env` replaces it. Same contract, different spelling.
    process: processFromEnv(),
  });
  try {
    console.log(`configured cwd: ${process.cwd()}`);
    const handle = await agent.run('Say hello in one short sentence.');
    const result = await handle.result;
    requireCompleted(result);
    console.log(result.text);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 7: Reconcile the TypeScript option names**

`AgentOptions` has no `handshakeTimeout` / `commandTimeout` — it has `callbackTimeoutMs` and a `process` block. Confirm the full list and fix any name above that does not exist:

```bash
cd typescript && sed -n '/interface AgentOptions/,/^}/p' node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/agent.d.ts
```

Where a Python parameter has no TypeScript counterpart, say so in a comment rather than inventing one — the two bindings are one contract, and a real asymmetry is worth recording.

- [ ] **Step 8: Add the npm script and run the suite**

```json
    "configuration": "node --experimental-strip-types examples/configuration.ts",
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 14 PASS.

- [ ] **Step 9: Commit**

```bash
git add python/examples/configuration.py python/examples/fixtures/settings.json \
        typescript/examples/configuration.ts typescript/examples/fixtures/settings.json \
        scripts/smoke.py typescript/package.json
git commit -m "feat(examples): set every construction-time parameter in one place"
```

---

## Task 7: `sessions` — the Session lifecycle and SessionStore

All seven `Session` members and `SessionStore` have nothing that reads them. Session state is Core-side, so this needs nothing from the peer to *work*; the peer's history-varying reply is what lets the example *assert* the conversation continued.

**Files:**
- Create: `python/examples/sessions.py`, `typescript/examples/sessions.ts`
- Modify: `scripts/smoke.py` (`EXAMPLES`, `ModelPeer.do_POST`), `typescript/package.json`

**Interfaces:**
- Consumes: `options()` / `with_task()`.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Make the peer's reply depend on the history it receives**

Without this a resumed session and a fresh one look identical, so the example could pass while proving nothing. In `scripts/smoke.py`, in `do_POST`, replace the non-tool-call assistant message line:

```python
        else:
            # Turn count in the reply, so "the conversation continued" is
            # observable. With one canned answer, a resumed session and a fresh
            # one are indistinguishable and an assertion on either is empty.
            turns = sum(1 for m in body.get("messages", []) if m.get("role") == "user")
            message = {"role": "assistant", "content":
                       "The result is 5." if used_tool else f"Demo reply: ready. turn={turns}"}
```

- [ ] **Step 2: Run the suite to confirm the existing rows still pass**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 14 PASS. Every row asserting `Demo reply: ready.` still matches, because the turn marker is appended.

- [ ] **Step 3: Add the failing smoke rows**

Append to `EXAMPLES`:

```python
    ("sessions", "second turn saw turn=2"),
```

- [ ] **Step 4: Run the suite to verify it fails**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/sessions`, file not found.

- [ ] **Step 5: Write the Python example**

Create `python/examples/sessions.py`:

```python
import asyncio
import json
from remy import Agent, SessionStore
from config import options, require_completed, with_task


async def main(config=None):
    config = with_task(options() if config is None else config)

    # An in-memory cache of snapshots, and explicitly NOT an authority: the
    # Core owns session state. Pass your own to inspect what was cached;
    # omit it and the Agent makes one.
    store = SessionStore()

    async with Agent(**config, session_store=store) as agent:
        # agent.sessions is the collection; a Session is the handle.
        session = await agent.sessions.create()
        print(f"session {session.session_id}")

        first = await session.run("Say hello in one short sentence.")
        result = await first.result(raise_on_error=True)
        require_completed(result)

        # Same session, so the Core sends the accumulated history. The peer
        # echoes the turn count, which is how "it continued" is observable
        # rather than assumed.
        second = await session.run("And again, please.")
        result = await second.result(raise_on_error=True)
        require_completed(result)
        print(f"second turn saw {result.text.strip().split()[-1]}")

        # refresh() re-reads from the Core, the authority. The local Session
        # object is a snapshot and goes stale the moment a run advances it.
        session = await session.refresh()
        print(f"{len(session.messages)} messages after two turns")

        # fork() branches: the original keeps its history, the copy starts from
        # it. Use it to try two continuations without losing the first.
        branch = await session.fork()
        print(f"forked {session.session_id} -> {branch.session_id}")

        # The snapshot is plain data, so a consumer can persist it anywhere.
        # This is the shape session_store caches.
        print(f"snapshot keys: {sorted(json.loads(json.dumps(session.snapshot)))}")

        # Every session the store saw, for a consumer listing conversations.
        print(f"store holds {len(store.list())} snapshot(s)")

        # A session id is enough to resume in a later process -- the Core still
        # has the state, so nothing needs to be carried but the id.
        resumed = await agent.sessions.get(session.session_id)
        print(f"resumed {resumed.session_id}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run it directly**

```bash
cd python && set -a && . ./.env && set +a && REMY_CORE="$CORE" .venv/bin/python examples/sessions.py
```

Expected: a session id, `second turn saw turn=2`, a message count, a fork line, snapshot keys, a store count, and a resumed id. Against the real gateway the turn marker is absent — the real model does not echo it — so `second turn saw ...` prints the reply's last word instead. That is why the smoke assertion, not the real run, is the check for this line.

- [ ] **Step 7: Write the TypeScript example**

Create `typescript/examples/sessions.ts`:

```ts
import { Agent, MemorySessionStore, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  // An in-memory cache of snapshots, and explicitly NOT an authority: the Core
  // owns session state. The Python binding spells this `SessionStore`.
  const store = new MemorySessionStore();
  const agent = await Agent.connect({ ...(await withTask(config)), sessionStore: store });
  try {
    const session = await agent.sessions.create();
    console.log(`session ${session.sessionId}`);

    const first = await session.run('Say hello in one short sentence.');
    requireCompleted(await first.result);

    // Same session, so the Core sends the accumulated history. The peer echoes
    // the turn count, which is how "it continued" is observable.
    const second = await session.run('And again, please.');
    const result = await second.result;
    requireCompleted(result);
    console.log(`second turn saw ${result.text.trim().split(/\s+/).pop()}`);

    // refresh() re-reads from the Core, the authority. The local object is a
    // snapshot and goes stale the moment a run advances it.
    const fresh = await session.refresh();
    console.log(`${fresh.messages.length} messages after two turns`);

    // fork() branches: the original keeps its history, the copy starts from it.
    const branch = await fresh.fork();
    console.log(`forked ${fresh.sessionId} -> ${branch.sessionId}`);

    console.log(`snapshot keys: ${Object.keys(fresh.snapshot).sort().join(', ')}`);
    console.log(`store holds ${store.list().length} snapshot(s)`);

    const resumed = await agent.sessions.get(fresh.sessionId);
    console.log(`resumed ${resumed.sessionId}`);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 8: Check the TypeScript session member names**

`Sessions` and `Session` are exported from `sessions.js`; confirm the member names used above:

```bash
cd typescript && sed -n '/class Session/,/^}/p;/class Sessions/,/^}/p' node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/sessions.d.ts
```

- [ ] **Step 9: Add the npm script and run the suite**

```json
    "sessions": "node --experimental-strip-types examples/sessions.ts",
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 16 PASS.

- [ ] **Step 10: Commit**

```bash
git add python/examples/sessions.py typescript/examples/sessions.ts scripts/smoke.py typescript/package.json
git commit -m "feat(examples): resume, refresh and fork a session"
```

---

## Task 8: `extending` — skills, agents, hooks and an in-process MCP server

Five parameters, and the one place where the SDK does not validate what you pass: `skills` and `agents` are handed to the Core verbatim as JSON. The Core's accepted shape is therefore a real unknown, and Step 1 establishes it rather than guessing.

**Files:**
- Create: `python/examples/extending.py`, `typescript/examples/extending.ts`
- Modify: `scripts/smoke.py` (`EXAMPLES`), `typescript/package.json`

**Interfaces:**
- Consumes: `options()` / `with_task()`.
- Produces: nothing later tasks depend on.

**Known from the installed package** (read, not assumed):
- `hooks` accepts a mapping `{event: callable}`, or a list of `{"event": ..., "callback": <registered name>}` / `{"event": ..., "command": ...}` registrations.
- Valid hook events are exactly `before_run`, `after_run`, `before_tool`, `after_tool`. Any other name raises `ConfigurationError`.
- `hook_callbacks` is a `{name: callable}` mapping, which is what a list-form registration's `"callback"` refers to. The mapping form of `hooks` registers callables automatically and needs no `hook_callbacks`.
- `mcp_servers` is `{name: server}` where a server is `{"type": "sdk", "tools": [...]}` (in-process), or a stdio/http descriptor. The `sdk` variant needs no external process and no dependency.
- `skills` / `agents` are passed through verbatim; only JSON-serializability is enforced by the SDK.

- [ ] **Step 1: Establish the inline skills and agents shape**

The SDK will accept any JSON. The Core decides what is meaningful, so probe it:

```bash
cd /Users/youland/project/remy-agent-sdk/python && set -a && . ./.env && set +a && \
REMY_CORE="$CORE" .venv/bin/python -c "
import asyncio, sys
sys.path.insert(0, 'examples')
from remy import Agent
from config import options, with_task
async def main():
    config = with_task(options())
    async with Agent(
        **config,
        skills={'greet': {'description': 'Greet in one line.', 'instructions': 'Reply with a greeting.'}},
        agents={'summarizer': {'description': 'Summarize text.', 'prompt': 'Summarize briefly.'}},
    ) as agent:
        handle = await agent.run('Say hello in one short sentence.')
        print('status:', (await handle.result(raise_on_error=True)).status)
asyncio.run(main())
"
```

Expected: `status: completed`. If the Core rejects a key, the error names it — adopt the shape it accepts and use that in Step 3 instead of the guess above. Record the accepted shape as a comment in the example, so the next reader knows it was verified rather than invented.

- [ ] **Step 2: Add the failing smoke rows**

Append to `EXAMPLES`:

```python
    ("extending", "before_run hook fired"),
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/extending`, file not found.

- [ ] **Step 3: Write the Python example**

Create `python/examples/extending.py`, substituting the shape Step 1 confirmed:

```python
import asyncio
from remy import Agent, PermissionDecision, tool
from config import options, require_completed, with_task


async def main(config=None):
    fired = []

    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers and return their product."""
        return a * b

    def note_run_start(context):
        # Hooks run in THIS process, like tools and permission callbacks. The
        # Core asks; your code answers. Valid events are exactly before_run,
        # after_run, before_tool and after_tool -- any other name is a
        # ConfigurationError at construction.
        fired.append("before_run")
        print("before_run hook fired")

    def note_tool_start(context):
        fired.append("before_tool")
        print("before_tool hook fired")

    async def allow_multiply(name, arguments):
        if name == "multiply":
            return PermissionDecision("allow", updated_input=arguments)
        return PermissionDecision("deny")

    config = with_task(options() if config is None else config)
    async with Agent(
        **config,
        # Inline, and inline REPLACES rather than merges -- passing skills here
        # does not add to whatever setting_sources loaded. Shape verified
        # against the Core; the SDK itself only checks JSON-serializability.
        skills={"greet": {
            "description": "Greet in one line.",
            "instructions": "Reply with a greeting.",
        }},
        # Sub-agents the Core may delegate to, declared the same way.
        agents={"summarizer": {
            "description": "Summarize text.",
            "prompt": "Summarize briefly.",
        }},
        # Mapping form: the callables are registered for you. The list form
        # ({"event": ..., "callback": "name"}) refers to names you registered
        # yourself through hook_callbacks, which is the next parameter.
        hooks={"before_run": note_run_start},
        # Named callables a list-form registration can point at. Shown together
        # with the mapping form above because the two are alternatives and the
        # difference is only where the name comes from.
        hook_callbacks={"on_tool": note_tool_start},
        # An in-process MCP server: no subprocess, no URL, no dependency. The
        # tools are the same Tool objects the `tools` parameter takes; what
        # differs is that they arrive namespaced under this server's name.
        mcp_servers={"local": {"type": "sdk", "tools": [multiply.descriptor()]}},
        tools=[multiply],
        can_use_tool=allow_multiply,
    ) as agent:
        handle = await agent.run("Use multiply to calculate 6 * 7, then say the result.")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print(f"hooks fired: {fired}")
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run it directly**

```bash
cd python && set -a && . ./.env && set +a && REMY_CORE="$CORE" .venv/bin/python examples/extending.py
```

Expected: `before_run hook fired`, a `hooks fired:` line, and the model's reply. If `multiply.descriptor()` is not the right way to pass a tool into an `sdk` MCP server, check what the descriptor looks like and what the server entry expects:

```bash
cd python && .venv/bin/python -c "
from remy import tool
@tool
def f(a: int) -> int:
    'Doc.'
    return a
print(f.descriptor())"
```

- [ ] **Step 5: Write the TypeScript example**

Create `typescript/examples/extending.ts`:

```ts
import { Agent, type AgentOptions, type Tool } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

const multiply: Tool = {
  name: 'multiply', description: 'Multiply two integers and return their product.',
  inputSchema: {
    type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
    required: ['a', 'b'], additionalProperties: false,
  },
  execute(input) { return Number(input.a) * Number(input.b); },
};

export async function main(config: AgentOptions = options()): Promise<void> {
  const fired: string[] = [];
  const agent = await Agent.connect({
    ...(await withTask(config)),
    // Inline, and inline REPLACES rather than merges. Shape verified against
    // the Core; the SDK only checks that it serializes.
    skills: { greet: { description: 'Greet in one line.', instructions: 'Reply with a greeting.' } },
    agents: { summarizer: { description: 'Summarize text.', prompt: 'Summarize briefly.' } },
    // Hooks run in THIS process, like tools and permission callbacks.
    hooks: [{
      event: 'before_run',
      callback: () => { fired.push('before_run'); console.log('before_run hook fired'); },
    }],
    // An in-process MCP server: no subprocess, no URL, no dependency.
    mcpServers: { local: { type: 'sdk', tools: [multiply] } },
    tools: [multiply],
    onPermission(name, input) {
      return name === 'multiply' ? { behavior: 'allow', updatedInput: input } : { behavior: 'deny' };
    },
  });
  try {
    const handle = await agent.run('Use multiply to calculate 6 * 7, then say the result.');
    const result = await handle.result;
    requireCompleted(result);
    console.log(`hooks fired: ${fired.join(', ')}`);
    console.log(result.text);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 6: Check the TypeScript hook shape**

The `Hook` type decides whether a hook is `{event, callback}` or something else, and whether the event names match Python's four:

```bash
cd typescript && grep -rn -A10 "Hook" node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/types.d.ts | head -20
```

Adjust the registration above to the real shape. If TypeScript has no `hook_callbacks` counterpart, note the asymmetry in a comment rather than inventing one.

- [ ] **Step 7: Add the npm script and run the suite**

```json
    "extending": "node --experimental-strip-types examples/extending.ts",
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 18 PASS.

- [ ] **Step 8: Commit**

```bash
git add python/examples/extending.py typescript/examples/extending.ts scripts/smoke.py typescript/package.json
git commit -m "feat(examples): add skills, agents, hooks and an in-process MCP server"
```

---

## Task 9: `errors` — RemyError and its retry metadata

Nothing demonstrates error handling, which is one of the nine rows of the public contract. This is the gap the spec's own coverage claim got wrong.

**Files:**
- Create: `python/examples/errors.py`, `typescript/examples/errors.ts`
- Modify: `scripts/smoke.py` (`EXAMPLES`), `typescript/package.json`

**Interfaces:**
- Consumes: the `[[fail]]` peer marker from Task 2.
- Produces: nothing later tasks depend on.

**Known from the installed package:** `RemyError(message, *, code="sdk_error", is_retryable=False, retry_after=None, request_id=None)`. Those four are instance attributes, so `dir(RemyError)` on the class does not list them — read them off the caught instance.

- [ ] **Step 1: Add the failing smoke rows**

Append to `EXAMPLES`:

```python
    ("errors", "retryable:"),
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/errors`, file not found.

- [ ] **Step 2: Write the Python example**

Create `python/examples/errors.py`:

```python
import asyncio
from remy import Agent, RemyError
from config import options, with_task


async def main(config=None):
    config = with_task(options() if config is None else config)
    async with Agent(**config) as agent:
        # "[[fail]]" asks the local smoke peer for a 429. It is an artefact of
        # this repository's offline harness, not SDK syntax -- a real gateway
        # sends one when you are actually rate limited.
        handle = await agent.run("[[fail]] provoke a gateway error")

        # raise_on_error=False returns the RunResult with .error set instead of
        # raising. Prefer it when you intend to inspect the failure; the other
        # examples pass True because they intend to stop.
        result = await handle.result()
        error = result.error
        if error is None:
            raise RuntimeError("expected the run to fail; the peer did not refuse")

        # Four machine-readable facts, which is the point of a typed error:
        # a caller can decide what to do without parsing a message string.
        print(f"code: {error.code}")
        print(f"retryable: {error.is_retryable}")
        print(f"retry_after: {error.retry_after}")
        print(f"request_id: {error.request_id}")

        # is_retryable is the one to branch on. retry_after says how long to
        # wait when it is set; request_id is what a support ticket needs.
        if error.is_retryable:
            print(f"would retry after {error.retry_after or 1}s")
        else:
            print("would not retry: this failure will not resolve on its own")

        # The same error raised, for a caller that would rather catch than check.
        try:
            await handle.result(raise_on_error=True)
        except RemyError as raised:
            print(f"raised as {type(raised).__name__}: {raised.code}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run it directly against the smoke peer, not the real gateway**

The real gateway will not honour `[[fail]]`, so verify through the smoke run rather than a direct call. Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: `PASS python/errors`. If it fails, the stderr in the failure message shows which attribute or status did not match.

- [ ] **Step 4: Write the TypeScript example**

Create `typescript/examples/errors.ts`:

```ts
import { Agent, SDKError, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, withTask, isMain } from './config.ts';

export async function main(config: AgentOptions = options()): Promise<void> {
  const agent = await Agent.connect(await withTask(config));
  try {
    // "[[fail]]" asks the local smoke peer for a 429. It is an artefact of
    // this repository's offline harness, not SDK syntax.
    const handle = await agent.run('[[fail]] provoke a gateway error');
    const result = await handle.result;
    const error = result.error;
    if (!error) throw new Error('expected the run to fail; the peer did not refuse');

    // Machine-readable facts, so a caller can decide without parsing a string.
    // The Python binding spells `is_retryable`; here it is `isRetryable`.
    console.log(`code: ${error.code}`);
    console.log(`retryable: ${error.isRetryable}`);
    console.log(`retry_after: ${error.retryAfter}`);
    console.log(`request_id: ${error.requestId}`);

    if (error.isRetryable) {
      console.log(`would retry after ${error.retryAfter ?? 1}s`);
    } else {
      console.log('would not retry: this failure will not resolve on its own');
    }
    console.log(`SDKError is the thrown form: ${SDKError.name}`);
  } finally {
    await agent.close();
  }
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 5: Confirm the TypeScript error field names**

`RunResult.error` is an `ErrorDetails`; check its spelling before trusting the camelCase above:

```bash
cd typescript && sed -n '/interface ErrorDetails/,/^}/p' node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/types.d.ts
```

- [ ] **Step 6: Add the npm script and run the suite**

```json
    "errors": "node --experimental-strip-types examples/errors.ts",
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: 20 PASS.

- [ ] **Step 7: Commit**

```bash
git add python/examples/errors.py typescript/examples/errors.ts scripts/smoke.py typescript/package.json
git commit -m "feat(examples): read a typed failure instead of a message string"
```

---

## Task 10: `permissions` — permission_mode, RunState and cancel

The most peer-dependent scenario, so it is last. `permission_mode`'s three values, the interrupt-and-resume flow, and `Run.cancel` / `status` / `aclose` have nothing that reads them.

**Files:**
- Create: `python/examples/permissions.py`, `typescript/examples/permissions.ts`
- Modify: `scripts/smoke.py` (`EXAMPLES`), `typescript/package.json`

**Interfaces:**
- Consumes: the `[[slow]]` peer marker from Task 2.
- Produces: nothing later tasks depend on.

**Known from the installed package** (read, not assumed):
- `PermissionDecision(behavior, updated_input=None, message=None)` where behavior is `"allow"`, `"deny"` or `"interrupt"`.
- `permission_mode` is exactly `"default"`, `"accept_edits"` or `"bypass_permissions"`; anything else is a `ConfigurationError`.
- `RunResult.run_state` carries the Core-authored `RunState` after an interrupt.
- `RunState` is a frozen wrapper with `to_dict()` and `with_approval(tool_call_id, behavior="allow", *, updated_input=None)`.
- `Agent.resume(state, *, prompt="")`, and `Agent.run(prompt, *, session=None, resume_at=None, run_state=None)`.
- `Run.cancel(*, ack_timeout=0.2, grace=2.0) -> RunResult`.

- [ ] **Step 1: Add the failing smoke rows**

Append to `EXAMPLES`:

```python
    ("permissions", "resumed after approval"),
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: FAIL on `python/permissions`, file not found.

- [ ] **Step 2: Write the Python example**

Create `python/examples/permissions.py`:

```python
import asyncio
import json
from remy import Agent, PermissionDecision, tool
from config import options, require_completed, with_task


async def main(config=None):
    config = with_task(options() if config is None else config)

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers and return their sum."""
        print(f"Local add({a}, {b}) = {a + b}")
        return a + b

    # Three behaviours, and "interrupt" is the interesting one: it does not
    # refuse the call, it stops the run and hands back resumable state so a
    # human can decide out of band.
    async def interrupt_first(name, arguments):
        return PermissionDecision("interrupt", message="a human should approve this")

    async def allow_everything(name, arguments):
        return PermissionDecision("allow", updated_input=arguments)

    # permission_mode is the standing policy; can_use_tool is the per-call
    # question. "default" asks. "accept_edits" pre-approves file edits only.
    # "bypass_permissions" stops asking -- for a sandbox you already trust,
    # never for a machine you would mind being wrong about.
    async with Agent(
        **config, tools=[add], can_use_tool=interrupt_first, permission_mode="default"
    ) as agent:
        handle = await agent.run("Use add to calculate 2 + 3, then say the result.")
        # status is readable without awaiting the result, for a UI that wants
        # to show progress rather than block.
        print(f"status while running: {handle.status}")
        interrupted = await handle.result()
        state = interrupted.run_state
        if state is None:
            raise RuntimeError("expected an interrupt to produce resumable state")

        # Plain serializable data, so the pause can outlive the process: write
        # it to a queue, let a human approve tomorrow, resume then.
        carried = json.dumps(state.to_dict())
        print(f"interrupted with {len(carried)} bytes of resumable state")

        # The approval names the specific tool call, not "whatever was pending"
        # -- a run can have more than one.
        pending = state.to_dict().get("pending_tool_calls") or []
        if not pending:
            raise RuntimeError(f"no pending call in state: {sorted(state.to_dict())}")
        approved = state.with_approval(pending[0]["id"])
        resumed = await agent.resume(approved)
        result = await resumed.result(raise_on_error=True)
        require_completed(result)
        print(f"resumed after approval: {result.status}")

    # A second Agent, because permission_mode is set at construction. This one
    # never asks, and demonstrates cancelling a reply still in flight --
    # "[[slow]]" makes the smoke peer stall between chunks, since a reply that
    # has already finished cannot be cancelled.
    async with Agent(
        **config, tools=[add], can_use_tool=allow_everything,
        permission_mode="bypass_permissions",
    ) as agent:
        handle = await agent.run("[[slow]] Say hello in one short sentence.")
        cancelled = await handle.cancel()
        print(f"cancelled run ended as {cancelled.status}")
        # Releases the event stream explicitly. Leaving the Agent's context
        # manager also does it; call this when you drop a handle early.
        await handle.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Verify the pending-call key name before trusting it**

`pending_tool_calls` and its `id` field are the plan's guess at Core-authored state; the Core owns that shape. Print it and correct the example:

```bash
REMY_CORE="$CORE" python3 - <<'EOF'
import json, subprocess, sys
from pathlib import Path
# Run the interrupt half only, dumping the state's keys.
code = '''
import asyncio, json, sys
sys.path.insert(0, "examples")
from remy import Agent, PermissionDecision, tool
from config import options, with_task
async def main():
    @tool
    def add(a: int, b: int) -> int:
        "Add two integers and return their sum."
        return a + b
    async def interrupt(name, arguments):
        return PermissionDecision("interrupt")
    async with Agent(**with_task(options()), tools=[add], can_use_tool=interrupt) as agent:
        handle = await agent.run("Use add to calculate 2 + 3.")
        result = await handle.result()
        print(json.dumps(result.run_state.to_dict(), indent=2)[:1200])
asyncio.run(main())
'''
print(subprocess.run([str(Path("python/.venv/bin/python")), "-c", code],
                     cwd="python", text=True, capture_output=True).stdout)
EOF
```

Read the real key and id field out of that dump and fix Step 2's two lines. If the state has no pending-call list at all, use whatever identifier it does carry — `with_approval`'s first argument is a tool call id, so the id is in there under some name.

- [ ] **Step 4: Run the suite**

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: `PASS python/permissions`.

- [ ] **Step 5: Write the TypeScript example**

Create `typescript/examples/permissions.ts`:

```ts
import { Agent, approveTool, denyTool, type AgentOptions } from '@corepass/remy-agent-sdk/agent';
import { options, requireCompleted, withTask, isMain } from './config.ts';

const add = {
  name: 'add', description: 'Add two integers and return their sum.',
  inputSchema: {
    type: 'object', properties: { a: { type: 'integer' }, b: { type: 'integer' } },
    required: ['a', 'b'], additionalProperties: false,
  },
  execute(input: Record<string, unknown>) {
    const sum = Number(input.a) + Number(input.b);
    console.log(`Local add(${input.a}, ${input.b}) = ${sum}`);
    return sum;
  },
};

export async function main(config: AgentOptions = options()): Promise<void> {
  const ready = await withTask(config);

  // permissionMode is the standing policy; onPermission is the per-call
  // question. 'interrupt' does not refuse — it stops the run and hands back
  // resumable state so a human can decide out of band.
  const asking = await Agent.connect({
    ...ready, tools: [add], permissionMode: 'default',
    onPermission() { return { behavior: 'interrupt', message: 'a human should approve this' }; },
  });
  try {
    const handle = await asking.run('Use add to calculate 2 + 3, then say the result.');
    console.log(`status while running: ${handle.status}`);
    const interrupted = await handle.result;
    const state = interrupted.runState;
    if (!state) throw new Error('expected an interrupt to produce resumable state');

    // Plain serializable data, so the pause can outlive the process.
    console.log(`interrupted with ${JSON.stringify(state).length} bytes of resumable state`);

    // approveTool / denyTool build the approval; the Python binding spells
    // this `RunState.with_approval`.
    const resumed = await asking.run('', { runState: approveTool(state) });
    const result = await resumed.result;
    requireCompleted(result);
    console.log(`resumed after approval: ${result.status}`);
    console.log(`denyTool is the other half: ${typeof denyTool}`);
  } finally {
    await asking.close();
  }

  // A second Agent, because permissionMode is set at construction.
  const trusting = await Agent.connect({
    ...ready, tools: [add], permissionMode: 'bypass_permissions',
    onPermission(_name, input) { return { behavior: 'allow', updatedInput: input }; },
  });
  try {
    // "[[slow]]" makes the smoke peer stall between chunks: a reply that has
    // already finished cannot be cancelled.
    const handle = await trusting.run('[[slow]] Say hello in one short sentence.');
    const cancelled = await handle.cancel();
    console.log(`cancelled run ended as ${cancelled.status}`);
  } finally {
    await trusting.close();
  }
}

if (isMain(import.meta.url)) await main();
```

- [ ] **Step 6: Reconcile approveTool's signature and the resume call**

`approveTool` and `denyTool` are exported from `run.js`; their arguments and whether resume goes through `run(prompt, {runState})` or a dedicated method must be read, not guessed:

```bash
cd typescript && sed -n '/approveTool/,+6p;/denyTool/,+6p' node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/run.d.ts
grep -n "runState\|cancel\|status" node_modules/@corepass/remy-agent-sdk/dist/protocol/agent/run.d.ts
```

Fix the two calls above to match. If `approveTool` needs a tool call id, take it from the state the same way the Python side does.

- [ ] **Step 7: Add the npm script and run the full suite**

```json
    "permissions": "node --experimental-strip-types examples/permissions.ts",
```

Run: `REMY_CORE="$CORE" python3 scripts/smoke.py`
Expected: **22 PASS** — eleven scenarios in two languages.

- [ ] **Step 8: Commit**

```bash
git add python/examples/permissions.py typescript/examples/permissions.ts scripts/smoke.py typescript/package.json
git commit -m "feat(examples): interrupt, approve, resume and cancel a run"
```

---

## Task 11: Documentation, and the closing check

Four READMEs carry claims this change falsifies, and each is a claim a reader would act on.

**Files:**
- Modify: `README.md`, `README.zh-CN.md`, `python/README.md`, `typescript/README.md`

**Interfaces:**
- Consumes: the eleven-row `EXAMPLES` table from Tasks 3-10.
- Produces: nothing.

- [ ] **Step 1: Update the root README scenario list**

In `README.md`, replace the four-item list and the sentence after it:

```markdown
Both language directories include the same eleven scenarios:

1. **Hello** — run a prompt and read the final result.
2. **Streaming** — consume text events and inspect final token usage.
3. **Custom tool** — expose a local addition function and explicitly authorize it.
4. **Models** — list what the gateway accepts as `model`, before choosing one.
5. **One shot** — one prompt with no Agent to manage, plus the version constants.
6. **Events** — every event type, and the envelope that says where each happened.
7. **Configuration** — every construction-time parameter, set in one place.
8. **Sessions** — resume, refresh and fork a conversation.
9. **Extending** — inline skills, agents, hooks and an in-process MCP server.
10. **Errors** — read a typed failure and its retry metadata.
11. **Permissions** — interrupt a tool call, approve it out of band, resume, cancel.

Ten of the eleven run a real Agent through its Core subprocess. The models
example does not: listing the catalog starts no Core and spends nothing, so it
needs neither `REMY_CORE` nor a usage task — only auth. A live model run
```

- [ ] **Step 2: Update the Chinese README**

In `README.zh-CN.md`, replace the four-scenario sentence:

```markdown
两种语言都提供 hello、流式输出、自定义工具、模型列表、一次性调用、事件、
配置、会话、扩展、错误、权限十一个对应场景。其中十个会通过 Core 子进程运行
真实 Agent；模型列表不会 —— 查询目录不启动 Core、不产生花费，所以既不需要
`REMY_CORE` 也不需要 usage task，只要 auth。
```

And the smoke sentence, which currently says six examples:

```markdown
它会运行二十二个示例，使用真实 Core 和本地模拟模型网关；不需要真实 token，
```

- [ ] **Step 3: Update the per-language run command lists**

In `python/README.md`, replace the example command block:

```bash
.venv/bin/python examples/hello.py
.venv/bin/python examples/streaming.py
.venv/bin/python examples/custom_tool.py
.venv/bin/python examples/one_shot.py
.venv/bin/python examples/events.py
.venv/bin/python examples/configuration.py
.venv/bin/python examples/sessions.py
.venv/bin/python examples/extending.py
.venv/bin/python examples/permissions.py
# Needs no REMY_CORE — it starts no Core.
.venv/bin/python examples/models.py
# Needs the smoke peer: it asks for a 429 the real gateway will not send.
# python3 ../scripts/smoke.py covers this one.
# .venv/bin/python examples/errors.py
```

In `typescript/README.md`, the same list as npm scripts:

```bash
npm run hello
npm run streaming
npm run tool
npm run one-shot
npm run events
npm run configuration
npm run sessions
npm run extending
npm run permissions
# Needs no REMY_CORE — it starts no Core.
npm run models
# Needs the smoke peer; see ../scripts/smoke.py.
# npm run errors
```

- [ ] **Step 4: Verify no stale count survives anywhere**

```bash
cd /Users/youland/project/remy-agent-sdk && \
grep -rniE "four scenarios|三个场景|四个场景|six examples|六个示例|the same three" \
  README.md README.zh-CN.md python/README.md typescript/README.md || echo "no stale counts"
```

Expected: `no stale counts`.

- [ ] **Step 5: Run every gate**

```bash
cd /Users/youland/project/remy-agent-sdk
python3 -m compileall -q python/examples scripts && echo "compileall PASS"
for f in typescript/examples/*.ts; do node --experimental-strip-types --check "$f" || echo "FAIL $f"; done
(cd typescript && npm run typecheck)
REMY_CORE="$CORE" python3 scripts/smoke.py
```

Expected: compileall PASS, no `--check` failures, clean `tsc`, and 22 PASS.

- [ ] **Step 6: Verify the coverage claim the spec makes**

The spec's central claim is that coverage closes. Check it rather than believing it:

```bash
cd /Users/youland/project/remy-agent-sdk/python && .venv/bin/python - <<'EOF'
import inspect, pathlib, re, remy
from remy import Agent
source = "\n".join(p.read_text() for p in pathlib.Path("examples").glob("*.py"))
params = list(inspect.signature(Agent.__init__).parameters)[1:]
missing_params = [p for p in params if not re.search(rf"\b{p}\s*=", source)]
exports = sorted(set(remy.__all__) - {"__version__"})
imported = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", source))
missing_exports = [e for e in exports if e not in imported]
print("params not set in any example:", missing_params or "none")
print("exports not named in any example:", missing_exports or "none")
EOF
```

Expected: `none` for both. A name reported here is a real gap — add it to whichever scenario owns it rather than adjusting the check.

- [ ] **Step 7: Commit**

```bash
git add README.md README.zh-CN.md python/README.md typescript/README.md
git commit -m "docs(examples): eleven scenarios, and which one needs no Core"
```

---

## Self-Review Notes

**Spec coverage.** Every spec section maps to a task: the seven-scenario table to Tasks 4-10, the five peer extensions to Tasks 1-2 (routing and catalog; stall, reasoning, failure) and Task 7 Step 1 (history-varying replies), the three smoke-constrained parameters to Task 6 (`core_spec`, timeouts) and Task 1 Step 1 (`preset`), the settings fixture to Task 6 Step 3, the documentation section to Task 11, and the spec's sequencing to the task order.

**Deliberate unknowns.** Three shapes are Core-owned and cannot be read from the SDK, so each has a probe step producing the real answer rather than a placeholder: the inline `skills`/`agents` shape (Task 8 Step 1), the interrupt state's pending-call key (Task 10 Step 3), and whether `preset="remy_code"` completes against the fake peer (Task 1 Step 1). Several TypeScript names are likewise read from the installed `.d.ts` rather than assumed (Tasks 5, 6, 7, 9, 10).

**Naming consistency.** `EXAMPLES` is defined in Task 3 and appended to in Tasks 4-10, one row each, reaching eleven. `ModelPeer.CATALOG` is defined in Task 1 and read in Task 3's `models` row. The three peer markers `[[slow]]`, `[[thinking]]` and `[[fail]]` are defined in Task 2 and used in Tasks 10, 5 and 9 respectively. `core_spec_from_env()` is local to Task 6 and used nowhere else.
