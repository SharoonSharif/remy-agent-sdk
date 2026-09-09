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
