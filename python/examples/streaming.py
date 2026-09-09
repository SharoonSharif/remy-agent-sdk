import asyncio
from remy import Agent, TextDeltaEvent
from config import options, require_completed


async def main():
    async with Agent(**options()) as agent:
        handle = await agent.run("Explain what an SDK is in two short sentences.")
        async for event in handle:
            if isinstance(event, TextDeltaEvent):
                print(event.text, end="", flush=True)
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print()
        print("Usage:", result.usage)


if __name__ == "__main__":
    asyncio.run(main())
