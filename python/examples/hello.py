import asyncio
from remy import Agent
from config import options, require_completed, with_task


async def main(config=None):
    config = options() if config is None else config
    async with Agent(**with_task(config)) as agent:
        handle = await agent.run("Who are you?")
        result = await handle.result(raise_on_error=True)
        require_completed(result)
        print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
