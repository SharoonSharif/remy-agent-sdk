# Examples that cover the whole public surface

**Date:** 2026-09-09
**Status:** approved, not yet implemented

## Problem

Four examples ship today — hello, streaming, custom-tool, models. Between
them they use 5 of `Agent`'s 20 parameters and import 6 of the package's 27
public exports by name. A consumer reading this repository to learn what the SDK can do
learns about a quarter of it, and the fifteen parameters nothing demonstrates
are exactly the ones whose behaviour is hard to guess: `setting_sources`
versus inline `skills`, what `permission_mode` changes, whether a `Session`
survives a process, what `RunState` is for.

The gap is not documentation. `Agent`'s docstrings describe each parameter;
what is missing is a runnable line that proves the description still matches
the code.

## Decisions taken before designing

Three, each settled with the requester rather than assumed:

1. **Scenario examples, not one file per parameter.** A file per parameter
   would be 30+ files across the two bindings, most differing by one line,
   and would bloat the smoke run and four READMEs for no gain in
   understanding. Instead each new example demonstrates a group of
   semantically related parameters.
2. **One pass, including `skills` / `agents` / `mcp_servers`.** These looked
   like the expensive third of the work because they appeared to need external
   fixtures — skill files, sub-agent definitions, a running MCP server.
   Checking the types removed that: `mcp_servers` accepts
   `{type: 'sdk', tools: [...]}`, an in-process server needing no external
   process and no dependency, and `skills` / `agents` accept inline values.
3. **Every new example joins the offline smoke run.** The alternative —
   verifying each once by hand against the real gateway — spends quota and
   leaves nothing to stop them from rotting.

## Scenario grouping

Seven new scenarios, in both bindings, for fourteen new files.

| Scenario | Parameters and exports it demonstrates |
|---|---|
| `configuration` | `cwd`, `system_prompt`, `preset`, `max_steps`, `setting_sources`, `handshake_timeout`, `command_timeout`, `core_spec`, `env`; `ConfigurationError`, `CoreSpec` |
| `sessions` | `session_store`; `Session` (all seven members), `SessionStore`, `Agent.resume` |
| `permissions` | `permission_mode` (all three values); `RunState`, `Run.cancel`, `Run.status`, `Run.aclose` |
| `events` | `EventEnvelope`, `RunEvent`, `ThinkingDeltaEvent`, `ToolEvent`, `UsageEvent` |
| `errors` | `RemyError` and its `code` / `is_retryable` / `retry_after` / `request_id` |
| `extending` | `skills`, `agents`, `hooks`, `hook_callbacks`, `mcp_servers` |
| `one_shot` | `arun()`; `SDK_API_VERSION`, `PROTOCOL_NAME`, `PROTOCOL_VERSION` (`run()`, the synchronous sibling, is discussed but deliberately not called — see the correction below) |

With the existing four, coverage closes: all 20 `Agent` parameters, and 26 of
27 exports, appear in at least one runnable example that actually exercises
them in code. The table above is the checkable claim — it was built by
enumerating both lists from the installed package, not by estimate.

`errors` was missing from the first version of this table, and the omission is
worth recording rather than quietly fixing: the claim "all 27 exports" was
made and was false, because `RemyError` appeared in no scenario. Re-deriving
the table from `remy.__all__` is what caught it. The gap was not one name — it
was that nothing demonstrated error handling at all, which is one of the nine
rows of the public contract.

A second correction, made in final review after implementation: "all 27
exports" was checked by `scripts/check_coverage.py` with a bare-identifier
regex over the whole source text, so a name spelled out only in a comment —
`run` in `one_shot.py`, in the comment explaining why `arun()` is used instead
— counted as "covered" exactly like a real import or `isinstance` check. It
was not alone: `Tool`, `RunEvent`, `Usage`, `Run` and `RunResult` were in the
same position, each mentioned only in a comment, until this review added a
real `isinstance` check for each (`custom_tool.py`, `events.py`, `streaming.py`,
`errors.py`; `Run` and `Tool` both landed in `custom_tool.py`) and one more
outright miss the tightened check then surfaced, `Session` in `sessions.py`
(also fixed the same way). `run()` — the SYNCHRONOUS one-shot entry point —
is the one export left deliberately unexercised: it raises
`RuntimeError("run() cannot nest an event loop; use await arun()")` when
called from inside a running event loop, and every example's `main()` runs
inside one (`scripts/smoke.py` drives both bindings by awaiting
`main(config)`), so calling it for real would mean contorting the harness for
one name rather than showing genuine usage. `check_coverage.py` now
distinguishes a name appearing in executable code (an AST `Name` or an
import) from one appearing only in a comment or string, and records `run` as
a single, documented, deliberate exception (`KNOWN_UNEXERCISED_EXPORTS`)
instead of silently counting it as covered. The honest claim is 26 of 27
exports exercised in real code, plus `run()` covered by discussion rather
than a call.

### Why these groups

`configuration` collects the parameters that are set once and then invisible.
Showing them in nine separate files would say nothing that one Agent
constructed with every knob set does not, and it would hide the one fact worth
seeing: they are all just constructor arguments.

`sessions` and `permissions` are separate because they answer different
questions — "does this conversation outlive the process" and "who authorises a
tool call" — even though both involve resuming.

`one_shot` exists because `run()` / `arun()` are a different entry point, not
a different configuration: a consumer who only needs one prompt should not
have to read the Agent lifecycle to find them.

