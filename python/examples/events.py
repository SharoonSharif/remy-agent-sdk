import asyncio
from remy import (
    Agent,
    PermissionDecision,
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

    # This example is about events, not permissions -- and the events above
    # fire regardless of the permission decision; the loop below runs to
    # completion either way. What the callback actually buys is a
    # "completed" run: without a decision the pending tool call
    # auto-resolves to "interrupt", and require_completed() raises before
    # the final print below. See custom_tool.py for the permission topic
    # itself.
    async def allow_add(name, arguments):
        if name == "add":
            return PermissionDecision("allow", updated_input=arguments)
        return PermissionDecision("deny")

    config = with_task(options() if config is None else config)
    async with Agent(**config, tools=[add], can_use_tool=allow_add) as agent:
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
                print(f"tool event seq={envelope.seq}: {event.tool_name}")
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
