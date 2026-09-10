import asyncio
import json
from remy import Agent, PermissionDecision, RunState, tool
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

    # can_use_tool WINS over permission_mode -- not the other way round, and
    # not a partnership between the two. The Core decides in this order: an
    # approval already carried on the RunState, then a can_use_tool callback
    # if one exists, and only then the mode. So permission_mode is the
    # fallback for a consumer that supplies NO callback; pass one and all
    # three values stop mattering. Verified by running this example under
    # each of the three: the callback is asked every time.
    #
    # That is the answer to "why am I still being asked when I set
    # bypass_permissions" -- and it is the right precedence. A consumer that
    # installs a gate should not have it bypassed by a config string.
    #
    # The modes themselves, for a callback-free consumer: "default" asks,
    # "accept_edits" pre-approves file edits only, "bypass_permissions" stops
    # asking -- for a sandbox you already trust, never for a machine you would
    # mind being wrong about. Every Agent below passes a callback, so none of
    # the three is doing anything here; they are set to show where they go.
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
        if not isinstance(state, RunState):
            raise RuntimeError(f"expected a RunState, got {type(state)!r}")

        # Plain serializable data, so the pause can outlive the process: write
        # it to a queue, let a human approve tomorrow, resume then.
        carried = json.dumps(state.to_dict())
        print(f"interrupted with {len(carried)} bytes of resumable state")

        # The approval names the specific tool call, not "whatever was pending"
        # -- a run can have more than one. Verified against this repo's smoke
        # peer: the Core's interruption state carries the pending call under
        # "pending_tool_calls", each entry keyed by "id" -- the same names
        # with_approval's own lookup uses internally.
        pending = state.to_dict().get("pending_tool_calls") or []
        if not pending:
            raise RuntimeError(f"no pending call in state: {sorted(state.to_dict())}")
        approved = state.with_approval(pending[0]["id"])
        resumed = await agent.resume(approved)
        result = await resumed.result(raise_on_error=True)
        require_completed(result)
        print(f"resumed after approval: {result.status}")

    # A second Agent, to actually exercise "accept_edits" instead of just
    # naming it in a comment. This example's only tool is arithmetic, not a
    # file edit, so can_use_tool still records whether it gets asked.
    edit_mode_calls = []

    async def record_and_allow(name, arguments):
        edit_mode_calls.append(name)
        return PermissionDecision("allow", updated_input=arguments)

    async with Agent(
        **config, tools=[add], can_use_tool=record_and_allow,
        permission_mode="accept_edits",
    ) as agent:
        handle = await agent.run("Use add to calculate 5 + 5, then say the result.")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        # Observed against this repo's smoke peer, in both this run and a
        # side-by-side probe over all three permission_mode values: can_use_tool
        # was invoked here for "add" exactly as it was above under "default"
        # and below under "bypass_permissions" -- accept_edits did not skip
        # asking for this non-file-edit tool. No observable difference here,
        # because accept_edits's documented effect (pre-approving file edits)
        # has nothing to act on when the registered tool is arithmetic, not a
        # file edit; a can_use_tool callback, once registered, appears to be
        # consulted regardless of permission_mode. That is an observation
        # about this Core's behaviour, not a guarantee read from any
        # docstring -- nothing in the installed package documents when
        # permission_mode itself (rather than can_use_tool's return value)
        # decides the outcome.
        print(f"accept_edits asked can_use_tool for a non-edit tool: {bool(edit_mode_calls)}")

    # A third Agent, because permission_mode is set at construction. This one
    # never asks, and demonstrates cancelling a reply still in flight --
    # "[[slow]]" asks the smoke peer to stall between chunks so the cancel is
    # meant to land mid-stream by design. Observed against this repo's smoke
    # peer: removing the marker did not change the outcome -- a local IPC
    # cancel still won the race against even a zero-delay reply in every run
    # tried. The marker is belt-and-braces here, not load-bearing; kept
    # because it is still the honest way to express the intent.
    async with Agent(
        **config, tools=[add], can_use_tool=allow_everything,
        permission_mode="bypass_permissions",
    ) as agent:
        handle = await agent.run("[[slow]] Say hello in one short sentence.")
        # Run.cancel's defaults (ack_timeout=0.2, grace=2.0) are tuned for how
        # fast a cancel is *acknowledged*, not for how long the Core actually
        # takes to unwind a turn afterward. Measured directly against this
        # repo's smoke peer and a real frozen Core, timing the gap between
        # sending "turn.cancel" and the terminal event actually arriving,
        # across 50 runs: the ack itself is near-instant (sub-millisecond)
        # every time, but termination lands anywhere from ~1.6s to ~2.3s in
        # the common case and, in 3 of the 50 runs, spiked to ~5.8-6.1s. That
        # spread sits on both sides of the 2.0s default grace, which is why
        # this example raised RemyError("... did not terminate after
        # cancellation") in roughly 2 of every 5 runs of the offline gate --
        # not a race with "[[slow]]"'s 0.4s stall (removing that marker
        # doesn't change this latency at all; it comes from the Core's own
        # cancellation teardown, not the peer). grace=10.0 leaves comfortable
        # room above the worst observed value; ack_timeout=1.0 is raised too,
        # both above their defaults, so this stays a realistic timeout rather
        # than one this harness happens to have gotten away with.
        cancelled = await handle.cancel(ack_timeout=1.0, grace=10.0)
        # A structural guard, matching the interrupt half's: if "[[slow]]" ever
        # stopped stalling the peer, the reply could complete before the
        # cancel request lands, and remy.Run.cancel returns whatever
        # RunResult the run actually settled with -- "completed", not
        # "cancelled". Fail loudly rather than silently accepting that.
        if cancelled.status != "cancelled":
            raise RuntimeError(
                f"expected the cancelled run to end as cancelled, got {cancelled.status!r}"
            )
        print(f"cancelled run ended as {cancelled.status}")
        # Awaits cancel() first if the run has not already settled, then
        # closes this handle's own spooled event-stream file and marks it
        # disposed (remy.Run.aclose). Leaving the Agent's context manager does
        # NOT do this -- Agent.aclose closes the Core subprocess and cancels
        # the pump and callback tasks, then fails any outstanding runs'
        # result futures and clears the agent's run registry; it never
        # touches a handle's stream. Call Run.aclose explicitly when you drop
        # a handle early, or the underlying file is only closed later by
        # Run.__del__ under non-deterministic GC.
        await handle.aclose()


if __name__ == "__main__":
    asyncio.run(main())
