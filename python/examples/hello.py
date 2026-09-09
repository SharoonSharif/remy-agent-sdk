import asyncio
from remy import Agent
from config import options, require_completed


async def main():
    async with Agent(**options()) as agent:
        handle = await agent.run("Say hello in one short sentence.")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
