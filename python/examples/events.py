import asyncio
from remy import (
    Agent,
    EventEnvelope,
    PermissionDecision,
    RunEvent,
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

    # This example is about events, not permissions -- but the permission
    # decision is NOT incidental to which events you see, unlike in
    # extending.py. Verified by removing this callback: the transcript
    # stops dead after the tool-call turn's usage event (seq 4-12, 9 events)
    # with no ToolEvent and no TextDeltaEvent, because the pending "add"
    # call auto-resolves to "interrupt" -- require_completed() then raises
    # before the loop or the final print ever see the rest. With the
    # callback allowing "add", the run continues through the tool call and
    # a second model turn (seq up to 28), so the callback is what makes the
    # ToolEvent and TextDeltaEvent branches below fire at all, not only what
    # makes the run end "completed". See custom_tool.py for the permission
    # topic itself.
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
            if not isinstance(envelope, EventEnvelope):
                raise RuntimeError(f"expected an EventEnvelope, got {type(envelope)!r}")
            # ThinkingDeltaEvent, TextDeltaEvent, ToolEvent and UsageEvent are
            # all subclasses of RunEvent; the base class is what the "every
            # other event" branch below falls back on.
            if not isinstance(event, RunEvent):
                raise RuntimeError(f"expected a RunEvent, got {type(event)!r}")
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
