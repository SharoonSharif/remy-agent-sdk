import asyncio
from remy import Agent, PermissionDecision, tool
from config import options, require_completed


async def main():
    calls = []

    @tool
    def add(a: int, b: int) -> int:
        """Add two integers and return their sum."""
        calls.append((a, b))
        print(f"Local add({a}, {b}) = {a + b}")
        return a + b

    async def allow_add(name, arguments):
        if name == "add":
            return PermissionDecision("allow", updated_input=arguments)
        return PermissionDecision("deny")

    async with Agent(**options(), tools=[add], can_use_tool=allow_add) as agent:
        handle = await agent.run("Use the add tool to calculate 2 + 3, then tell me its result.")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        if not calls:
            raise RuntimeError("The model did not call add; try a tool-capable model.")
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
