import asyncio
from remy import Model, models
from config import options


async def main(config=None):
    # No Agent, and no with_task(): asking which models exist starts no Core
    # and spends nothing, so neither a Core executable nor a usage task is
    # needed here. Only auth is.
    config = options() if config is None else config
    found = await models(auth=config["auth"])
    assert all(isinstance(entry, Model) for entry in found)
    print(f"{len(found)} models available")
    for model in found:
        print(f"  {model.id} ({model.owned_by or 'unknown provider'})")
    # The ids are exactly what `model` accepts, so a consumer can pick one
    # from this list and hand it straight back.
    if not any(model.id == config["model"] for model in found):
        print(f"\nNote: {config['model']} is not in this list.")


if __name__ == "__main__":
    asyncio.run(main())
