import asyncio
from remy import PROTOCOL_NAME, PROTOCOL_VERSION, SDK_API_VERSION, arun
from config import options, require_completed, with_task


async def main(config=None):
    # These three say which contract this binding speaks. Log them when
    # reporting a bug: "it does not work" and "it speaks protocol 1 against an
    # SDK expecting 2" are different reports.
    print(f"SDK API v{SDK_API_VERSION}, {PROTOCOL_NAME} v{PROTOCOL_VERSION}")

    # arun() is one prompt with no Agent to manage: it constructs one, runs,
    # and closes it. Use it when there is no second turn. The synchronous
    # sibling run() is the same call for a script with no event loop, and
    # cannot be used here because this function is already inside one.
    config = with_task(options() if config is None else config)
    result = await arun("Say hello in one short sentence.", **config)
    require_completed(result)
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