`errors` is separate from `events` rather than folded into it. Both involve
reading what came back, but a consumer arriving with "how do I handle a rate
limit" should not have to read an event-iteration example to find the answer,
and provoking a failure is structurally different from consuming a successful
stream. It also needs a deliberately failing run, which no other scenario
wants.

## The interruption flow

`RunState` was the one part whose shape was unverified when the design was
approved. Resolved before writing this: no Core cooperation is needed beyond a
tool call, which the existing fake peer already produces.

```
can_use_tool returns PermissionDecision("interrupt")
  → RunResult.run_state carries Core-authored state
  → state.with_approval(tool_call_id)
  → agent.resume(state) continues the run
```

`RunState` is a frozen wrapper over serialisable data with `to_dict()`, so the
example can also show the state surviving a round trip through JSON, which is
the property that makes it worth having.

## Fake gateway extensions

`scripts/smoke.py` serves a stateless fixed reply today. Four additions, each
tied to a scenario that cannot otherwise be verified offline:

1. **Delayed streaming chunks** — `Run.cancel` and the interrupt path need a
   response still in flight when the cancel lands. A reply that completes
   instantly cannot be cancelled, and a test that cancels a finished run
   proves nothing.
2. **A reasoning field in the stream** — for `ThinkingDeltaEvent`.
3. **A real `GET /models` body** — currently `{"data": []}`. The models
   example asserts against the catalog, and an empty list would let a broken
   parse pass.
4. **Distinguishable replies across turns** — needed to ASSERT session
   behaviour, not to make it work. Session state is Core-side: `smoke.py`
   already gives the real Core a `COREPASS_HOME` temp directory, and the fake
   peer is only a model endpoint (`chat/completions` and `/tasks`), so resume
   and fork function without touching it. What does not function is the
   assertion: with one canned reply for every request, a resumed session and a
   fresh one look identical, so the example could pass while proving nothing.
   The peer must therefore vary its answer with the history it receives.

   An earlier version of this spec listed this as a prerequisite for
   `sessions` to work at all, which put that scenario last in the sequence
   below. It is not a prerequisite, and the order is corrected accordingly.

5. **An error response on demand** — `errors` needs a run that fails with a
   `code`, `retry_after` and `request_id` to read. A 429 carrying those is the
   cheapest shape, and the peer must produce it for that example only, since
   every other case needs the success path.

The peer must also route by path, which it began doing when `/tasks` was
added; `GET` still ignores the path and needs the same treatment.

The example list in `smoke.py` is hard-coded as three names. It becomes all
eleven, so the run is 22 cases — eleven scenarios in two languages.

## Three parameters constrained by the smoke run

Demonstrating these naively breaks the offline check, so the examples are
bounded up front rather than debugged later:

- **`core_spec` overrides `REMY_CORE`.** The smoke run works by injecting
  `REMY_CORE`; a `CoreSpec` with a hard-coded path would point somewhere that
  does not exist there. `configuration` must derive its `CoreSpec` from the
  environment, which is also the honest demonstration — a consumer writes a
  path they know, not a literal from someone else's machine.
- **`handshake_timeout` / `command_timeout` must stay generous.** The
  temptation is to set them low so the effect is visible; that converts the
  smoke run into an intermittent failure on a loaded machine. They are
  demonstrated as explicit values at or above their defaults, with a comment
  saying what lowering them would do.
- **`preset="remy_code"` needs verifying before it is written.** It turns on
  product behaviour — real skills and filesystem tools — and the fake peer
  answers with a canned reply that ignores the tools it is offered. Whether
  the Core then attempts a real tool call is unknown, and step 1 below settles
  it. If it does, `configuration` demonstrates `preset` and skips executing
  that run, rather than shipping a scenario that hangs.

## Fixtures

One file needs to exist on disk: a settings file for `setting_sources`, at
`examples/fixtures/settings.json` in each language directory. Everything else
is inline, per decision 2 above.

## Documentation

Four READMEs carry claims that this change falsifies, and each is a claim a
reader would act on:

- "the same four scenarios" becomes eleven, in `README.md` and
  `README.zh-CN.md`.
- "The first three run a real Agent through its Core subprocess" needs
  rewriting: after this, ten do and only `models` does not.
- The per-language READMEs list run commands; seven more are added. Only
  `models` is marked as needing no `REMY_CORE`: `run()` and `arun()` spawn a
  Core like any Agent, so `one_shot` needs one.
- `README.zh-CN.md` says the smoke run covers six examples. It becomes 22.

## Sequencing

Dependency order, not preference:

1. Extend the fake gateway, and settle the `preset` question above. Nothing
   new can be verified before this.
2. `configuration`, `one_shot`, `events` — no new peer capability needed.
3. `sessions` — moved up from last. Its Core-side state needs nothing from the
   peer; only its assertion does.
4. `extending` — inline skills, agents, hooks and an sdk-type MCP server.
5. `errors` — needs the peer's on-demand failure.
6. `permissions` — needs delayed streaming; the most peer-dependent, so last.
7. Documentation, then the full 22-case smoke run as the closing check.

## Non-goals

- **Not `preset` as a default.** The repository's stated position is that the
  SDK starts blank; `configuration` demonstrates `preset="remy_code"` with a
  comment saying what it turns on, and does not make it the default any
  example inherits.
- **Not a stdio or http MCP server.** The `sdk` variant demonstrates the
  parameter without an external process or a dependency. A stdio server is a
  separate exercise about packaging, not about this SDK's surface.
- **No new runtime dependency**, in either binding. This repository exists to
  show what integrating the SDK costs, and every dependency added here is a
  wrong answer to that question.
