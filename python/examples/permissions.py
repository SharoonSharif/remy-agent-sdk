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
        cancelled = await handle.cancel()
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
