import asyncio
from remy import Agent, TextDeltaEvent, Usage
from config import options, require_completed, with_task


async def main(config=None):
    config = options() if config is None else config
    async with Agent(**with_task(config)) as agent:
        handle = await agent.run("Explain what an SDK is in two short sentences.")
        async for event in handle:
            if isinstance(event, TextDeltaEvent):
                print(event.text, end="", flush=True)
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        if not isinstance(result.usage, Usage):
            raise RuntimeError(f"expected a Usage, got {type(result.usage)!r}")
        print()
        print("Usage:", result.usage)


if __name__ == "__main__":
    asyncio.run(main())
