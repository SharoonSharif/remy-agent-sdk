import asyncio
from remy import Agent, PermissionDecision, Run, Tool, tool
from config import options, require_completed, with_task


async def main(config=None):
    calls = []

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers and return their sum."""
        calls.append((a, b))
        print(f"Local add({a}, {b}) = {a + b}")
        return a + b

    # @tool doesn't just mark a function -- it returns a Tool, the same
    # dataclass tools=[...] wants (name, description, input_schema, callback).
    if not isinstance(add, Tool):
        raise RuntimeError(f"expected @tool to produce a Tool, got {type(add)!r}")

    async def allow_add(name, arguments):
        if name == "add":
            return PermissionDecision("allow", updated_input=arguments)
        return PermissionDecision("deny")

    config = options() if config is None else config
    async with Agent(**with_task(config), tools=[add], can_use_tool=allow_add) as agent:
        handle = await agent.run("Use the add tool to calculate 2 + 3, then tell me its result.")
        # agent.run() hands back a Run: a durable handle you can iterate for
        # events, await for the result, or cancel -- not a bare coroutine.
        if not isinstance(handle, Run):
            raise RuntimeError(f"expected agent.run() to return a Run, got {type(handle)!r}")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        if not calls:
            raise RuntimeError("The model did not call add; try a tool-capable model.")
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
